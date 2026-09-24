"""STEP 1 - Bronze to Silver, plus the rule layer.

Bronze = the CSV exactly as downloaded. We never edit it.
Silver = same rows, but typed, renamed, and with quality facts attached.

The rule layer runs FIRST and stays forever. SPC does not replace fixed
rules, it sits on top of them. Rules catch what we already know can break;
SPC catches what nobody wrote a rule for yet. Deleting the rules because you
now have a model is how teams lose their cheapest, clearest checks.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (RAW_CSV, SILVER_DIR, OUT_DIR, INCOMPLETE_FY,
                    LAST_COMPLETE_FY, EXTRACT_DATE)

RENAME = {
    "Financier": "financier",
    "Fiscal Year": "fiscal_year",
    "Region": "region",
    "Country / Economy": "country",
    "Gross Disbursement (US$)": "gross_disbursement_usd",
    "Repayments (US$)": "repayments_usd",
    "Net Disbursement (US$)": "net_disbursement_usd",
    "Interest (US$)": "interest_usd",
    "Fees (US$)": "fees_usd",
    "IBRD Commitments (US$)": "ibrd_commitments_usd",
    "IDA Grant Commitments (US$)": "ida_grant_commitments_usd",
    "IDA Non-Concessional Commitments (US$)": "ida_nonconcessional_commitments_usd",
    "IDA Concessional Commitments (US$)": "ida_concessional_commitments_usd",
    "IDA Other Commitments (US$)": "ida_other_commitments_usd",
}


def load_bronze():
    df = pd.read_csv(RAW_CSV)
    missing = set(RENAME) - set(df.columns)
    if missing:
        # Schema drift: the source changed a column name and we would rather
        # fail loudly here than silently produce a column of NaNs downstream.
        raise SystemExit(f"SCHEMA DRIFT - expected columns absent: {sorted(missing)}")
    return df.rename(columns=RENAME)


def run_rules(df):
    """Each rule returns (name, boolean mask of offending rows, note)."""
    checks = []

    # R1 - accounting identity. Net must equal Gross minus Repayments.
    resid = df.net_disbursement_usd - (df.gross_disbursement_usd - df.repayments_usd)
    checks.append(("R1_net_identity", resid.abs() > 1.0,
                   "Net != Gross - Repayments by more than $1 (rounding tolerance)"))

    # R2 - negative gross disbursement. Not automatically wrong: a refund or a
    # prior-year correction booked against the current year looks like this.
    # We record it rather than reject it. "Violates a simple rule" is not the
    # same as "incorrect".
    checks.append(("R2_negative_gross", df.gross_disbursement_usd < 0,
                   "Gross disbursement below zero - usually a refund/correction, verify"))

    # R3 - negative repayments should not happen at all.
    checks.append(("R3_negative_repayments", df.repayments_usd < 0,
                   "Repayments below zero"))

    # R4 - primary key uniqueness. If this ever fires, an upstream join fanned out.
    dup = df.duplicated(["financier", "fiscal_year", "country"], keep=False)
    checks.append(("R4_duplicate_key", dup,
                   "More than one row per (financier, fiscal_year, country)"))

    # R5 - reference-data drift. A country should not change region mid-series.
    # When it does, every regional total before and after is on a different basis.
    n_regions = df.groupby("country").region.transform("nunique")
    checks.append(("R5_region_reassigned", n_regions > 1,
                   "Country appears under more than one region across years"))

    rows = []
    for name, mask, note in checks:
        rows.append({"rule": name, "n_rows_flagged": int(mask.sum()),
                     "pct_of_rows": round(100 * mask.mean(), 3), "note": note})
        df[f"flag_{name}"] = mask
    return df, pd.DataFrame(rows)


def add_period_completeness(df):
    """The partial-period trap, handled once and centrally."""
    df["fy_is_complete"] = df.fiscal_year <= LAST_COMPLETE_FY
    return df


def coverage_report(df):
    """Which country series have holes in them?

    A missing year is invisible in a table and lethal in a time series: the
    chart silently compares FY2019 with FY2021 as if they were adjacent.
    """
    rows = []
    for (fin, country), g in df[df.fy_is_complete].groupby(["financier", "country"]):
        years = sorted(g.fiscal_year)
        expected = set(range(min(years), max(years) + 1))
        gaps = sorted(expected - set(years))
        rows.append({"financier": fin, "country": country, "first_fy": min(years),
                     "last_fy": max(years), "n_years": len(years),
                     "n_gap_years": len(gaps),
                     "gap_years": ",".join(map(str, gaps))})
    return pd.DataFrame(rows).sort_values(["n_gap_years", "country"], ascending=[False, True])


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

    print(f"extract date {EXTRACT_DATE}  |  rows {len(df):,}  |  "
          f"FY {df.fiscal_year.min()}-{df.fiscal_year.max()}")
    print(f"FY{INCOMPLETE_FY} marked incomplete: {int((~df.fy_is_complete).sum()):,} rows excluded from SPC\n")
    print("RULE LAYER")
    print(rules.to_string(index=False))

    drift = df[df.flag_R5_region_reassigned].groupby(["country", "region"]).fiscal_year.agg(["min", "max"])
    if len(drift):
        print(f"\nR5 detail - {df[df.flag_R5_region_reassigned].country.nunique()} countries reassigned:")
        print(drift.head(8).to_string())

    print(f"\nSeries with gaps: {int((cov.n_gap_years > 0).sum())} of {len(cov)}")
    print(f"\nwrote {SILVER_DIR/'net_flows_silver.csv'}")


if __name__ == "__main__":
    main()
