"""Build (or refresh) the sheet a human uses to label the alert queue.

Recall can be measured with synthetic errors. PRECISION cannot - only a person
can say whether "Chad FY2021, -50%" was worth an analyst's morning. So this
script writes every growth-chart alert to labels/alert_labels.csv with an
empty `label` column, and you fill it in with one of:

    investigate | explained | noise      (definitions in config.LABELS)

Run it again after the detector changes and it MERGES: new alerts are added
blank, existing labels are kept, and alerts that no longer fire stay in the
file with currently_alerting = False. A label is an afternoon of human
judgement - no script is allowed to throw one away. Running this twice in a
row changes nothing, which is what idempotent means.

Labels are keyed on (country, fiscal_year), not on the method version:
whether Chad FY2021 deserved a look is a fact about the data, so a label
written against v1 still counts when v2 flags the same point.

The file is written as UTF-8 with a byte-order mark so that Excel opens
"Cote d'Ivoire" and "Sao Tome" with their accents intact.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import OUT_DIR, LABELS_CSV, LABELS

KEY = ["country", "fiscal_year"]
COLUMNS = KEY + ["robust_z", "severity", "change_pct", "rule", "currently_alerting",
                 "explanation", "label", "note"]


def load_labels():
    """Existing labels, or an empty frame. Also used by step3_evaluate."""
    if not LABELS_CSV.exists():
        return pd.DataFrame({c: pd.Series(dtype="int64" if c == "fiscal_year" else "object")
                             for c in COLUMNS})
    lab = pd.read_csv(LABELS_CSV, encoding="utf-8-sig", dtype={"label": str, "note": str})
    lab["label"] = lab["label"].fillna("").str.strip().str.lower()
    lab["note"] = lab["note"].fillna("")
    bad = lab[(lab.label != "") & ~lab.label.isin(LABELS)]
    if len(bad):
        rows = "; ".join(f"{r.country} FY{r.fiscal_year}='{r.label}'" for r in bad.itertuples())
        raise SystemExit(f"Unknown label value(s): {rows}\nAllowed: {', '.join(LABELS)}")
    return lab


def main():
    alerts = pd.read_csv(OUT_DIR / "spc_alerts.csv")
    alerts = alerts[alerts.chart == "B_growth"].copy()
    alerts["change_pct"] = ((np.exp(alerts.value) - 1) * 100).round(0)
    alerts["robust_z"] = alerts.robust_z.round(1)
    alerts["currently_alerting"] = True
    current = alerts[KEY + ["robust_z", "severity", "change_pct", "rule",
                            "currently_alerting", "explanation"]]

    old = load_labels()
    human = old[KEY + ["label", "note"]]

    # Current alerts, with any label already written for them.
    merged = current.merge(human, on=KEY, how="left")
    # Alerts that fired before but not now: kept, never dropped.
    gone = old[~old.set_index(KEY).index.isin(current.set_index(KEY).index)].copy()
    gone["currently_alerting"] = False
    out = pd.concat([merged, gone[COLUMNS]], ignore_index=True) if len(gone) else merged
    out[["label", "note"]] = out[["label", "note"]].fillna("")
    out["_abs_z"] = out.robust_z.abs()
    out = out.sort_values(["currently_alerting", "_abs_z"], ascending=[False, False])[COLUMNS]

    LABELS_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LABELS_CSV, index=False, encoding="utf-8-sig")

    live = out[out.currently_alerting]
    done = live[live.label != ""]
    print(f"wrote {LABELS_CSV}")
    print(f"current alerts: {len(live)}  |  labelled: {len(done)}  |  still to label: {len(live) - len(done)}")
    if len(done):
        print("label counts:", done.label.value_counts().to_dict())
    if (~out.currently_alerting).any():
        print(f"kept {int((~out.currently_alerting).sum())} labelled row(s) for alerts that no longer fire")
    print("\nFill the `label` column with one of:")
    for k, v in LABELS.items():
        print(f"  {k:12s} {v}")
    print("Work top-down: rows are sorted by |z|, so the first 10 decide precision@10.")


if __name__ == "__main__":
    main()
