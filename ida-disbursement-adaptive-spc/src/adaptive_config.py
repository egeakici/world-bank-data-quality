"""Every knob Project 02 adds on top of Project 01.

Anything the two projects share - sigma multiplier, MAD scaling, minimum
baseline points, run length, severity threshold, monitoring window, seeds,
the five original error types - is read from Project 01's config through
v1_bridge, so the comparison is on identical statistical ground. Only what is
new lives here.
"""
from pathlib import Path

from v1_bridge import v1_config as V1

ROOT = Path(__file__).resolve().parents[1]           # ida-disbursement-adaptive-spc
SILVER_DIR = ROOT / "data" / "silver"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
LEDGER_CSV = ROOT / "experiments" / "ledger.csv"
V1_LEDGER_CSV = V1.LEDGER_CSV                         # read-only: the published v1.1 numbers

# ---------------------------------------------------------------- growth transform
# Same stabiliser as Project 01 (hard-coded there in step2_spc.to_growth):
# c = max(C_FLOOR, C_FRACTION * median level of the baseline years).
C_FRACTION = 0.05
C_FLOOR = 1e5

# ---------------------------------------------------------------- rolling baseline
# The baseline for year t is the most recent WINDOW_YEARS *eligible* growth
# observations before t. With no exclusions that is exactly the calendar window
# FY(t-10)..FY(t-1): FY2021 is judged on FY2011-2020, FY2026 on FY2016-2025.
# When lifecycle or held-out years are skipped, the look-back extends further
# into the past (never into the future) to keep the sample size - which is what
# lets a reactivated country be charted again without waiting 8 new years.
WINDOW_YEARS = 10

# ---------------------------------------------------------------- lifecycle
# "Zero" for lifecycle purposes = gross disbursement <= 0. Negative values
# (refunds, R2) count as zero here ONLY; the silver data and R2 flags keep the
# original numbers. A zero year that follows another zero year is DORMANT: the
# chart does not evaluate it (growth $0 -> $0 = 0% means nothing), and the
# zero period is reported once as a lifecycle incident instead.
LIFECYCLE_MIN_ZERO_YEARS = 2      # zero periods this long become lifecycle incidents

# ---------------------------------------------------------------- recalibration policy
# What happens to a flagged observation when later baselines are built.
#   "confirm"     - a beyond-limits point is HELD OUT while unconfirmed:
#                   * if the next year jumps back the opposite way and is also
#                     flagged, the pair is a transient (spike and reversal) and
#                     both stay out of every future baseline;
#                   * if the next year does not reverse it, the new level is
#                     confirmed and the point is readmitted from then on;
#                   * a point from the year just before t is still unconfirmed
#                     at t, so it is held out.
#   "include_all" - textbook rolling: every observation enters the baseline.
# Sustained-shift points are never held out - they are close to the centre by
# construction and are the evidence the limits need to catch up.
RECALIBRATION_POLICIES = ("confirm", "include_all")

# ---------------------------------------------------------------- methods compared
# v1.1-reference runs Project 01's own code, unchanged. The v2 methods run the
# chronological engine in adaptive_core. v2-fixed isolates the effect of the
# engine fixes (gap-aware growth, chronological run rule, lifecycle, severity);
# v2-rolling vs v2-fixed isolates the effect of the rolling window itself;
# v2-rolling-naive is the ablation that shows what the lifecycle handling and
# recalibration policy are protecting against.
METHODS = {
    "v1.1-reference":   {"engine": "v1"},
    "v2-fixed":         {"engine": "v2", "baseline": "fixed",   "policy": "confirm",     "lifecycle": True},
    "v2-rolling":       {"engine": "v2", "baseline": "rolling", "policy": "confirm",     "lifecycle": True},
    "v2-rolling-naive": {"engine": "v2", "baseline": "rolling", "policy": "include_all", "lifecycle": False},
}
PRIMARY_METHOD = "v2-rolling"
METHOD_VERSION = "p02-v1"          # bump when the engine changes; ledger key is (version, method, split)

# ---------------------------------------------------------------- severity
# v1.1 labelled every sustained-shift alert "medium", so Azerbaijan's points at
# z = -0.07 came out medium. A shift is only material if the run sits well away
# from the centre: medium if the median |z| of the run is >= SHIFT_MEDIUM_Z,
# otherwise low (statistically notable, practically small).
SHIFT_MEDIUM_Z = 1.0
SEVERITY_RANK = {"": 0, "info": 0, "low": 1, "medium": 2, "high": 3}

# ---------------------------------------------------------------- evaluation
# The five Project 01 error types, in their original order (which fixes their
# random draws), plus one new type appended at the end so it cannot disturb
# the draws of the other five.
ERROR_CATALOG = dict(V1.ERROR_CATALOG)
ERROR_CATALOG["feed_stops"] = ("the feed stops delivering a country - value set to 0 from a "
                               "random monitored year to the end of the window")

# ---------------------------------------------------------------- report
REPORT_COUNTRIES = ["Bangladesh", "Kosovo", "Afghanistan", "Azerbaijan"]
