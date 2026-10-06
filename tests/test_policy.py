import pytest
import pandas as pd

from src.policy.rules import (
    evaluate_r1_refund_plus_replacement,
    evaluate_r2_refund_exceeds_order,
    evaluate_r3_multiple_refunds,
    evaluate_r4_reason_code_mismatch,
    evaluate_r5_goodwill_cap,
)
from src.policy.exposure import calculate_non_overlapping_exposure


def test_r1_refund_plus_replacement():
    ledger = pd.DataFrame([
        {"ticket_id": "T1", "refund_amount_inr": 1000.0, "replacement_issued": "Y", "agent_id": "A1"},
        {"ticket_id": "T2", "refund_amount_inr": 1000.0, "replacement_issued": "N", "agent_id": "A1"},
        {"ticket_id": "T3", "refund_amount_inr": 0.0, "replacement_issued": "Y", "agent_id": "A1"},
    ])

    findings = evaluate_r1_refund_plus_replacement(ledger)
    assert len(findings) == 1
    assert findings[0]["ticket_id"] == "T1"
    assert findings[0]["finding_type"] == "REFUND_PLUS_REPLACEMENT"
    assert findings[0]["observed_excess_inr"] == 1000.0


def test_r2_refund_exceeds_order_strict_high_confidence():
    ledger = pd.DataFrame([
        # High confidence explicit match -> Order ORD-1 refunded 2500 total (Value 2000 -> Excess 500)
        {"ticket_id": "T1", "resolved_order_id": "ORD-1", "join_confidence": "HIGH_CONFIDENCE", "refund_amount_inr": 1500.0, "agent_id": "A1"},
        {"ticket_id": "T2", "resolved_order_id": "ORD-1", "join_confidence": "HIGH_CONFIDENCE", "refund_amount_inr": 1000.0, "agent_id": "A1"},
        
        # Ambiguous match -> MUST NOT BE USED AUTHORITATIVELY FOR R2
        {"ticket_id": "T3", "resolved_order_id": "ORD-AMBIGUOUS", "join_confidence": "AMBIGUOUS", "refund_amount_inr": 5000.0, "agent_id": "A1"},
    ])

    orders = pd.DataFrame([
        {"order_id": "ORD-1", "order_value_inr": 2000.0},
        {"order_id": "ORD-AMBIGUOUS", "order_value_inr": 1000.0},
    ])

    findings = evaluate_r2_refund_exceeds_order(ledger, orders)
    
    # Should only flag ORD-1 (T1 and T2), ignoring ORD-AMBIGUOUS
    assert len(findings) == 2
    for f in findings:
        assert f["resolved_order_id"] == "ORD-1"
        assert f["observed_excess_inr"] == 500.0


def test_r3_multiple_refunds():
    ledger = pd.DataFrame([
        {"ticket_id": "T1", "resolved_order_id": "ORD-1", "refund_amount_inr": 500.0, "agent_id": "A1"},
        {"ticket_id": "T2", "resolved_order_id": "ORD-1", "refund_amount_inr": 500.0, "agent_id": "A1"},
        {"ticket_id": "T3", "resolved_order_id": "ORD-2", "refund_amount_inr": 500.0, "agent_id": "A1"},
    ])

    findings = evaluate_r3_multiple_refunds(ledger)
    assert len(findings) == 2  # T1 and T2 belong to ORD-1
    tids = [f["ticket_id"] for f in findings]
    assert "T1" in tids and "T2" in tids
    assert "T3" not in tids


def test_r5_goodwill_cap_never_flags_gw_other_blindly():
    ledger = pd.DataFrame([
        # Case 1: Dropdown is GW-OTHER, but AI determined true_reason = OTHER -> NOT FLAGGED
        {"ticket_id": "T1", "original_reason_code": "GW-OTHER", "refund_amount_inr": 1200.0, "agent_id": "A1"},
        
        # Case 2: AI determined true_reason = GOODWILL, refund > 500 -> FLAGGED
        {"ticket_id": "T2", "original_reason_code": "GW-OTHER", "refund_amount_inr": 1200.0, "agent_id": "A1"},
    ])

    classifications = pd.DataFrame([
        {"ticket_id": "T1", "true_reason": "OTHER", "evidence": "general inquiry", "code_matches_text": False, "confidence": 0.9},
        {"ticket_id": "T2", "true_reason": "GOODWILL", "evidence": "apology credit for delay", "code_matches_text": True, "confidence": 0.95},
    ])

    findings = evaluate_r5_goodwill_cap(ledger, classifications)
    assert len(findings) == 1
    assert findings[0]["ticket_id"] == "T2"
    assert findings[0]["observed_excess_inr"] == 700.0  # 1200 - 500


def test_non_overlapping_exposure():
    findings = pd.DataFrame([
        {"finding_type": "REFUND_PLUS_REPLACEMENT", "ticket_id": "T1", "resolved_order_id": "ORD-1", "refund_amount_inr": 1000.0, "observed_excess_inr": 1000.0},
        {"finding_type": "REFUND_EXCEEDS_ORDER_VALUE", "ticket_id": "T1", "resolved_order_id": "ORD-1", "refund_amount_inr": 1000.0, "observed_excess_inr": 300.0},  # Overlap on T1
        {"finding_type": "REFUND_PLUS_REPLACEMENT", "ticket_id": "T2", "resolved_order_id": "ORD-2", "refund_amount_inr": 500.0, "observed_excess_inr": 500.0},
    ])

    ledger = pd.DataFrame()
    exp = calculate_non_overlapping_exposure(findings, ledger)

    assert exp["refund_plus_replacement_exposure"] == 1500.0
    assert exp["validated_over_refund_exposure"] == 300.0
    assert exp["overlap_count"] == 1
    assert exp["non_overlapping_review_exposure"] == 1800.0  # R1 (1500) + R2 (300)


def test_multi_ticket_order_r2_exposure_deduplication():
    """Regression test proving that a multi-ticket order under R2 cannot double-count R2 excess."""
    ledger = pd.DataFrame([
        {"ticket_id": "T1", "resolved_order_id": "ORD-MULTI", "join_confidence": "HIGH_CONFIDENCE", "refund_amount_inr": 1000.0, "agent_id": "A1"},
        {"ticket_id": "T2", "resolved_order_id": "ORD-MULTI", "join_confidence": "HIGH_CONFIDENCE", "refund_amount_inr": 1000.0, "agent_id": "A1"},
        {"ticket_id": "T3", "resolved_order_id": "ORD-MULTI", "join_confidence": "HIGH_CONFIDENCE", "refund_amount_inr": 1000.0, "agent_id": "A1"},
    ])
    orders = pd.DataFrame([
        {"order_id": "ORD-MULTI", "order_value_inr": 2000.0},
    ])

    r2_findings = evaluate_r2_refund_exceeds_order(ledger, orders)
    assert len(r2_findings) == 3  # 3 tickets belong to ORD-MULTI
    for f in r2_findings:
        assert f["observed_excess_inr"] == 1000.0

    exp = calculate_non_overlapping_exposure(pd.DataFrame(r2_findings), ledger)

    # R2 order excess MUST be counted ONCE (1000.0), NOT 3 times (3000.0)
    assert exp["validated_over_refund_exposure"] == 1000.0
    assert exp["non_overlapping_review_exposure"] == 1000.0

