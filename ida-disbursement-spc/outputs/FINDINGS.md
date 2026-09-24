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
| R6_stale_gross | 1 | 0.029 | Gross disbursement identical to the cent to the prior fiscal year - stale feed? |

## 2. Control charts

- **Level chart (A)** flags 449 of 582 monitored country-years, and the portfolio total breaches its upper limit in 7 of 7 monitored years. That is a trend, not an incident - the chart is measuring growth.
- **Growth chart (B)** flags 62 points, 11 of them high severity - about 9 alerts per fiscal year, which a team can actually work through.
- Those 62 alerts group into **39 incidents** (about 6 per year): 25 single, 7 spike_and_reversal, 4 persistent, 3 two_year_move.

### Multi-year incidents

- **spike_and_reversal** (high) Chad: FY2020 moved +40% and FY2021 moved -50% straight back - most likely ONE unusual year (FY2020); check that year's level first.
- **persistent** (high) Cameroon: flagged in 3 consecutive years FY2020-FY2022 (+178%, -46%, +42%). The FY2010-2019 baseline no longer describes this country - treat as one regime change and re-fit its limits, not as 3 separate investigations.
- **two_year_move** (high) Chad: two unusual years in the same direction, FY2023 +77% and FY2024 +99% - a two-step change rather than a one-off.
- **persistent** (high) Kosovo: flagged in 4 consecutive years FY2021-FY2024 (+654%, -67%, +182%, -69%). The FY2010-2019 baseline no longer describes this country - treat as one regime change and re-fit its limits, not as 4 separate investigations.
- **spike_and_reversal** (high) Uzbekistan: FY2020 moved -75% and FY2021 moved +181% straight back - most likely ONE unusual year (FY2020); check that year's level first.
- **two_year_move** (high) Cameroon: two unusual years in the same direction, FY2025 +55% and FY2026 +30% - a two-step change rather than a one-off.
- **spike_and_reversal** (medium) Haiti: FY2023 moved -45% and FY2024 moved +116% straight back - most likely ONE unusual year (FY2023); check that year's level first.
- **persistent** (medium) Congo, Democratic Republic of: flagged in 3 consecutive years FY2023-FY2025 (+102%, -49%, +80%). The FY2010-2019 baseline no longer describes this country - treat as one regime change and re-fit its limits, not as 3 separate investigations.
- **spike_and_reversal** (medium) Afghanistan: FY2023 moved -96% and FY2024 moved +1327% straight back - most likely ONE unusual year (FY2023); check that year's level first.
- **spike_and_reversal** (medium) Papua New Guinea: FY2022 moved +632% and FY2023 moved -71% straight back - most likely ONE unusual year (FY2022); check that year's level first.
- **spike_and_reversal** (medium) Niger: FY2024 moved -80% and FY2025 moved +303% straight back - most likely ONE unusual year (FY2024); check that year's level first.
- **spike_and_reversal** (medium) Kenya: FY2025 moved -26% and FY2026 moved +71% straight back - most likely ONE unusual year (FY2025); check that year's level first.
- **two_year_move** (medium) Kenya: two unusual years in the same direction, FY2021 -24% and FY2022 -26% - a two-step change rather than a one-off.
- **persistent** (medium) Azerbaijan: flagged in 7 consecutive years FY2020-FY2026 (+0%, +0%, +0%, +0%, +0%, +0%, +0%). The FY2010-2019 baseline no longer describes this country - treat as one regime change and re-fit its limits, not as 7 separate investigations.

### Top 10 growth-chart alerts

- **high** (z=-13.0) Chad FY2021: year-over-year change of -50% is below the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 13.0 robust sigmas from the typical year (limits sit at 3), so 10.0 beyond the -6% limit.
- **high** (z=+11.5) Cameroon FY2020: year-over-year change of +178% is above the expected range -27% to +27% (learned from FY2010-2019, where a typical year was -4%); that is 11.5 robust sigmas from the typical year (limits sit at 3), so 8.5 beyond the +27% limit.
- **high** (z=+8.7) Chad FY2024: year-over-year change of +99% is above the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 8.7 robust sigmas from the typical year (limits sit at 3), so 5.7 beyond the +38% limit.
- **high** (z=+8.2) Kosovo FY2021: year-over-year change of +654% is above the expected range -60% to +92% (learned from FY2010-2019, where a typical year was -12%); that is 8.2 robust sigmas from the typical year (limits sit at 3), so 5.2 beyond the +92% limit.
- **high** (z=-7.5) Uzbekistan FY2020: year-over-year change of -75% is below the expected range -36% to +128% (learned from FY2010-2019, where a typical year was +21%); that is 7.5 robust sigmas from the typical year (limits sit at 3), so 4.5 beyond the -36% limit.
- **high** (z=+7.2) Kosovo FY2026: year-over-year change of +480% is above the expected range -60% to +92% (learned from FY2010-2019, where a typical year was -12%); that is 7.2 robust sigmas from the typical year (limits sit at 3), so 4.2 beyond the +92% limit.
- **high** (z=+6.8) Chad FY2023: year-over-year change of +77% is above the expected range -6% to +38% (learned from FY2010-2019, where a typical year was +14%); that is 6.8 robust sigmas from the typical year (limits sit at 3), so 3.8 beyond the +38% limit.
- **high** (z=-6.4) Nicaragua FY2026: year-over-year change of -91% is below the expected range -68% to +160% (learned from FY2010-2019, where a typical year was -9%); that is 6.4 robust sigmas from the typical year (limits sit at 3), so 3.4 beyond the -68% limit.
- **high** (z=-6.4) Cameroon FY2021: year-over-year change of -46% is below the expected range -27% to +27% (learned from FY2010-2019, where a typical year was -4%); that is 6.4 robust sigmas from the typical year (limits sit at 3), so 3.4 beyond the -27% limit.
- **high** (z=-6.1) Central Asia FY2024: year-over-year change of -97% is below the expected range -82% to +432% (learned from FY2010-2019, where a typical year was -1%); that is 6.1 robust sigmas from the typical year (limits sit at 3), so 3.1 beyond the -82% limit.

## 3. Evaluation (synthetic injection, latest run)

| error_type | trials | injected_per_trial | detected_per_trial | recall_pct_mean | recall_pct_min | recall_pct_max | collateral_per_trial |
|---|---|---|---|---|---|---|---|
| spike_x10 | 10 | 28.9 | 22.8 | 79.1 | 65.5 | 92.9 | 16.8 |
| units_x1000 | 10 | 29.0 | 28.2 | 97.2 | 92.9 | 100.0 | 22.6 |
| drop_to_zero | 10 | 28.7 | 25.0 | 87.2 | 80.0 | 96.4 | 18.6 |
| misstate_25pct | 10 | 28.1 | 3.3 | 11.9 | 3.1 | 33.3 | 2.2 |
| stale_repeat | 10 | 30.3 | 30.3 | 100.0 | 100.0 | 100.0 | 11.8 |

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
| v1.1-quick-fixes | tuning | 8.9 | 0 |  |  | 74.4 | 98.2 | 84.5 | 9.9 | 100.0 |
| v1.1-quick-fixes | holdout | 8.9 | 0 |  |  | 79.1 | 97.2 | 87.2 | 11.9 | 100.0 |

## 5. Figures

- `figures/fig1_portfolio_level_trend.png` - why a level chart fails on this data
- `figures/fig2_cameroon_level_vs_growth.png` - level vs growth, volatile borrower
- `figures/fig2_bangladesh_level_vs_growth.png` - level vs growth, large steady borrower
- `figures/fig3_partial_fiscal_year.png` - the partial-period trap
