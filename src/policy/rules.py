from typing import List, Dict, Any
import pandas as pd

from src.ai.reason_classifier import REASON_CODE_TO_TAXONOMY


def evaluate_r1_refund_plus_replacement(ledger_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Rule R1: Refund + Replacement.
    
    Identifies tickets where refund was issued AND a replacement unit was sent.
    """
    findings = []
    for _, row in ledger_df.iterrows():
        repl_flag = str(row.get("replacement_issued", "")).strip().upper()
        amt = float(row.get("refund_amount_inr", 0.0))

        if amt > 0 and repl_flag == "Y":
            findings.append({
                "finding_id": f"R1-{row['ticket_id']}",
                "rule_id": "R1",
                "finding_type": "REFUND_PLUS_REPLACEMENT",
                "ticket_id": str(row["ticket_id"]),
                "resolved_order_id": str(row.get("resolved_order_id") or "") or None,
                "agent_id": str(row["agent_id"]),
                "team": str(row.get("team") or ""),
                "refund_amount_inr": round(amt, 2),
                "observed_excess_inr": round(amt, 2),  # Full refund is review exposure
                "original_reason_code": str(row.get("original_reason_code") or ""),
                "policy_reference": "Policy §4 — Refund + Replacement prohibited for same order",
                "source_fields": ["refund_amount_inr", "replacement_issued"],
                "calculation_description": "refund_amount_inr > 0 AND replacement_issued == 'Y'",
                "confidence": "HIGH",
                "review_status": "REVIEW_REQUIRED",
            })
    return findings


def evaluate_r2_refund_exceeds_order(ledger_df: pd.DataFrame, orders_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Rule R2: Refund Exceeds Order Value.
    
    CRITICAL: Only relies on HIGH_CONFIDENCE explicit order matches.
    Identifies orders where total canonical refunds exceed original order value.
    """
    # Strict filter: ONLY HIGH_CONFIDENCE explicit order matches
    high_conf_df = ledger_df[
        (ledger_df["join_confidence"] == "HIGH_CONFIDENCE") &
        (ledger_df["resolved_order_id"].notnull())
    ].copy()

    order_value_map = orders_df.set_index("order_id")["order_value_inr"].to_dict()

    findings = []
    grouped = high_conf_df.groupby("resolved_order_id")

    for order_id, group in grouped:
        total_refunded = float(group["refund_amount_inr"].sum())
        order_val = float(order_value_map.get(order_id, 0.0))

        if order_val > 0 and total_refunded > order_val:
            excess = total_refunded - order_val
            ticket_ids = group["ticket_id"].tolist()

            for _, row in group.iterrows():
                findings.append({
                    "finding_id": f"R2-{order_id}-{row['ticket_id']}",
                    "rule_id": "R2",
                    "finding_type": "REFUND_EXCEEDS_ORDER_VALUE",
                    "ticket_id": str(row["ticket_id"]),
                    "resolved_order_id": str(order_id),
                    "agent_id": str(row["agent_id"]),
                    "team": str(row.get("team") or ""),
                    "refund_amount_inr": round(float(row["refund_amount_inr"]), 2),
                    "observed_excess_inr": round(excess, 2),  # Excess amount over order value
                    "original_reason_code": str(row.get("original_reason_code") or ""),
                    "policy_reference": "Policy §3 — Total refund amount cannot exceed original order value",
                    "source_fields": ["resolved_order_id", "refund_amount_inr", "order_value_inr"],
                    "calculation_description": f"SUM(refunds) ₹{total_refunded:,.2f} > order_value ₹{order_val:,.2f} (Excess: ₹{excess:,.2f})",
                    "confidence": "HIGH",
                    "review_status": "REVIEW_REQUIRED",
                })
    return findings


def evaluate_r3_multiple_refunds(ledger_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Rule R3: Multiple Refunds against the same order.
    
    Identifies orders with >1 canonical refund event (independent from R2).
    """
    valid_orders_df = ledger_df[ledger_df["resolved_order_id"].notnull()].copy()
    grouped = valid_orders_df.groupby("resolved_order_id")

    findings = []
    for order_id, group in grouped:
        if len(group) > 1:
            for _, row in group.iterrows():
                findings.append({
                    "finding_id": f"R3-{order_id}-{row['ticket_id']}",
                    "rule_id": "R3",
                    "finding_type": "MULTIPLE_REFUNDS",
                    "ticket_id": str(row["ticket_id"]),
                    "resolved_order_id": str(order_id),
                    "agent_id": str(row["agent_id"]),
                    "team": str(row.get("team") or ""),
                    "refund_amount_inr": round(float(row["refund_amount_inr"]), 2),
                    "observed_excess_inr": 0.0,  # Multiple refunds alone is a process signal, not automatic excess
                    "original_reason_code": str(row.get("original_reason_code") or ""),
                    "policy_reference": "Policy §3 — Multiple refunds on individual order",
                    "source_fields": ["resolved_order_id", "ticket_id"],
                    "calculation_description": f"Order {order_id} has {len(group)} distinct refund events",
                    "confidence": "HIGH",
                    "review_status": "REVIEW_REQUIRED",
                })
    return findings


def evaluate_r4_reason_code_mismatch(
    ledger_df: pd.DataFrame,
    classifications_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """Rule R4: Reason Code Mismatch.
    
    Identifies tickets where the agent's dropdown reason code materially conflicts with AI text classification.
    """
    class_map = classifications_df.set_index("ticket_id").to_dict(orient="index")

    findings = []
    for _, row in ledger_df.iterrows():
        tid = str(row["ticket_id"])
        ai_info = class_map.get(tid, {})
        true_reason = ai_info.get("true_reason", "UNKNOWN")
        evidence = ai_info.get("evidence", "")
        code_matches = ai_info.get("code_matches_text", True)
        confidence = float(ai_info.get("confidence", 0.0))

        orig_code = str(row.get("original_reason_code") or "")
        mapped_orig = REASON_CODE_TO_TAXONOMY.get(orig_code, "OTHER")

        if not code_matches and true_reason != "UNKNOWN" and confidence >= 0.70:
            findings.append({
                "finding_id": f"R4-{tid}",
                "rule_id": "R4",
                "finding_type": "REASON_CODE_MISMATCH",
                "ticket_id": tid,
                "resolved_order_id": str(row.get("resolved_order_id") or "") or None,
                "agent_id": str(row["agent_id"]),
                "team": str(row.get("team") or ""),
                "refund_amount_inr": round(float(row["refund_amount_inr"]), 2),
                "observed_excess_inr": 0.0,
                "original_reason_code": orig_code,
                "true_reason": true_reason,
                "evidence": evidence,
                "policy_reference": "Policy §5 — Accurate reason code dropdown selection required",
                "source_fields": ["original_reason_code", "agent_notes", "customer_message"],
                "calculation_description": f"Dropdown code '{orig_code}' ({mapped_orig}) conflicts with derived true reason '{true_reason}'",
                "confidence": "HIGH" if confidence >= 0.90 else "MEDIUM",
                "review_status": "REVIEW_REQUIRED",
            })
    return findings


def evaluate_r5_goodwill_cap(
    ledger_df: pd.DataFrame,
    classifications_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """Rule R5: Goodwill Cap Review.
    
    CRITICAL: Requires AI true_reason == 'GOODWILL' AND refund_amount_inr > 500.
    NEVER flags GW-OTHER blindly.
    """
    class_map = classifications_df.set_index("ticket_id").to_dict(orient="index")

    findings = []
    for _, row in ledger_df.iterrows():
        tid = str(row["ticket_id"])
        amt = float(row.get("refund_amount_inr", 0.0))
        ai_info = class_map.get(tid, {})
        true_reason = ai_info.get("true_reason", "UNKNOWN")
        evidence = ai_info.get("evidence", "")

        if true_reason == "GOODWILL" and amt > 500.0:
            findings.append({
                "finding_id": f"R5-{tid}",
                "rule_id": "R5",
                "finding_type": "GOODWILL_CAP_REVIEW",
                "ticket_id": tid,
                "resolved_order_id": str(row.get("resolved_order_id") or "") or None,
                "agent_id": str(row["agent_id"]),
                "team": str(row.get("team") or ""),
                "refund_amount_inr": round(amt, 2),
                "observed_excess_inr": round(amt - 500.0, 2),  # Excess over ₹500 cap
                "original_reason_code": str(row.get("original_reason_code") or ""),
                "true_reason": "GOODWILL",
                "evidence": evidence,
                "policy_reference": "Policy §5.1 — Goodwill credits capped at ₹500 per ticket without TL signoff",
                "source_fields": ["true_reason", "refund_amount_inr"],
                "calculation_description": f"True Goodwill refund ₹{amt:,.2f} exceeds ₹500 cap (Excess: ₹{amt - 500.0:,.2f})",
                "confidence": "HIGH",
                "review_status": "REVIEW_REQUIRED",
            })
    return findings
