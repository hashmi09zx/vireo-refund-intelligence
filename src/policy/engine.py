import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List

import pandas as pd

from src.config import OUTPUT_DIR, ORDERS_CSV
from src.ai.reason_classifier import classify_all_refund_tickets
from src.policy.rules import (
    evaluate_r1_refund_plus_replacement,
    evaluate_r2_refund_exceeds_order,
    evaluate_r3_multiple_refunds,
    evaluate_r4_reason_code_mismatch,
    evaluate_r5_goodwill_cap,
)
from src.policy.exposure import calculate_non_overlapping_exposure
from src.policy.findings import save_control_outputs

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_policy_engine() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Runs the Phase 3 Deterministic Policy Engine + AI Text Intelligence pipeline."""
    logger.info("Starting Phase 3 Refund Control Engine & Groq Text Intelligence...")

    # 1. Load canonical refund ledger & order metadata
    ledger_path = OUTPUT_DIR / "canonical_refund_ledger.csv"
    if not ledger_path.exists():
        raise FileNotFoundError("Canonical Refund Ledger missing! Run Phase 1 first.")

    ledger_df = pd.read_csv(ledger_path)
    orders_df = pd.read_csv(ORDERS_CSV)

    # Load agent analysis for review signals count
    agent_path = OUTPUT_DIR / "agent_refund_analysis.csv"
    if agent_path.exists():
        agent_df = pd.read_csv(agent_path)
        agent_review_signals_count = int(agent_df["agent_review_signal"].sum()) if "agent_review_signal" in agent_df.columns else 0
    else:
        agent_review_signals_count = 0

    # 2. Hybrid AI Text Intelligence classification
    logger.info("Running hybrid AI text classification (Stage 1 Deterministic + Stage 2 Groq)...")
    classifications_df = classify_all_refund_tickets(ledger_df)

    # 3. Evaluate Policy Rules
    logger.info("Evaluating deterministic policy rules R1 - R5...")
    r1_findings = evaluate_r1_refund_plus_replacement(ledger_df)
    r2_findings = evaluate_r2_refund_exceeds_order(ledger_df, orders_df)
    r3_findings = evaluate_r3_multiple_refunds(ledger_df)
    r4_findings = evaluate_r4_reason_code_mismatch(ledger_df, classifications_df)
    r5_findings = evaluate_r5_goodwill_cap(ledger_df, classifications_df)

    all_findings = r1_findings + r2_findings + r3_findings + r4_findings + r5_findings
    findings_df = pd.DataFrame(all_findings)

    # 4. Calculate Non-Overlapping Exposure
    exposure_summary = calculate_non_overlapping_exposure(findings_df, ledger_df)

    # 5. Save outputs
    findings_path, summary_path = save_control_outputs(
        all_findings,
        exposure_summary,
        agent_review_signals_count
    )

    with open(summary_path, "r", encoding="utf-8") as f:
        control_summary = json.load(f)

    return findings_df, control_summary


def print_terminal_control_summary(summary: Dict[str, Any], class_df: pd.DataFrame) -> None:
    """Prints concise control summary to terminal."""
    r1 = summary["refund_plus_replacement"]
    r2 = summary["refund_exceeds_order"]
    r3 = summary["multiple_refunds"]
    r4 = summary["reason_code_mismatch"]
    r5 = summary["goodwill_cap_review"]
    agent_sig = summary["agent_review_signals"]
    exp = summary["non_overlapping_review_exposure"]

    counts_by_method = class_df["classification_method"].value_counts().to_dict() if not class_df.empty else {}

    print("\n" + "=" * 65)
    print("      VIREO REFUND CONTROL ENGINE — POLICY & AI SUMMARY      ")
    print("=" * 65)

    print(f"\n[AI TEXT CLASSIFICATION STATS]")
    print(f"  • Stage 1 Deterministic Classifications: {counts_by_method.get('DETERMINISTIC', 0):,}")
    print(f"  • Stage 2 Groq Classifications:          {counts_by_method.get('GROQ', 0):,}")
    print(f"  • Groq Error Fallbacks:                 {counts_by_method.get('GROQ_ERROR', 0):,}")
    print(f"  • Cached Classifications Reused:         {counts_by_method.get('CACHE', 0):,}")
    print(f"  • Total Refund Tickets Analyzed:        {len(class_df):,}")

    print(f"\n[DETERMINISTIC CONTROL RULES SUMMARY]")
    print(f"  • R1 Refund + Replacement:   {r1['cases']:,} cases | Exposure: ₹{r1['refund_value_inr']:,.2f}")
    print(f"  • R2 Refund Exceeds Order:    {r2['orders']:,} orders | Observed Excess: ₹{r2['excess_value_inr']:,.2f}")
    print(f"  • R3 Multiple Refunds:        {r3['orders']:,} orders | Total Refund: ₹{r3['total_refund_value_inr']:,.2f}")
    print(f"  • R4 Reason Code Mismatches:  {r4['cases']:,} cases | Total Refund: ₹{r4['refund_value_inr']:,.2f}")
    print(f"  • R5 Goodwill Cap Review:     {r5['cases']:,} cases | Excess over ₹500: ₹{r5['refund_value_inr']:,.2f}")
    print(f"  • Agent Review Signals:       {agent_sig['agents_count']} agents (>= 5.0 pp above team rate)")

    print(f"\n[NON-OVERLAPPING REVIEW EXPOSURE]")
    print(f"  • Total Non-Overlapping Exposure: ₹{exp['value_inr']:,.2f}")
    print(f"  • Definition:                     {exp['label']}")
    print(f"  • Overlapping Cases Count:        {summary['overlap']['overlapping_cases_count']}")

    print("\n" + "=" * 65 + "\n")


if __name__ == "__main__":
    findings_df, summary = run_policy_engine()
    class_df = pd.read_csv(OUTPUT_DIR / "refund_text_classifications.csv")
    print_terminal_control_summary(summary, class_df)
