import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

import pandas as pd
from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def build_evidence_object(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Formats a control finding into a fully auditable Evidence Object."""
    return {
        "finding_id": finding["finding_id"],
        "rule_id": finding["rule_id"],
        "finding_type": finding["finding_type"],
        "ticket_id": finding["ticket_id"],
        "resolved_order_id": finding.get("resolved_order_id"),
        "agent_id": finding["agent_id"],
        "team": finding.get("team"),
        "financial_amount": finding.get("refund_amount_inr"),
        "observed_excess_inr": finding.get("observed_excess_inr", 0.0),
        "original_reason_code": finding.get("original_reason_code"),
        "true_reason": finding.get("true_reason"),
        "policy_rule": finding.get("policy_reference"),
        "source_fields": finding.get("source_fields", []),
        "evidence_text": finding.get("evidence"),
        "calculation_description": finding.get("calculation_description"),
        "confidence": finding.get("confidence", "HIGH"),
        "review_status": finding.get("review_status", "REVIEW_REQUIRED"),
    }


def save_control_outputs(
    all_findings: List[Dict[str, Any]],
    exposure_summary: Dict[str, Any],
    agent_review_signals_count: int
) -> Tuple[Path, Path]:
    """Saves outputs/control_findings.csv and outputs/control_summary.json."""
    evidence_objects = [build_evidence_object(f) for f in all_findings]
    findings_df = pd.DataFrame(evidence_objects)

    findings_path = OUTPUT_DIR / "control_findings.csv"
    findings_df.to_csv(findings_path, index=False)
    logger.info(f"Saved {len(findings_df)} control findings to {findings_path}")

    # Build summary JSON
    findings_by_type = findings_df["finding_type"].value_counts().to_dict() if not findings_df.empty else {}

    r1_df = findings_df[findings_df["finding_type"] == "REFUND_PLUS_REPLACEMENT"] if not findings_df.empty else pd.DataFrame()
    r2_df = findings_df[findings_df["finding_type"] == "REFUND_EXCEEDS_ORDER_VALUE"] if not findings_df.empty else pd.DataFrame()
    r3_df = findings_df[findings_df["finding_type"] == "MULTIPLE_REFUNDS"] if not findings_df.empty else pd.DataFrame()
    r4_df = findings_df[findings_df["finding_type"] == "REASON_CODE_MISMATCH"] if not findings_df.empty else pd.DataFrame()
    r5_df = findings_df[findings_df["finding_type"] == "GOODWILL_CAP_REVIEW"] if not findings_df.empty else pd.DataFrame()

    control_summary = {
        "refund_plus_replacement": {
            "cases": len(r1_df),
            "refund_value_inr": float(r1_df["financial_amount"].sum()) if not r1_df.empty else 0.0,
        },
        "refund_exceeds_order": {
            "orders": int(r2_df["resolved_order_id"].nunique()) if not r2_df.empty else 0,
            "excess_value_inr": float(r2_df.drop_duplicates(subset=["resolved_order_id"])["observed_excess_inr"].sum()) if not r2_df.empty else 0.0,
        },
        "multiple_refunds": {
            "orders": int(r3_df["resolved_order_id"].nunique()) if not r3_df.empty else 0,
            "total_refund_value_inr": float(r3_df["financial_amount"].sum()) if not r3_df.empty else 0.0,
        },
        "reason_code_mismatch": {
            "cases": len(r4_df),
            "refund_value_inr": float(r4_df["financial_amount"].sum()) if not r4_df.empty else 0.0,
        },
        "goodwill_cap_review": {
            "cases": len(r5_df),
            "refund_value_inr": float(r5_df["financial_amount"].sum()) if not r5_df.empty else 0.0,
        },
        "agent_review_signals": {
            "agents_count": agent_review_signals_count,
            "threshold": "minimum 30 tickets AND agent_rate >= team_rate + 5.0 pp",
        },
        "overlap": {
            "overlapping_cases_count": exposure_summary["overlap_count"],
        },
        "non_overlapping_review_exposure": {
            "value_inr": exposure_summary["non_overlapping_review_exposure"],
            "label": "OBSERVED REVIEW EXPOSURE (Not confirmed financial loss)",
        },
        "findings_by_type_counts": {str(k): int(v) for k, v in findings_by_type.items()},
    }

    summary_path = OUTPUT_DIR / "control_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(control_summary, f, indent=2)
    logger.info(f"Saved control summary JSON to {summary_path}")

    return findings_path, summary_path
