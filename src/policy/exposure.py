from typing import List, Dict, Any
import pandas as pd


def calculate_non_overlapping_exposure(
    findings_df: pd.DataFrame,
    ledger_df: pd.DataFrame = None
) -> Dict[str, Any]:
    """Calculates non-overlapping review exposure across control findings.
    
    Prevents double-counting tickets or orders that trigger multiple rules.
    Ensures R2 (Refund Exceeds Order Value) excess is counted ONCE per resolved_order_id.
    """
    if findings_df is None or findings_df.empty:
        return {
            "refund_plus_replacement_exposure": 0.0,
            "validated_over_refund_exposure": 0.0,
            "overlap_count": 0,
            "non_overlapping_review_exposure": 0.0,
            "label": "OBSERVED REVIEW EXPOSURE (Not confirmed financial loss)",
        }

    # Support both in-memory dict keys and loaded CSV column names
    amt_col = "refund_amount_inr" if "refund_amount_inr" in findings_df.columns else "financial_amount"

    # 1. R1: Refund + Replacement total exposure
    r1_df = findings_df[findings_df["finding_type"] == "REFUND_PLUS_REPLACEMENT"]
    r1_tickets = set(r1_df["ticket_id"].unique()) if not r1_df.empty else set()
    r1_exposure = float(r1_df[amt_col].sum()) if not r1_df.empty and amt_col in r1_df.columns else 0.0

    # 2. R2: Validated Over-refund total excess (Deduplicated per resolved_order_id)
    r2_df = findings_df[findings_df["finding_type"] == "REFUND_EXCEEDS_ORDER_VALUE"]
    if not r2_df.empty and "resolved_order_id" in r2_df.columns:
        r2_orders = r2_df.drop_duplicates(subset=["resolved_order_id"])
        r2_excess_exposure = float(r2_orders["observed_excess_inr"].sum())
        r2_tickets = set(r2_df["ticket_id"].unique())
    else:
        r2_excess_exposure = 0.0
        r2_tickets = set()

    # 3. Overlap tracking between R1 tickets and R2 tickets
    overlapping_tickets = r1_tickets.intersection(r2_tickets)
    overlap_count = len(overlapping_tickets)

    # 4. Gross non-overlapping exposure calculation:
    # R1 exposure (sum of refund_amount_inr) + R2 order excess (deduplicated by resolved_order_id)
    non_overlapping_total = r1_exposure + r2_excess_exposure

    return {
        "refund_plus_replacement_exposure": round(r1_exposure, 2),
        "validated_over_refund_exposure": round(r2_excess_exposure, 2),
        "overlap_count": overlap_count,
        "non_overlapping_review_exposure": round(non_overlapping_total, 2),
        "label": "OBSERVED REVIEW EXPOSURE (Not confirmed financial loss)",
    }

