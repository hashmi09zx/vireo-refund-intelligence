import pytest
import pandas as pd
import numpy as np

from src.reconciliation.deduplication import normalize_refund_amount, resolve_canonical_records, classify_duplicate_group
from src.reconciliation.entity_resolution import resolve_ticket_orders
from src.reconciliation.ledger import build_canonical_refund_ledger
from src.reconciliation.reconcile import run_reconciliation


def test_normalize_refund_amount():
    # Helpdesk row
    row_helpdesk = pd.Series({"refund_amount_inr": 1500.0, "source_system": "helpdesk"})
    amt_h, rule_h = normalize_refund_amount(row_helpdesk)
    assert amt_h == 1500.0
    assert rule_h == "HELPDESK_NATIVE_RUPEES"

    # Legacy FD row (divided by 100)
    row_legacy = pd.Series({"refund_amount_inr": 150000.0, "source_system": "legacy_fd"})
    amt_l, rule_l = normalize_refund_amount(row_legacy)
    assert amt_l == 1500.0
    assert rule_l == "LEGACY_DIVIDED_BY_100"

    # Null refund
    row_null = pd.Series({"refund_amount_inr": np.nan, "source_system": "helpdesk"})
    amt_n, rule_n = normalize_refund_amount(row_null)
    assert pd.isna(amt_n)
    assert rule_n == "NO_REFUND"


def test_duplicate_resolution_prefers_helpdesk():
    df_raw = pd.DataFrame([
        {
            "ticket_id": "TK-1001",
            "created_at": "2025-01-01 10:00:00",
            "source_system": "legacy_fd",
            "refund_amount_inr": 90000.0,
            "agent_id": "A1",
            "customer_id": "C1",
            "order_id": "O1",
            "product_sku": "SKU1",
        },
        {
            "ticket_id": "TK-1001",
            "created_at": "2025-01-01 10:00:00",
            "source_system": "helpdesk",
            "refund_amount_inr": 900.0,
            "agent_id": "A1",
            "customer_id": "C1",
            "order_id": "O1",
            "product_sku": "SKU1",
        },
    ])

    canonical_all, refund_events, dedup_report = resolve_canonical_records(df_raw)

    assert len(canonical_all) == 1
    assert len(refund_events) == 1
    rec = refund_events.iloc[0]
    assert rec["ticket_id"] == "TK-1001"
    assert rec["source_system"] == "helpdesk"
    assert rec["refund_amount_inr"] == 900.0
    assert rec["canonicalization_reason"] == "CANONICAL_HELPDESK_RECORD_PREFERRED"


def test_entity_resolution_hierarchy():
    tickets_df = pd.DataFrame([
        {"ticket_id": "T1", "order_id": "ORD-1", "customer_id": "C1", "product_sku": "S1"},  # Explicit
        {"ticket_id": "T2", "order_id": None, "customer_id": "C2", "product_sku": "S2"},     # Unique fallback
        {"ticket_id": "T3", "order_id": None, "customer_id": "C3", "product_sku": "S3"},     # Ambiguous fallback
        {"ticket_id": "T4", "order_id": None, "customer_id": "C4", "product_sku": "S4"},     # Unmatched
    ])

    orders_df = pd.DataFrame([
        {"order_id": "ORD-1", "customer_id": "C1", "sku": "S1"},
        {"order_id": "ORD-2", "customer_id": "C2", "sku": "S2"},
        {"order_id": "ORD-3A", "customer_id": "C3", "sku": "S3"},
        {"order_id": "ORD-3B", "customer_id": "C3", "sku": "S3"},
    ])

    resolved = resolve_ticket_orders(tickets_df, orders_df)
    res_map = resolved.set_index("ticket_id").to_dict(orient="index")

    # T1: Explicit
    assert res_map["T1"]["resolved_order_id"] == "ORD-1"
    assert res_map["T1"]["join_method"] == "EXPLICIT_ORDER_ID"
    assert res_map["T1"]["join_confidence"] == "HIGH_CONFIDENCE"

    # T2: Unique fallback
    assert res_map["T2"]["resolved_order_id"] == "ORD-2"
    assert res_map["T2"]["join_method"] == "CUSTOMER_SKU_UNIQUE"
    assert res_map["T2"]["join_confidence"] == "MEDIUM_CONFIDENCE"

    # T3: Ambiguous fallback (MUST NOT SELECT ARBITRARILY)
    assert res_map["T3"]["resolved_order_id"] is None
    assert res_map["T3"]["join_method"] == "AMBIGUOUS_CUSTOMER_SKU"
    assert res_map["T3"]["join_confidence"] == "AMBIGUOUS"
    assert res_map["T3"]["join_candidates_count"] == 2

    # T4: Unmatched
    assert res_map["T4"]["resolved_order_id"] is None
    assert res_map["T4"]["join_method"] == "NO_MATCH"
    assert res_map["T4"]["join_confidence"] == "UNMATCHED"


def test_full_reconciliation_integration():
    ledger_df, summary = run_reconciliation()

    # Empirical values validation
    assert len(ledger_df) == 2340
    assert summary["metrics"]["canonical_refund_cases"] == 2340
    assert summary["metrics"]["raw_refund_rows"] == 2465
    assert summary["metrics"]["duplicate_refund_rows_removed"] == 125
    assert summary["metrics"]["canonical_refund_value"] == 6709932.0

    # Invariants
    assert summary["invariant_validation"]["all_passed"] is True
    assert ledger_df["ticket_id"].is_unique


def test_reconciliation_idempotency():
    ledger1, summary1 = run_reconciliation()
    ledger2, summary2 = run_reconciliation()

    assert summary1["metrics"]["canonical_refund_value"] == summary2["metrics"]["canonical_refund_value"]
    assert len(ledger1) == len(ledger2)
    pd.testing.assert_frame_equal(ledger1, ledger2)
