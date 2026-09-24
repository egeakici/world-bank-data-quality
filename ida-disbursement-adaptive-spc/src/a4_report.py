"""STEP 4 - Figures and outputs/COMPARISON.md.

Same visual language as Project 01 (its palette and rcParams are imported, not
redefined): one series in blue, limits as thin recessive rules, alerts in the
reserved red AND an X marker so a flag never depends on colour alone.

Each country gets two panels on a SHARED y-axis - fixed limits left, rolling
limits right - rather than two sets of limits overlaid on one plot.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v1_bridge import v1_config as V1
from step4_report import INK, MUTED, GRID, SERIES, CRITICAL, BAND, md_table   # Project 01 style
from adaptive_config import (OUT_DIR, FIG_DIR, LEDGER_CSV, METHODS, METHOD_VERSION, REPORT_COUNTRIES,
                             ERROR_CATALOG, WINDOW_YEARS)
from adaptive_core import CountrySeries, select_baseline, stabiliser
from a2_adaptive_spc import load_series

DORMANT = "#e7e6e1"
pct = lambda v: f"{(np.exp(v) - 1) * 100:+.0f}%"


def history(df, country):
    """FY2011-2019 growth, computed with the FY2020 stabiliser, as grey context:
    the observations the first chart of both methods was built from."""
    g = df[df.country == country].sort_values("fiscal_year")
    cs = CountrySeries(g)
    chosen, _ = select_baseline(cs, V1.MONITOR_START_FY, METHODS["v2-fixed"], {})
    if not chosen:
        return [], []
    c = stabiliser(cs, chosen)
    ys = [y for y in range(V1.BASELINE_START_FY + 1, V1.MONITOR_START_FY) if cs.has_growth(y)]
    return ys, [cs.growth(y, c) for y in ys]


def panel(ax, pts, hist, title):
    hy, hv = hist
    if hy:
        ax.plot(hy, hv, color=MUTED, lw=1.4, marker="o", ms=3.5, zorder=2, label="baseline history")
    for r in pts[pts.status == "dormant"].itertuples():
        ax.axvspan(r.fiscal_year - 0.5, r.fiscal_year + 0.5, color=DORMANT, zorder=0, lw=0)
    ch = pts[pts.status == "charted"].sort_values("fiscal_year")
    if len(ch):
        x = ch.fiscal_year.to_numpy()
        # Limits drawn per monitored year as steps: flat for fixed, moving for rolling.
        ax.fill_between(np.r_[x - 0.5, x[-1] + 0.5][:len(x) + 1],
                        np.r_[ch.lcl, ch.lcl.iloc[-1]], np.r_[ch.ucl, ch.ucl.iloc[-1]],
                        step="post", color=BAND, zorder=1, lw=0)
        for col, ls in [("ucl", "-"), ("lcl", "-"), ("center", (0, (4, 3)))]:
            ax.step(np.r_[x - 0.5, x[-1] + 0.5], np.r_[ch[col], ch[col].iloc[-1]], where="post",
                    color=MUTED, lw=1, ls=ls, zorder=2)
        ax.plot(x, ch.value, color=SERIES, lw=2, marker="o", ms=5, mfc="#fcfcfb", mew=1.6, zorder=3,
                label="monitored year")
        fl = ch[ch.rule != ""]
        if len(fl):
            ax.scatter(fl.fiscal_year, fl.value, s=95, marker="X", color=CRITICAL, zorder=4, label="alert")
    ax.axvline(V1.BASELINE_END_FY + 0.5, color=MUTED, lw=1, ls=(0, (2, 3)))
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=8)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.set_xlim(V1.BASELINE_START_FY + 0.3, V1.MONITOR_END_FY + 0.7)
    ax.set_xticks(range(V1.BASELINE_START_FY + 2, V1.MONITOR_END_FY + 1, 2))
    ax.yaxis.set_major_formatter(lambda v, _: pct(v))


def fig_country(df, points, country):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.3), sharey=True)
    hist = history(df, country)
    for ax, m, label in [(axes[0], "v2-fixed", "fixed FY2011-2019 limits"),
                         (axes[1], "v2-rolling", f"rolling {WINDOW_YEARS}-year limits")]:
        pts = points[(points.method == m) & (points.country == country)]
        panel(ax, pts, hist, f"{country} - {label}")
        if (pts.status == "dormant").any():
            ax.text(0.99, 0.04, "shaded = dormant (zero after zero):\nnot evaluated, reported once",
                    transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=MUTED)
    axes[0].set_ylabel("change vs prior year")
    legend = {}
    for ax in axes:
        for h, lab in zip(*ax.get_legend_handles_labels()):
            legend.setdefault(lab, h)
    fig.legend(list(legend.values()), list(legend), loc="upper right", frameon=False, fontsize=8, ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    name = "fig_" + country.split(",")[0].replace(" ", "_").lower() + "_fixed_vs_rolling.png"
    fig.savefig(FIG_DIR / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return name


def classify_difference(diff, points):
    """Why an alert exists under only one baseline."""
    fixed_cov = set(points[(points.method == "v2-fixed") & (points.status == "charted")].country)
    out = []
    for r in diff.itertuples():
        if r.only_in == "v2-rolling" and r.country not in fixed_cov:
            why = "coverage: the fixed baseline could not chart this country at all"
        elif r.only_in == "v2-rolling":
            why = "sensitivity: recent calmer years tightened the rolling limits"
        else:
            why = "adaptation: the rolling baseline has absorbed a newer, more volatile regime"
        out.append(why)
    return diff.assign(why=out)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = load_series()
    points = pd.read_csv(OUT_DIR / "points.csv")
    points["rule"] = points.rule.fillna("")          # CSV turns "" into NaN
    summary = pd.read_csv(OUT_DIR / "method_summary.csv")
    incidents = pd.read_csv(OUT_DIR / "incidents.csv")
    diff = classify_difference(pd.read_csv(OUT_DIR / "fixed_vs_rolling.csv"), points)
    figs = [fig_country(df, points, c) for c in REPORT_COUNTRIES]

    L = ["# Fixed vs rolling control limits - comparison", "",
         f"Version `{METHOD_VERSION}`. Monitoring FY{V1.MONITOR_START_FY}-FY{V1.MONITOR_END_FY}; "
         f"rolling window {WINDOW_YEARS} eligible years; everything else inherited from Project 01 "
         f"({V1.SIGMA_MULTIPLIER:.0f} sigma, median/MAD, min {V1.MIN_BASELINE_POINTS} baseline years).", "",
         "## 1. On the real data", "",
         md_table(summary.drop(columns=["excluded_reasons"])), ""]
    L += [f"- **{r.method}** not monitored: {r.excluded_reasons}" for r in summary.itertuples()]

    if LEDGER_CSV.exists():
        led = pd.read_csv(LEDGER_CSV)
        led = led[led.version == METHOD_VERSION]
        for split in ["holdout", "tuning"]:
            s = led[led.split == split].set_index("method").reindex(list(METHODS)).dropna(how="all")
            if s.empty:
                continue
            L += ["", f"## 2{'a' if split == 'holdout' else 'b'}. Performance - {split} draws"
                  + (" (report these)" if split == "holdout" else " (development only)"), ""]
            for prefix, title in [("recall_", "Recall, % of charted injections"),
                                  ("e2e_", "End-to-end recall, % of all injections"),
                                  ("collateral_", "Collateral alerts per trial")]:
                t = s[[prefix + k for k in ERROR_CATALOG]].T
                t.index = [k for k in ERROR_CATALOG]
                L += [f"**{title}**", "", md_table(t.reset_index().rename(columns={"index": "error_type"})), ""]
            f = s[["feed_silent_end_pct", "feed_surfaced_end_pct"]].reset_index()
            f.columns = ["method", "feed stop: chart says in control %", "feed stop: still surfaced %"]
            L += ["**Feed stops lasting 2+ years, final monitored year**", "", md_table(f), "",
                  f"Code `{s.code_commit.iloc[0]}`, config hash `{s.code_config_hash.iloc[0]}`."]

    L += ["", "## 3. Where the rolling baseline helps and where it hurts", "",
          f"{len(diff)} alerts differ between v2-fixed and v2-rolling on the real data "
          f"({int((diff.only_in == 'v2-fixed').sum())} only fixed, "
          f"{int((diff.only_in == 'v2-rolling').sum())} only rolling).", ""]
    for why, g in diff.groupby("why"):
        L += [f"**{why}** ({len(g)})", ""]
        L += [f"- {r.country} FY{r.fiscal_year} ({r.only_in}, z={r.robust_z:+.1f}, {pct(r.value)}, "
              f"baseline FY{r.baseline_span})" for r in g.itertuples()]
        L += [""]

    life = incidents[(incidents.method == "v2-rolling") & (incidents.source == "lifecycle")]
    L += ["## 4. Lifecycle incidents (v2)", "",
          "Observations about the data, not IDA status. One per prolonged zero period.", ""]
    L += [f"- **{r.kind}** ({r.severity}) {r.summary}" for r in life.itertuples()]
    L += ["", "## 5. Figures", ""] + [f"- `figures/{f}`" for f in figs] + [""]
    (OUT_DIR / "COMPARISON.md").write_text("\n".join(L), encoding="utf-8")
    print(f"figures -> {FIG_DIR}\nreport  -> {OUT_DIR / 'COMPARISON.md'}")


if __name__ == "__main__":
    main()
