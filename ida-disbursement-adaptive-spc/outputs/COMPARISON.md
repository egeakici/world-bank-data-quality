# Fixed vs rolling control limits - comparison

Version `p02-v1`. Monitoring FY2020-FY2026; rolling window 10 eligible years; everything else inherited from Project 01 (3 sigma, median/MAD, min 8 baseline years).

## 1. On the real data

| method | alerts | alerts_high | shift_alerts | recurring_countries | incidents | persistent_incidents | lifecycle_incidents | countries_monitored | observations_monitored | countries_excluded | dormant_observations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.1-reference | 62 | 11 | 7 | 7 | 39 | 4 | 0 | 82 | 560 | 59 | 0 |
| v2-fixed | 53 | 11 | 0 | 6 | 36 | 3 | 17 | 74 | 495 | 67 | 157 |
| v2-rolling | 61 | 16 | 0 | 7 | 42 | 4 | 17 | 84 | 533 | 57 | 157 |
| v2-rolling-naive | 54 | 11 | 0 | 2 | 44 | 0 | 0 | 92 | 586 | 49 | 0 |

- **v1.1-reference** not monitored: only 0 baseline years (<8) 20; zero baseline variation (MAD = 0) 19; only 5 baseline years (<8) 3; only 2 baseline years (<8) 2; only 6 baseline years (<8) 2; only 7 baseline years (<8) 2; only 3 baseline years (<8) 1; only 4 baseline years (<8) 1
- **v2-fixed** not monitored: insufficient_history 28; dormant 22; no_prior_year 8
- **v2-rolling** not monitored: dormant 22; insufficient_history 18; no_prior_year 8
- **v2-rolling-naive** not monitored: zero_mad 17; insufficient_history 15; no_prior_year 8

## 2a. Performance - holdout draws (report these)

**Recall, % of charted injections**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 79.1 | 81.2 | 80.5 | 77.6 |
| units_x1000 | 97.2 | 98.2 | 99.3 | 99.1 |
| drop_to_zero | 87.2 | 89.8 | 94.8 | 92.0 |
| misstate_25pct | 11.9 | 10.5 | 12.7 | 12.3 |
| stale_repeat | 100.0 | 100.0 | 100.0 | 100.0 |
| feed_stops | 85.2 | 87.3 | 89.5 | 86.4 |

**End-to-end recall, % of all injections**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 57.0 | 55.8 | 58.2 | 60.0 |
| units_x1000 | 70.5 | 67.8 | 74.0 | 77.5 |
| drop_to_zero | 62.5 | 60.5 | 68.2 | 69.2 |
| misstate_25pct | 8.2 | 6.8 | 9.0 | 9.2 |
| stale_repeat | 75.8 | 72.2 | 77.0 | 80.8 |
| feed_stops | 58.8 | 56.0 | 62.2 | 64.0 |

**Collateral alerts per trial**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 16.8 | 16.8 | 18.8 | 17.2 |
| units_x1000 | 22.6 | 21.0 | 24.0 | 24.0 |
| drop_to_zero | 18.6 | 18.2 | 21.4 | 21.0 |
| misstate_25pct | 2.2 | 2.2 | 2.2 | 2.0 |
| stale_repeat | 11.8 | 13.2 | 14.5 | 13.2 |
| feed_stops | 4.4 | 0.0 | 0.0 | 0.0 |

**Feed stops lasting 2+ years, final monitored year**

| method | feed stop: chart says in control % | feed stop: still surfaced % |
|---|---|---|
| v1.1-reference | 75.0 | 2.6 |
| v2-fixed | 0.0 | 94.8 |
| v2-rolling | 0.0 | 94.8 |
| v2-rolling-naive | 86.1 | 0.0 |

Code `d2cae27-dirty`, config hash `faae709436b4`.

## 2b. Performance - tuning draws (development only)

**Recall, % of charted injections**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 74.4 | 76.1 | 79.4 | 77.0 |
| units_x1000 | 98.2 | 98.9 | 99.6 | 99.6 |
| drop_to_zero | 84.5 | 88.3 | 91.1 | 88.0 |
| misstate_25pct | 9.9 | 10.4 | 12.4 | 9.8 |
| stale_repeat | 100.0 | 100.0 | 100.0 | 100.0 |
| feed_stops | 86.2 | 87.8 | 92.1 | 88.4 |

**End-to-end recall, % of all injections**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 50.8 | 49.8 | 55.2 | 56.5 |
| units_x1000 | 68.0 | 66.2 | 71.5 | 74.2 |
| drop_to_zero | 61.8 | 60.8 | 66.0 | 66.8 |
| misstate_25pct | 7.0 | 7.0 | 9.0 | 7.2 |
| stale_repeat | 72.2 | 69.0 | 73.5 | 76.8 |
| feed_stops | 60.0 | 58.0 | 65.2 | 67.0 |

**Collateral alerts per trial**

| error_type | v1.1-reference | v2-fixed | v2-rolling | v2-rolling-naive |
|---|---|---|---|---|
| spike_x10 | 15.6 | 15.6 | 19.0 | 16.6 |
| units_x1000 | 20.9 | 20.5 | 25.1 | 23.9 |
| drop_to_zero | 18.8 | 18.5 | 21.5 | 19.6 |
| misstate_25pct | 1.2 | 1.2 | 2.3 | 2.1 |
| stale_repeat | 12.8 | 14.1 | 15.2 | 14.2 |
| feed_stops | 3.1 | 0.0 | 0.0 | 0.0 |

**Feed stops lasting 2+ years, final monitored year**

| method | feed stop: chart says in control % | feed stop: still surfaced % |
|---|---|---|
| v1.1-reference | 75.3 | 2.0 |
| v2-fixed | 0.0 | 93.9 |
| v2-rolling | 0.0 | 93.9 |
| v2-rolling-naive | 85.7 | 0.0 |

Code `d2cae27-dirty`, config hash `faae709436b4`.

## 3. Where the rolling baseline helps and where it hurts

34 alerts differ between v2-fixed and v2-rolling on the real data (13 only fixed, 21 only rolling).

**adaptation: the rolling baseline has absorbed a newer, more volatile regime** (13)

- Cameroon FY2025 (v2-fixed, z=+5.1, +55%, baseline FY2011-2019)
- Cameroon FY2026 (v2-fixed, z=+3.3, +30%, baseline FY2011-2019)
- Cote d'Ivoire FY2026 (v2-fixed, z=-3.1, -40%, baseline FY2011-2019)
- Dominica FY2026 (v2-fixed, z=-3.6, -84%, baseline FY2011-2019)
- India FY2026 (v2-fixed, z=-3.1, -52%, baseline FY2011-2019)
- Kenya FY2021 (v2-fixed, z=-3.7, -24%, baseline FY2011-2019)
- Kenya FY2022 (v2-fixed, z=-3.9, -26%, baseline FY2011-2019)
- Kenya FY2025 (v2-fixed, z=-4.0, -26%, baseline FY2011-2019)
- Kenya FY2026 (v2-fixed, z=+3.9, +71%, baseline FY2011-2019)
- Mali FY2023 (v2-fixed, z=+4.0, +106%, baseline FY2011-2019)
- Nepal FY2026 (v2-fixed, z=-3.2, -59%, baseline FY2011-2019)
- Papua New Guinea FY2023 (v2-fixed, z=-3.1, -71%, baseline FY2011-2019)
- Sri Lanka FY2026 (v2-fixed, z=-3.4, -59%, baseline FY2011-2019)

**coverage: the fixed baseline could not chart this country at all** (7)

- Central Africa FY2026 (v2-rolling, z=-7.6, -95%, baseline FY2014-2025)
- Myanmar FY2022 (v2-rolling, z=-4.5, -79%, baseline FY2014-2021)
- Myanmar FY2023 (v2-rolling, z=-4.9, -81%, baseline FY2014-2021)
- Myanmar FY2026 (v2-rolling, z=+4.0, +450%, baseline FY2014-2022)
- Tuvalu FY2021 (v2-rolling, z=-4.7, -63%, baseline FY2013-2020)
- Tuvalu FY2023 (v2-rolling, z=-4.7, -63%, baseline FY2013-2022)
- Tuvalu FY2024 (v2-rolling, z=+4.4, +543%, baseline FY2013-2022)

**sensitivity: recent calmer years tightened the rolling limits** (14)

- Armenia FY2025 (v2-rolling, z=-4.0, -86%, baseline FY2015-2024)
- Bhutan FY2025 (v2-rolling, z=-3.2, -93%, baseline FY2015-2024)
- Bosnia and Herzegovina FY2021 (v2-rolling, z=-3.6, -75%, baseline FY2011-2020)
- Bosnia and Herzegovina FY2022 (v2-rolling, z=-4.0, -79%, baseline FY2011-2020)
- Congo, Democratic Republic of FY2021 (v2-rolling, z=+4.5, +50%, baseline FY2011-2020)
- Ethiopia FY2021 (v2-rolling, z=-3.3, -43%, baseline FY2011-2020)
- Georgia FY2021 (v2-rolling, z=+3.2, +174%, baseline FY2011-2020)
- Georgia FY2024 (v2-rolling, z=-4.8, -92%, baseline FY2014-2023)
- Ghana FY2024 (v2-rolling, z=+3.2, +102%, baseline FY2014-2023)
- Ghana FY2025 (v2-rolling, z=-3.0, -32%, baseline FY2014-2023)
- Ghana FY2026 (v2-rolling, z=-3.0, -32%, baseline FY2014-2023)
- Grenada FY2024 (v2-rolling, z=+3.5, +816%, baseline FY2014-2023)
- Mozambique FY2025 (v2-rolling, z=-3.9, -35%, baseline FY2015-2024)
- Nicaragua FY2025 (v2-rolling, z=-4.3, -60%, baseline FY2015-2024)

## 4. Lifecycle incidents (v2)

Observations about the data, not IDA status. One per prolonged zero period.

- **zero_period_ongoing** (info) Albania: gross disbursement at or below zero for 5 consecutive years FY2022-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Angola: gross disbursement at or below zero for 4 consecutive years FY2023-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Armenia: gross disbursement at or below zero for 2 consecutive years FY2025-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Azerbaijan: gross disbursement at or below zero for 8 consecutive years FY2019-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Bosnia and Herzegovina: gross disbursement at or below zero for 5 consecutive years FY2022-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Egypt, Arab Republic of: gross disbursement at or below zero for 13 consecutive years FY2014-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Georgia: gross disbursement at or below zero for 2 consecutive years FY2025-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Indonesia: gross disbursement at or below zero for 13 consecutive years FY2014-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Iraq: gross disbursement at or below zero for 10 consecutive years FY2017-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Jordan: gross disbursement at or below zero for 2 consecutive years FY2025-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ended** (info) Lebanon: gross disbursement at or below zero for 2 consecutive years FY2022-FY2023 (positive again in FY2024); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Lebanon: gross disbursement at or below zero for 2 consecutive years FY2025-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Montenegro: gross disbursement at or below zero for 12 consecutive years FY2015-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ended** (info) Myanmar: gross disbursement at or below zero for 3 consecutive years FY2023-FY2025 (positive again in FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Serbia: gross disbursement at or below zero for 12 consecutive years FY2015-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ended** (info) Sudan: gross disbursement at or below zero for 2 consecutive years FY2023-FY2024 (positive again in FY2025); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.
- **zero_period_ongoing** (info) Zimbabwe: gross disbursement at or below zero for 3 consecutive years FY2024-FY2026 (still zero at FY2026); repayments/commitments continue, consistent with lending winding down. The chart does not evaluate dormant years; this is an observation about the data, not an IDA status.

## 5. Figures

- `figures/fig_bangladesh_fixed_vs_rolling.png`
- `figures/fig_kosovo_fixed_vs_rolling.png`
- `figures/fig_afghanistan_fixed_vs_rolling.png`
- `figures/fig_azerbaijan_fixed_vs_rolling.png`
