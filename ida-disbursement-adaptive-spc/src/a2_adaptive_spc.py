"""STEP 2 - Every method on the real data, side by side.

Runs the four methods in adaptive_config.METHODS on the same silver data and
writes one file per artefact, each with a `method` column, so any row can be
compared across methods with a filter:

    outputs/points.csv            every monitored country-year and its status
                                  (charted / dormant / no_prior_year /
                                  insufficient_history / zero_mad)
    outputs/alerts.csv            raw statistical alerts, with incident_id
    outputs/incidents.csv         grouped incidents: source = statistical | lifecycle
    outputs/zero_periods.csv      every run of zero years (method-independent)
    outputs/method_summary.csv    coverage and alarm profile per method
    outputs/fixed_vs_rolling.csv  alerts raised by only one of v2-fixed / v2-rolling
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from adaptive_config import SILVER_DIR, OUT_DIR, METHODS, PRIMARY_METHOD
from adaptive_core import series_from_silver, run_method, coverage, alarm_profile


def load_series():
    return series_from_silver(pd.read_csv(SILVER_DIR / "net_flows_silver.csv"))


def fixed_vs_rolling(alerts):
    """Which alerts appear under one baseline and not the other - the raw
    material for 'where does adaptive SPC help, where does it hurt'."""
    key = ["country", "fiscal_year"]
    f = alerts[alerts.method == "v2-fixed"].set_index(key)
    r = alerts[alerts.method == "v2-rolling"].set_index(key)
    only_f = f.loc[f.index.difference(r.index)].assign(only_in="v2-fixed")
    only_r = r.loc[r.index.difference(f.index)].assign(only_in="v2-rolling")
    cols = ["only_in", "rule", "severity", "robust_z", "value", "baseline_span", "explanation"]
    return pd.concat([only_f, only_r])[cols].reset_index().sort_values(key)


def main():
    df = load_series()
    runs = {m: run_method(df, m) for m in METHODS}
    points = pd.concat([r["points"] for r in runs.values()], ignore_index=True)
    alerts = pd.concat([r["alerts"] for r in runs.values()], ignore_index=True)
    incidents = pd.concat([r["incidents"] for r in runs.values()], ignore_index=True)

    summary = []
    for m, r in runs.items():
        cov = coverage(r["points"], df.country.unique())
        summary.append({"method": m, **alarm_profile(r["alerts"], r["incidents"]),
                        **{k: v for k, v in cov.items() if k != "excluded_reasons"},
                        "excluded_reasons": "; ".join(f"{k} {v}" for k, v in cov["excluded_reasons"].items())})
    summary = pd.DataFrame(summary)
    diff = fixed_vs_rolling(alerts)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    points.to_csv(OUT_DIR / "points.csv", index=False)
    alerts.sort_values(["method", "robust_z"], key=lambda s: s.abs() if s.dtype != object else s) \
        .to_csv(OUT_DIR / "alerts.csv", index=False)
    incidents.to_csv(OUT_DIR / "incidents.csv", index=False)
    runs[PRIMARY_METHOD]["periods"].to_csv(OUT_DIR / "zero_periods.csv", index=False)
    summary.to_csv(OUT_DIR / "method_summary.csv", index=False)
    diff.to_csv(OUT_DIR / "fixed_vs_rolling.csv", index=False)

    print("METHODS ON THE REAL DATA (monitoring FY2020-FY2026)\n")
    print(summary.drop(columns=["excluded_reasons"]).to_string(index=False))
    print("\nwhy countries were not monitored:")
    for r in summary.itertuples():
        print(f"  {r.method:18s} {r.excluded_reasons}")
    print(f"\nv2-fixed vs v2-rolling: {int((diff.only_in == 'v2-fixed').sum())} alerts only under the fixed "
          f"baseline, {int((diff.only_in == 'v2-rolling').sum())} only under the rolling one "
          f"-> outputs/fixed_vs_rolling.csv")
    print(f"wrote points, alerts, incidents, zero_periods, method_summary to {OUT_DIR}")


if __name__ == "__main__":
    main()
