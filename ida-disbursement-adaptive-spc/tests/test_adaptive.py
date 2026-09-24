"""Regression tests for Project 02.

Standard library only (unittest) - no new dependency for a team to install.
Run from the project folder:

    python -m unittest discover -s tests -v

Real-country tests read Project 02's silver file, so run src/a1_prepare.py once
first. Synthetic tests build their own tiny series and need nothing.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from v1_bridge import v1_config as V1, stale_repeat_mask, v1_build, v1_add_growth   # noqa: E402
from spc_core import run_rule_flags                                                  # noqa: E402 (Project 01)
from adaptive_config import METHODS, SILVER_DIR                                      # noqa: E402
from adaptive_core import (evaluate_country, run_method, series_from_silver, zero_periods,  # noqa: E402
                           CountrySeries, shift_severity, build_incidents, MEASURE, OTHER_FLOWS)

ROLLING, FIXED, NAIVE = METHODS["v2-rolling"], METHODS["v2-fixed"], METHODS["v2-rolling-naive"]
MON = range(V1.MONITOR_START_FY, V1.MONITOR_END_FY + 1)


def load():
    path = SILVER_DIR / "net_flows_silver.csv"
    if not path.exists():
        raise unittest.SkipTest("run src/a1_prepare.py first")
    return series_from_silver(pd.read_csv(path))


def synthetic(levels, country="Testland"):
    """A one-country series frame from {fiscal_year: gross}. Other flows are
    non-zero so lifecycle treats any zero stretch as a wind-down, not a lost feed."""
    df = pd.DataFrame({"country": country, "fiscal_year": list(levels), MEASURE: list(levels.values())})
    for c in OTHER_FLOWS:
        df[c] = 1.0
    return df


def rows(df, cfg, country):
    g = df[df.country == country].sort_values("fiscal_year")
    return pd.DataFrame(evaluate_country(country, g, cfg)).set_index("fiscal_year")


class NoFutureLeakage(unittest.TestCase):

    def test_changing_the_future_does_not_change_the_past(self):
        """Multiply every value from FY2023 on by 7: every verdict for
        FY2020-2022 must be bit-for-bit identical."""
        df = load()
        for country in ["Bangladesh", "Kosovo", "Kenya"]:
            before = rows(df, ROLLING, country)
            future = df.copy()
            future.loc[(future.country == country) & (future.fiscal_year >= 2023), MEASURE] *= 7
            after = rows(future, ROLLING, country)
            cols = ["center", "lcl", "ucl", "value", "robust_z"]
            pd.testing.assert_frame_equal(before.loc[2020:2022, cols], after.loc[2020:2022, cols])
            self.assertListEqual(list(before.loc[2020:2022, "rule"]), list(after.loc[2020:2022, "rule"]))

    def test_year_under_evaluation_never_sets_its_own_limits(self):
        df = load()
        base = rows(df, ROLLING, "Bangladesh")
        moved = df.copy()
        moved.loc[(moved.country == "Bangladesh") & (moved.fiscal_year == 2024), MEASURE] *= 3
        after = rows(moved, ROLLING, "Bangladesh")
        self.assertAlmostEqual(base.loc[2024, "ucl"], after.loc[2024, "ucl"])
        self.assertAlmostEqual(base.loc[2024, "center"], after.loc[2024, "center"])

    def test_rolling_window_ends_before_the_evaluated_year(self):
        df = load()
        for country in ["Bangladesh", "Ghana", "Kosovo"]:
            for t, r in rows(df, ROLLING, country).iterrows():
                self.assertLess(int(r.baseline_span.split("-")[1]), t)
        # A country with no alerts: the window is exactly the calendar window.
        gh = rows(df, ROLLING, "Ghana")
        self.assertEqual(gh.loc[2021, "baseline_span"], "2011-2020")
        self.assertEqual(gh.loc[2023, "baseline_span"], "2013-2022")

    def test_flagged_year_is_held_out_until_confirmed(self):
        """Bangladesh FY2020 (-29%) is flagged. At FY2021 it is unconfirmed and
        held out; FY2021 did not reverse it, so from FY2022 it is readmitted."""
        bd = rows(load(), ROLLING, "Bangladesh")
        self.assertEqual((bd.loc[2021, "baseline_span"], bd.loc[2021, "n_held_out"]), ("2011-2019", 1))
        self.assertEqual((bd.loc[2022, "baseline_span"], bd.loc[2022, "n_held_out"]), ("2012-2021", 0))
        self.assertEqual(bd.loc[2026, "baseline_span"], "2016-2025")

    def test_v1_run_rule_looks_ahead(self):
        """Documents the v1.1 defect this project fixes: Project 01's run rule
        flags Azerbaijan FY2020 only because FY2021-2026 continue the run."""
        g = v1_add_growth(load()[lambda d: d.country == "Azerbaijan"])
        g = g.dropna(subset=["yoy_log_growth"])
        center = 0.07303                                   # Azerbaijan's v1.1 centre line
        full = dict(zip(g.fiscal_year, run_rule_flags(g.yoy_log_growth, center)))
        upto = g[g.fiscal_year <= 2020]
        known_then = dict(zip(upto.fiscal_year, run_rule_flags(upto.yoy_log_growth, center)))
        self.assertTrue(full[2020])
        self.assertFalse(known_then[2020])


class MissingYears(unittest.TestCase):

    def test_gap_is_never_bridged(self):
        levels = {y: 100e6 * 1.1 ** (y - 2010) for y in range(2010, 2027) if y != 2022}
        df = synthetic(levels)
        cs = CountrySeries(df)
        self.assertFalse(cs.has_growth(2023))              # FY2023 vs FY2021 is not a 1-year change
        pts = rows(df, ROLLING, "Testland")
        self.assertNotIn(2022, pts.index)
        self.assertEqual(pts.loc[2023, "status"], "no_prior_year")
        self.assertEqual(pts.loc[2024, "status"], "charted")


class Bangladesh(unittest.TestCase):

    def test_fixed_engine_reproduces_v1_1(self):
        df = load()
        v1, _ = v1_build(v1_add_growth(df[df.country == "Bangladesh"][["country", "fiscal_year", MEASURE]]),
                         "yoy_log_growth", "B_growth", floor_at_zero=False, kind="growth")
        v1 = v1.set_index("fiscal_year")
        v2 = rows(df, FIXED, "Bangladesh")
        for col in ["center", "lcl", "ucl", "value"]:
            np.testing.assert_allclose(v2[col].to_numpy(float), v1.loc[v2.index, col].to_numpy(float), rtol=1e-12)
        self.assertEqual(list(v2.index[v2.rule != ""]), [2020])

    def test_rolling_flags_fy2020_like_v1(self):
        pts = rows(load(), ROLLING, "Bangladesh")
        self.assertEqual(pts.loc[2020, "rule"], "beyond_limits")
        self.assertAlmostEqual(pts.loc[2020, "robust_z"], -4.05, delta=0.05)


class Azerbaijan(unittest.TestCase):

    def test_zero_period_is_one_lifecycle_incident_not_seven_alerts(self):
        df = load()
        az = df[df.country == "Azerbaijan"]
        self.assertEqual(len(run_method(az, "v1.1-reference")["alerts"]), 7)
        for m in ["v2-fixed", "v2-rolling"]:
            res = run_method(az, m)
            self.assertEqual(len(res["alerts"]), 0, m)
            self.assertTrue((res["points"].status == "dormant").all(), m)
            life = res["incidents"][res["incidents"].source == "lifecycle"]
            self.assertEqual(len(life), 1, m)
            self.assertEqual((life.first_fy.iloc[0], life.last_fy.iloc[0]), (2019, 2026))
            self.assertEqual(life.kind.iloc[0], "zero_period_ongoing")

    def test_negative_gross_counts_as_zero_for_lifecycle_only(self):
        df = load()
        az = df[df.country == "Azerbaijan"]
        self.assertLess(az.set_index("fiscal_year").loc[2019, MEASURE], 0)   # original value preserved
        p = zero_periods(az)
        self.assertEqual(p.first_fy.iloc[0], 2019)                            # FY2019 refund starts the period


class Afghanistan(unittest.TestCase):

    def test_temporary_drop_is_caught_and_monitoring_resumes_next_year(self):
        pts = rows(load(), ROLLING, "Afghanistan")
        self.assertEqual(pts.loc[2023, "rule"], "beyond_limits")
        self.assertLess(pts.loc[2023, "robust_z"], 0)
        self.assertEqual(pts.loc[2024, "status"], "charted")                 # reactivation is evaluated
        self.assertEqual(pts.loc[2025, "status"], "charted")                 # no 8-year wait
        self.assertEqual(pts.loc[2025, "n_lifecycle_skipped"], 2)            # FY2023/24 kept out of baseline

    def test_one_year_zero_is_not_a_lifecycle_incident(self):
        res = run_method(load()[lambda d: d.country == "Afghanistan"], "v2-rolling")
        self.assertEqual(int((res["incidents"].source == "lifecycle").sum()), 0)


class FeedStops(unittest.TestCase):

    def setUp(self):
        df = load()
        self.broken = df[df.country == "Bangladesh"].copy()
        self.broken.loc[self.broken.fiscal_year >= 2022, MEASURE] = 0.0

    def test_onset_flagged_then_dormant_and_still_visible(self):
        res = run_method(self.broken, "v2-rolling")
        p = res["points"].set_index("fiscal_year")
        self.assertEqual(p.loc[2022, "rule"], "beyond_limits")
        self.assertTrue((p.loc[2023:2026, "status"] == "dormant").all())
        life = res["incidents"][res["incidents"].source == "lifecycle"]
        self.assertEqual(life.last_fy.iloc[0], 2026)

    def test_naive_rolling_learns_the_failure(self):
        """The ablation: without lifecycle handling the chart evaluates FY2026
        and calls a dead feed in control."""
        p = run_method(self.broken, "v2-rolling-naive")["points"].set_index("fiscal_year")
        self.assertEqual(p.loc[2026, "status"], "charted")
        self.assertEqual(p.loc[2026, "rule"], "")


class SeverityAndIncidents(unittest.TestCase):

    def test_shift_severity_depends_on_distance(self):
        self.assertEqual(shift_severity([0.01] * 8, center=0.0, sigma=0.2), "low")
        self.assertEqual(shift_severity([0.30] * 8, center=0.0, sigma=0.2), "medium")

    def test_no_v2_shift_alert_is_near_the_centre_and_medium(self):
        a = run_method(load(), "v2-rolling")["alerts"]
        shifts = a[a.rule == "sustained_shift"]
        self.assertFalse(((shifts.robust_z.abs() < 0.5) & (shifts.severity == "medium")).any())

    def test_incident_takes_worst_member_severity(self):
        alerts = pd.DataFrame({
            "country": ["X", "X", "Y"], "fiscal_year": [2021, 2022, 2024], "robust_z": [4.0, -3.5, 0.2],
            "value": [1.0, -1.0, 0.05], "severity": ["medium", "high", "low"], "rule": ["beyond_limits"] * 2
            + ["sustained_shift"], "explanation": ["a", "b", "c"]})
        _, inc = build_incidents(alerts, "rolling", pd.DataFrame(), lifecycle_on=False)
        inc = inc.set_index("country")
        self.assertEqual(inc.loc["X", "kind"], "spike_and_reversal")
        self.assertEqual(inc.loc["X", "severity"], "high")
        self.assertEqual(inc.loc["Y", "severity"], "low")                   # v1.1 would have said medium


class RuleR6(unittest.TestCase):

    def test_consecutive_zero_years_are_not_stale(self):
        df = synthetic({2019: 5e6, 2020: 0.0, 2021: 0.0, 2022: 0.0, 2023: 7e6, 2024: 7e6})
        m = stale_repeat_mask(df, MEASURE, ["country"])
        self.assertEqual(list(df.fiscal_year[m]), [2024])                   # only the positive repeat


if __name__ == "__main__":
    unittest.main()
