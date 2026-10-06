import pandas as pd
from typing import Dict, Any
from src.analytics.metrics import safe_divide

REASON_TAXONOMY_MAP = {
    "GW-OTHER": "Goodwill / Other",
    "DOA-REPL": "DOA / Replacement Requested",
    "LOST-TRANSIT": "Lost in Transit",
    "DUP-PAYMENT": "Duplicate Payment",
    "CANCEL": "Order Cancellation",
    "PRICE-ADJ": "Price Adjustment",
    "RETURN-QC-OK": "Return - QC Passed",
    "WTY-BUYBACK": "Warranty Buyback",
}


def analyze_refund_reasons(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates refund statistics by original reason code mapped to policy taxonomy."""
    df = ledger_df.copy()

    reason_col = "original_reason_code" if "original_reason_code" in df.columns else "refund_reason_code"

    # Map raw reason codes
    df["normalized_reason"] = df[reason_col].map(
        lambda code: REASON_TAXONOMY_MAP.get(str(code).strip(), "Other / Unmapped") if pd.notnull(code) else "Other / Unmapped"
    )

    total_cases = len(df)
    total_val = float(df["refund_amount_inr"].sum())

    # Group by normalized_reason
    grouped = df.groupby("normalized_reason").agg(
        refund_cases=("ticket_id", "count"),
        refund_value_inr=("refund_amount_inr", "sum")
    ).reset_index()

    # Calculate shares
    grouped["share_of_refund_cases"] = grouped["refund_cases"].apply(
        lambda c: round(safe_divide(c, total_cases), 4)
    )
    grouped["share_of_refund_value"] = grouped["refund_value_inr"].apply(
        lambda v: round(safe_divide(v, total_val), 4)
    )
    grouped["refund_value_inr"] = grouped["refund_value_inr"].round(2)

    # Sort descending by refund value
    grouped.sort_values(by="refund_value_inr", ascending=False, inplace=True)
    grouped.reset_index(drop=True, inplace=True)

    return grouped
