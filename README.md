# World Bank Data Quality

Data-quality and anomaly-detection work on public World Bank lending data.

The question running through every project here is the same one a financial data pipeline has to answer every month: **is this number unusual, or does it just look unusual?** Fixed rules catch the errors someone already imagined. Everything else needs a model that has learned what normal looks like — and, in a reporting chain that ends at donor governments, that model has to be able to explain itself in a sentence.

> Independent work using publicly available World Bank data. Not affiliated with or endorsed by the World Bank Group.

---

## Projects

| Project | What it does | Status |
|---|---|---|
| [ida-disbursement-spc](ida-disbursement-spc) | Statistical Process Control on IDA country-level gross disbursements. Robust (median/MAD) control charts with a separated baseline and monitoring window, a fixed-rule layer underneath, and a measurement harness: recall on five planted error types, precision from human labels, and a ledger of every method version. | complete (v1.1) |
| [ida-disbursement-adaptive-spc](ida-disbursement-adaptive-spc) | Project 02. Rolling, leakage-free control limits compared against the fixed baseline on identical synthetic errors. Adds gap-aware growth, a chronological sustained-shift rule, minimal zero-period (lifecycle) handling, a recalibration policy for flagged points, a `feed_stops` error type and regression tests. Reuses Project 01's code rather than copying it. | complete |

Each project has its own README, its own `outputs/`, and its own run commands. Project 02 imports Project 01's building blocks (statistics, rules, injectors) through a single bridge module and never writes into Project 01's folders, so Project 01 stays the reproducible v1.1 reference.

---

## Data

Raw data is **not committed**. It is reproducible from the World Bank's [Finances One](https://financesone.worldbank.org/data) data portal, and one of the files is 460 MB — past GitHub's 100 MB limit, and not something a repository should carry when the source is a public API.

Download into `data/` at the repository root:

| File | What it is | Source | Size |
|---|---|---|---|
| `ibrd_and_ida_net_flows_commitments_09-16-2026.csv` | IBRD & IDA net flows and commitments, summarised by country and fiscal year (FY2010–FY2027, 3,445 rows). **Used by Projects 01 and 02.** | [IBRD and IDA Net Flows & Commitments — DS00044](https://financesone.worldbank.org/ibrd-and-ida-net-flows-commitments/DS00044) (Finances One), extracted 2026-09-16 | 374 KB |
| `IDA_historical.csv` | IDA credit-level portfolio snapshots, one per month since April 2011 | [Finances One](https://financesone.worldbank.org/data) | 460 MB |

To reproduce Projects 01 and 02, export the full DS00044 dataset as CSV from the link above and save it into `data/` under the filename shown. A fresh export will carry a later extraction date and may contain more of the current fiscal year, so its numbers will differ slightly from the ones documented here — which were produced from the 2026-09-16 extract.

Two grains, deliberately. The summary file is small enough to reason about by hand — which is why the first project uses only that one. The snapshot file is where the same methods have to survive real volume, and where a **reconciliation** between the two becomes possible: aggregate the credit-level monthly flows by country and fiscal year, and they should land on the summary file's gross disbursement figures. Two independent sources agreeing is a far stronger signal than either one looking plausible alone.

> **On the fiscal year:** the World Bank's runs 1 July – 30 June and is named for the year it *ends*. FY2027 began 1 July 2026. Any extract taken mid-year contains a partial period that looks exactly like a failed data load — see the first project for what that does to a naive control chart.

---

## Layout

```
world-bank-data-quality/
├── data/                        # git-ignored; shared download target
├── ida-disbursement-spc/        # Project 01 - fixed-baseline robust SPC (v1.1 reference)
│   ├── README.md                # the method, the findings, the limitations
│   ├── src/                     # config, spc_core, four numbered steps
│   ├── labels/, experiments/    # human labels, results ledger
│   └── outputs/                 # alerts, figures, FINDINGS.md (committed)
├── ida-disbursement-adaptive-spc/  # Project 02 - rolling limits vs fixed
│   ├── README.md
│   ├── src/                     # v1_bridge, adaptive_config/core, a1..a4 steps
│   ├── tests/                   # unittest regression tests
│   ├── experiments/             # ledger: one row per method x split
│   └── outputs/                 # points, alerts, incidents, COMPARISON.md, figures
└── README.md
```

## Running anything here

```bash
pip install -r ida-disbursement-spc/requirements.txt
cd ida-disbursement-spc
python src/step1_prepare.py && python src/step2_spc.py
python src/review_alerts.py && python src/step3_evaluate.py && python src/step4_report.py
```

Project 02 (PowerShell; exact commands and options in its README):

```powershell
cd ida-disbursement-adaptive-spc
python src/a1_prepare.py; python src/a2_adaptive_spc.py
python src/a3_evaluate.py; python src/a3_evaluate.py --split holdout
python src/a4_report.py
python -m unittest discover -s tests -v
```

Python 3.11+, and nothing beyond pandas, numpy and matplotlib. That constraint is intentional: a detector that a team has to keep alive after its author leaves is worth more than a more accurate one they cannot maintain.

---

## Where this goes

1. ~~**Rolling control limits**~~ — done in Project 02, with the trade-offs it exposed documented there.
2. **Scale to the credit-level snapshots** — same maths, finer grain. Two free rules arrive with it: cumulative disbursement should never *decrease*, and a credit that vanishes between snapshots is a missing-data pattern rather than an amount anomaly.
3. **Reconcile the two datasets** against each other.
4. **A second, multivariate detector** (Isolation Forest) for what a one-variable-at-a-time chart structurally cannot see — keeping SPC as the explainable first layer rather than replacing it.
