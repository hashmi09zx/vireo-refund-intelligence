import pytest
import pandas as pd
from src.ai.reason_classifier import classify_deterministically, classify_single_ticket
from src.ai.groq_client import classify_text_with_groq


def test_stage1_deterministic_classifier():
    row_dup = pd.Series({"customer_message": "I was charged twice on my card", "agent_notes": "verified PG duplicate", "original_reason_code": "DUP-PAYMENT"})
    res_dup = classify_deterministically(row_dup)
    assert res_dup is not None
    assert res_dup["true_reason"] == "DUPLICATE_PAYMENT"
    assert res_dup["classification_method"] == "DETERMINISTIC"

    row_cancel = pd.Series({"customer_message": "please cancel order before shipping", "agent_notes": "cancelled request", "original_reason_code": "CANCEL"})
    res_cancel = classify_deterministically(row_cancel)
    assert res_cancel is not None
    assert res_cancel["true_reason"] == "CANCELLATION"


def test_groq_client_fallback_handling(monkeypatch):
    # Ensure GROQ_API_KEY is empty for test
    monkeypatch.setenv("GROQ_API_KEY", "")

    res = classify_text_with_groq(
        original_reason_code="GW-OTHER",
        refund_amount_inr=1000.0,
        customer_message="messy ambiguous notes",
        agent_notes="cx ok"
    )

    assert res["true_reason"] == "UNKNOWN"
    assert res["classification_method"] == "GROQ_ERROR"
    assert res["confidence"] == 0.0


def test_groq_exception_never_crashes_pipeline(monkeypatch):
    # Set invalid API key to trigger error handling
    monkeypatch.setenv("GROQ_API_KEY", "gsk_invalid_test_key_123")

    row = pd.Series({
        "ticket_id": "T999",
        "original_reason_code": "GW-OTHER",
        "refund_amount_inr": 1000.0,
        "customer_message": "some ambiguous text",
        "agent_notes": "notes"
    })

    res = classify_single_ticket(row, allow_groq=True)
    assert res["true_reason"] == "UNKNOWN"
    assert res["classification_method"] == "GROQ_ERROR"
    assert res["confidence"] == 0.0
