import sys
from pathlib import Path

# Ensure project root is in sys.path when running via 'streamlit run src/dashboard/app.py'
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import pandas as pd
import streamlit as st

from src.dashboard.data_loader import load_all_artifacts
from src.dashboard.components import (
    render_header,
    render_kpi_cards,
    render_exposure_derivation_box,
    render_evidence_card,
)

# Page Configuration
st.set_page_config(
    page_title="Vireo Refund Intelligence",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    render_header()

    # Load artifacts dynamically
    try:
        data = load_all_artifacts()
    except Exception as e:
        st.error(f"❌ Error loading system artifacts: {e}")
        st.stop()

    ledger_df = data["ledger"]
    monthly_df = data["monthly"]
    quarterly_df = data["quarterly"]
    growth_json = data["growth"]
    reasons_df = data["reasons"]
    teams_df = data["teams"]
    agents_df = data["agents"]
    class_df = data["classifications"]
    findings_df = data["findings"]
    control_sum = data["control_summary"]

    # Sidebar Navigation
    st.sidebar.title("📌 Navigation")
    page = st.sidebar.radio(
        "Select Page",
        [
            "1. Executive Summary",
            "2. Refund Trends",
            "3. Refund Reasons",
            "4. Control Findings",
            "5. Evidence Explorer",
            "6. Agent Review"
        ]
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Export Datasets")
    st.sidebar.download_button("Canonical Ledger CSV", ledger_df.to_csv(index=False), "canonical_refund_ledger.csv", "text/csv")
    st.sidebar.download_button("Control Findings CSV", findings_df.to_csv(index=False), "control_findings.csv", "text/csv")
    st.sidebar.download_button("AI Classifications CSV", class_df.to_csv(index=False), "refund_text_classifications.csv", "text/csv")
    st.sidebar.download_button("Monthly Analysis CSV", monthly_df.to_csv(index=False), "monthly_refund_analysis.csv", "text/csv")

    # =========================================================================
    # PAGE 1: EXECUTIVE SUMMARY
    # =========================================================================
    if page == "1. Executive Summary":
        st.subheader("📊 Executive Summary")

        canon_val = float(ledger_df["refund_amount_inr"].sum())
        canon_cases = len(ledger_df)
        total_tickets = int(monthly_df["total_tickets"].sum())
        ref_rate = canon_cases / total_tickets if total_tickets > 0 else 0.0
        val_per_case = canon_val / canon_cases if canon_cases > 0 else 0.0
        exp_val = float(control_sum.get("non_overlapping_review_exposure", {}).get("value_inr", 0.0))

        render_kpi_cards(canon_val, canon_cases, ref_rate, val_per_case, exp_val)

        st.markdown("---")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 📈 Refund Growth Driver Explanation")
            q_comp = growth_json.get("quarterly_comparison", {})
            p_driver = growth_json.get("primary_driver", "VOLUME")

            st.info(f"**Primary Driver:** `{p_driver}`")
            st.markdown(f"""
            - **Analysis Period:** {q_comp.get('initial_quarter')} → {q_comp.get('final_quarter')}
            - **Refund Outlay Change:** **+{q_comp.get('refund_value_change_pct')}%** (₹{q_comp.get('refund_value_initial_inr'):,.0f} → ₹{q_comp.get('refund_value_final_inr'):,.0f})
            - **Support Ticket Volume:** **+{q_comp.get('ticket_volume_change_pct')}%** (1,053 → 2,277 tickets)
            - **Refund Rate Difference:** **{q_comp.get('refund_rate_change_pp'):+.2f} pp** (20.13% → 20.77%)
            - **Refund Value / Ticket:** **{q_comp.get('refund_value_per_ticket_change_pct'):+.2f}%** (₹578.90 → ₹562.07)
            """)

            st.success("**Empirical Insight:** Refund outlay grew because total support ticket volume doubled (+116%). Frontline refund propensity remained flat (~20%), proving that frontline refund behavior did NOT deteriorate.")

        with col2:
            st.markdown("### 🛡️ Control Rules Summary (R1 – R5)")
            r1 = control_sum.get("refund_plus_replacement", {})
            r2 = control_sum.get("refund_exceeds_order", {})
            r3 = control_sum.get("multiple_refunds", {})
            r4 = control_sum.get("reason_code_mismatch", {})
            r5 = control_sum.get("goodwill_cap_review", {})

            ctrl_rows = [
                {"Rule": "R1 — Refund + Replacement", "Cases/Orders": f"{r1.get('cases', 0)} cases", "Observed Value": f"₹{r1.get('refund_value_inr', 0.0):,.2f}", "Status": "Review Signal"},
                {"Rule": "R2 — Refund Exceeds Order Value", "Cases/Orders": f"{r2.get('orders', 0)} orders", "Observed Value": f"₹{r2.get('excess_value_inr', 0.0):,.2f}", "Status": "Observed Excess"},
                {"Rule": "R3 — Multiple Refunds per Order", "Cases/Orders": f"{r3.get('orders', 0)} orders", "Observed Value": f"₹{r3.get('total_refund_value_inr', 0.0):,.2f}", "Status": "Process Signal"},
                {"Rule": "R4 — Reason Code Mismatch", "Cases/Orders": f"{r4.get('cases', 0)} cases", "Observed Value": f"₹{r4.get('refund_value_inr', 0.0):,.2f}", "Status": "Classification Signal"},
                {"Rule": "R5 — Goodwill Cap Review", "Cases/Orders": f"{r5.get('cases', 0)} cases", "Observed Value": f"₹{r5.get('refund_value_inr', 0.0):,.2f}", "Status": "Cap Review"},
            ]
            st.table(pd.DataFrame(ctrl_rows))

        render_exposure_derivation_box(control_sum)

        st.caption("ℹ️ **Reconciliation Note:** The canonical ledger reconciles normalized source records after deduplication of migrated pairs and strict entity resolution.")

    # =========================================================================
    # PAGE 2: REFUND TRENDS
    # =========================================================================
    elif page == "2. Refund Trends":
        st.subheader("📈 Refund Trends & Growth Decomposition")

        st.markdown("### Monthly Metrics (Jan 2025 – Jun 2026)")
        
        # Monthly charts
        tab1, tab2, tab3 = st.tabs(["Ticket Volume vs Refund Cases", "Refund Value Outlay", "Refund Rate & ₹/Ticket"])
        
        with tab1:
            st.bar_chart(monthly_df.set_index("month")[["total_tickets", "refund_cases"]])
        with tab2:
            st.line_chart(monthly_df.set_index("month")["refund_value_inr"])
        with tab3:
            st.line_chart(monthly_df.set_index("month")[["refund_rate", "refund_value_per_ticket_inr"]])

        st.markdown("---")
        st.markdown("### Quarterly Analysis & Driver Decomposition")
        st.dataframe(quarterly_df, use_container_width=True)

    # =========================================================================
    # PAGE 3: REFUND REASONS
    # =========================================================================
    elif page == "3. Refund Reasons":
        st.subheader("🏷️ Refund Reasons: Original Dropdown vs AI True Reason")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Original Reason Code Outlay")
            st.dataframe(reasons_df, use_container_width=True)

        with col2:
            st.markdown("#### AI Interpreted True Reason Distribution")
            ai_dist = class_df["true_reason"].value_counts().reset_index()
            ai_dist.columns = ["true_reason", "case_count"]
            st.dataframe(ai_dist, use_container_width=True)

        st.markdown("---")
        st.markdown("### ⚠️ Reason Code Mismatch Analysis (`GW-OTHER` Breakdown)")
        st.caption("`GW-OTHER` is a heterogeneous catch-all bucket. AI text classification reveals specific underlying reasons:")

        gw_cases = class_df[class_df["original_reason_code"] == "GW-OTHER"]
        gw_breakdown = gw_cases["true_reason"].value_counts().reset_index()
        gw_breakdown.columns = ["AI Derived True Reason", "Case Count"]
        st.dataframe(gw_breakdown, use_container_width=True)

    # =========================================================================
    # PAGE 4: CONTROL FINDINGS
    # =========================================================================
    elif page == "4. Control Findings":
        st.subheader("🛡️ Filterable Control Findings Center")

        # Filters
        f1, f2, f3 = st.columns(3)
        with f1:
            finding_types = ["ALL"] + sorted(list(findings_df["finding_type"].unique()))
            selected_type = st.selectbox("Filter Finding Type", finding_types)
        with f2:
            confidence_list = ["ALL"] + sorted(list(findings_df["confidence"].unique()))
            selected_conf = st.selectbox("Filter Confidence", confidence_list)
        with f3:
            teams_list = ["ALL"] + sorted(list(findings_df["team"].dropna().unique()))
            selected_team = st.selectbox("Filter Team", teams_list)

        filtered_df = findings_df.copy()
        if selected_type != "ALL":
            filtered_df = filtered_df[filtered_df["finding_type"] == selected_type]
        if selected_conf != "ALL":
            filtered_df = filtered_df[filtered_df["confidence"] == selected_conf]
        if selected_team != "ALL":
            filtered_df = filtered_df[filtered_df["team"] == selected_team]

        st.markdown(f"**Showing {len(filtered_df):,} findings:**")
        display_cols = ["finding_id", "rule_id", "finding_type", "ticket_id", "resolved_order_id", "agent_id", "team", "financial_amount", "observed_excess_inr", "confidence", "review_status"]
        st.dataframe(filtered_df[[c for c in display_cols if c in filtered_df.columns]], use_container_width=True)

    # =========================================================================
    # PAGE 5: EVIDENCE EXPLORER
    # =========================================================================
    elif page == "5. Evidence Explorer":
        st.subheader("🔍 Ticket-Level Evidence Explorer")
        st.caption("Select a finding to inspect the complete auditable evidence chain.")

        finding_ids = list(findings_df["finding_id"].unique())
        selected_fid = st.selectbox("Select Finding ID to Inspect", finding_ids)

        if selected_fid:
            selected_row = findings_df[findings_df["finding_id"] == selected_fid].iloc[0]
            render_evidence_card(selected_row, ledger_df, class_df)

    # =========================================================================
    # PAGE 6: AGENT REVIEW
    # =========================================================================
    elif page == "6. Agent Review":
        st.subheader("👥 Contextual Agent Review Signals")
        st.caption("⚠️ **Notice:** *Rates are signals for operational review and do not establish individual causality. Evaluated against team benchmarks (min 30 tickets, >= 5.0 pp above team rate).*")

        st.markdown("### Team Benchmark Overview")
        st.dataframe(teams_df, use_container_width=True)

        st.markdown("---")
        st.markdown("### Agent Review Signals (>= 5.0 pp Above Team Benchmark)")
        flagged_agents = agents_df[agents_df["agent_review_signal"] == True]
        if flagged_agents.empty:
            st.success("✅ Zero agents exceeded the within-team threshold (>= 5.0 pp above team benchmark with >= 30 tickets).")
        else:
            st.dataframe(flagged_agents, use_container_width=True)

        st.markdown("---")
        st.markdown("### All Agents Performance")
        st.dataframe(agents_df, use_container_width=True)


if __name__ == "__main__":
    main()
