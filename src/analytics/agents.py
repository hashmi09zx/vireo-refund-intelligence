import pandas as pd
from typing import Tuple, Dict, Any
from src.analytics.metrics import safe_divide


def analyze_teams(
    canonical_tickets_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    agents_df: pd.DataFrame
) -> pd.DataFrame:
    """Calculates team-level ticket volume, refund cases, refund rate, and total refund value."""
    tickets = canonical_tickets_df.copy()
    ledger = ledger_df.copy()

    # Map team onto tickets if missing
    agent_team_map = agents_df.set_index("agent_id")["team"].to_dict()
    if "team" not in tickets.columns:
        tickets["team"] = tickets["agent_id"].map(agent_team_map)
    if "team" not in ledger.columns:
        ledger["team"] = ledger["agent_id"].map(agent_team_map)

    team_total_tickets = tickets.groupby("team").size()
    team_refund_cases = ledger.groupby("team").size()
    team_refund_val = ledger.groupby("team")["refund_amount_inr"].sum()

    team_df = pd.DataFrame({
        "team_total_tickets": team_total_tickets,
        "team_refund_cases": team_refund_cases,
        "team_refund_value_inr": team_refund_val,
    }).fillna(0)

    team_df.reset_index(inplace=True)

    team_df["team_refund_rate"] = team_df.apply(
        lambda r: round(safe_divide(r["team_refund_cases"], r["team_total_tickets"]), 4),
        axis=1
    )
    team_df["team_refund_value_inr"] = team_df["team_refund_value_inr"].round(2)

    team_df.sort_values(by="team_refund_value_inr", ascending=False, inplace=True)
    team_df.reset_index(drop=True, inplace=True)

    return team_df


def analyze_agents(
    canonical_tickets_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    agents_df: pd.DataFrame,
    team_df: pd.DataFrame,
    min_tickets_threshold: int = 30,
    rate_diff_pp_threshold: float = 5.0
) -> pd.DataFrame:
    """Calculates agent-level refund performance contextualized within their team benchmark.
    
    Generates a 'Review signal' if agent refund rate is meaningfully higher than team rate (>= 5.0 pp)
    and observation volume is statistically sensible (>= 30 tickets).
    """
    tickets = canonical_tickets_df.copy()
    ledger = ledger_df.copy()

    agent_total = tickets.groupby("agent_id").size()
    agent_refund_cases = ledger.groupby("agent_id").size()
    agent_refund_val = ledger.groupby("agent_id")["refund_amount_inr"].sum()

    df = pd.DataFrame({
        "agent_id": agent_total.index,
        "total_tickets": agent_total.values,
    })

    df["refund_cases"] = df["agent_id"].map(agent_refund_cases).fillna(0).astype(int)
    df["refund_value_inr"] = df["agent_id"].map(agent_refund_val).fillna(0.0).round(2)

    # Join metadata from agents.csv
    agent_info = agents_df.set_index("agent_id")[["name", "team", "tier"]].to_dict(orient="index")
    df["name"] = df["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("name"))
    df["team"] = df["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("team"))
    df["tier"] = df["agent_id"].map(lambda aid: agent_info.get(aid, {}).get("tier"))

    # Join team benchmark rate
    team_rate_map = team_df.set_index("team")["team_refund_rate"].to_dict()
    df["team_refund_rate"] = df["team"].map(team_rate_map).fillna(0.0)

    # Calculate agent refund rate & rate difference in percentage points
    df["refund_rate"] = df.apply(
        lambda r: round(safe_divide(r["refund_cases"], r["total_tickets"]), 4),
        axis=1
    )
    df["rate_difference_pp"] = df.apply(
        lambda r: round((r["refund_rate"] - r["team_refund_rate"]) * 100.0, 2),
        axis=1
    )

    # Deterministic Review Signal (NOT a risk score or judgment of guilt)
    df["agent_review_signal"] = df.apply(
        lambda r: bool(r["total_tickets"] >= min_tickets_threshold and r["rate_difference_pp"] >= rate_diff_pp_threshold),
        axis=1
    )

    columns_order = [
        "agent_id",
        "name",
        "team",
        "tier",
        "total_tickets",
        "refund_cases",
        "refund_value_inr",
        "refund_rate",
        "team_refund_rate",
        "rate_difference_pp",
        "agent_review_signal",
    ]

    df = df[columns_order].copy()
    df.sort_values(by=["agent_review_signal", "rate_difference_pp"], ascending=[False, False], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
