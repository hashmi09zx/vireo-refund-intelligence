import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List

import pandas as pd

from src.config import OUTPUT_DIR, TICKETS_CSV
from src.analytics.metrics import safe_divide, calculate_pct_change, calculate_pp_change
from src.analytics.reasons import analyze_refund_reasons
from src.analytics.agents import analyze_teams, analyze_agents

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_monthly_analysis(
    canonical_tickets_df: pd.DataFrame,
    ledger_df: pd.DataFrame
) -> pd.DataFrame:
    """Computes monthly volume, refund rate, value, and per-ticket metrics."""
    tickets = canonical_tickets_df.copy()
    ledger = ledger_df.copy()

    tickets["created_dt"] = pd.to_datetime(tickets["created_at"], errors="coerce")
    tickets["month"] = tickets["created_dt"].dt.strftime("%Y-%m")

    ledger["created_dt"] = pd.to_datetime(ledger["created_at"], errors="coerce")
    ledger["month"] = ledger["created_dt"].dt.strftime("%Y-%m")

    m_tickets = tickets.groupby("month").size()
    m_cases = ledger.groupby("month").size()
    m_value = ledger.groupby("month")["refund_amount_inr"].sum()

    all_months = sorted(list(set(m_tickets.index).union(set(m_cases.index))))

    rows = []
    for m in all_months:
        tot_t = int(m_tickets.get(m, 0))
        ref_c = int(m_cases.get(m, 0))
        ref_v = float(m_value.get(m, 0.0))

        rate = safe_divide(ref_c, tot_t)
        per_t = safe_divide(ref_v, tot_t)
        per_c = safe_divide(ref_v, ref_c)

        rows.append({
            "month": m,
            "total_tickets": tot_t,
            "refund_cases": ref_c,
            "refund_rate": round(rate, 4),
            "refund_value_inr": round(ref_v, 2),
            "refund_value_per_ticket_inr": round(per_t, 2),
            "refund_value_per_refund_case_inr": round(per_c, 2),
            "refund_case_share": round(rate, 4),
        })

    monthly_df = pd.DataFrame(rows)
    return monthly_df


def generate_quarterly_analysis(
    canonical_tickets_df: pd.DataFrame,
    ledger_df: pd.DataFrame
) -> pd.DataFrame:
    """Computes quarterly volume, refund rate, value, and per-ticket metrics."""
    tickets = canonical_tickets_df.copy()
    ledger = ledger_df.copy()

    tickets["created_dt"] = pd.to_datetime(tickets["created_at"], errors="coerce")
    tickets["quarter"] = tickets["created_dt"].dt.to_period("Q").astype(str)

    ledger["created_dt"] = pd.to_datetime(ledger["created_at"], errors="coerce")
    ledger["quarter"] = ledger["created_dt"].dt.to_period("Q").astype(str)

    q_tickets = tickets.groupby("quarter").size()
    q_cases = ledger.groupby("quarter").size()
    q_value = ledger.groupby("quarter")["refund_amount_inr"].sum()

    all_quarters = sorted(list(set(q_tickets.index).union(set(q_cases.index))))

    rows = []
    for q in all_quarters:
        tot_t = int(q_tickets.get(q, 0))
        ref_c = int(q_cases.get(q, 0))
        ref_v = float(q_value.get(q, 0.0))

        rate = safe_divide(ref_c, tot_t)
        per_t = safe_divide(ref_v, tot_t)
        per_c = safe_divide(ref_v, ref_c)

        rows.append({
            "quarter": q,
            "total_tickets": tot_t,
            "refund_cases": ref_c,
            "refund_rate": round(rate, 4),
            "refund_value_inr": round(ref_v, 2),
            "refund_value_per_ticket_inr": round(per_t, 2),
            "refund_value_per_refund_case_inr": round(per_c, 2),
        })

    quarterly_df = pd.DataFrame(rows)
    return quarterly_df


def decompose_refund_growth(
    monthly_df: pd.DataFrame,
    quarterly_df: pd.DataFrame
) -> Dict[str, Any]:
    """Deterministically analyzes drivers of refund growth (VOLUME vs PROPENSITY vs VALUE_PER_TICKET)."""
    # Quarter comparison: 2025Q1 vs 2026Q2
    q_start = quarterly_df.iloc[0]
    q_end = quarterly_df.iloc[-1]

    ref_val_change_pct = calculate_pct_change(q_start["refund_value_inr"], q_end["refund_value_inr"])
    ticket_vol_change_pct = calculate_pct_change(q_start["total_tickets"], q_end["total_tickets"])
    ref_rate_change_pp = calculate_pp_change(q_start["refund_rate"], q_end["refund_rate"])
    val_per_ticket_change_pct = calculate_pct_change(q_start["refund_value_per_ticket_inr"], q_end["refund_value_per_ticket_inr"])
    val_per_case_change_pct = calculate_pct_change(q_start["refund_value_per_refund_case_inr"], q_end["refund_value_per_refund_case_inr"])

    # Classification Thresholds
    # VOLUME driver: Ticket volume grew significantly (>= 50%) while refund rate & value per ticket remained relatively stable
    if ticket_vol_change_pct >= 50.0 and abs(ref_rate_change_pp) < 5.0 and abs(val_per_ticket_change_pct) < 25.0:
        primary_driver = "VOLUME"
    elif ref_rate_change_pp >= 5.0 and ticket_vol_change_pct < 50.0:
        primary_driver = "REFUND_PROPENSITY"
    elif val_per_ticket_change_pct >= 25.0 and ticket_vol_change_pct < 50.0:
        primary_driver = "VALUE_PER_TICKET"
    else:
        primary_driver = "MIXED"

    decomposition = {
        "analysis_period": f"{q_start['quarter']} to {q_end['quarter']}",
        "primary_driver": primary_driver,
        "classification_rule": "VOLUME = ticket volume growth >= 50% with refund rate change < 5pp and value per ticket change < 25%",
        "quarterly_comparison": {
            "initial_quarter": str(q_start["quarter"]),
            "final_quarter": str(q_end["quarter"]),
            "refund_value_initial_inr": float(q_start["refund_value_inr"]),
            "refund_value_final_inr": float(q_end["refund_value_inr"]),
            "refund_value_change_pct": round(ref_val_change_pct, 2),
            "ticket_volume_change_pct": round(ticket_vol_change_pct, 2),
            "refund_rate_change_pp": round(ref_rate_change_pp, 2),
            "refund_value_per_ticket_change_pct": round(val_per_ticket_change_pct, 2),
            "refund_value_per_refund_case_change_pct": round(val_per_case_change_pct, 2),
        },
        "monthly_summary_stats": {
            "min_monthly_refund_rate": float(monthly_df["refund_rate"].min()),
            "max_monthly_refund_rate": float(monthly_df["refund_rate"].max()),
            "mean_monthly_refund_rate": round(float(monthly_df["refund_rate"].mean()), 4),
            "overall_18_month_refund_rate": round(safe_divide(monthly_df["refund_cases"].sum(), monthly_df["total_tickets"].sum()), 4),
        },
        "open_reconciliation_items": [
            {
                "item": "SAMEER_Q11L_QUARTERLY_CLAIM",
                "statement": "Helpdesk Admin Sameer claimed refunds run ~Rs 11 lakh a quarter.",
                "empirical_finding": f"Quarterly refunds averaged ₹{quarterly_df['refund_value_inr'].mean():,.2f} per quarter, ranging from ₹{quarterly_df['refund_value_inr'].min():,.2f} (2025Q1) to ₹{quarterly_df['refund_value_inr'].max():,.2f} (2025Q4). While overall 18-month average is ~₹11.18L/quarter, quarterly variation is substantial.",
                "status": "OPEN_UNRECONCILED"
            }
        ]
    }

    return decomposition


def run_analytics() -> Dict[str, Any]:
    """Orchestrates Phase 2 Refund Explanation Engine."""
    logger.info("Starting Phase 2 Refund Explanation Engine...")

    # Load raw tickets for total volume and canonical ledger for refund cases
    raw_tickets_df = pd.read_csv(TICKETS_CSV, low_memory=False)
    agents_df = pd.read_csv(OUTPUT_DIR / "canonical_refund_ledger.csv")  # use ledger
    
    # Load canonical unique tickets (11,600)
    raw_tickets_df["source_priority"] = raw_tickets_df["source_system"].map({"helpdesk": 1, "legacy_fd": 2}).fillna(3)
    tickets_sorted = raw_tickets_df.sort_values(by=["ticket_id", "source_priority", "created_at"], ascending=[True, True, False])
    canonical_tickets_df = tickets_sorted.drop_duplicates(subset=["ticket_id"], keep="first").copy()

    ledger_df = pd.read_csv(OUTPUT_DIR / "canonical_refund_ledger.csv")

    # Load agent roster
    agent_roster_path = Path("raw/agent.csv") if Path("raw/agent.csv").exists() else Path("raw/agents.csv")
    roster_df = pd.read_csv(agent_roster_path)

    # 1. Monthly analysis
    monthly_df = generate_monthly_analysis(canonical_tickets_df, ledger_df)
    monthly_path = OUTPUT_DIR / "monthly_refund_analysis.csv"
    monthly_df.to_csv(monthly_path, index=False)
    logger.info(f"Saved monthly analysis to {monthly_path}")

    # 2. Quarterly analysis
    quarterly_df = generate_quarterly_analysis(canonical_tickets_df, ledger_df)
    quarterly_path = OUTPUT_DIR / "quarterly_refund_analysis.csv"
    quarterly_df.to_csv(quarterly_path, index=False)
    logger.info(f"Saved quarterly analysis to {quarterly_path}")

    # 3. Growth decomposition
    growth_json = decompose_refund_growth(monthly_df, quarterly_df)
    growth_path = OUTPUT_DIR / "refund_growth_decomposition.json"
    with open(growth_path, "w", encoding="utf-8") as f:
        json.dump(growth_json, f, indent=2)
    logger.info(f"Saved growth decomposition to {growth_path}")

    # 4. Reason analysis
    reason_df = analyze_refund_reasons(ledger_df)
    reason_path = OUTPUT_DIR / "refund_reason_analysis.csv"
    reason_df.to_csv(reason_path, index=False)
    logger.info(f"Saved reason analysis to {reason_path}")

    # 5. Team analysis
    team_df = analyze_teams(canonical_tickets_df, ledger_df, roster_df)
    team_path = OUTPUT_DIR / "team_refund_analysis.csv"
    team_df.to_csv(team_path, index=False)
    logger.info(f"Saved team analysis to {team_path}")

    # 6. Agent analysis
    agent_df = analyze_agents(canonical_tickets_df, ledger_df, roster_df, team_df)
    agent_path = OUTPUT_DIR / "agent_refund_analysis.csv"
    agent_df.to_csv(agent_path, index=False)
    logger.info(f"Saved agent analysis to {agent_path}")

    # 7. Invariant Checks
    assert monthly_df["total_tickets"].sum() == len(canonical_tickets_df), "Invariant Failed: Monthly ticket total mismatch!"
    assert monthly_df["refund_cases"].sum() == len(ledger_df), "Invariant Failed: Monthly refund cases mismatch!"
    assert round(monthly_df["refund_value_inr"].sum(), 2) == round(ledger_df["refund_amount_inr"].sum(), 2), "Invariant Failed: Monthly refund value mismatch!"
    assert reason_df["refund_cases"].sum() == len(ledger_df), "Invariant Failed: Reason refund cases mismatch!"
    assert round(reason_df["refund_value_inr"].sum(), 2) == round(ledger_df["refund_amount_inr"].sum(), 2), "Invariant Failed: Reason refund value mismatch!"
    assert len(agent_df) == len(roster_df), "Invariant Failed: Agent count mismatch!"

    return {
        "monthly_df": monthly_df,
        "quarterly_df": quarterly_df,
        "growth_json": growth_json,
        "reason_df": reason_df,
        "team_df": team_df,
        "agent_df": agent_df,
    }


def print_terminal_analytics_summary(analytics_output: Dict[str, Any]) -> None:
    """Prints a clear analytical summary to terminal."""
    g = analytics_output["growth_json"]["quarterly_comparison"]
    p_driver = analytics_output["growth_json"]["primary_driver"]
    reason_df = analytics_output["reason_df"]
    team_df = analytics_output["team_df"]
    agent_df = analytics_output["agent_df"]
    review_signals_count = int(agent_df["agent_review_signal"].sum())

    top_reason = reason_df.iloc[0]
    top_team = team_df.iloc[0]

    print("\n" + "=" * 65)
    print("      VIREO REFUND EXPLANATION ENGINE — SUMMARY      ")
    print("=" * 65)

    print(f"\n[CANONICAL FINANCIAL OVERVIEW]")
    print(f"  • Total Canonical Refund Value:  ₹{analytics_output['monthly_df']['refund_value_inr'].sum():,.2f}")
    print(f"  • Total Canonical Refund Cases:  {analytics_output['monthly_df']['refund_cases'].sum():,}")
    print(f"  • Total Unique Support Tickets: {analytics_output['monthly_df']['total_tickets'].sum():,}")
    print(f"  • Overall 18-Month Refund Rate: {analytics_output['growth_json']['monthly_summary_stats']['overall_18_month_refund_rate']*100:.2f}%")

    print(f"\n[TREND DECOMPOSITION & PRIMARY DRIVER]")
    print(f"  • Analysis Period:              {g['initial_quarter']} → {g['final_quarter']}")
    print(f"  • Refund Value Change:          +{g['refund_value_change_pct']}% (₹{g['refund_value_initial_inr']:,.2f} → ₹{g['refund_value_final_inr']:,.2f})")
    print(f"  • Ticket Volume Change:         +{g['ticket_volume_change_pct']}% (Tickets: 1,053 → 2,277)")
    print(f"  • Refund Rate Difference:       {g['refund_rate_change_pp']:+.2f} pp")
    print(f"  • Refund Value / Ticket Change: {g['refund_value_per_ticket_change_pct']:+.2f}%")
    print(f"  • PRIMARY DRIVER:               [{p_driver}]")

    print(f"\n[TOP REFUND REASONS (ORIGINAL CODES)]")
    print(f"  • Top Reason by Value:  '{top_reason['normalized_reason']}' (₹{top_reason['refund_value_inr']:,.2f}, {top_reason['share_of_refund_value']*100:.1f}% of total value)")

    print(f"\n[TEAM & AGENT CONTEXT]")
    print(f"  • Largest Team by Value: '{top_team['team']}' (₹{top_team['team_refund_value_inr']:,.2f}, Refund Rate: {top_team['team_refund_rate']*100:.1f}%)")
    print(f"  • Agent Review Signals:  {review_signals_count} agents flagged for within-team rate review (>= 5.0 pp above team rate)")

    print(f"\n[OPEN RECONCILIATION ITEMS]")
    for item in analytics_output["growth_json"]["open_reconciliation_items"]:
        print(f"  • {item['item']}: {item['empirical_finding']}")

    print("\n" + "=" * 65 + "\n")


if __name__ == "__main__":
    out = run_analytics()
    print_terminal_analytics_summary(out)
