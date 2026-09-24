# Findings

Source: `IDA` rows of the IBRD/IDA net flows & commitments extract (FY2010-FY2027).
Baseline FY2010-FY2019, monitored FY2020-FY2026, FY2027 excluded as an incomplete period.

## 1. Rule layer

| rule | n_rows_flagged | pct_of_rows | note |
|---|---|---|---|
| R1_net_identity | 0 | 0.0 | Net != Gross - Repayments by more than $1 (rounding tolerance) |
| R2_negative_gross | 42 | 1.219 | Gross disbursement below zero - usually a refund/correction, verify |
| R3_negative_repayments | 0 | 0.0 | Repayments below zero |
| R4_duplicate_key | 0 | 0.0 | More than one row per (financier, fiscal_year, country) |
| R5_region_reassigned | 318 | 9.231 | Country appears under more than one region across years |

## 2. Control charts

- **Level chart (A)** flags 449 of 582 monitored country-years, and the portfolio total breaches its upper limit in 7 of 7 monitored years. That is a trend, not an incident - the chart is measuring growth.
- **Growth chart (B)** flags 62 points, 11 of them high severity - about 9 alerts per fiscal year, which a team can actually work through.

### Top 10 growth-chart alerts

- **high** (z=-13.0) Chad FY2021: year-over-year change of -50% is below the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 13.0 robust sigmas past the -6% limit.
- **high** (z=+11.5) Cameroon FY2020: year-over-year change of +178% is above the expected range -27% to +27% (learned from FY2010-2019, where a typical year was -4%); that is 11.5 robust sigmas past the +27% limit.
- **high** (z=+8.7) Chad FY2024: year-over-year change of +99% is above the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 8.7 robust sigmas past the +38% limit.
- **high** (z=+8.2) Kosovo FY2021: year-over-year change of +654% is above the expected range -60% to +92% (learned from FY2010-2019, where a typical year was -12%); that is 8.2 robust sigmas past the +92% limit.
- **high** (z=-7.5) Uzbekistan FY2020: year-over-year change of -75% is below the expected range -36% to +128% (learned from FY2010-2019, where a typical year was +21%); that is 7.5 robust sigmas past the -36% limit.
- **high** (z=+7.2) Kosovo FY2026: year-over-year change of +480% is above the expected range -60% to +92% (learned from FY2010-2019, where a typical year was -12%); that is 7.2 robust sigmas past the +92% limit.
- **high** (z=+6.8) Chad FY2023: year-over-year change of +77% is above the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 6.8 robust sigmas past the +38% limit.
- **high** (z=-6.4) Nicaragua FY2026: year-over-year change of -91% is below the expected range -68% to +160% (learned from FY2010-2019, where a typical year was -9%); that is 6.4 robust sigmas past the -68% limit.
- **high** (z=-6.4) Cameroon FY2021: year-over-year change of -46% is below the expected range -27% to +27% (learned from FY2010-2019, where a typical year was -4%); that is 6.4 robust sigmas past the -27% limit.
- **high** (z=-6.1) Central Asia FY2024: year-over-year change of -97% is below the expected range -82% to +432% (learned from FY2010-2019, where a typical year was -1%); that is 6.1 robust sigmas past the -82% limit.

## 3. Evaluation (synthetic injection, latest run)

| error_type | trials | injected_per_trial | detected_per_trial | recall_pct_mean | recall_pct_min | recall_pct_max | collateral_per_trial |
|---|---|---|---|---|---|---|---|
| spike_x10 | 10 | 27.4 | 20.3 | 74.4 | 57.7 | 91.3 | 15.6 |
| units_x1000 | 10 | 27.7 | 27.2 | 98.2 | 93.3 | 100.0 | 20.9 |
| drop_to_zero | 10 | 29.2 | 24.7 | 84.5 | 76.7 | 93.5 | 18.8 |
| misstate_25pct | 10 | 28.3 | 2.8 | 9.9 | 0.0 | 23.1 | 1.2 |
| stale_repeat | 10 | 28.9 | 0.0 | 0.0 | 0.0 | 0.0 | 1.7 |

Error types:

- `spike_x10` - an extra zero typed - value x10
- `units_x1000` - thousands loaded as dollars - value x1000
- `drop_to_zero` - the feed delivered nothing - value set to 0
- `misstate_25pct` - a plausible misstatement - value x0.75 or x1.25
- `stale_repeat` - last year's figure re-delivered - value = prior year

## 4. Measurement ledger

One row per method version and split (`experiments/ledger.csv`). Blank precision means the alerts are not labelled yet.

| version | split | alerts_per_year | alerts_labelled | precision_strict | precision_at_10 | recall_spike_x10 | recall_units_x1000 | recall_drop_to_zero | recall_misstate_25pct | recall_stale_repeat |
|---|---|---|---|---|---|---|---|---|---|---|
| v1-frozen-baseline | holdout | 8.9 | 0 |  |  | 79.1 | 97.2 | 87.2 | 11.9 | 0.0 |
| v1-frozen-baseline | tuning | 8.9 | 0 |  |  | 74.4 | 98.2 | 84.5 | 9.9 | 0.0 |

## 5. Figures

- `figures/fig1_portfolio_level_trend.png` - why a level chart fails on this data
- `figures/fig2_cameroon_level_vs_growth.png` - level vs growth, volatile borrower
- `figures/fig2_bangladesh_level_vs_growth.png` - level vs growth, large steady borrower
- `figures/fig3_partial_fiscal_year.png` - the partial-period trap
