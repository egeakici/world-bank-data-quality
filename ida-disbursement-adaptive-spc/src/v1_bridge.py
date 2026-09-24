"""The one place Project 02 reaches into Project 01.

Project 01 (ida-disbursement-spc) is the v1.1 reference implementation and is
never modified from here. Its pure building blocks - robust statistics, chart
fitting, explanations, incident grouping, the rule layer, the error injectors,
the v1.1 chart itself - are imported, not copied. If a formula is fixed in
Project 01, Project 02 inherits the fix; if it were copied, the two would drift
apart silently.

Why a bridge module instead of scattered imports: Project 01's modules import
each other by bare name (`from config import ...`). Putting its src/ folder on
sys.path once, here, makes those imports resolve to Project 01's own config.
Every Project 02 module has a distinct name (adaptive_*, a1_..a4_) so nothing
in Project 02 can shadow a Project 01 module.
"""
import sys
from pathlib import Path

V1_ROOT = Path(__file__).resolve().parents[2] / "ida-disbursement-spc"
V1_SRC = V1_ROOT / "src"
if not V1_SRC.exists():
    raise SystemExit(f"Project 01 not found at {V1_ROOT} - Project 02 reuses its code.")
if str(V1_SRC) not in sys.path:
    sys.path.append(str(V1_SRC))

import config as v1_config                                          # noqa: E402
from spc_core import (fit_chart, robust_z, explain,                 # noqa: E402,F401
                      group_incidents)
from step1_prepare import (load_bronze, run_rules,                  # noqa: E402,F401
                           add_period_completeness, coverage_report,
                           stale_repeat_mask)
from step2_spc import build as v1_build, add_growth as v1_add_growth  # noqa: E402,F401
from step3_evaluate import inject as v1_inject                      # noqa: E402,F401
from step3_evaluate import alerts_for as v1_alerts_for              # noqa: E402,F401
