from typing import Tuple, Dict, Any, List
import pandas as pd
import numpy as np


def normalize_refund_amount(row: pd.Series) -> Tuple[float, str]:
    """Applies explicit monetary unit normalization based on source_system.
    
    Working rule:
    - Current helpdesk stores monetary values in native INR rupees.
    - Legacy Freshdesk (legacy_fd) stored monetary values in hundredths of rupees (legacy 100x multiplier).
    """
    raw_amt = row.get("refund_amount_inr")
    source_sys = row.get("source_system")

    if pd.isna(raw_amt) or raw_amt is None:
        return np.nan, "NO_REFUND"

    try:
        val = float(raw_amt)
    except (ValueError, TypeError):
        return np.nan, "INVALID_NUMERIC"

    if source_sys == "legacy_fd":
        return val / 100.0, "LEGACY_DIVIDED_BY_100"
    elif source_sys == "helpdesk":
        return val, "HELPDESK_NATIVE_RUPEES"
    else:
        return val, "UNKNOWN_SOURCE_UNCHANGED"


def classify_duplicate_group(group: pd.DataFrame) -> Dict[str, Any]:
    """Classifies a group of rows sharing the same ticket_id."""
    sources = set(group["source_system"].dropna())
    has_refund = (group["normalized_refund_amount"].notnull() & (group["normalized_refund_amount"] > 0)).any()
    
    # Extract normalized refund values if refund exists
    norm_refunds = [
        round(r["normalized_refund_amount"], 2)
        for _, r in group.iterrows()
        if pd.notnull(r["normalized_refund_amount"]) and r["normalized_refund_amount"] > 0
    ]
    is_conflicting = len(set(norm_refunds)) > 1

    if is_conflicting:
        dup_class = "CONFLICTING_DUPLICATE"
    elif sources == {"helpdesk", "legacy_fd"}:
        dup_class = "LEGACY_HELPDESK_PAIR"
    elif len(sources) == 1:
        dup_class = "SAME_SOURCE_DUPLICATE"
    elif has_refund:
        dup_class = "REFUND_DUPLICATE"
    else:
        dup_class = "NON_REFUND_DUPLICATE"

    return {
        "ticket_id": group["ticket_id"].iloc[0],
        "group_size": len(group),
        "sources": list(sources),
        "has_refund": has_refund,
        "classification": dup_class,
        "is_conflicting": is_conflicting,
    }


def resolve_canonical_records(tickets_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Deduplicates ticket records and selects canonical records for the refund ledger.
    
    Returns:
    - canonical_tickets_df: All 11,600 unique canonical tickets (refund & non-refund)
    - canonical_refund_events_df: The subset of 2,340 canonical refund events
    - deduplication_report: Analytical report of duplicate resolution
    """
    df = tickets_df.copy()

    # Preserve raw refund amount
    df["refund_amount_raw"] = df["refund_amount_inr"]

    # Normalize monetary values
    norm_results = df.apply(normalize_refund_amount, axis=1)
    df["normalized_refund_amount"] = [res[0] for res in norm_results]
    df["monetary_normalization_rule"] = [res[1] for res in norm_results]

    # Assign duplicate group IDs for provenance
    dup_mask = df["ticket_id"].duplicated(keep=False)
    df["duplicate_group_id"] = np.where(dup_mask, df["ticket_id"], None)

    # Analyze duplicate groups
    dup_groups = df[dup_mask].groupby("ticket_id")
    dup_classifications = [classify_duplicate_group(group) for _, group in dup_groups]

    # Canonical selection logic:
    # 1. Sort by ticket_id
    # 2. Sort source_system so 'helpdesk' comes before 'legacy_fd'
    # 3. Sort resolved_at / created_at descending so most recent record is prioritized
    df["source_priority"] = df["source_system"].map({"helpdesk": 1, "legacy_fd": 2}).fillna(3)
    
    df_sorted = df.sort_values(
        by=["ticket_id", "source_priority", "created_at"],
        ascending=[True, True, False]
    )

    # Set canonicalization reason
    df_sorted["canonicalization_reason"] = np.where(
        df_sorted["duplicate_group_id"].notnull(),
        np.where(
            df_sorted["source_system"] == "helpdesk",
            "CANONICAL_HELPDESK_RECORD_PREFERRED",
            "SECONDARY_LEGACY_DUPLICATE_REMOVED"
        ),
        "SINGLETON_UNIQUE_RECORD"
    )

    # Select canonical records (keep first per ticket_id)
    canonical_tickets_df = df_sorted.drop_duplicates(subset=["ticket_id"], keep="first").copy()

    # Replace refund_amount_inr with canonical normalized value
    canonical_tickets_df["refund_amount_inr"] = canonical_tickets_df["normalized_refund_amount"]

    # Subset of canonical refund events (refund_amount_inr > 0)
    canonical_refund_events_df = canonical_tickets_df[
        canonical_tickets_df["refund_amount_inr"].notnull() & (canonical_tickets_df["refund_amount_inr"] > 0)
    ].copy()

    # Build report
    dedup_report = {
        "raw_total_rows": int(len(tickets_df)),
        "unique_ticket_ids": int(df["ticket_id"].nunique()),
        "duplicate_ticket_ids_count": int(len(dup_groups)),
        "total_duplicate_rows_removed": int(len(tickets_df) - len(canonical_tickets_df)),
        "duplicate_classifications_summary": pd.DataFrame(dup_classifications)["classification"].value_counts().to_dict() if dup_classifications else {},
        "raw_unnormalized_refund_sum": float(df["refund_amount_raw"].sum(skipna=True)),
        "normalized_raw_refund_sum_before_dedup": float(df["normalized_refund_amount"].sum(skipna=True)),
        "canonical_refund_sum_after_dedup": float(canonical_refund_events_df["refund_amount_inr"].sum()),
        "canonical_refund_cases_count": int(len(canonical_refund_events_df)),
    }

    return canonical_tickets_df, canonical_refund_events_df, dedup_report
