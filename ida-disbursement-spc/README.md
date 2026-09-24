# SPC on IDA net flows — a first anomaly-detection project

A deliberately small project: **one financier (IDA), one measure (gross disbursement), one method (Statistical Process Control)**, on the 374 KB country × fiscal-year extract. The 460 MB credit-level snapshot file is *not* used here — the point is to understand the method on data you can hold in your head first.

**Data:** `data/ibrd_and_ida_net_flows_commitments_09-16-2026.csv` at the repository root — 3,445 rows, 174 countries, FY2010–FY2027, extracted 2026-09-16.

---

## Run it

```bash
pip install -r requirements.txt
python src/step1_prepare.py    # bronze -> silver, plus the fixed-rule layer
python src/step2_spc.py        # the control charts
python src/review_alerts.py    # refresh the labelling sheet (labels/alert_labels.csv)
python src/step3_evaluate.py   # how good is it? recall, precision, alert load -> ledger
python src/step4_report.py     # figures + outputs/FINDINGS.md
```

Generated results land in `outputs/` and are rebuilt on every run. Two things live outside it on purpose, because no script can rebuild them: `labels/` (human judgement) and `experiments/` (the history of the method). Nothing writes back to the shared `data/` folder — the raw file stays raw.

---

## What SPC actually is

One question, asked of every new observation:

> Given how this series behaved in the past, is this point inside the range that ordinary variation produces, or far enough outside that something changed?

You need three numbers: a **centre line** (where the process normally sits), and two **control limits** at centre ± 3σ. A point outside is *out of control* — which in SPC does **not** mean "wrong", it means "this did not come from the same process as the history, go look".

We use an **individuals chart** (one observation per period, no subgroup to average) because a country reports one figure per fiscal year.

### Why median and MAD instead of mean and standard deviation

```python
center = median(x)
sigma  = 1.4826 * median(|x - center|)      # MAD, rescaled
```

A single crisis-year disbursement inflates *both* the mean and the standard deviation. Wider limits then hide every later problem — **the outlier protects itself**. Median and MAD barely move, so the chart keeps its sensitivity. The 1.4826 makes MAD estimate the same quantity as σ for normal data, which is what keeps "3 sigma" meaning the usual thing. → [spc_core.py:20](src/spc_core.py#L20)

### Two windows, never one

| Phase | Years | Role |
|---|---|---|
| I — baseline | FY2010–FY2019 | limits are **learned** here |
| II — monitoring | FY2020–FY2026 | limits are **applied** here |

The limits that judge FY2023 never saw FY2023. That is the same discipline as avoiding data leakage in ML, and it is the difference between a number you can quote and a number that flatters itself. → [config.py:35](src/config.py#L35)

---

## The four things this dataset taught, in order

### 1. FY2027 is not a collapse — it is a partial period

IDA disbursement by fiscal year: FY2025 $33.2bn, FY2026 $29.8bn, **FY2027 $1.5bn**.

The World Bank fiscal year runs 1 July – 30 June and is named for the year it *ends*, so FY2027 began 1 July 2026 and was ~2.5 months old when this file was extracted. Include it and every country in the portfolio looks catastrophic. It is handled once, centrally, in `step1_prepare.py`, and never thought about again.

![partial year](outputs/figures/fig3_partial_fiscal_year.png)

**The general lesson:** a period that is still filling looks identical to a period that failed to load. Only the calendar can tell them apart, so the calendar has to be in the code.

### 2. The rule layer runs first — and keeps running

| rule | rows flagged | what it means |
|---|---|---|
| R1 net identity (`Net = Gross − Repayments`) | 0 | holds to the dollar across all 3,445 rows |
| R2 negative gross disbursement | 42 | **not errors** — refunds and prior-year corrections |
| R3 negative repayments | 0 | — |
| R4 duplicate primary key | 0 | no fan-out from an upstream join |
| R5 country changed region | 318 | **a real structural change** |
| R6 gross identical to prior year | 1 | IBRD Chile FY2020, a round $10,000,000 — plausibly genuine |

R5 is the interesting one. In FY2026 the Bank reorganised its regions: Afghanistan and Pakistan left `SOUTH ASIA`, eleven MENA countries left `MIDDLE EAST AND NORTH AFRICA`, and all thirteen now sit in `MID EAST,NORTH AFRICA,AFG,PAK`. Nothing about the money changed. But **every regional total before FY2026 is on a different basis than every regional total after**, and an unsuspecting year-over-year regional comparison would show a South Asia "collapse" that is pure taxonomy.

This is reference-data drift, and note what found it: not the model. A five-line rule. Which is exactly why SPC sits *on top of* the rule layer and never replaces it — rules catch what you already know can break, cheaply and explainably.

R2 is the counterpart lesson: 42 rows violate "amounts are non-negative" and all 42 are probably fine. **"Violates a simple rule" is not the same as "incorrect."** The rule reports; a human decides.

R6 was added *because the measurement harness found a blind spot* (see below): a stale feed that re-delivers last year's figure produces 0% growth, which the chart can never flag. The rule is deliberately **gross-only**. Gross disbursement follows project invoices and repeats to the cent once in 3,445 rows; repayments follow fixed instalment schedules and repeat exactly **136 times**, legitimately. The same rule on the wrong field would be an alert generator — a rule is only as valid as the behaviour of the field it is applied to. → [step1_prepare.py:49](src/step1_prepare.py#L49)

### 3. The textbook chart fails here — and the failure is the lesson

Build the obvious chart: is this year's dollar amount inside its historical range?

![portfolio level chart](outputs/figures/fig1_portfolio_level_trend.png)

The IDA portfolio grew from ~$11bn (FY2010) to ~$33bn (FY2025). The baseline learned a centre of $12.8bn and an upper limit of $19.3bn, so **all 7 monitored years breach it**, and at country level the chart flags **449 of 582 country-years — 77%**.

A detector that fires on 77% of observations has not found 449 problems. It has found one: *SPC assumes a process that is stable around a fixed centre, and this process is trending.* Growth is not a defect.

The fix is the oldest trick in time-series: **difference the series first.** Chart the year-over-year change instead of the level. A steadily growing country has a roughly stable *growth rate*, so the differenced series is approximately stable, and a flag now means "this change was unusual **for this country**" rather than "this country grew".

```python
g_t = ln( (x_t + c) / (x_{t-1} + c) )     # c = 5% of the country's typical year, floor $100k
```

The stabiliser `c` stops a near-zero prior year producing an infinite growth rate, and scaling it to the country's own size keeps a $2m country and a $2bn country on the same footing. → [step2_spc.py:41](src/step2_spc.py#L41)

Result: **62 alerts instead of 449** — 11% of points, about 9 per fiscal year.

![Bangladesh](outputs/figures/fig2_bangladesh_level_vs_growth.png)

Bangladesh is the cleanest illustration. The level chart (left) has limits of $0m–$2,506m — so wide they are unfalsifiable, and it flags **nothing, ever**. The growth chart (right) flags exactly **one** point: FY2020, −29%, the first COVID year. One alert, seven years, and an analyst knows instantly what it is about.

### 4. Alert fatigue is a modelling constraint, not an afterthought

62 alerts / 7 years is workable. 449 is not — and a queue nobody reads has an effective recall of zero, no matter what the offline metric says. So the output is **triaged rather than dumped**:

| severity | rule | action |
|---|---|---|
| high (\|z\| ≥ 5) | 11 alerts | investigate |
| medium (3 ≤ \|z\| < 5) | 51 alerts | batch review |
| below limits | — | logged, not surfaced |

And every alert carries a sentence, generated from the chart itself:

> **Bangladesh FY2020:** year-over-year change of −29% is below the expected range −19% to +66% (learned from FY2010-2019, where a typical year was +16%); that is 4.1 robust sigmas from the typical year (limits sit at 3), so 1.1 beyond the −19% limit.

An earlier version said "4.1 robust sigmas *past the limit*". The z-score is measured from the centre line, not from the limit, so that wording overstated every alert by 3σ. The flags were right; the sentence was wrong — and in a system whose whole selling point is the sentence, that is a real defect.

That sentence is the whole argument for choosing SPC over an autoencoder as a *first* system. "The model said so" does not survive contact with a financial controller. → [spc_core.py:116](src/spc_core.py#L116)

Two rules fire, not one:
- **beyond_limits** (55 alerts) — a spike.
- **sustained_shift** (7 alerts) — 8+ consecutive years on one side of the centre line without ever breaking a limit. A process can move by one sigma and never trip a 3-sigma test; every point looks fine and the *level* has changed. This is the difference between "a bad month" and "this country's disbursement profile is now different."

### 5. Alerts are not incidents

One disruption rarely produces one alert on a year-over-year chart. A single bad year flags twice — the jump, then the jump back. A country whose level moved for good flags every year after. So alerts in consecutive years of one country are grouped into one **incident**, the unit an analyst actually opens (`outputs/spc_incidents.csv`):

| incident kind | pattern | count | what to do |
|---|---|---|---|
| `single` | one flagged year | 25 | investigate that year |
| `spike_and_reversal` | 2 years, opposite directions | 7 | check the **first** year's level — the second is the return to normal |
| `two_year_move` | 2 years, same direction | 3 | a two-step change |
| `persistent` | 3+ years in a row | 4 | the baseline no longer describes this country — re-fit, don't investigate n times |

**62 alerts → 39 incidents, 9 → 6 a year.** Detection is untouched: every alert is still in `spc_alerts.csv`, with an `incident_id` pointing at its incident. Only the unit of work changed. → [spc_core.py:141](src/spc_core.py#L141)

The grouping immediately explained the worst repeat offender. Azerbaijan's 7 alerts are one `persistent` incident reading *+0%, +0%, +0%…*: **IDA stopped disbursing to Azerbaijan after FY2018** (repayments continue). Growth from $0 to $0 is 0%, just under its baseline centre of +7.6%, so the 8-in-a-row rule fires every year. That is a lifecycle event, not a data problem — and a series that has gone permanently to zero needs its own handling, which belongs with rolling limits.

---

## Measuring a detector when nothing is labelled

No column in this dataset says "this row is wrong". Unsupervised, though, does not mean unevaluated. Three numbers are tracked, because any one of them alone can be gamed — a detector that flags everything has perfect recall, one that flags nothing never raises a false alarm:

| number | question | where it comes from |
|---|---|---|
| **recall** | of the errors we plant, how many are caught? | synthetic injection, `step3_evaluate.py` |
| **precision** | of the real alerts, how many were worth a look? | human labels, `labels/alert_labels.csv` |
| **alert load** | how many alerts per year must someone read? | the clean run |

### Recall — five planted error types

We make our own labels by breaking data we believe is clean, one error per country, 10 trials each:

| error type | what it simulates | recall (tuning) | recall (hold-out) |
|---|---|---|---|
| `units_x1000` | thousands loaded as dollars | 98.2% | 97.2% |
| `drop_to_zero` | the feed delivered nothing | 84.5% | 87.2% |
| `spike_x10` | an extra zero typed | 74.4% | 79.1% |
| `misstate_25pct` | value ×0.75 or ×1.25 | 9.9% | 11.9% |
| `stale_repeat` | last year's figure re-delivered | **0.0%** → 100% with R6 | **0.0%** → 100% with R6 |

The bottom two rows are the point of having a catalogue. A 25% misstatement sits inside the ordinary year-to-year variation of most countries, so a 3σ chart structurally cannot see it. A stale repeat produces a growth of exactly 0% — which is *closer* to normal than most real years, so the chart will never flag it. That is not a tuning problem; it is a blind spot, and its fix belongs in the rule layer (`value == last year's value`), not in the chart — which is what R6 now does. A catalogue with only the easy errors would have hidden both.

Recall is measured on the **system** (growth chart + R6), not the chart alone: an analyst does not care which layer caught the stale feed, only that something did. The other four rows did not move by a decimal between v1 and v1.1, which is the check that the fixes changed only what they were meant to change.

**Tuning vs hold-out.** The injections are drawn from two seeds. Anything that gets tuned — the sigma multiplier, the windows — is tuned against the *tuning* draws only. The *hold-out* draws are run once per finished version and those are the numbers reported. Tune and score on the same draws and you measure how well you fitted your own test. The gap between the two columns above (74% vs 79% on the same method) is pure sampling noise, which is also a useful calibration: differences smaller than that between two versions are not evidence of anything.

Three further rules the harness enforces, each learned the hard way:

- **Injections must be sparse.** The first version of this project injected 200 errors at once — 35% of all monitored cells — and measured 54% recall on a 10× spike. The detector looked weak; the *experiment* was broken. Two injections in consecutive years of the same country partly cancel in a year-over-year chart. Real pipeline errors are rare events, so the test is one per country. → [step3_evaluate.py](src/step3_evaluate.py)
- **Never inject into the baseline.** If the corruption lands in Phase I, the limits *learn* it, widen, and then fail to flag it.
- **Report the spread, not just the mean.** 74% with a range of 58–91% across draws is a very different claim from 74% measured once.

Recall here is a **lower bound** on the obvious errors and an honest zero on the subtle ones.

### Precision — human labels

Only a person can say whether "Chad FY2021, −50%" deserved an analyst's morning. `review_alerts.py` writes every growth-chart alert to `labels/alert_labels.csv`, sorted by |z|, with an empty `label` column to fill with:

| label | meaning |
|---|---|
| `investigate` | worth sending to an analyst — could be a data problem |
| `explained` | real, but explained by a known event (COVID, conflict, a new IDA cycle) |
| `noise` | ordinary variation the chart should not have flagged |

From those, `step3_evaluate.py` reports **strict precision** (`investigate` / labelled), **lenient precision** (`investigate` + `explained` / labelled), and **precision@10** (the 10 highest-|z| alerts, the ones an analyst reads first — only reported once all 10 are labelled, since a precision computed on whichever alerts happened to get labelled is biased).

The labels file is designed to survive the detector changing: labels are keyed on (country, fiscal year) rather than the method version, re-running the script merges instead of overwriting, and a label on an alert that no longer fires is kept with `currently_alerting = False`. No script is allowed to throw away human judgement.

> **Status:** 0 of 62 alerts labelled. Precision is blank in the ledger until they are.

### The ledger

Every `step3_evaluate.py` run upserts one row into `experiments/ledger.csv`, keyed by (method version, split): the parameters it ran with, alert load, precision, and recall per error type. Re-running a version replaces its row rather than appending a duplicate. When the method changes, bump `METHOD_VERSION` in `config.py` (or pass `--version`), and "v2 is better than v1" becomes a claim with a row of evidence under it.

```bash
python src/step3_evaluate.py                                   # tuning draws
python src/step3_evaluate.py --split holdout                   # once per finished version
python src/step3_evaluate.py --version v2-rolling-baseline --note "10-year rolling window"
```

---

## What this system cannot do

Being explicit about this is part of the deliverable, not a disclaimer.

- **59 of the 141 country series are never charted.** 22 have no baseline at all (the country entered IDA after FY2019), 19 have a baseline of all-identical values so MAD = 0, the rest are too short. `fit_chart` **refuses to fit** rather than produce confident nonsense from three points. "Not enough evidence" is a legitimate output and it is what keeps the queue credible. → [spc_not_charted.csv](outputs/spc_not_charted.csv)
- **Robust limits can be too tight.** Chad's baseline was unusually quiet, giving limits of −6% to +38%; four of its seven monitored years flag. MAD protects against outliers inflating limits, but a placid baseline produces limits too narrow for a genuinely volatile borrower.
- **Persistent incidents are grouped, not solved.** Azerbaijan, Kosovo, Cameroon and DR Congo are now one incident each instead of 3–7 alerts, but they will keep firing every year until the limits are re-fitted on a window that includes the new behaviour. Grouping fixes the count; rolling limits fix the cause.
- **One variable at a time.** SPC cannot see "this amount is normal, and this credit age is normal, but this amount *for a credit of this age* is not". That is the gap Isolation Forest fills, and the reason to reach for it second, not first.
- **Baseline points can sit outside their own limits** (see Cameroon FY2013 in the figure). A strict Phase I procedure excludes such points and refits. Not done here — worth knowing that the textbook has a further step.

## Where this goes next

1. **Re-fit limits on a rolling window** rather than a frozen FY2010–2019 baseline, so a legitimate regime change stops generating alerts forever.
2. **Scale to the credit-level snapshots.** Same maths, different grain: 185 monthly snapshots, cumulative disbursement per credit. Two free rules arrive with it — cumulative disbursed should never *decrease*, and a credit that vanishes between snapshots is a missing-data pattern, not an amount anomaly.
3. **Reconciliation.** Aggregate credit-level monthly flows by country and fiscal year and check them against the gross disbursement figures in *this* file. Two independent sources agreeing is a stronger signal than either one looking plausible alone.
4. **Add a second, multivariate detector** (Isolation Forest) for the interactions SPC cannot see, keeping SPC as the explainable first layer.

---

## Files

```
src/config.py           every threshold and window, in one place
src/spc_core.py         the maths: robust stats, limits, run rule, explanations
src/step1_prepare.py    bronze -> silver, rule layer, coverage report
src/step2_spc.py        chart A (level) and chart B (growth), alerts
src/review_alerts.py    builds/merges the human labelling sheet
src/step3_evaluate.py   recall (5 error types), precision, alert load -> ledger
src/step4_report.py     figures + FINDINGS.md

labels/alert_labels.csv       human labels for the alert queue (committed, hand-edited)
experiments/ledger.csv        one row per method version x split (committed)

outputs/FINDINGS.md     generated summary
outputs/spc_alerts.csv  the alert queue, ranked by |robust z|, each with its incident_id
outputs/spc_incidents.csv     alerts grouped into incidents - the analyst's unit of work
outputs/spc_points.csv  every monitored point with its limits (audit trail)
outputs/spc_not_charted.csv   what was skipped, and why
outputs/evaluation.csv  recall per error type, latest run
outputs/series_coverage.csv   gaps in each country's year series
```
