"""STEP 4 - The figures, and a findings file a human can read.

A control chart is a picture for a reason. The numbers in spc_alerts.csv are
correct, but the reason SPC survived a century in factories is that a
supervisor could glance at a wall chart and see the process leave its lane.
Keep the picture.

Design choices here follow one rule: the chart must be readable in one pass.
One data series in blue, control limits as thin rules, the centre line
recessive, and out-of-control points in the reserved critical red AND a
different marker shape - so the flag is never carried by colour alone.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (SILVER_DIR, OUT_DIR, FIG_DIR, FINANCIER, MEASURE, INCOMPLETE_FY,
                    BASELINE_START_FY, BASELINE_END_FY, MONITOR_START_FY,
                    MONITOR_END_FY, MIN_BASELINE_POINTS)
from spc_core import fit_chart
from step2_spc import load_series, add_growth

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d6d5d0"
SERIES, CRITICAL, BAND = "#2a78d6", "#d03b3b", "#eef2f7"

plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6,
})


def draw_chart(ax, years, values, chart, title, ylabel, fmt):
    """One individuals chart: series, centre line, limits, flagged points."""
    years = list(years)
    values = np.asarray(values, dtype=float)
    ax.axhspan(chart["lcl"], chart["ucl"], color=BAND, zorder=1)
    ax.axhline(chart["center"], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
    for y, label in [(chart["ucl"], "UCL"), (chart["lcl"], "LCL")]:
        ax.axhline(y, color=MUTED, lw=1, zorder=2)
        ax.annotate(label + " " + fmt(y), (years[-1], y), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=8, color=MUTED)
    ax.plot(years, values, color=SERIES, lw=2, marker="o", ms=5,
            mfc="#fcfcfb", mew=1.6, zorder=3, label="observed")

    out = (values > chart["ucl"]) | (values < chart["lcl"])
    if out.any():
        ax.scatter(np.asarray(years)[out], values[out], s=95, marker="X",
                   color=CRITICAL, zorder=4, label="out of control")
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    # Headroom so the legend never lands on the data or the UCL label.
    lo = min(values.min(), chart["lcl"])
    hi = max(values.max(), chart["ucl"])
    pad = 0.10 * (hi - lo)
    ax.set_ylim(lo - pad, hi + 2.2 * pad)
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    ax.set_xticks([y for y in years if y % 2 == 0])
    ax.set_xlim(years[0] - 0.8, years[-1] + 0.8)

    # The Phase I / Phase II divider. Everything left of it taught the limits;
    # everything right of it is being judged by them.
    ax.axvline(BASELINE_END_FY + 0.5, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=2)
    ax.annotate("baseline (limits learned here)   |   monitored",
                (BASELINE_END_FY + 0.5, ax.get_ylim()[0]), xytext=(-4, 6),
                textcoords="offset points", fontsize=8, color=MUTED, ha="right")


def md_table(df):
    """A markdown table without pulling in `tabulate`. Fewer dependencies is a
    production virtue, not laziness - every extra package is something the team
    has to keep installed after the intern leaves."""
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    rule = "|" + "|".join(["---"] * len(cols)) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule] + body)


def usd_b(v):
    return "${:.1f}bn".format(v / 1e9)


def usd_m(v):
    return "${:.0f}m".format(v / 1e6)


def pct(v):
    return "{:+.0f}%".format((np.exp(v) - 1) * 100)


def fig_portfolio(df):
    """Why the level chart fails here: the portfolio is trending, not stable."""
    tot = df.groupby("fiscal_year")[MEASURE].sum()
    chart = fit_chart(tot.loc[BASELINE_START_FY:BASELINE_END_FY], MIN_BASELINE_POINTS)
    chart["baseline_span"] = "{}-{}".format(BASELINE_START_FY, BASELINE_END_FY)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    draw_chart(ax, tot.index, tot.values, chart,
               FINANCIER + " total gross disbursement - a LEVEL chart on a growing process",
               "US$", usd_b)
    ax.yaxis.set_major_formatter(lambda v, _: "${:.0f}bn".format(v / 1e9))
    fig.text(0.01, -0.03,
             "Every year from FY2020 on sits above the upper limit. The process is not out of control - "
             "it is growing.\nA chart that flags almost every recent point is telling you the model is "
             "wrong, not that the data is.", fontsize=8.5, color=MUTED, ha="left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_portfolio_level_trend.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return int((tot.loc[MONITOR_START_FY:MONITOR_END_FY] > chart["ucl"]).sum())


def fig_country(df, country):
    """The same country, both charts, side by side."""
    g = df[df.country == country].sort_values("fiscal_year")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))

    lvl = fit_chart(g[g.fiscal_year <= BASELINE_END_FY][MEASURE], MIN_BASELINE_POINTS)
    lvl["baseline_span"] = "{}-{}".format(BASELINE_START_FY, BASELINE_END_FY)
    draw_chart(axes[0], g.fiscal_year, g[MEASURE], lvl,
               "A - " + country + ": level (US$)", "US$", usd_m)
    axes[0].yaxis.set_major_formatter(lambda v, _: "${:.0f}m".format(v / 1e6))

    gg = g.dropna(subset=["yoy_log_growth"])
    gr = fit_chart(gg[gg.fiscal_year <= BASELINE_END_FY]["yoy_log_growth"], MIN_BASELINE_POINTS)
    gr["lcl"] = gr["center"] - 3 * gr["sigma"]
    gr["baseline_span"] = "{}-{}".format(BASELINE_START_FY, BASELINE_END_FY)
    draw_chart(axes[1], gg.fiscal_year, gg.yoy_log_growth, gr,
               "B - " + country + ": year-over-year change", "change vs prior year", pct)
    axes[1].yaxis.set_major_formatter(lambda v, _: "{:+.0f}%".format((np.exp(v) - 1) * 100))

    fig.text(0.01, -0.04,
             "Same country, same data. Differencing the series removes the growth trend, so the limits "
             "describe ordinary\nyear-to-year movement and a flag means 'this change was unusual for this "
             "country', not 'this country grew'.", fontsize=8.5, color=MUTED, ha="left")
    fig.tight_layout()
    name = country.split(",")[0].replace(" ", "_").lower()
    fig.savefig(FIG_DIR / ("fig2_" + name + "_level_vs_growth.png"), dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_partial(raw):
    """The partial-period trap, drawn once so it is never forgotten."""
    tot = raw[raw.financier == FINANCIER].groupby("fiscal_year")[MEASURE].sum() / 1e9
    fig, ax = plt.subplots(figsize=(9, 3.8))
    colors = [CRITICAL if y == INCOMPLETE_FY else SERIES for y in tot.index]
    ax.bar(tot.index, tot.values, color=colors, width=0.7)
    ax.set_xticks([y for y in tot.index if y % 2 == 0])
    ax.annotate("FY{}: ${:.1f}bn - not a collapse.\nThe year was only ~2.5 months old\nwhen the file was extracted."
                .format(INCOMPLETE_FY, tot.iloc[-1]),
                xy=(tot.index[-1], tot.iloc[-1]), xytext=(0.03, 0.80), textcoords="axes fraction",
                fontsize=9, color=CRITICAL, ha="left", va="top",
                arrowprops=dict(arrowstyle="->", color=CRITICAL, lw=1,
                                connectionstyle="arc3,rad=-0.18"))
    ax.set_title("{} gross disbursement by fiscal year - why FY{} is excluded"
                 .format(FINANCIER, INCOMPLETE_FY), loc="left", fontsize=11, color=INK, pad=10)
    ax.set_ylabel("US$ bn")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_partial_fiscal_year.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SILVER_DIR / "net_flows_silver.csv")
    df = add_growth(load_series())

    n_trend = fig_portfolio(df)
    for c in ["Cameroon", "Bangladesh"]:
        fig_country(df, c)
    fig_partial(raw)

    alerts = pd.read_csv(OUT_DIR / "spc_alerts.csv")
    points = pd.read_csv(OUT_DIR / "spc_points.csv")
    rules = pd.read_csv(OUT_DIR / "rule_layer_report.csv")
    ev = pd.read_csv(OUT_DIR / "evaluation.csv")

    n_a_pts = int((points.chart == "A_level").sum())
    n_a = int((alerts.chart == "A_level").sum())
    n_b = int((alerts.chart == "B_growth").sum())
    n_b_high = int(((alerts.chart == "B_growth") & (alerts.severity == "high")).sum())
    n_mon_years = MONITOR_END_FY - MONITOR_START_FY + 1

    lines = [
        "# Findings", "",
        "Source: `{}` rows of the IBRD/IDA net flows & commitments extract "
        "(FY{}-FY{}).".format(FINANCIER, BASELINE_START_FY, INCOMPLETE_FY),
        "Baseline FY{}-FY{}, monitored FY{}-FY{}, FY{} excluded as an incomplete period."
        .format(BASELINE_START_FY, BASELINE_END_FY, MONITOR_START_FY, MONITOR_END_FY, INCOMPLETE_FY),
        "", "## 1. Rule layer", "", md_table(rules), "",
        "## 2. Control charts", "",
        "- **Level chart (A)** flags {} of {} monitored country-years, and the portfolio total "
        "breaches its upper limit in {} of {} monitored years. That is a trend, not an incident - "
        "the chart is measuring growth.".format(n_a, n_a_pts, n_trend, n_mon_years),
        "- **Growth chart (B)** flags {} points, {} of them high severity - about {:.0f} alerts per "
        "fiscal year, which a team can actually work through.".format(n_b, n_b_high, n_b / n_mon_years),
        "", "### Top 10 growth-chart alerts", "",
    ]
    for _, r in alerts[alerts.chart == "B_growth"].head(10).iterrows():
        lines.append("- **{}** (z={:+.1f}) {}".format(r.severity, r.robust_z, r.explanation))
    lines += ["", "## 3. Evaluation (synthetic injection)", "",
              md_table(ev.drop(columns=["example_misses"])), "",
              "## 4. Figures", "",
              "- `figures/fig1_portfolio_level_trend.png` - why a level chart fails on this data",
              "- `figures/fig2_cameroon_level_vs_growth.png` - level vs growth, volatile borrower",
              "- `figures/fig2_bangladesh_level_vs_growth.png` - level vs growth, large steady borrower",
              "- `figures/fig3_partial_fiscal_year.png` - the partial-period trap", ""]
    (OUT_DIR / "FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")

    print("portfolio years above UCL: {} of {}".format(n_trend, n_mon_years))
    print("figures  -> {}".format(FIG_DIR))
    print("findings -> {}".format(OUT_DIR / "FINDINGS.md"))


if __name__ == "__main__":
    main()
