from typing import Tuple, Dict, Any, List
import pandas as pd


def resolve_ticket_orders(
    tickets_df: pd.DataFrame,
    orders_df: pd.DataFrame
) -> pd.DataFrame:
    """Performs strict entity resolution hierarchy to match support tickets to orders.
    
    Resolution hierarchy:
    - Level 1: EXPLICIT_ORDER_ID (HIGH_CONFIDENCE)
    - Level 2: CUSTOMER_SKU_UNIQUE (MEDIUM_CONFIDENCE)
    - Level 2 (Multiple Candidates): AMBIGUOUS_CUSTOMER_SKU (AMBIGUOUS, resolved_order_id=None)
    - Level 2 (Zero Candidates): NO_MATCH (UNMATCHED, resolved_order_id=None)
    """
    df = tickets_df.copy()

    # Pre-build lookup sets and indices for O(1) performance
    valid_order_set = set(orders_df["order_id"].dropna().unique())

    # Map (customer_id, sku) -> list of order_ids
    orders_grouped = orders_df.groupby(["customer_id", "sku"])["order_id"].apply(list).to_dict()

    resolved_order_ids: List[Any] = []
    join_methods: List[str] = []
    join_confidences: List[str] = []
    join_candidates_counts: List[int] = []

    for _, row in df.iterrows():
        raw_order_id = row.get("order_id")
        cust_id = row.get("customer_id")
        sku = row.get("product_sku")

        # Level 1: Explicit order_id match
        if pd.notnull(raw_order_id) and str(raw_order_id).strip() != "" and str(raw_order_id) in valid_order_set:
            resolved_order_ids.append(str(raw_order_id))
            join_methods.append("EXPLICIT_ORDER_ID")
            join_confidences.append("HIGH_CONFIDENCE")
            join_candidates_counts.append(1)
        else:
            # Level 2: Fallback to customer_id + product_sku match
            candidates = orders_grouped.get((cust_id, sku), [])
            cand_count = len(candidates)
            join_candidates_counts.append(cand_count)

            if cand_count == 1:
                resolved_order_ids.append(candidates[0])
                join_methods.append("CUSTOMER_SKU_UNIQUE")
                join_confidences.append("MEDIUM_CONFIDENCE")
            elif cand_count > 1:
                # Ambiguous: Never select arbitrarily
                resolved_order_ids.append(None)
                join_methods.append("AMBIGUOUS_CUSTOMER_SKU")
                join_confidences.append("AMBIGUOUS")
            else:
                resolved_order_ids.append(None)
                join_methods.append("NO_MATCH")
                join_confidences.append("UNMATCHED")

    df["resolved_order_id"] = resolved_order_ids
    df["join_method"] = join_methods
    df["join_confidence"] = join_confidences
    df["join_candidates_count"] = join_candidates_counts

    return df
