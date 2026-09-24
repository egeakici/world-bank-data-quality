"""The actual SPC maths. Roughly 60 lines of it.

An SPC chart answers one question: given how this series has behaved in the
past, is today's point inside the range we would expect from ordinary
variation, or is it far enough outside that something changed?

Two vocabulary items:
  centre line (CL) - where the process normally sits
  control limits   - CL +/- 3 * sigma, the boundary of "ordinary variation"

We use an INDIVIDUALS chart (often written I-MR) because we get exactly one
observation per country per fiscal year. There is no subgroup to average.
"""
import numpy as np
import pandas as pd

from config import MAD_TO_SIGMA, SIGMA_MULTIPLIER, RUN_LENGTH_RULE, INCIDENT_PERSISTENT_RUN


def robust_center_and_sigma(values):
    """Median and MAD-based sigma instead of mean and standard deviation.

    Why: one crisis-year disbursement of $4bn in a country that normally gets
    $300m would drag the mean up AND inflate the standard deviation. Wider
    limits then hide every future problem. The extreme point would have
    protected itself. Median and MAD barely move, so the chart keeps its
    sensitivity.

    MAD = median(|x - median(x)|). Multiplying by 1.4826 rescales it so that
    for normally distributed data it estimates the same thing as the standard
    deviation - which is what makes "3 sigma" mean the usual thing.
    """
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size == 0:
        return np.nan, np.nan
    center = float(np.median(v))
    mad = float(np.median(np.abs(v - center)))
    return center, mad * MAD_TO_SIGMA


def control_limits(center, sigma, floor_at_zero=True):
    """CL +/- 3 sigma. Gross disbursement cannot be negative in normal
    operation, so we clip the lower limit at zero rather than telling an
    analyst that -$40m would have been acceptable."""
    lcl = center - SIGMA_MULTIPLIER * sigma
    ucl = center + SIGMA_MULTIPLIER * sigma
    if floor_at_zero:
        lcl = max(lcl, 0.0)
    return lcl, ucl


def robust_z(value, center, sigma):
    """How many robust sigmas away from the centre line. This single number
    is what makes the alert explainable and rankable."""
    if not np.isfinite(sigma) or sigma <= 0:
        return np.nan
    return (value - center) / sigma


def run_rule_flags(values, center, run_length=RUN_LENGTH_RULE):
    """Nelson rule 2: `run_length` consecutive points on the same side of the
    centre line.

    Why bother when we already test 3-sigma? Because a process can shift by
    one sigma and never once break a limit. Every point looks fine; the level
    has simply moved. A sustained one-sided run catches that. In this domain
    it is the difference between "a spike" and "this country's disbursement
    profile has permanently changed".
    """
    v = np.asarray(values, dtype=float)
    side = np.sign(v - center)
    flags = np.zeros(v.size, dtype=bool)
    streak = 0
    prev = 0.0
    for i, s in enumerate(side):
        if s != 0 and s == prev:
            streak += 1
        else:
            streak = 1
        prev = s
        if streak >= run_length:
            flags[i - run_length + 1: i + 1] = True
    return flags


def fit_chart(baseline_values, min_points):
    """Phase I: learn limits. Returns a dict plus a reason when we refuse.

    Refusing to fit is a feature. A chart built on 3 points, or on a country
    whose baseline is all zeros, produces confident nonsense. "Not enough
    evidence" is a legitimate output and it is what keeps the alert queue
    credible.
    """
    v = np.asarray(baseline_values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size < min_points:
        return {"fitted": False, "reason": f"only {v.size} baseline years (<{min_points})"}
    center, sigma = robust_center_and_sigma(v)
    if not np.isfinite(sigma) or sigma <= 0:
        return {"fitted": False, "reason": "zero baseline variation (MAD = 0)"}
    lcl, ucl = control_limits(center, sigma)
    return {"fitted": True, "reason": "", "center": center, "sigma": sigma,
            "lcl": lcl, "ucl": ucl, "n_baseline": int(v.size)}


def _fmt(value, kind):
    """A control chart is only as useful as its units. The level chart speaks
    dollars; the growth chart speaks percent change per year. Printing a log
    ratio as '$1' is how a technically correct alert becomes unreadable."""
    if kind == "usd":
        return f"${value:,.0f}"
    return f"{(np.exp(value) - 1) * 100:+.0f}%"


def explain(entity, fy, value, chart, z, rule, kind="usd"):
    """One sentence an analyst can act on without reading any code.

    'The model flagged it' is not an acceptable explanation in a regulated
    financial environment. This is the whole reason SPC was chosen over an
    autoencoder for a first system.
    """
    f = lambda v: _fmt(v, kind)
    noun = "disbursement" if kind == "usd" else "year-over-year change"
    if rule == "beyond_limits":
        direction = "above" if value > chart["ucl"] else "below"
        bound = chart["ucl"] if value > chart["ucl"] else chart["lcl"]
        return (f"{entity} FY{fy}: {noun} of {f(value)} is {direction} the expected range "
                f"{f(chart['lcl'])} to {f(chart['ucl'])} "
                f"(learned from FY{chart['baseline_span']}, where a typical year was {f(chart['center'])}); "
                f"that is {abs(z):.1f} robust sigmas from the typical year (limits sit at "
                f"{SIGMA_MULTIPLIER:.0f}), so {abs(z) - SIGMA_MULTIPLIER:.1f} beyond the {f(bound)} limit.")
    if rule == "sustained_shift":
        side = "above" if value > chart["center"] else "below"
        return (f"{entity} FY{fy}: no single year breaks a control limit, but this is part of a run of "
                f"{RUN_LENGTH_RULE}+ consecutive years {side} the historical typical {noun} of "
                f"{f(chart['center'])} - the level has shifted rather than spiked.")
    return f"{entity} FY{fy}: flagged by {rule}."


def group_incidents(alerts, baseline_span):
    """Collapse growth-chart alerts into incidents - what an analyst opens.

    One disruption rarely produces one alert on a year-over-year chart:
      * a single bad year t flags at t (the jump) AND at t+1 (the jump back);
      * a country whose level moved for good flags every year after the move.
    Counting those as 2 or 7 separate problems inflates the queue with
    duplicates, which is alert fatigue by another route. So alerts in
    consecutive fiscal years of one country become one incident:

      single              one flagged year, nothing either side
      spike_and_reversal  2 years, opposite directions -> one unusual year (t);
                          t+1 is the return to normal
      two_year_move       2 years, same direction -> a two-step change
      persistent          INCIDENT_PERSISTENT_RUN+ years in a row -> the
                          baseline no longer describes this country; the fix
                          is re-fitting the limits, not n investigations

    Detection is untouched - every alert is still in spc_alerts.csv with an
    incident_id pointing here. Only the unit of work changes.
    """
    pct = lambda v: f"{(np.exp(v) - 1) * 100:+.0f}%"
    a = alerts.sort_values(["country", "fiscal_year"]).copy()
    a["incident_id"] = ""
    incidents = []
    for country, g in a.groupby("country"):
        years = g.fiscal_year.tolist()
        runs, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                runs.append(cur)
                cur = [y]
        runs.append(cur)

        for run in runs:
            part = g[g.fiscal_year.isin(run)]
            z, v = part.robust_z.to_numpy(), part.value.to_numpy()
            first, last = run[0], run[-1]
            iid = f"{country} FY{first}" + (f"-{last}" if last != first else "")
            if len(run) >= INCIDENT_PERSISTENT_RUN:
                kind = "persistent"
                summary = (f"{country}: flagged in {len(run)} consecutive years FY{first}-FY{last} "
                           f"({', '.join(pct(x) for x in v)}). The FY{baseline_span} baseline no longer "
                           f"describes this country - treat as one regime change and re-fit its limits, "
                           f"not as {len(run)} separate investigations.")
            elif len(run) == 2 and np.sign(z[0]) != np.sign(z[1]):
                kind = "spike_and_reversal"
                summary = (f"{country}: FY{first} moved {pct(v[0])} and FY{last} moved {pct(v[1])} straight "
                           f"back - most likely ONE unusual year (FY{first}); check that year's level first.")
            elif len(run) == 2:
                kind = "two_year_move"
                summary = (f"{country}: two unusual years in the same direction, FY{first} {pct(v[0])} "
                           f"and FY{last} {pct(v[1])} - a two-step change rather than a one-off.")
            else:
                kind = "single"
                summary = part.explanation.iloc[0]
            a.loc[part.index, "incident_id"] = iid
            incidents.append({
                "incident_id": iid, "country": country, "first_fy": first, "last_fy": last,
                "n_alerts": len(run), "kind": kind,
                "max_abs_z": round(float(np.abs(z).max()), 1),
                "severity": "high" if (part.severity == "high").any() else "medium",
                "summary": summary,
            })
    inc = pd.DataFrame(incidents)
    if len(inc):
        inc = inc.sort_values("max_abs_z", ascending=False).reset_index(drop=True)
    return a, inc


def tidy_chart_frame(rows):
    return pd.DataFrame(rows)
