"""STEP 3 - Fixed vs rolling, on identical broken data.

Project 01's harness, extended rather than rewritten:
  * the five original error types use Project 01's own `inject`, with the same
    per-type seeds - so the v1.1-reference row here must reproduce Project 01's
    published recall exactly (checked at the end of every run);
  * one new type, feed_stops, appended last so it cannot disturb those draws;
  * every method is scored on the SAME broken dataset in each trial - the only
    thing that differs between two ledger rows is the method.

Recall is measured on the system (chart + rule R6), as in Project 01, two ways:
  recall_*  - of the injections the method actually charts (Project 01's
              definition; comparable to its published numbers)
  e2e_*     - of ALL injections; an error in a country the method does not
              monitor counts as missed. This is where coverage shows up.

feed_stops also gets two numbers of its own, because the question it asks is
not "was the onset caught?" but "did the baseline learn the failure as normal?":
  feed_silent_end_pct   - of multi-year stops, how often the chart evaluated the
                          final monitored year and called it IN CONTROL
                          (the failure has been learned)
  feed_surfaced_end_pct - how often anything - an alert, or an ongoing lifecycle
                          incident - still points at that country in the final year

    python src/a3_evaluate.py                    # tuning draws (default)
    python src/a3_evaluate.py --split holdout    # once per finished version
"""
import argparse
import hashlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v1_bridge import v1_config as V1, v1_inject, stale_repeat_mask, V1_SRC
from adaptive_config import (ROOT, OUT_DIR, LEDGER_CSV, V1_LEDGER_CSV, METHODS, METHOD_VERSION,
                             ERROR_CATALOG, WINDOW_YEARS)
from adaptive_core import run_method, coverage, alarm_profile, MEASURE
from a2_adaptive_spc import load_series

END = V1.MONITOR_END_FY


# ---------------------------------------------------------------- injection
def inject_feed_stops(df, rng, n):
    """Zero a country's gross disbursement from a random monitored year s to
    the end of the window. Same sampling pattern as Project 01's inject: one
    country at most once, never inside the baseline."""
    pool = df[df.fiscal_year.between(V1.MONITOR_START_FY, END) & (df[MEASURE] > 0)]
    one = pool.groupby("country", group_keys=False).sample(1, random_state=int(rng.integers(1e9)))
    picked = one.sample(min(n, len(one)), random_state=int(rng.integers(1e9)))
    out = df.copy()
    for r in picked.itertuples():
        out.loc[(out.country == r.country) & out.fiscal_year.between(r.fiscal_year, END), MEASURE] = 0.0
    truth = set(zip(picked.country, picked.fiscal_year))
    return out, truth


def inject(df, rng, kind):
    if kind == "feed_stops":
        return inject_feed_stops(df, rng, V1.SYNTHETIC_PER_TRIAL)
    return v1_inject(df, rng, kind, V1.SYNTHETIC_PER_TRIAL)


# ---------------------------------------------------------------- scoring
def system_view(df, res):
    """What the system flags (chart alerts + R6) and what the chart covers."""
    a = res["alerts"]
    found = set(zip(a.country, a.fiscal_year))
    stale = stale_repeat_mask(df, MEASURE, ["country"]) & df.fiscal_year.between(V1.MONITOR_START_FY, END)
    found |= set(zip(df.country[stale], df.fiscal_year[stale]))
    p = res["points"]
    ch = p[p.status == "charted"]
    covered = set(zip(ch.country, ch.fiscal_year))
    return found, covered, ch


def feed_visibility(truth, res, found, charted, df):
    """For stops lasting 2+ years: silent = final year charted and in control;
    surfaced = an alert or an ongoing lifecycle incident in the final year.

    Only stops that really span 2+ zeroed rows AND reach a final-year row count:
    a country whose data ends before FY{END} (e.g. an aggregate that was
    discontinued) has no final year to be silent or loud about."""
    at_end = set(df.country[df.fiscal_year == END])
    long_stops = [c for c, s in truth if s <= END - 1 and c in at_end]
    if not long_stops:
        return np.nan, np.nan
    in_control = set(charted.country[(charted.fiscal_year == END) & (charted.rule == "")])
    inc = res["incidents"]
    lifecycle_live = set(inc.country[(inc.source == "lifecycle") & (inc.last_fy >= END)]) if len(inc) else set()
    silent = sum(c in in_control for c in long_stops)
    surfaced = sum(((c, END) in found) or (c in lifecycle_live) for c in long_stops)
    return 100 * silent / len(long_stops), 100 * surfaced / len(long_stops)


def evaluate(clean, seed):
    clean_res = {m: run_method(clean, m) for m in METHODS}
    clean_found = {m: system_view(clean, r)[0] for m, r in clean_res.items()}

    rows = []
    for i, kind in enumerate(ERROR_CATALOG):
        rng = np.random.default_rng([seed, i])          # Project 01's seeding scheme
        acc = {m: [] for m in METHODS}
        for _ in range(V1.SYNTHETIC_TRIALS):
            broken, truth = inject(clean, rng, kind)
            for m in METHODS:
                res = run_method(broken, m)
                found, covered, charted = system_view(broken, res)
                truth_c = truth & covered
                detected = truth_c & found
                collateral = found - truth_c - clean_found[m]
                silent, surfaced = (feed_visibility(truth, res, found, charted, broken)
                                    if kind == "feed_stops" else (np.nan, np.nan))
                acc[m].append((len(truth), len(truth_c), len(detected), len(collateral), silent, surfaced))
        for m, t in acc.items():
            t = np.array(t, dtype=float)
            rec = 100 * t[:, 2] / np.maximum(t[:, 1], 1)
            e2e = 100 * t[:, 2] / np.maximum(t[:, 0], 1)
            rows.append({"method": m, "error_type": kind, "trials": V1.SYNTHETIC_TRIALS,
                         "injected_per_trial": round(t[:, 0].mean(), 1),
                         "charted_per_trial": round(t[:, 1].mean(), 1),
                         "detected_per_trial": round(t[:, 2].mean(), 1),
                         "recall_pct_mean": round(rec.mean(), 1),
                         "recall_pct_min": round(rec.min(), 1), "recall_pct_max": round(rec.max(), 1),
                         "e2e_recall_pct_mean": round(e2e.mean(), 1),
                         "collateral_per_trial": round(t[:, 3].mean(), 1),
                         "feed_silent_end_pct": round(np.nanmean(t[:, 4]), 1) if kind == "feed_stops" else np.nan,
                         "feed_surfaced_end_pct": round(np.nanmean(t[:, 5]), 1) if kind == "feed_stops" else np.nan})
    return clean_res, pd.DataFrame(rows)


# ---------------------------------------------------------------- provenance
def provenance():
    """Which code and configuration produced a ledger row. The commit alone is
    not enough when the tree is dirty, so a hash of the files that define the
    method is recorded as well."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True).stdout.strip() or "no-git"
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", str(V1_SRC)], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        commit += "-dirty" if dirty else ""
    except OSError:
        commit = "no-git"
    h = hashlib.sha256()
    for f in [ROOT / "src" / "adaptive_config.py", ROOT / "src" / "adaptive_core.py",
              V1_SRC / "config.py", V1_SRC / "spc_core.py", V1_SRC / "step2_spc.py"]:
        h.update(f.read_bytes())
    return commit, h.hexdigest()[:12]


def upsert_ledger(new_rows):
    new = pd.DataFrame(new_rows)
    if LEDGER_CSV.exists():
        old = pd.read_csv(LEDGER_CSV)
        keys = set(zip(new.version, new.method, new.split))
        old = old[[k not in keys for k in zip(old.version, old.method, old.split)]]
        new = pd.concat([old, new], ignore_index=True)
    LEDGER_CSV.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(LEDGER_CSV, index=False)
    return new


def check_v1_reproduction(ev, split):
    """The v1.1-reference row must equal Project 01's own published numbers.
    If it does not, the reuse is broken and no comparison here can be trusted."""
    if not V1_LEDGER_CSV.exists():
        return "Project 01 ledger not found - reproduction not checked"
    v1 = pd.read_csv(V1_LEDGER_CSV)
    v1 = v1[(v1.version == "v1.1-quick-fixes") & (v1.split == split)]
    if v1.empty:
        return f"no v1.1-quick-fixes {split} row in Project 01's ledger - not checked"
    mine = ev[ev.method == "v1.1-reference"].set_index("error_type").recall_pct_mean
    bad = [f"{k}: {mine[k]} vs {v1[f'recall_{k}'].iloc[0]}" for k in V1.ERROR_CATALOG
           if abs(mine[k] - v1[f"recall_{k}"].iloc[0]) > 1e-9]
    return "OK - v1.1-reference reproduces Project 01's ledger exactly" if not bad else "MISMATCH: " + "; ".join(bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=["tuning", "holdout"], default="tuning")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    seed = V1.TUNING_SEED if args.split == "tuning" else V1.HOLDOUT_SEED

    clean = load_series()
    clean_res, ev = evaluate(clean, seed)
    commit, cfg_hash = provenance()

    rows = []
    for m, cfg in METHODS.items():
        r = clean_res[m]
        cov = coverage(r["points"], clean.country.unique())
        e = ev[ev.method == m].set_index("error_type")
        rows.append({
            "run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "version": METHOD_VERSION, "method": m,
            "split": args.split, "seed": seed, "code_commit": commit, "code_config_hash": cfg_hash,
            "baseline": cfg.get("baseline", "fixed"),
            "window_years": WINDOW_YEARS if cfg.get("baseline") == "rolling" else "",
            "policy": cfg.get("policy", "v1.1"), "lifecycle": cfg.get("lifecycle", False),
            "sigma_multiplier": V1.SIGMA_MULTIPLIER, "min_baseline_points": V1.MIN_BASELINE_POINTS,
            **alarm_profile(r["alerts"], r["incidents"]),
            **{k: v for k, v in cov.items() if k != "excluded_reasons"},
            **{f"recall_{k}": e.loc[k, "recall_pct_mean"] for k in ERROR_CATALOG},
            **{f"e2e_{k}": e.loc[k, "e2e_recall_pct_mean"] for k in ERROR_CATALOG},
            **{f"collateral_{k}": e.loc[k, "collateral_per_trial"] for k in ERROR_CATALOG},
            "feed_silent_end_pct": e.loc["feed_stops", "feed_silent_end_pct"],
            "feed_surfaced_end_pct": e.loc["feed_stops", "feed_surfaced_end_pct"],
            "note": args.note,
        })
    ledger = upsert_ledger(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev.to_csv(OUT_DIR / "evaluation.csv", index=False)

    print(f"FIXED vs ROLLING - {args.split} draws (seed {seed}), version {METHOD_VERSION}, "
          f"code {commit}, config {cfg_hash}\n")
    for metric, label in [("recall_pct_mean", "RECALL, % of charted injections (Project 01 definition)"),
                          ("e2e_recall_pct_mean", "END-TO-END RECALL, % of all injections"),
                          ("collateral_per_trial", "COLLATERAL alerts per trial")]:
        print(label)
        print(ev.pivot(index="error_type", columns="method", values=metric)
              .reindex(list(ERROR_CATALOG))[list(METHODS)].to_string(), "\n")
    fs = ev[ev.error_type == "feed_stops"].set_index("method")
    print("FEED STOPS lasting 2+ years - final monitored year")
    print(fs[["feed_silent_end_pct", "feed_surfaced_end_pct"]].reindex(list(METHODS))
          .rename(columns={"feed_silent_end_pct": "chart says in control %",
                           "feed_surfaced_end_pct": "still surfaced %"}).to_string(), "\n")
    print("v1.1 reproduction check:", check_v1_reproduction(ev, args.split))
    if args.split == "holdout":
        print("HOLDOUT numbers: report these, do not tune against them.")
    print(f"\nledger -> {LEDGER_CSV} ({len(ledger)} rows)   detail -> {OUT_DIR / 'evaluation.csv'}")


if __name__ == "__main__":
    main()
