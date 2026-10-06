from pathlib import Path
from typing import Dict, Any
import pandas as pd

from src.config import OUTPUT_DIR


def build_canonical_refund_ledger(
    refund_events_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    products_df: pd.DataFrame,
    agents_df: pd.DataFrame
) -> pd.DataFrame:
    """Enriches canonical refund events with metadata and formats the Canonical Refund Ledger."""
    ledger = refund_events_df.copy()

    # Format created_at date and extract YYYY-MM month
    created_dt = pd.to_datetime(ledger["created_at"], errors="coerce")
    ledger["created_at"] = created_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    ledger["month"] = created_dt.dt.strftime("%Y-%m")

    # Rename refund_reason_code -> original_reason_code for clarity
    if "refund_reason_code" in ledger.columns and "original_reason_code" not in ledger.columns:
        ledger.rename(columns={"refund_reason_code": "original_reason_code"}, inplace=True)

    # 1. Join order_value_inr from orders.csv on resolved_order_id
    order_values = orders_df.set_index("order_id")["order_value_inr"].to_dict()
    ledger["order_value_inr"] = ledger["resolved_order_id"].map(order_values)

    # 2. Join unit_cost_inr from products.csv on product_sku
    unit_costs = products_df.set_index("sku")["unit_cost_inr"].to_dict()
    ledger["unit_cost_inr"] = ledger["product_sku"].map(unit_costs)

    # 3. Join team, shift, tier from agents.csv on agent_id
    agent_info = agents_df.set_index("agent_id")[["team", "shift", "tier"]].to_dict(orient="index")
    ledger["team"] = ledger["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("team"))
    ledger["shift"] = ledger["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("shift"))
    ledger["tier"] = ledger["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("tier"))

    # Final column ordering
    columns_order = [
        "ticket_id",
        "created_at",
        "month",
        "agent_id",
        "customer_id",
        "resolved_order_id",
        "product_sku",
        "refund_amount_raw",
        "refund_amount_inr",
        "original_reason_code",
        "replacement_issued",
        "source_system",
        "canonicalization_reason",
        "duplicate_group_id",
        "join_method",
        "join_confidence",
        "join_candidates_count",
        "order_value_inr",
        "unit_cost_inr",
        "team",
        "shift",
        "tier",
    ]

    # Keep any additional existing columns at the end if present
    existing_cols = [c for c in columns_order if c in ledger.columns]
    other_cols = [c for c in ledger.columns if c not in existing_cols]

    final_ledger = ledger[existing_cols + other_cols].copy()
    
    # Sort deterministically by created_at and ticket_id
    final_ledger.sort_values(by=["created_at", "ticket_id"], ascending=[True, True], inplace=True)
    
    return final_ledger


def save_canonical_ledger(ledger_df: pd.DataFrame) -> Path:
    """Saves Canonical Refund Ledger to outputs/canonical_refund_ledger.csv."""
    ledger_path = OUTPUT_DIR / "canonical_refund_ledger.csv"
    ledger_df.to_csv(ledger_path, index=False)
    return ledger_path
