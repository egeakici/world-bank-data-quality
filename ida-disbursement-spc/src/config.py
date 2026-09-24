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
SYNTHETIC_SPIKE = 10.0        # "someone typed an extra zero"
RANDOM_SEED = 7
