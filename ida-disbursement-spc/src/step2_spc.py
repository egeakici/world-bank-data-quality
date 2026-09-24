"""STEP 2 - The control charts.

We build the same chart two ways, on purpose, because the comparison is the
lesson:

  Chart A - LEVEL      : is this year's dollar amount inside the historical range?
  Chart B - YoY GROWTH : is this year's change from last year inside the
                         historical range of changes?

Chart A is the textbook chart and it is the one most people build first. On
this dataset it misfires, and the reason it misfires is worth more than the
chart itself: IDA disbursements grew from ~$11bn to ~$33bn between FY2010 and
FY2025. SPC assumes a process that is stable around a fixed centre. A growing
process is not "out of control", it is trending - but a chart whose limits
were learned in 2010-2019 will scream about every year after 2020.

Chart B differences the series first. A steadily growing country has a
roughly stable growth rate, so the differenced series IS approximately
stable, and a flag then means "the change this year was unlike this
country's usual changes" - which is the question we actually wanted.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (SILVER_DIR, OUT_DIR, FINANCIER, MEASURE, BASELINE_START_FY,
                    BASELINE_END_FY, MONITOR_START_FY, MONITOR_END_FY,
                    MIN_BASELINE_POINTS, HIGH_SEVERITY_Z, TOP_N_ALERTS)
from spc_core import fit_chart, robust_z, run_rule_flags, explain


def load_series():
    df = pd.read_csv(SILVER_DIR / "net_flows_silver.csv")
    df = df[(df.financier == FINANCIER) & df.fy_is_complete]
    return df[["country", "fiscal_year", MEASURE]].sort_values(["country", "fiscal_year"])


def to_growth(g):
    """Year-over-year log change, stabilised so that near-zero years do not
    produce infinite growth rates.

    The stabiliser c is 5% of the country's own typical year (floor $100k), so
    a $2m country and a $2bn country are treated on the same relative footing.
    Negative gross disbursements (refunds) are clipped to zero first - they are
    real, but they are a different phenomenon and the rule layer already
    reported them.
    """
    x = g[MEASURE].clip(lower=0).to_numpy(dtype=float)
    base = x[(g.fiscal_year >= BASELINE_START_FY) & (g.fiscal_year <= BASELINE_END_FY)]
    c = max(1e5, 0.05 * (np.median(base) if base.size else np.median(x)))
    out = np.full(x.size, np.nan)
    out[1:] = np.log((x[1:] + c) / (x[:-1] + c))
    return out


def add_growth(df):
    df = df.copy()
    df["yoy_log_growth"] = df.groupby("country", group_keys=False).apply(
        to_growth, include_groups=False).explode().astype(float).to_numpy()
    return df


def build(df, value_col, chart_name, floor_at_zero, kind):
    """Phase I on the baseline window, Phase II on the monitoring window."""
    points, skipped = [], []

    for country, g in df.groupby("country"):
        g = g.sort_values("fiscal_year")
        base = g[(g.fiscal_year >= BASELINE_START_FY) & (g.fiscal_year <= BASELINE_END_FY)]
        mon = g[(g.fiscal_year >= MONITOR_START_FY) & (g.fiscal_year <= MONITOR_END_FY)]

        chart = fit_chart(base[value_col], MIN_BASELINE_POINTS)
        if not chart["fitted"]:
            skipped.append({"chart": chart_name, "country": country, "reason": chart["reason"]})
            continue
        if not floor_at_zero:            # growth chart: negative side is meaningful
            chart["lcl"] = chart["center"] - 3 * chart["sigma"]
        chart["baseline_span"] = f"{BASELINE_START_FY}-{BASELINE_END_FY}"

        # Nelson run rule is evaluated over the whole series so a shift that
        # started in the baseline is still visible when it reaches monitoring.
        full = g.dropna(subset=[value_col])
        runs = dict(zip(full.fiscal_year, run_rule_flags(full[value_col], chart["center"])))

        for _, r in mon.dropna(subset=[value_col]).iterrows():
            v = float(r[value_col])
            z = robust_z(v, chart["center"], chart["sigma"])
            beyond = v > chart["ucl"] or v < chart["lcl"]
            shift = bool(runs.get(r.fiscal_year, False))
            rule = "beyond_limits" if beyond else ("sustained_shift" if shift else "")
            points.append({
                "chart": chart_name, "country": country, "fiscal_year": int(r.fiscal_year),
                "value": v, "center": chart["center"], "lcl": chart["lcl"],
                "ucl": chart["ucl"], "sigma": chart["sigma"], "robust_z": z,
                "n_baseline": chart["n_baseline"], "rule": rule,
                "severity": "" if not rule else ("high" if abs(z) >= HIGH_SEVERITY_Z else "medium"),
                "explanation": explain(country, int(r.fiscal_year), v, chart, z, rule, kind) if rule else "",
            })

    return pd.DataFrame(points), pd.DataFrame(skipped)


def main():
    df = load_series()

    # Chart A - raw level.
    a_pts, a_skip = build(df, MEASURE, "A_level", floor_at_zero=True, kind="usd")

    # Chart B - year-over-year log growth.
    df = add_growth(df)
    b_pts, b_skip = build(df, "yoy_log_growth", "B_growth", floor_at_zero=False, kind="growth")

    pts = pd.concat([a_pts, b_pts], ignore_index=True)
    skip = pd.concat([a_skip, b_skip], ignore_index=True)
    alerts = pts[pts.rule != ""].copy()
    alerts["abs_z"] = alerts.robust_z.abs()
    alerts = alerts.sort_values(["chart", "abs_z"], ascending=[True, False])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pts.to_csv(OUT_DIR / "spc_points.csv", index=False)
    alerts.to_csv(OUT_DIR / "spc_alerts.csv", index=False)
    skip.to_csv(OUT_DIR / "spc_not_charted.csv", index=False)

    n_mon_years = MONITOR_END_FY - MONITOR_START_FY + 1
    print(f"monitoring window FY{MONITOR_START_FY}-FY{MONITOR_END_FY} ({n_mon_years} years)\n")
    for name in ["A_level", "B_growth"]:
        p = pts[pts.chart == name]
        a = alerts[alerts.chart == name]
        rate = 100 * len(a) / max(len(p), 1)
        print(f"{name:9s} countries charted {p.country.nunique():3d} | points {len(p):4d} | "
              f"alerts {len(a):4d} ({rate:5.1f}% of points) | "
              f"alerts per country-year {len(a)/max(len(p),1):.2f}")
        print(f"{'':9s} not charted: {len(skip[skip.chart==name]):3d} "
              f"({skip[skip.chart==name].reason.str.split(' ').str[0].value_counts().to_dict()})")
    print(f"\nTop {TOP_N_ALERTS} growth-chart alerts by |robust z|:\n")
    for _, r in alerts[alerts.chart == "B_growth"].head(TOP_N_ALERTS).iterrows():
        print(f"  [{r.severity:6s} z={r.robust_z:+6.1f}] {r.explanation[:150]}")


if __name__ == "__main__":
    main()
