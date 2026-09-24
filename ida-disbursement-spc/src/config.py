"""Single place for every knob in this project.

Entry-level rule: no magic numbers scattered through the code. If a reviewer
asks "why 3 sigma?" or "why does the baseline stop in 2019?", the answer has
to live somewhere findable. That is this file.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # ida-disbursement-spc
WORKSPACE = ROOT.parent                             # repository root
# Raw data lives once at the workspace root and is shared by every project here.
# It is git-ignored: it is reproducible from the World Bank Finances API, so it
# is an input to the repo, not part of it.
RAW_CSV = WORKSPACE / "data" / "ibrd_and_ida_net_flows_commitments_09-16-2026.csv"

SILVER_DIR = ROOT / "data" / "silver"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"

# ---------------------------------------------------------------- scope
# We keep this project deliberately small: IDA only, one measure.
FINANCIER = "IDA"
MEASURE = "gross_disbursement_usd"

# The data was extracted 2026-09-16. The World Bank fiscal year runs
# 1 July - 30 June and is named after the year it ENDS in, so FY2027 =
# Jul 2026 - Jun 2027 and was only ~2.5 months old at extraction time.
# Including it would make almost every country look catastrophically low.
# This is the classic partial-period false positive.
EXTRACT_DATE = "2026-09-16"
INCOMPLETE_FY = 2027
LAST_COMPLETE_FY = 2026

# ---------------------------------------------------------------- SPC windows
# Phase I  = "learn what normal looks like"  (limits are computed here)
# Phase II = "monitor"                       (limits are only applied here)
# Splitting them is what keeps the model honest: the control limits used to
# judge FY2023 never saw FY2023. Same idea as avoiding data leakage in ML.
BASELINE_START_FY = 2010
BASELINE_END_FY = 2019
MONITOR_START_FY = 2020
MONITOR_END_FY = LAST_COMPLETE_FY

# ---------------------------------------------------------------- SPC parameters
SIGMA_MULTIPLIER = 3.0        # classic Shewhart 3-sigma limits
MAD_TO_SIGMA = 1.4826         # makes MAD comparable to a normal std dev
MIN_BASELINE_POINTS = 8       # below this, MAD is too unstable to trust
RUN_LENGTH_RULE = 8           # 8 points on one side of the centre = shift

# ---------------------------------------------------------------- alerting
# Alert fatigue is an operational failure mode, not a modelling detail.
HIGH_SEVERITY_Z = 5.0
TOP_N_ALERTS = 25

# ---------------------------------------------------------------- evaluation
# Injections must be SPARSE. An early version of this project corrupted 35% of
# the monitored cells at once and measured 54% recall on a 10x spike - the
# detector looked weak, but the experiment was broken: two injections in
# consecutive years of the same country cancel out in a year-over-year chart.
# Real pipeline errors are rare events, so the test must be rare events too.
SYNTHETIC_PER_TRIAL = 40      # at most one injected error per country per trial
SYNTHETIC_TRIALS = 10         # repeat, then average - one draw is not a measurement

# The error catalogue. Each entry is a failure a real pipeline can produce.
# The obvious ones (spike, drop) are easy; the subtle ones are there to show
# where SPC is blind, not to make the numbers look good.
ERROR_CATALOG = {
    "spike_x10":      "an extra zero typed - value x10",
    "units_x1000":    "thousands loaded as dollars - value x1000",
    "drop_to_zero":   "the feed delivered nothing - value set to 0",
    "misstate_25pct": "a plausible misstatement - value x0.75 or x1.25",
    "stale_repeat":   "last year's figure re-delivered - value = prior year",
}
MISSTATEMENT = 0.25

# Two seeds, two jobs. Tune anything (sigma multiplier, windows, ...) against
# the TUNING draws only. Run the HOLDOUT draws once per finished version and
# report those. If you tune on the same injections you score on, the recall
# number measures how well you fitted your own test, not the detector.
TUNING_SEED = 7
HOLDOUT_SEED = 2026

# ---------------------------------------------------------------- measurement
# The name of the method as it stands. Change it whenever the detector changes
# (e.g. "v2-rolling-baseline") so the ledger keeps one row per version.
METHOD_VERSION = "v1-frozen-baseline"

# Human labels and the ledger live OUTSIDE outputs/ because outputs/ is
# rebuilt on every run, and neither of these can be rebuilt: labels are an
# afternoon of human judgement, the ledger is the history of the method.
LABELS_CSV = ROOT / "labels" / "alert_labels.csv"
LEDGER_CSV = ROOT / "experiments" / "ledger.csv"

# What a reviewer writes in the `label` column of the labels file.
LABELS = {
    "investigate": "worth sending to an analyst - could be a data problem",
    "explained":   "real, but explained by a known event (COVID, conflict, new cycle)",
    "noise":       "nothing there - ordinary variation the chart should not have flagged",
}
PRECISION_AT_N = 10
