"""STEP 3 - Evaluating a detector when nothing is labelled.

There is no column in this dataset that says "this row is wrong". That makes
this an unsupervised problem, and unsupervised does NOT mean unevaluated.

Two standard moves, both used here:

1. SYNTHETIC ANOMALY INJECTION - take data we believe is clean, deliberately
   break known cells, and measure how many of our own breakages the detector
   catches. That fraction is RECALL. It is a lower bound on real performance
   (real errors may be subtler than ours) but it is a number, and a number can
   be tracked release over release.

2. BACKGROUND ALERT RATE - how many alerts fire on the untouched data. Those
   are not necessarily false positives (some are genuine), but they set the
   daily workload. If the queue is unreadable, analysts stop reading it, and
   a detector nobody reads has zero recall in practice. That is alert fatigue,
   and it is an operational failure, not a statistical one.

The two error types injected mirror two real pipeline failures:
   SPIKE - a magnitude error, e.g. an extra zero or a units mix-up
   DROP  - a feed that silently delivered nothing for a country-year
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (OUT_DIR, MEASURE, MONITOR_START_FY, MONITOR_END_FY,
                    SYNTHETIC_PER_TRIAL, SYNTHETIC_TRIALS, SYNTHETIC_SPIKE, RANDOM_SEED,
                    HIGH_SEVERITY_Z)
from step2_spc import load_series, add_growth, build


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
    pool = df[(df.fiscal_year >= MONITOR_START_FY) & (df.fiscal_year <= MONITOR_END_FY)
              & (df[MEASURE] > 0)]
    one_per_country = pool.groupby("country", group_keys=False).sample(1, random_state=int(rng.integers(1e9)))
    picked = one_per_country.sample(min(n, len(one_per_country)),
                                    random_state=int(rng.integers(1e9))).index
    out = df.copy()
    if kind == "spike":
        out.loc[picked, MEASURE] *= SYNTHETIC_SPIKE
    else:
        out.loc[picked, MEASURE] = 0.0
    truth = set(zip(out.loc[picked, "country"], out.loc[picked, "fiscal_year"]))
    return out, truth


def alerts_for(df):
    pts, _ = build(add_growth(df), "yoy_log_growth", "B_growth",
                   floor_at_zero=False, kind="growth")
    hit = pts[pts.rule != ""]
    return pts, set(zip(hit.country, hit.fiscal_year)), hit


def main():
    rng = np.random.default_rng(RANDOM_SEED)
    clean = load_series().reset_index(drop=True)
    _, clean_alerts, clean_hits = alerts_for(clean)

    rows = []
    for kind in ["spike", "drop"]:
        trials = []
        misses = []
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
            trials.append((len(truth_c), len(detected), len(found), len(collateral)))
            misses += sorted(truth_c - detected)

        t_arr = np.array(trials, dtype=float)
        recalls = 100 * t_arr[:, 1] / np.maximum(t_arr[:, 0], 1)
        rows.append({
            "error_type": kind,
            "trials": SYNTHETIC_TRIALS,
            "injected_per_trial": round(t_arr[:, 0].mean(), 1),
            "detected_per_trial": round(t_arr[:, 1].mean(), 1),
            "recall_pct_mean": round(recalls.mean(), 1),
            "recall_pct_min": round(recalls.min(), 1),
            "recall_pct_max": round(recalls.max(), 1),
            "alerts_on_clean_data": len(clean_alerts),
            "collateral_per_trial": round(t_arr[:, 3].mean(), 1),
            "example_misses": "; ".join(f"{c} FY{y}" for c, y in misses[:5]),
        })

    res = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT_DIR / "evaluation.csv", index=False)

    print("SYNTHETIC ANOMALY INJECTION (chart B, year-over-year growth)\n")
    print(res.drop(columns=["example_misses"]).to_string(index=False))
    print("\nexample misses:")
    for _, r in res.iterrows():
        print(f"  {r.error_type:5s} -> {r.example_misses}")

    n_high = int((clean_hits.robust_z.abs() >= HIGH_SEVERITY_Z).sum())
    print(f"\nBACKGROUND LOAD on untouched data: {len(clean_alerts)} alerts over "
          f"{MONITOR_END_FY - MONITOR_START_FY + 1} fiscal years "
          f"({len(clean_alerts) / (MONITOR_END_FY - MONITOR_START_FY + 1):.0f}/year), "
          f"of which {n_high} are high severity (|z| >= {HIGH_SEVERITY_Z}).")
    print("Triage: high -> investigate, medium -> batch review, everything else -> log only.")


if __name__ == "__main__":
    main()
