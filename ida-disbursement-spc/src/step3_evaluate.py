"""STEP 3 - Measuring a detector when nothing is labelled.

There is no column in this dataset that says "this row is wrong". That makes
this an unsupervised problem, and unsupervised does NOT mean unevaluated.
Three numbers, because any one of them alone can be gamed:

1. RECALL - of the errors we plant ourselves, how many does the chart catch?
   Five error types (config.ERROR_CATALOG), from the blatant (x1000) to the
   ones SPC is expected to miss (a 25% misstatement, a stale repeat). A lower
   bound on real performance, but a number that can be tracked.

2. PRECISION - of the alerts on the real data, how many were worth a look?
   Only a human can say, so this comes from labels/alert_labels.csv
   (built by review_alerts.py). Unlabelled alerts are reported, not guessed.

3. ALERT LOAD - how many alerts per year the team has to read. A queue nobody
   reads has zero recall in practice. That is alert fatigue.

Every run upserts one row into experiments/ledger.csv, keyed by
(method version, split). The ledger is how "v2 is better than v1" becomes a
claim with evidence behind it.

    python src/step3_evaluate.py                      # tuning draws (default)
    python src/step3_evaluate.py --split holdout      # once per finished version
    python src/step3_evaluate.py --version v2-rolling-baseline --note "..."
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (OUT_DIR, MEASURE, MONITOR_START_FY, MONITOR_END_FY, BASELINE_START_FY,
                    BASELINE_END_FY, SIGMA_MULTIPLIER, MIN_BASELINE_POINTS, RUN_LENGTH_RULE,
                    SYNTHETIC_PER_TRIAL, SYNTHETIC_TRIALS, ERROR_CATALOG, MISSTATEMENT,
                    TUNING_SEED, HOLDOUT_SEED, METHOD_VERSION, LEDGER_CSV, HIGH_SEVERITY_Z,
                    PRECISION_AT_N, EXTRACT_DATE)
from step2_spc import load_series, add_growth, build
from review_alerts import load_labels

N_MON_YEARS = MONITOR_END_FY - MONITOR_START_FY + 1


# ---------------------------------------------------------------- recall
def inject(df, rng, kind, n):
    """Break n randomly chosen country-years inside the monitoring window,
    at most ONE per country.

    Two design rules, both learned the hard way:
      * never touch the baseline window - corrupting it would teach the control
        limits to accept the corruption, so the detector would score itself on
        a chart it had already been fooled into widening;
      * never inject twice into one country - in a year-over-year chart, two
        errors in consecutive years partly cancel, and you end up measuring
        your experiment instead of your detector.
    """
    prev = df.groupby("country")[MEASURE].shift(1)
    in_window = df.fiscal_year.between(MONITOR_START_FY, MONITOR_END_FY) & (df[MEASURE] > 0)
    if kind == "stale_repeat":
        # Only cells where repeating last year actually changes something.
        in_window &= (prev > 0) & (prev != df[MEASURE])
    pool = df[in_window]
    one_per_country = pool.groupby("country", group_keys=False).sample(
        1, random_state=int(rng.integers(1e9)))
    picked = one_per_country.sample(min(n, len(one_per_country)),
                                    random_state=int(rng.integers(1e9))).index

    out = df.copy()
    if kind == "spike_x10":
        out.loc[picked, MEASURE] *= 10.0
    elif kind == "units_x1000":
        out.loc[picked, MEASURE] *= 1000.0
    elif kind == "drop_to_zero":
        out.loc[picked, MEASURE] = 0.0
    elif kind == "misstate_25pct":
        signs = rng.choice([-1.0, 1.0], size=len(picked))
        out.loc[picked, MEASURE] *= 1.0 + signs * MISSTATEMENT
    elif kind == "stale_repeat":
        out.loc[picked, MEASURE] = prev.loc[picked]
    else:
        raise ValueError(f"no injector for error type {kind!r} - add one or remove it from ERROR_CATALOG")
    truth = set(zip(out.loc[picked, "country"], out.loc[picked, "fiscal_year"]))
    return out, truth


def alerts_for(df):
    pts, _ = build(add_growth(df), "yoy_log_growth", "B_growth",
                   floor_at_zero=False, kind="growth")
    hit = pts[pts.rule != ""]
    return pts, set(zip(hit.country, hit.fiscal_year)), hit


def measure_recall(clean, clean_alerts, seed):
    rows = []
    for i, kind in enumerate(ERROR_CATALOG):
        # One generator per error type, derived from (seed, position): adding a
        # new error type later does not reshuffle the draws of the existing ones,
        # so their numbers stay comparable across ledger rows.
        rng = np.random.default_rng([seed, i])
        trials, misses = [], []
        for _ in range(SYNTHETIC_TRIALS):
            broken, truth = inject(clean, rng, kind, SYNTHETIC_PER_TRIAL)
            pts, found, _ = alerts_for(broken)
            # Only score injections in country-years the chart actually covers.
            covered = set(zip(pts.country, pts.fiscal_year))
            truth_c = truth & covered
            detected = truth_c & found
            # Alerts that are neither an injection nor present on clean data:
            # collateral, mostly the FOLLOWING year, because corrupting year t
            # also distorts the year-over-year change at t+1. Expected, not a bug.
            collateral = found - truth_c - clean_alerts
            trials.append((len(truth_c), len(detected), len(collateral)))
            misses += sorted(truth_c - detected)

        t = np.array(trials, dtype=float)
        recalls = 100 * t[:, 1] / np.maximum(t[:, 0], 1)
        rows.append({
            "error_type": kind,
            "trials": SYNTHETIC_TRIALS,
            "injected_per_trial": round(t[:, 0].mean(), 1),
            "detected_per_trial": round(t[:, 1].mean(), 1),
            "recall_pct_mean": round(recalls.mean(), 1),
            "recall_pct_min": round(recalls.min(), 1),
            "recall_pct_max": round(recalls.max(), 1),
            "collateral_per_trial": round(t[:, 2].mean(), 1),
            "example_misses": "; ".join(f"{c} FY{y}" for c, y in misses[:5]),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- precision
def measure_precision(clean_hits):
    """Precision from human labels, on the alerts this version raises.

    strict  = investigate / labelled          "was it worth an analyst's time?"
    lenient = (investigate + explained) / labelled
                                              "did it point at something real?"
    precision@N uses the N highest-|z| alerts - the ones an analyst reads
    first - and is only reported when all N are labelled. A precision computed
    on whichever alerts happened to get labelled is a biased number.
    """
    lab = load_labels()[["country", "fiscal_year", "label"]]
    q = clean_hits[["country", "fiscal_year", "robust_z"]].merge(
        lab, on=["country", "fiscal_year"], how="left")
    q["label"] = q.label.fillna("")
    q = q.reindex(q.robust_z.abs().sort_values(ascending=False).index)

    done = q[q.label != ""]
    res = {"alerts_labelled": len(done), "alerts_unlabelled": len(q) - len(done),
           "precision_strict": np.nan, "precision_lenient": np.nan,
           f"precision_at_{PRECISION_AT_N}": np.nan}
    if len(done):
        res["precision_strict"] = round(100 * (done.label == "investigate").mean(), 1)
        res["precision_lenient"] = round(100 * done.label.isin(["investigate", "explained"]).mean(), 1)
    top = q.head(PRECISION_AT_N)
    if len(top) == PRECISION_AT_N and (top.label != "").all():
        res[f"precision_at_{PRECISION_AT_N}"] = round(100 * (top.label == "investigate").mean(), 1)
    return res


# ---------------------------------------------------------------- ledger
def upsert_ledger(row):
    """One row per (version, split). Re-running the same version replaces its
    row instead of appending a duplicate - running twice gives the same ledger
    as running once."""
    new = pd.DataFrame([row])
    if LEDGER_CSV.exists():
        old = pd.read_csv(LEDGER_CSV)
        old = old[~((old.version == row["version"]) & (old.split == row["split"]))]
        new = pd.concat([old, new], ignore_index=True)
    LEDGER_CSV.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(LEDGER_CSV, index=False)
    return new


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=["tuning", "holdout"], default="tuning")
    ap.add_argument("--version", default=METHOD_VERSION)
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    seed = TUNING_SEED if args.split == "tuning" else HOLDOUT_SEED

    clean = load_series().reset_index(drop=True)
    _, clean_alerts, clean_hits = alerts_for(clean)
    n_high = int((clean_hits.robust_z.abs() >= HIGH_SEVERITY_Z).sum())

    recall = measure_recall(clean, clean_alerts, seed)
    precision = measure_precision(clean_hits)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    recall.to_csv(OUT_DIR / "evaluation.csv", index=False)

    row = {
        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "version": args.version, "split": args.split, "seed": seed,
        "data_extract": EXTRACT_DATE,
        "sigma_multiplier": SIGMA_MULTIPLIER,
        "baseline": f"FY{BASELINE_START_FY}-{BASELINE_END_FY}",
        "min_baseline_points": MIN_BASELINE_POINTS, "run_length": RUN_LENGTH_RULE,
        "alerts": len(clean_alerts),
        "alerts_per_year": round(len(clean_alerts) / N_MON_YEARS, 1),
        "alerts_high": n_high,
        **precision,
        **{f"recall_{r.error_type}": r.recall_pct_mean for r in recall.itertuples()},
        "note": args.note,
    }
    ledger = upsert_ledger(row)

    print(f"MEASUREMENT - version {args.version}, {args.split} draws (seed {seed})\n")
    print("RECALL (planted errors, chart B)")
    print(recall.drop(columns=["example_misses"]).to_string(index=False))
    print("\nexample misses:")
    for r in recall.itertuples():
        print(f"  {r.error_type:15s} -> {r.example_misses or '-'}")

    print(f"\nALERT LOAD on untouched data: {len(clean_alerts)} alerts over {N_MON_YEARS} fiscal years "
          f"({len(clean_alerts) / N_MON_YEARS:.0f}/year), {n_high} high severity (|z| >= {HIGH_SEVERITY_Z}).")

    print("\nPRECISION (human labels)")
    if precision["alerts_labelled"] == 0:
        print(f"  none of the {precision['alerts_unlabelled']} alerts is labelled yet - "
              "run src/review_alerts.py and fill in labels/alert_labels.csv")
    else:
        pa = precision[f"precision_at_{PRECISION_AT_N}"]
        print(f"  labelled {precision['alerts_labelled']} of "
              f"{precision['alerts_labelled'] + precision['alerts_unlabelled']}  |  "
              f"strict {precision['precision_strict']}%  |  lenient {precision['precision_lenient']}%  |  "
              f"precision@{PRECISION_AT_N} "
              + (f"{pa}%" if pd.notna(pa) else f"n/a (label all top {PRECISION_AT_N} first)"))

    if args.split == "holdout":
        print("\nHOLDOUT numbers: report these, do not tune against them.")
    print(f"\nledger -> {LEDGER_CSV}  ({len(ledger)} row(s))")
    print(f"recall -> {OUT_DIR / 'evaluation.csv'}")


if __name__ == "__main__":
    main()
