import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any
import pandas as pd
import streamlit as st


def render_header():
    """Renders clean Finance & Operations top header."""
    st.markdown("""
        <div style="background-color: #0f172a; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 6px solid #3b82f6;">
            <h1 style="color: #f8fafc; margin: 0; font-size: 1.8rem;">Vireo Refund Truth & Leakage Intelligence</h1>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0; font-size: 0.95rem;">
                Auditable Finance Ledger • Growth Explanation • Policy Control Exceptions • Ticket Evidence Explorer
            </p>
        </div>
    """, unsafe_allow_html=True)


def render_kpi_cards(
    canonical_val: float,
    canonical_cases: int,
    refund_rate: float,
    val_per_case: float,
    review_exposure: float
):
    """Renders executive KPI cards with explicit exposure disclaimers."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Canonical Refund Value",
            value=f"₹{canonical_val:,.0f}",
            help="Reconciled single source of truth refund total across 18 months"
        )
    with col2:
        st.metric(
            label="Canonical Cases",
            value=f"{canonical_cases:,}",
            help="Unique canonical refund tickets (deduplicated)"
        )
    with col3:
        st.metric(
            label="Refund Rate",
            value=f"{refund_rate*100:.2f}%",
            help="Canonical refund cases / total support ticket volume"
        )
    with col4:
        st.metric(
            label="₹ / Refund Case",
            value=f"₹{val_per_case:,.0f}",
            help="Average refund amount per canonical refund event"
        )
    with col5:
        st.metric(
            label="Observed Review Exposure",
            value=f"₹{review_exposure:,.0f}",
            delta="Review Signal",
            delta_color="off",
            help="Deduplicated non-overlapping value across policy flags. NOT confirmed financial loss."
        )

    st.caption("⚠️ **Notice:** *Observed Review Exposure represents policy exceptions flagged for operational audit. It does not constitute confirmed financial loss.*")


def render_exposure_derivation_box(control_summary: Dict[str, Any]):
    """Renders mathematically consistent exposure derivation box."""
    r1 = control_summary.get("refund_plus_replacement", {})
    r2 = control_summary.get("refund_exceeds_order", {})
    exp = control_summary.get("non_overlapping_review_exposure", {})
    overlap = control_summary.get("overlap", {})

    r1_val = float(r1.get("refund_value_inr", 0.0))
    r2_excess = float(r2.get("excess_value_inr", 0.0))
    non_overlap_val = float(exp.get("value_inr", 0.0))
    overlap_count = int(overlap.get("overlapping_cases_count", 0))

    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 1.2rem; border-radius: 8px; border: 1px solid #334155; margin: 1rem 0;">
            <h4 style="color: #38bdf8; margin-top: 0;">📐 Mathematically Clean Exposure Derivation</h4>
            <table style="width: 100%; color: #e2e8f0; font-size: 0.95rem;">
                <tr>
                    <td><strong>R1 Refund + Replacement Exposure:</strong></td>
                    <td style="text-align: right;">₹{r1_val:,.2f} ({r1.get('cases', 0)} cases)</td>
                </tr>
                <tr>
                    <td><strong>R2 Validated Over-Refund Excess:</strong></td>
                    <td style="text-align: right;">₹{r2_excess:,.2f} ({r2.get('orders', 0)} orders)</td>
                </tr>
                <tr>
                    <td><strong>Overlapping Cases (Deduplicated):</strong></td>
                    <td style="text-align: right;">{overlap_count} overlapping tickets</td>
                </tr>
                <tr style="border-top: 1px solid #475569; font-weight: bold; font-size: 1.05rem; color: #f1f5f9;">
                    <td>TOTAL NON-OVERLAPPING REVIEW EXPOSURE:</td>
                    <td style="text-align: right; color: #f43f5e;">₹{non_overlap_val:,.2f}</td>
                </tr>
            </table>
            <p style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.8rem; margin-bottom: 0;">
                <em>Label: OBSERVED REVIEW EXPOSURE — NOT CONFIRMED FINANCIAL LOSS. Calculated by taking maximum finding exposure per ticket ID.</em>
            </p>
        </div>
    """, unsafe_allow_html=True)


def render_evidence_card(finding_row: pd.Series, ledger_df: pd.DataFrame, class_df: pd.DataFrame):
    """Renders structured evidence card for selected finding in Evidence Explorer."""
    tid = str(finding_row["ticket_id"])

    # Lookup ticket in ledger and classifications
    ledger_matches = ledger_df[ledger_df["ticket_id"] == tid]
    ledger_row = ledger_matches.iloc[0] if not ledger_matches.empty else pd.Series()

    class_matches = class_df[class_df["ticket_id"] == tid]
    class_row = class_matches.iloc[0] if not class_matches.empty else pd.Series()

    st.markdown(f"### 🔍 Ticket Evidence Explorer — Ticket ID: `{tid}`")

    # Section 1: Finding Overview
    st.subheader("1. Finding & Policy Classification")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**Rule ID:** `{finding_row.get('rule_id')}`")
        st.write(f"**Finding Type:** `{finding_row.get('finding_type')}`")
    with c2:
        st.write(f"**Review Status:** 🟡 `{finding_row.get('review_status', 'REVIEW_REQUIRED')}`")
        st.write(f"**Confidence:** `{finding_row.get('confidence', 'HIGH')}`")
    with c3:
        st.write("**Policy Reference:**")
        st.info(finding_row.get("policy_rule") or finding_row.get("policy_reference") or "Policy §3/4/5")

    st.markdown("---")

    # Section 2: Financial Breakdown
    st.subheader("2. Financial Context")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.metric("Refund Amount", f"₹{float(finding_row.get('financial_amount', 0.0)):,.2f}")
    with f2:
        st.metric("Observed Excess", f"₹{float(finding_row.get('observed_excess_inr', 0.0)):,.2f}")
    with f3:
        ord_val = ledger_row.get("order_value_inr")
        st.metric("Order Value", f"₹{float(ord_val):,.2f}" if pd.notnull(ord_val) else "N/A")
    with f4:
        unit_c = ledger_row.get("unit_cost_inr")
        st.metric("Unit Cost", f"₹{float(unit_c):,.2f}" if pd.notnull(unit_c) else "N/A")

    st.write(f"**Calculation Description:** {finding_row.get('calculation_description') or 'Policy condition met'}")

    st.markdown("---")

    # Section 3: Text & AI Interpretation Evidence
    st.subheader("3. Text Evidence & AI Reason Analysis")
    t1, t2, t3 = st.columns(3)
    with t1:
        st.write(f"**Original Dropdown Reason:** `{finding_row.get('original_reason_code')}`")
    with t2:
        st.write(f"**AI Derived True Reason:** `{class_row.get('true_reason', finding_row.get('true_reason', 'UNKNOWN'))}`")
    with t3:
        st.write(f"**Classification Method:** `{class_row.get('classification_method', 'DETERMINISTIC')}`")

    st.write("**Extracted Text Snippet / Evidence:**")
    ev_text = class_row.get("evidence") or finding_row.get("evidence_text") or "N/A"
    st.code(ev_text, language="text")

    with st.expander("📄 View Full Customer Message & Agent Notes", expanded=False):
        st.write("**Customer Opening Message:**")
        st.info(ledger_row.get("customer_message") or "N/A")
        st.write("**Agent Closing Note:**")
        st.success(ledger_row.get("agent_notes") or "N/A")

    st.markdown("---")

    # Section 4: Operational Provenance
    st.subheader("4. Operational Provenance & Context")
    o1, o2, o3, o4 = st.columns(4)
    with o1:
        st.write(f"**Agent ID:** `{ledger_row.get('agent_id') or finding_row.get('agent_id')}`")
        st.write(f"**Team:** `{ledger_row.get('team') or finding_row.get('team')}`")
    with o2:
        st.write(f"**Customer ID:** `{ledger_row.get('customer_id')}`")
        st.write(f"**Resolved Order ID:** `{ledger_row.get('resolved_order_id') or 'None'}`")
    with o3:
        st.write(f"**Product SKU:** `{ledger_row.get('product_sku')}`")
        st.write(f"**Replacement Issued:** `{ledger_row.get('replacement_issued')}`")
    with o4:
        st.write(f"**Entity Match Method:** `{ledger_row.get('join_method')}`")
        st.write(f"**Match Confidence:** `{ledger_row.get('join_confidence')}`")
