"""STEP 1 - Bronze to Silver, using Project 01's rule layer unchanged.

Nothing new is computed here. The loader, the schema-drift check, rules R1-R6
and the coverage report are Project 01's functions; this script only writes
their output into Project 02's own folders, so Project 02 runs without anyone
having run Project 01 first - and without writing into Project 01's outputs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v1_bridge import v1_config as V1, load_bronze, run_rules, add_period_completeness, coverage_report
from adaptive_config import SILVER_DIR, OUT_DIR


def main():
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_bronze()
    df, rules = run_rules(df)
    df = add_period_completeness(df)
    cov = coverage_report(df)

    df.to_csv(SILVER_DIR / "net_flows_silver.csv", index=False)
    rules.to_csv(OUT_DIR / "rule_layer_report.csv", index=False)
    cov.to_csv(OUT_DIR / "series_coverage.csv", index=False)

    print(f"raw {V1.RAW_CSV.name}  |  rows {len(df):,}  |  FY {df.fiscal_year.min()}-{df.fiscal_year.max()}")
    print(rules[["rule", "n_rows_flagged"]].to_string(index=False))
    gaps = cov[(cov.financier == V1.FINANCIER) & (cov.n_gap_years > 0)]
    print(f"\nIDA series with missing fiscal years: {len(gaps)} "
          f"({', '.join(f'{r.country} [{r.gap_years}]' for r in gaps.head(6).itertuples())}"
          f"{', ...' if len(gaps) > 6 else ''})")
    print(f"\nwrote {SILVER_DIR / 'net_flows_silver.csv'}")


if __name__ == "__main__":
    main()
