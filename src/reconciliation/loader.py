import pandas as pd
from typing import Dict, Any
from src.config import (
    TICKETS_CSV,
    CUSTOMERS_CSV,
    ORDERS_CSV,
    PRODUCTS_CSV,
    AGENTS_CSV,
)


def load_raw_data() -> Dict[str, pd.DataFrame]:
    """Loads all raw Vireo CSV datasets without mutating original raw files.
    
    Parses dates where appropriate and normalizes obvious null representations.
    """
    tickets_df = pd.read_csv(TICKETS_CSV, low_memory=False)
    agents_df = pd.read_csv(AGENTS_CSV)
    customers_df = pd.read_csv(CUSTOMERS_CSV)
    orders_df = pd.read_csv(ORDERS_CSV)
    products_df = pd.read_csv(PRODUCTS_CSV)

    # Clean string null representations if any
    for df in [tickets_df, agents_df, customers_df, orders_df, products_df]:
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].apply(lambda x: None if pd.isna(x) or str(x).strip().lower() in ["nan", "null", "none", ""] else str(x).strip())

    # Ensure numeric conversion for financial fields
    tickets_df["refund_amount_inr"] = pd.to_numeric(tickets_df["refund_amount_inr"], errors="coerce")
    orders_df["order_value_inr"] = pd.to_numeric(orders_df["order_value_inr"], errors="coerce")
    products_df["unit_cost_inr"] = pd.to_numeric(products_df["unit_cost_inr"], errors="coerce")
    products_df["retail_price_inr"] = pd.to_numeric(products_df["retail_price_inr"], errors="coerce")

    return {
        "tickets": tickets_df,
        "agents": agents_df,
        "customers": customers_df,
        "orders": orders_df,
        "products": products_df,
    }
