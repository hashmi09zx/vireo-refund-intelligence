import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from src.config import OUTPUT_DIR, ORDERS_CSV
from src.reconciliation.loader import load_raw_data
from src.reconciliation.deduplication import resolve_canonical_records
from src.reconciliation.entity_resolution import resolve_ticket_orders
from src.reconciliation.ledger import build_canonical_refund_ledger, save_canonical_ledger

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def validate_reconciliation_invariants(
    raw_tickets_df: pd.DataFrame,
    canonical_tickets_df: pd.DataFrame,
    canonical_ledger_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    dedup_report: Dict[str, Any]
) -> List[str]:
    """Runs strict invariant validation assertions on the reconciliation pipeline output."""
    passed_checks = []

    # 1. Unique ticket_id in canonical ledger
    assert canonical_ledger_df["ticket_id"].is_unique, "Invariant Failed: Duplicate ticket_id in canonical ledger!"
    passed_checks.append("Canonical ticket_id uniqueness")

    # 2. Every canonical refund amount > 0
    assert (canonical_ledger_df["refund_amount_inr"] > 0).all(), "Invariant Failed: Non-positive refund in canonical ledger!"
    passed_checks.append("Canonical refund_amount_inr > 0")

    # 3. Canonical refund cases <= raw refund rows
    raw_refund_count = (raw_tickets_df["refund_amount_inr"].notnull() & (raw_tickets_df["refund_amount_inr"] > 0)).sum()
    canonical_cases_count = len(canonical_ledger_df)
    assert canonical_cases_count <= raw_refund_count, "Invariant Failed: Canonical refund cases exceed raw refund rows!"
    passed_checks.append(f"Canonical cases ({canonical_cases_count}) <= Raw refund rows ({raw_refund_count})")

    # 4. Canonical refund value <= normalized raw refund value
    norm_raw_sum = dedup_report["normalized_raw_refund_sum_before_dedup"]
    canonical_sum = float(canonical_ledger_df["refund_amount_inr"].sum())
    assert round(canonical_sum, 2) <= round(norm_raw_sum, 2), "Invariant Failed: Canonical sum exceeds normalized raw sum!"
    passed_checks.append(f"Canonical value (₹{canonical_sum:,.2f}) <= Normalized raw value (₹{norm_raw_sum:,.2f})")

    # 5. Valid agent_id on all canonical records
    assert canonical_ledger_df["agent_id"].notnull().all(), "Invariant Failed: Null agent_id in canonical ledger!"
    passed_checks.append("All canonical records have non-null agent_id")

    # 6. Explicit order_id matches exist in orders.csv
    valid_orders_set = set(orders_df["order_id"].dropna().unique())
    explicit_matches = canonical_ledger_df[canonical_ledger_df["join_method"] == "EXPLICIT_ORDER_ID"]
    invalid_explicit = explicit_matches[~explicit_matches["resolved_order_id"].isin(valid_orders_set)]
    assert len(invalid_explicit) == 0, f"Invariant Failed: Found {len(invalid_explicit)} invalid explicit order matches!"
    passed_checks.append("All explicit order_id matches exist in orders.csv")

    # 7. Ambiguous fallback matches remain None for resolved_order_id
    ambiguous_rows = canonical_ledger_df[canonical_ledger_df["join_confidence"] == "AMBIGUOUS"]
    assert ambiguous_rows["resolved_order_id"].isnull().all(), "Invariant Failed: Ambiguous join has non-null resolved_order_id!"
    passed_checks.append("All ambiguous fallback matches have resolved_order_id=None")

    return passed_checks


def run_reconciliation() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Runs the complete Phase 1 Refund Truth Engine pipeline."""
    logger.info("Starting Phase 1 Refund Reconciliation Engine...")

    # 1. Load raw data
    raw_data = load_raw_data()
    tickets_df = raw_data["tickets"]
    agents_df = raw_data["agents"]
    orders_df = raw_data["orders"]
    products_df = raw_data["products"]

    # 2. Duplicate resolution and monetary unit normalization
    canonical_tickets_df, refund_events_df, dedup_report = resolve_canonical_records(tickets_df)

    # 3. Entity resolution (Order matching hierarchy)
    resolved_refund_events_df = resolve_ticket_orders(refund_events_df, orders_df)

    # 4. Build canonical refund ledger
    canonical_ledger_df = build_canonical_refund_ledger(
        resolved_refund_events_df,
        orders_df,
        products_df,
        agents_df
    )

    # 5. Save canonical ledger CSV
    ledger_path = save_canonical_ledger(canonical_ledger_df)
    logger.info(f"Saved Canonical Refund Ledger ({len(canonical_ledger_df)} rows) to {ledger_path}")

    # 6. Validate invariants
    invariant_checks = validate_reconciliation_invariants(
        tickets_df,
        canonical_tickets_df,
        canonical_ledger_df,
        orders_df,
        dedup_report
    )

    # 7. Build reconciliation summary report
    raw_refund_rows = int((tickets_df["refund_amount_inr"].notnull() & (tickets_df["refund_amount_inr"] > 0)).sum())
    raw_unnorm_val = float(dedup_report["raw_unnormalized_refund_sum"])
    norm_raw_val = float(dedup_report["normalized_raw_refund_sum_before_dedup"])
    canonical_val = float(canonical_ledger_df["refund_amount_inr"].sum())
    dup_removed_val = float(norm_raw_val - canonical_val)

    # Helpdesk vs legacy values
    helpdesk_val = float(canonical_ledger_df[canonical_ledger_df["source_system"] == "helpdesk"]["refund_amount_inr"].sum())
    legacy_norm_val = float(canonical_ledger_df[canonical_ledger_df["source_system"] == "legacy_fd"]["refund_amount_inr"].sum())

    confidence_dist = canonical_ledger_df["join_confidence"].value_counts().to_dict()

    reconciliation_summary = {
        "methodology": {
            "reconciliation_rule": "helpdesk native INR unchanged; legacy_fd amounts divided by 100",
            "duplicate_rule": "prefer helpdesk record over legacy_fd record for duplicate migrated pairs",
            "entity_resolution_hierarchy": "Level 1: Explicit order_id match. Level 2: customer_id + product_sku fallback match.",
        },
        "metrics": {
            "raw_ticket_rows": int(len(tickets_df)),
            "unique_ticket_ids": int(tickets_df["ticket_id"].nunique()),
            "duplicate_ticket_ids": int(dedup_report["duplicate_ticket_ids_count"]),
            "raw_refund_rows": raw_refund_rows,
            "canonical_refund_cases": int(len(canonical_ledger_df)),
            "duplicate_refund_rows_removed": int(raw_refund_rows - len(canonical_ledger_df)),
            "raw_unnormalized_refund_value": round(raw_unnorm_val, 2),
            "normalized_raw_refund_value": round(norm_raw_val, 2),
            "canonical_refund_value": round(canonical_val, 2),
            "duplicate_reconciliation_difference": round(dup_removed_val, 2),
            "helpdesk_refund_value": round(helpdesk_val, 2),
            "legacy_normalized_refund_value": round(legacy_norm_val, 2),
        },
        "order_match_confidence_distribution": {
            "high_confidence_order_matches": int(confidence_dist.get("HIGH_CONFIDENCE", 0)),
            "medium_confidence_order_matches": int(confidence_dist.get("MEDIUM_CONFIDENCE", 0)),
            "ambiguous_order_matches": int(confidence_dist.get("AMBIGUOUS", 0)),
            "unmatched_order_matches": int(confidence_dist.get("UNMATCHED", 0)),
        },
        "duplicate_classifications": dedup_report["duplicate_classifications_summary"],
        "invariant_validation": {
            "all_passed": True,
            "passed_checks": invariant_checks,
        },
    }

    # Save summary JSON & CSV
    json_summary_path = OUTPUT_DIR / "reconciliation_summary.json"
    with open(json_summary_path, "w", encoding="utf-8") as f:
        json.dump(reconciliation_summary, f, indent=2)
    logger.info(f"Saved JSON reconciliation summary to {json_summary_path}")

    summary_df = pd.DataFrame([{
        "metric": k,
        "value": str(v)
    } for k, v in reconciliation_summary["metrics"].items()])
    csv_summary_path = OUTPUT_DIR / "reconciliation_summary.csv"
    summary_df.to_csv(csv_summary_path, index=False)
    logger.info(f"Saved CSV reconciliation summary to {csv_summary_path}")

    return canonical_ledger_df, reconciliation_summary


def print_terminal_reconciliation_summary(summary: Dict[str, Any]) -> None:
    """Prints formatted executive reconciliation summary to terminal."""
    m = summary["metrics"]
    o = summary["order_match_confidence_distribution"]

    print("\n" + "=" * 65)
    print("      VIREO REFUND TRUTH ENGINE — RECONCILIATION SUMMARY      ")
    print("=" * 65)

    print(f"\n[CANONICAL FINANCIAL RECONCILIATION]")
    print(f"  • Raw Export Refund Value (Unnormalized): ₹{m['raw_unnormalized_refund_value']:,.2f}")
    print(f"  • Normalized Raw Refund Value (/100 legacy): ₹{m['normalized_raw_refund_value']:,.2f}")
    print(f"  • CANONICAL RECONCILED REFUND VALUE:        ₹{m['canonical_refund_value']:,.2f}")
    print(f"  • Duplicate Refund Value Removed:           ₹{m['duplicate_reconciliation_difference']:,.2f}")

    print(f"\n[VOLUME & DEDUPLICATION]")
    print(f"  • Raw Ticket Export Rows:   {m['raw_ticket_rows']:,}")
    print(f"  • Unique Ticket IDs:         {m['unique_ticket_ids']:,}")
    print(f"  • Duplicate Ticket IDs:      {m['duplicate_ticket_ids']:,}")
    print(f"  • Raw Refund Rows:           {m['raw_refund_rows']:,}")
    print(f"  • CANONICAL REFUND CASES:    {m['canonical_refund_cases']:,}")
    print(f"  • Duplicate Refunds Removed: {m['duplicate_refund_rows_removed']:,}")

    print(f"\n[ENTITY RESOLUTION CONFIDENCE DISTRIBUTION]")
    print(f"  • High Confidence (Explicit Order ID):    {o['high_confidence_order_matches']:,}")
    print(f"  • Medium Confidence (Unique Cust+SKU):     {o['medium_confidence_order_matches']:,}")
    print(f"  • Ambiguous (Multiple Cust+SKU Candidates):{o['ambiguous_order_matches']:,}")
    print(f"  • Unmatched (Zero Order Candidates):       {o['unmatched_order_matches']:,}")

    print(f"\n[INVARIANT VALIDATION]")
    for check in summary["invariant_validation"]["passed_checks"]:
        print(f"  ✓ {check}")

    print("\n" + "=" * 65 + "\n")


if __name__ == "__main__":
    ledger_df, summary = run_reconciliation()
    print_terminal_reconciliation_summary(summary)
