import pytest
import pandas as pd
import numpy as np

from src.analytics.metrics import safe_divide, calculate_pct_change, calculate_pp_change
from src.analytics.reasons import analyze_refund_reasons, REASON_TAXONOMY_MAP
from src.analytics.agents import analyze_teams, analyze_agents
from src.analytics.trends import generate_monthly_analysis, generate_quarterly_analysis, decompose_refund_growth, run_analytics


def test_metrics_utilities():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(None, 5) == 0.0

    assert calculate_pct_change(100, 150) == 50.0
    assert calculate_pct_change(100, 50) == -50.0
    assert calculate_pct_change(0, 100) == 0.0

    assert calculate_pp_change(0.20, 0.25) == 5.0
    assert calculate_pp_change(0.25, 0.20) == -5.0


def test_reason_taxonomy_mapping():
    ledger = pd.DataFrame([
        {"ticket_id": "T1", "original_reason_code": "GW-OTHER", "refund_amount_inr": 1000.0},
        {"ticket_id": "T2", "original_reason_code": "GW-OTHER", "refund_amount_inr": 500.0},
        {"ticket_id": "T3", "original_reason_code": "DUP-PAYMENT", "refund_amount_inr": 2000.0},
    ])

    result = analyze_refund_reasons(ledger)
    res_map = result.set_index("normalized_reason").to_dict(orient="index")

    assert res_map["Goodwill / Other"]["refund_cases"] == 2
    assert res_map["Goodwill / Other"]["refund_value_inr"] == 1500.0
    assert res_map["Duplicate Payment"]["refund_cases"] == 1
    assert res_map["Duplicate Payment"]["refund_value_inr"] == 2000.0


def test_growth_decomposition_volume_driver():
    quarterly_df = pd.DataFrame([
        {
            "quarter": "2025Q1",
            "total_tickets": 1000,
            "refund_cases": 200,
            "refund_rate": 0.20,
            "refund_value_inr": 500000.0,
            "refund_value_per_ticket_inr": 500.0,
            "refund_value_per_refund_case_inr": 2500.0,
        },
        {
            "quarter": "2026Q2",
            "total_tickets": 2200,
            "refund_cases": 440,
            "refund_rate": 0.20,
            "refund_value_inr": 1100000.0,
            "refund_value_per_ticket_inr": 500.0,
            "refund_value_per_refund_case_inr": 2500.0,
        },
    ])
    monthly_df = pd.DataFrame([{"total_tickets": 3200, "refund_cases": 640, "refund_rate": 0.20}])

    decomposition = decompose_refund_growth(monthly_df, quarterly_df)
    assert decomposition["primary_driver"] == "VOLUME"
    assert decomposition["quarterly_comparison"]["ticket_volume_change_pct"] == 120.0
    assert decomposition["quarterly_comparison"]["refund_rate_change_pp"] == 0.0


def test_agent_review_signal_logic():
    canonical_tickets = pd.DataFrame([
        {"ticket_id": f"T{i}", "agent_id": "A1"} for i in range(40)
    ] + [
        {"ticket_id": f"T_B{i}", "agent_id": "A2"} for i in range(40)
    ])

    ledger = pd.DataFrame([
        {"ticket_id": f"T{i}", "agent_id": "A1", "refund_amount_inr": 100.0} for i in range(12)  # 12/40 = 30%
    ] + [
        {"ticket_id": f"T_B{i}", "agent_id": "A2", "refund_amount_inr": 100.0} for i in range(4)   # 4/40 = 10%
    ])

    roster = pd.DataFrame([
        {"agent_id": "A1", "name": "Agent High", "team": "Billing", "tier": 1},
        {"agent_id": "A2", "name": "Agent Low", "team": "Billing", "tier": 1},
    ])

    team_df = analyze_teams(canonical_tickets, ledger, roster)
    agent_df = analyze_agents(canonical_tickets, ledger, roster, team_df, min_tickets_threshold=30, rate_diff_pp_threshold=5.0)

    a1_row = agent_df[agent_df["agent_id"] == "A1"].iloc[0]
    a2_row = agent_df[agent_df["agent_id"] == "A2"].iloc[0]

    # Team rate is (12+4)/80 = 20%
    # A1 rate is 30% -> +10pp -> Review signal TRUE
    # A2 rate is 10% -> -10pp -> Review signal FALSE
    assert bool(a1_row["agent_review_signal"]) is True
    assert bool(a2_row["agent_review_signal"]) is False


def test_full_analytics_pipeline():
    res = run_analytics()

    assert len(res["monthly_df"]) == 18
    assert len(res["quarterly_df"]) == 6
    assert res["growth_json"]["primary_driver"] == "VOLUME"
    assert res["monthly_df"]["refund_cases"].sum() == 2340
    assert round(res["monthly_df"]["refund_value_inr"].sum(), 2) == 6709932.0
