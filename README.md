# World Bank Data Quality

Data-quality and anomaly-detection work on public World Bank lending data.

The question running through every project here is the same one a financial data pipeline has to answer every month: **is this number unusual, or does it just look unusual?** Fixed rules catch the errors someone already imagined. Everything else needs a model that has learned what normal looks like — and, in a reporting chain that ends at donor governments, that model has to be able to explain itself in a sentence.

> Independent work using publicly available World Bank data. Not affiliated with or endorsed by the World Bank Group.

---

## Projects

| Project | What it does | Status |
|---|---|---|
| [ida-disbursement-spc](ida-disbursement-spc) | Statistical Process Control on IDA country-level gross disbursements. Robust (median/MAD) control charts with a separated baseline and monitoring window, a fixed-rule layer underneath, and recall measured by synthetic error injection. | complete |

Each project is self-contained: its own README, its own `outputs/`, runnable in four commands.

---

## Data

Raw data is **not committed**. It is reproducible from [finances.worldbank.org](https://financesone.worldbank.org/data), and one of the files is 460 MB — past GitHub's 100 MB limit, and not something a repository should carry when the source is a public API.

Download into `data/` at the repository root:

| File | What it is | Size |
|---|---|---|
| `ibrd_and_ida_net_flows_commitments_09-16-2026.csv` | IBRD & IDA net flows and commitments, summarised by country and fiscal year (FY2010–FY2027, 3,445 rows) | 374 KB |
| `IDA_historical.csv` | IDA credit-level portfolio snapshots, one per month since April 2011 | 460 MB |

Two grains, deliberately. The summary file is small enough to reason about by hand — which is why the first project uses only that one. The snapshot file is where the same methods have to survive real volume, and where a **reconciliation** between the two becomes possible: aggregate the credit-level monthly flows by country and fiscal year, and they should land on the summary file's gross disbursement figures. Two independent sources agreeing is a far stronger signal than either one looking plausible alone.

> **On the fiscal year:** the World Bank's runs 1 July – 30 June and is named for the year it *ends*. FY2027 began 1 July 2026. Any extract taken mid-year contains a partial period that looks exactly like a failed data load — see the first project for what that does to a naive control chart.

---

## Layout

```
world-bank-data-quality/
├── data/                        # git-ignored; shared download target
├── ida-disbursement-spc/        # one folder per project, at the root
│   ├── README.md                # the method, the findings, the limitations
│   ├── src/                     # config, spc_core, four numbered steps
│   └── outputs/                 # alerts, figures, FINDINGS.md (committed)
└── README.md
```

## Running anything here

```bash
pip install -r ida-disbursement-spc/requirements.txt
cd ida-disbursement-spc
python src/step1_prepare.py && python src/step2_spc.py
python src/step3_evaluate.py && python src/step4_report.py
```

Python 3.11+, and nothing beyond pandas, numpy and matplotlib. That constraint is intentional: a detector that a team has to keep alive after its author leaves is worth more than a more accurate one they cannot maintain.

---

## Where this goes

1. **Rolling control limits** — a frozen baseline eventually describes a process that no longer exists, and every legitimate regime change then alerts forever.
2. **Scale to the credit-level snapshots** — same maths, finer grain. Two free rules arrive with it: cumulative disbursement should never *decrease*, and a credit that vanishes between snapshots is a missing-data pattern rather than an amount anomaly.
3. **Reconcile the two datasets** against each other.
4. **A second, multivariate detector** (Isolation Forest) for what a one-variable-at-a-time chart structurally cannot see — keeping SPC as the explainable first layer rather than replacing it.
