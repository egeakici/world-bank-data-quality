"""The chronological SPC engine behind the v2 methods.

Project 01 fits one chart per country and then applies it to every monitored
year. That only works when the baseline is frozen. Here, every monitored year
t gets its own chart, built from information that existed before t:

    for each country, for t = FY2020 .. FY2026, in order:
        1. choose the baseline years     (fixed window, or the most recent
                                          eligible years before t)
        2. derive the growth series      (gap-aware, stabiliser from those years)
        3. fit the chart                 (Project 01's fit_chart - may refuse)
        4. only now look at year t       (beyond limits? end of an 8-point run?)
        5. remember t's verdict          (the recalibration policy of t+1 needs it)

The statistics themselves - median/MAD sigma, 3-sigma limits, robust z, the
explanation sentence, incident grouping - are Project 01's functions,
imported through v1_bridge. What is new is the order of operations, and the
three things the order makes possible: rolling windows, a sustained-shift rule
that cannot see the future, and a recalibration policy for flagged points.
"""
import numpy as np
import pandas as pd

from v1_bridge import v1_config as V1, fit_chart, robust_z, explain, group_incidents, v1_build, v1_add_growth
from adaptive_config import (C_FRACTION, C_FLOOR, WINDOW_YEARS, LIFECYCLE_MIN_ZERO_YEARS,
                             SHIFT_MEDIUM_Z, SEVERITY_RANK, METHODS)

MEASURE = V1.MEASURE
MONITOR_YEARS = list(range(V1.MONITOR_START_FY, V1.MONITOR_END_FY + 1))
OTHER_FLOWS = ["repayments_usd", "ida_grant_commitments_usd", "ida_nonconcessional_commitments_usd",
               "ida_concessional_commitments_usd", "ida_other_commitments_usd"]


# ---------------------------------------------------------------- data
def series_from_silver(silver):
    """IDA, complete fiscal years, one row per country-year - the same rows and
    order as Project 01's load_series, plus the other flows lifecycle needs."""
    df = silver[(silver.financier == V1.FINANCIER) & silver.fy_is_complete]
    cols = ["country", "fiscal_year", MEASURE] + OTHER_FLOWS
    return df[cols].sort_values(["country", "fiscal_year"]).reset_index(drop=True)


class CountrySeries:
    """One country's levels, indexed by fiscal year, with the gap and zero
    facts the engine keeps asking about."""

    def __init__(self, g):
        self.years = [int(y) for y in g.fiscal_year]
        raw = g[MEASURE].to_numpy(dtype=float)
        self.raw = dict(zip(self.years, raw))
        # Growth uses clipped levels, exactly as Project 01 does (refunds are a
        # different phenomenon, reported by R2). Lifecycle "zero" = raw <= 0.
        self.x = {y: max(v, 0.0) for y, v in self.raw.items()}
        self.zero = {y: v <= 0 for y, v in self.raw.items()}

    def has_growth(self, y):
        """A year-over-year change needs BOTH adjacent fiscal years. A missing
        FY is never bridged: FY2023 vs FY2021 is a two-year change, and
        charting it as one year would double its apparent volatility."""
        return y in self.x and (y - 1) in self.x

    def touches_zero(self, y):
        """The change at y starts or ends at zero: an onset, a dormant year or a
        reactivation - lifecycle, not ordinary variation."""
        return self.zero[y] or self.zero[y - 1]

    def growth(self, y, c):
        return float(np.log((self.x[y] + c) / (self.x[y - 1] + c)))


# ---------------------------------------------------------------- recalibration
def held_out(y, t, flags, policy):
    """Is the flagged observation at y kept out of the baseline used at t?

    flags maps year -> sign (+1/-1) of every beyond-limits alert raised so far.
    Only years < t can be in it, so this can never look ahead.
    """
    if policy == "include_all" or y not in flags:
        return False
    s = flags[y]
    reversed_next = (y + 1) < t and flags.get(y + 1) == -s
    reverses_prev = flags.get(y - 1) == -s
    if reversed_next or reverses_prev:
        return True                 # transient spike-and-reversal: out for good
    if y == t - 1:
        return True                 # not yet confirmed by a following year
    return False                    # confirmed new level: readmitted


def select_baseline(cs, t, cfg, flags):
    """The years whose growth values form the baseline at t, plus what was skipped."""
    lifecycle, policy = cfg["lifecycle"], cfg["policy"]
    skipped = {"lifecycle": 0, "held_out": 0}

    def eligible(y):
        if not cs.has_growth(y):
            return False
        if lifecycle and cs.touches_zero(y):
            skipped["lifecycle"] += 1
            return False
        if held_out(y, t, flags, policy):
            skipped["held_out"] += 1
            return False
        return True

    if cfg["baseline"] == "fixed":
        chosen = [y for y in range(V1.BASELINE_START_FY, V1.BASELINE_END_FY + 1) if eligible(y)]
    else:
        # Most recent WINDOW_YEARS eligible years strictly before t. Skipped
        # years extend the look-back into the PAST, never past t.
        chosen = []
        for y in range(t - 1, min(cs.years), -1):
            if eligible(y):
                chosen.append(y)
                if len(chosen) == WINDOW_YEARS:
                    break
        chosen.sort()
    return chosen, skipped


def stabiliser(cs, chosen):
    """c = 5% of the typical level over the baseline years (floor $100k) -
    Project 01's formula, computed from the baseline only, so it is as
    leakage-free as the limits it feeds."""
    lv = [cs.x[y] for y in set(chosen) | {y - 1 for y in chosen}]
    return max(C_FLOOR, C_FRACTION * float(np.median(lv)))


def shift_severity(run_values, center, sigma):
    """Severity of a sustained shift = how far the run sits from the centre,
    not merely that it exists. v1.1 called every shift "medium", which put
    Azerbaijan's points at z = -0.07 in the same bucket as a real level change."""
    run_z = float(np.median(np.abs(np.asarray(run_values) - center)) / sigma)
    return "medium" if run_z >= SHIFT_MEDIUM_Z else "low"


# ---------------------------------------------------------------- one country
def evaluate_country(country, g, cfg):
    cs = CountrySeries(g)
    flags, rows = {}, []
    run = V1.RUN_LENGTH_RULE

    for t in MONITOR_YEARS:
        if t not in cs.x:
            continue                                   # no row at all: coverage report's job
        chosen, skipped = select_baseline(cs, t, cfg, flags)
        row = {"country": country, "fiscal_year": t, "level": cs.raw[t], "status": "",
               "value": np.nan, "center": np.nan, "lcl": np.nan, "ucl": np.nan, "sigma": np.nan,
               "robust_z": np.nan, "n_baseline": len(chosen), "n_held_out": skipped["held_out"],
               "n_lifecycle_skipped": skipped["lifecycle"],
               "baseline_span": f"{chosen[0]}-{chosen[-1]}" if chosen else "",
               "rule": "", "severity": "", "explanation": ""}

        if (t - 1) not in cs.x:
            row["status"] = "no_prior_year"
        elif cfg["lifecycle"] and cs.zero[t] and cs.zero[t - 1]:
            row["status"] = "dormant"
        elif not chosen:
            row["status"] = "insufficient_history: no eligible baseline years"
        else:
            c = stabiliser(cs, chosen)
            chart = fit_chart([cs.growth(y, c) for y in chosen], V1.MIN_BASELINE_POINTS)
            if not chart["fitted"]:
                kind = "zero_mad" if "MAD" in chart["reason"] else "insufficient_history"
                row["status"] = f"{kind}: {chart['reason']}"
            else:
                chart["lcl"] = chart["center"] - V1.SIGMA_MULTIPLIER * chart["sigma"]
                chart["baseline_span"] = row["baseline_span"]
                v = cs.growth(t, c)
                z = robust_z(v, chart["center"], chart["sigma"])
                row.update(status="charted", value=v, center=chart["center"], lcl=chart["lcl"],
                           ucl=chart["ucl"], sigma=chart["sigma"], robust_z=z)

                beyond = v > chart["ucl"] or v < chart["lcl"]
                if beyond:
                    row["rule"] = "beyond_limits"
                    row["severity"] = "high" if abs(z) >= V1.HIGH_SEVERITY_Z else "medium"
                    flags[t] = int(np.sign(v - chart["center"]))
                else:
                    # Chronological run rule: the run must END at t and consist
                    # of t and the run-1 years before it - nothing after t.
                    span = range(t - run + 1, t + 1)
                    ok = all(cs.has_growth(y) and not (cfg["lifecycle"] and cs.touches_zero(y))
                             for y in span)
                    if ok:
                        vals = np.array([cs.growth(y, c) for y in span])
                        sides = np.sign(vals - chart["center"])
                        if sides[0] != 0 and (sides == sides[0]).all():
                            row["rule"] = "sustained_shift"
                            row["severity"] = shift_severity(vals, chart["center"], chart["sigma"])
                if row["rule"]:
                    text = explain(country, t, v, chart, z, row["rule"], "growth")
                    if skipped["held_out"] or skipped["lifecycle"]:
                        text += (f" Baseline: {len(chosen)} years, {skipped['held_out']} flagged year(s) "
                                 f"held out, {skipped['lifecycle']} zero-period year(s) skipped.")
                    row["explanation"] = text
        rows.append(row)
    return rows


# ---------------------------------------------------------------- lifecycle
def zero_periods(df):
    """Every run of consecutive fiscal years with gross disbursement <= 0.

    Method-independent: this is an observation about the data, not an IDA
    status. A zero period does not prove a country left IDA, and a country
    that left IDA can still disburse old credits.
    """
    rows = []
    for country, g in df.groupby("country"):
        g = g.sort_values("fiscal_year")
        years = g.fiscal_year.to_numpy()
        zero = (g[MEASURE] <= 0).to_numpy()
        others = (g[OTHER_FLOWS].abs().sum(axis=1) == 0).to_numpy()
        pos = dict(zip(years, ~zero))
        first_positive = years[~zero].min() if (~zero).any() else None
        i = 0
        while i < len(years):
            if not zero[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(years) and zero[j + 1] and years[j + 1] == years[j] + 1:
                j += 1
            first, last = int(years[i]), int(years[j])
            rows.append({
                "country": country, "first_fy": first, "last_fy": last, "n_years": j - i + 1,
                # Any activity BEFORE the period, not only in the adjacent year:
                # a gap year or an earlier zero stretch must not hide a real stop.
                "has_prior_activity": first_positive is not None and first_positive < first,
                "reactivated_fy": last + 1 if pos.get(last + 1, False) else np.nan,
                "ongoing": last == int(years.max()),
                "other_flows_zero": bool(others[i:j + 1].all()),
            })
            i = j + 1
    return pd.DataFrame(rows, columns=["country", "first_fy", "last_fy", "n_years", "has_prior_activity",
                                       "reactivated_fy", "ongoing", "other_flows_zero"])


def lifecycle_incidents(periods):
    """Prolonged zero periods that follow real activity and reach into the
    monitoring window become ONE incident each - visible for as long as they
    last, instead of one sustained-shift alert per year (Azerbaijan in v1.1)
    or nothing at all (a chart that has quietly learned the zeros)."""
    p = periods[(periods.n_years >= LIFECYCLE_MIN_ZERO_YEARS) & periods.has_prior_activity
                & (periods.last_fy >= V1.MONITOR_START_FY)]
    out = []
    for r in p.itertuples():
        if r.ongoing:
            state = f"still zero at FY{r.last_fy}"
        elif pd.notna(r.reactivated_fy):
            state = f"positive again in FY{int(r.reactivated_fy)}"
        else:
            state = f"followed by a missing FY{r.last_fy + 1} row"
        other = ("repayments and commitments are ALSO zero - the whole country may be missing from the "
                 "feed; verify" if r.other_flows_zero else
                 "repayments/commitments continue, consistent with lending winding down")
        out.append({
            "source": "lifecycle", "incident_id": f"{r.country} FY{r.first_fy}-{r.last_fy} zero",
            "country": r.country, "first_fy": r.first_fy, "last_fy": r.last_fy, "n_alerts": 0,
            "kind": "zero_period_ongoing" if r.ongoing else "zero_period_ended",
            "max_abs_z": np.nan, "severity": "medium" if r.other_flows_zero else "info",
            "summary": (f"{r.country}: gross disbursement at or below zero for {r.n_years} consecutive years "
                        f"FY{r.first_fy}-FY{r.last_fy} ({state}); {other}. The chart does not evaluate "
                        f"dormant years; this is an observation about the data, not an IDA status."),
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------- incidents
def build_incidents(alerts, cfg_baseline, periods, lifecycle_on):
    """Project 01's group_incidents for the statistical alerts, then severity
    recomputed as the worst member (v1.1 only knew high/medium), plus the
    lifecycle incidents as a separate source."""
    cols = ["source", "incident_id", "country", "first_fy", "last_fy", "n_alerts", "kind",
            "max_abs_z", "severity", "summary"]
    parts = []
    if len(alerts):
        span = (f"{V1.BASELINE_START_FY}-{V1.BASELINE_END_FY}" if cfg_baseline == "fixed" else "ROLLING")
        tagged, inc = group_incidents(alerts, span)
        worst = (tagged.assign(r=tagged.severity.map(SEVERITY_RANK)).groupby("incident_id").r.max())
        inv = {v: k for k, v in SEVERITY_RANK.items() if k != "info"}
        inc["severity"] = inc.incident_id.map(worst).map(inv)
        inc["summary"] = inc.summary.str.replace("The FYROLLING baseline", "The rolling baseline", regex=False)
        inc["source"] = "statistical"
        parts.append(inc)
        alerts = alerts.assign(incident_id=tagged.incident_id.reindex(alerts.index))
    if lifecycle_on and len(periods):
        parts.append(lifecycle_incidents(periods))
    inc = pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) \
        else pd.DataFrame(columns=cols)
    return alerts, inc[cols]


# ---------------------------------------------------------------- one method
def run_method(df, method):
    """Run one method end to end on a series frame (clean or deliberately
    broken). Returns points (every monitored country-year, with a status),
    alerts, incidents and the zero periods."""
    cfg = METHODS[method]
    periods = zero_periods(df)

    if cfg["engine"] == "v1":
        pts, skipped = v1_build(v1_add_growth(df[["country", "fiscal_year", MEASURE]]),
                                "yoy_log_growth", "B_growth", floor_at_zero=False, kind="growth")
        pts = pts.drop(columns=["chart"]).assign(status="charted")
        # Countries v1.1 refused, as rows, so coverage can be compared like for like.
        present = set(zip(df.country, df.fiscal_year))
        refused = [{"country": r.country, "fiscal_year": t, "status": r.reason}
                   for r in skipped.itertuples() for t in MONITOR_YEARS if (r.country, t) in present]
        pts = pd.concat([pts, pd.DataFrame(refused)], ignore_index=True)
        pts["rule"] = pts.rule.fillna("")
        cfg_baseline = "fixed"
    else:
        rows = []
        for country, g in df.groupby("country", sort=True):
            rows += evaluate_country(country, g.sort_values("fiscal_year"), cfg)
        pts = pd.DataFrame(rows)
        cfg_baseline = cfg["baseline"]

    pts.insert(0, "method", method)
    alerts = pts[pts.rule != ""].copy()
    alerts, incidents = build_incidents(alerts, cfg_baseline, periods, cfg.get("lifecycle", False))
    incidents.insert(0, "method", method)
    return {"points": pts, "alerts": alerts, "incidents": incidents, "periods": periods}


# ---------------------------------------------------------------- summaries
def coverage(points, all_countries):
    """Who was actually monitored, and why the rest were not."""
    charted = points[points.status == "charted"]
    mon = set(charted.country)
    excluded = sorted(set(all_countries) - mon)
    reasons = (points[points.country.isin(excluded)].groupby("country").status
               .agg(lambda s: s.str.split(":").str[0].value_counts().index[0]))
    return {"countries_monitored": len(mon), "observations_monitored": len(charted),
            "countries_excluded": len(excluded),
            "excluded_reasons": reasons.value_counts().to_dict(),
            "dormant_observations": int((points.status == "dormant").sum())}


def alarm_profile(alerts, incidents):
    stat = incidents[incidents.source == "statistical"] if len(incidents) else incidents
    years_per_country = alerts.groupby("country").fiscal_year.nunique() if len(alerts) else pd.Series(dtype=int)
    return {"alerts": len(alerts),
            "alerts_high": int((alerts.severity == "high").sum()),
            "shift_alerts": int((alerts.rule == "sustained_shift").sum()),
            "recurring_countries": int((years_per_country >= 3).sum()),
            "incidents": len(stat),
            "persistent_incidents": int((stat.kind == "persistent").sum()) if len(stat) else 0,
            "lifecycle_incidents": int((incidents.source == "lifecycle").sum()) if len(incidents) else 0}
