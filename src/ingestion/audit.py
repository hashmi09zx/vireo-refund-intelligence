import json
import logging
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from src.config import (
    TICKETS_CSV,
    CUSTOMERS_CSV,
    ORDERS_CSV,
    PRODUCTS_CSV,
    AGENTS_CSV,
    OUTPUT_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def audit_dataframe(df: pd.DataFrame, filename: str, primary_key: str = None) -> Dict[str, Any]:
    """Inspects a single DataFrame for schema, nulls, duplicates, and data types."""
    result: Dict[str, Any] = {
        "filename": filename,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "column_names": list(df.columns),
        "inferred_dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
        "total_nulls": int(df.isnull().sum().sum()),
        "unique_counts": {col: int(df[col].nunique(dropna=True)) for col in df.columns},
    }

    if primary_key and primary_key in df.columns:
        pk_series = df[primary_key].dropna()
        duplicate_mask = pk_series.duplicated(keep=False)
        result["primary_key"] = primary_key
        result["pk_unique_count"] = int(pk_series.nunique())
        result["pk_duplicate_rows_count"] = int(duplicate_mask.sum())
        result["pk_duplicate_keys_count"] = int(pk_series[duplicate_mask].nunique())
    
    return result


def validate_foreign_keys(
    source_df: pd.DataFrame,
    source_col: str,
    target_df: pd.DataFrame,
    target_col: str,
    relationship_name: str
) -> Dict[str, Any]:
    """Validates foreign-key integrity between source and target DataFrames."""
    source_values = source_df[source_col].dropna()
    target_values_set = set(target_df[target_col].dropna().unique())
    
    unmatched = source_values[~source_values.isin(target_values_set)]
    unmatched_unique = unmatched.unique().tolist()
    
    return {
        "relationship": relationship_name,
        "source_column": source_col,
        "target_column": target_col,
        "total_source_non_null": int(len(source_values)),
        "total_missing_in_source": int(source_df[source_col].isnull().sum()),
        "unmatched_rows_count": int(len(unmatched)),
        "unmatched_unique_keys_count": int(len(unmatched_unique)),
        "unmatched_sample": [str(k) for k in unmatched_unique[:5]],
        "is_valid": len(unmatched) == 0,
    }


def audit_all_data() -> Dict[str, Any]:
    """Performs full Phase 0 data audit across all Vireo datasets."""
    logger.info("Starting Phase 0 data audit...")
    
    # 1. Load files
    tickets_df = pd.read_csv(TICKETS_CSV, low_memory=False)
    agents_df = pd.read_csv(AGENTS_CSV)
    customers_df = pd.read_csv(CUSTOMERS_CSV)
    orders_df = pd.read_csv(ORDERS_CSV)
    products_df = pd.read_csv(PRODUCTS_CSV)

    # 2. File-level audits
    file_audits = {
        "tickets": audit_dataframe(tickets_df, TICKETS_CSV.name, primary_key="ticket_id"),
        "agents": audit_dataframe(agents_df, AGENTS_CSV.name, primary_key="agent_id"),
        "customers": audit_dataframe(customers_df, CUSTOMERS_CSV.name, primary_key="customer_id"),
        "orders": audit_dataframe(orders_df, ORDERS_CSV.name, primary_key="order_id"),
        "products": audit_dataframe(products_df, PRODUCTS_CSV.name, primary_key="sku"),
    }

    # 3. Specific Entity Validations
    # Tickets specific checks
    tickets_refund_rows = tickets_df["refund_amount_inr"].notnull() & (tickets_df["refund_amount_inr"] > 0)
    source_sys_dist = tickets_df["source_system"].value_counts(dropna=False).to_dict()
    
    entity_checks = {
        "tickets": {
            "total_rows": int(len(tickets_df)),
            "unique_ticket_ids": int(tickets_df["ticket_id"].nunique()),
            "duplicate_ticket_ids_count": int(tickets_df["ticket_id"].duplicated().sum()),
            "missing_customer_id": int(tickets_df["customer_id"].isnull().sum()),
            "missing_order_id": int(tickets_df["order_id"].isnull().sum()),
            "missing_product_sku": int(tickets_df["product_sku"].isnull().sum()),
            "missing_agent_id": int(tickets_df["agent_id"].isnull().sum()),
            "refund_rows_count": int(tickets_refund_rows.sum()),
            "source_system_distribution": {str(k): int(v) for k, v in source_sys_dist.items()},
        },
        "agents": {
            "total_roster_rows": int(len(agents_df)),
            "unique_agent_ids": int(agents_df["agent_id"].nunique()),
            "duplicate_assignment_rows": int(agents_df.duplicated().sum()),
        },
        "customers": {
            "total_customers": int(len(customers_df)),
            "unique_customer_ids": int(customers_df["customer_id"].nunique()),
            "is_customer_id_unique": bool(len(customers_df) == customers_df["customer_id"].nunique()),
        },
        "orders": {
            "total_orders": int(len(orders_df)),
            "unique_order_ids": int(orders_df["order_id"].nunique()),
            "is_order_id_unique": bool(len(orders_df) == orders_df["order_id"].nunique()),
        },
        "products": {
            "total_products": int(len(products_df)),
            "unique_skus": int(products_df["sku"].nunique()),
            "is_sku_unique": bool(len(products_df) == products_df["sku"].nunique()),
        },
    }

    # 4. Foreign Key Integrity Checks
    fk_checks = [
        validate_foreign_keys(tickets_df, "customer_id", customers_df, "customer_id", "tickets.customer_id -> customers.customer_id"),
        validate_foreign_keys(tickets_df, "order_id", orders_df, "order_id", "tickets.order_id -> orders.order_id"),
        validate_foreign_keys(tickets_df, "product_sku", products_df, "sku", "tickets.product_sku -> products.sku"),
        validate_foreign_keys(tickets_df, "agent_id", agents_df, "agent_id", "tickets.agent_id -> agents.agent_id"),
        validate_foreign_keys(orders_df, "customer_id", customers_df, "customer_id", "orders.customer_id -> customers.customer_id"),
        validate_foreign_keys(orders_df, "sku", products_df, "sku", "orders.sku -> products.sku"),
    ]

    # 5. Timestamp Parsing Checks
    date_checks = {}
    timestamp_columns = [
        ("tickets", tickets_df, "created_at"),
        ("tickets", tickets_df, "first_response_at"),
        ("tickets", tickets_df, "resolved_at"),
        ("orders", orders_df, "order_date"),
        ("customers", customers_df, "signup_date"),
        ("products", products_df, "launch_date"),
        ("agents", agents_df, "from_date"),
        ("agents", agents_df, "to_date"),
    ]
    for dataset_name, df, col in timestamp_columns:
        if col in df.columns:
            non_null = df[col].dropna()
            parsed = pd.to_datetime(non_null, errors="coerce")
            unparseable_count = int(parsed.isnull().sum())
            key = f"{dataset_name}.{col}"
            date_checks[key] = {
                "total_non_null": int(len(non_null)),
                "unparseable_count": unparseable_count,
                "min_date": str(parsed.min()) if not parsed.empty else None,
                "max_date": str(parsed.max()) if not parsed.empty else None,
            }

    # Complete Data Quality Report
    report = {
        "summary": {
            "total_files_audited": 5,
            "tickets_rows": entity_checks["tickets"]["total_rows"],
            "tickets_unique_ids": entity_checks["tickets"]["unique_ticket_ids"],
            "tickets_duplicate_ids": entity_checks["tickets"]["duplicate_ticket_ids_count"],
            "agents_rows": entity_checks["agents"]["total_roster_rows"],
            "agents_unique": entity_checks["agents"]["unique_agent_ids"],
            "customers_rows": entity_checks["customers"]["total_customers"],
            "orders_rows": entity_checks["orders"]["total_orders"],
            "products_rows": entity_checks["products"]["total_products"],
        },
        "file_audits": file_audits,
        "entity_checks": entity_checks,
        "foreign_key_checks": fk_checks,
        "timestamp_checks": date_checks,
    }

    return report


def save_audit_report(report: Dict[str, Any]) -> None:
    """Saves data quality report to outputs/data_quality_report.json and .csv."""
    json_path = OUTPUT_DIR / "data_quality_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved JSON data quality report to {json_path}")

    # Build summary CSV
    summary_rows = []
    for file_key, info in report["file_audits"].items():
        summary_rows.append({
            "dataset": file_key,
            "filename": info["filename"],
            "row_count": info["row_count"],
            "column_count": info["column_count"],
            "total_nulls": info["total_nulls"],
            "pk_unique_count": info.get("pk_unique_count", "N/A"),
            "pk_duplicate_rows": info.get("pk_duplicate_rows_count", "N/A"),
        })
    csv_path = OUTPUT_DIR / "data_quality_report.csv"
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    logger.info(f"Saved CSV data quality summary to {csv_path}")


def print_terminal_summary(report: Dict[str, Any]) -> None:
    """Prints a clear, high-impact terminal summary of audit findings."""
    print("\n" + "=" * 60)
    print("      VIREO DATA AUDIT REPORT (PHASE 0)      ")
    print("=" * 60)
    
    s = report["summary"]
    print(f"\n[FILE SUMMARY]")
    print(f"  • Tickets Rows:          {s['tickets_rows']:,}")
    print(f"  • Tickets Unique IDs:    {s['tickets_unique_ids']:,}")
    print(f"  • Tickets Duplicate IDs: {s['tickets_duplicate_ids']:,}")
    print(f"  • Customers:             {s['customers_rows']:,}")
    print(f"  • Orders:                {s['orders_rows']:,}")
    print(f"  • Agents (Roster Rows):  {s['agents_rows']:,} (Unique Agent IDs: {s['agents_unique']})")
    print(f"  • Products:              {s['products_rows']:,}")

    e_t = report["entity_checks"]["tickets"]
    print(f"\n[TICKETS DETAILS]")
    print(f"  • Refund Rows (non-null & >0): {e_t['refund_rows_count']:,}")
    print(f"  • Missing customer_id:         {e_t['missing_customer_id']:,}")
    print(f"  • Missing order_id:            {e_t['missing_order_id']:,}")
    print(f"  • Missing product_sku:         {e_t['missing_product_sku']:,}")
    print(f"  • Missing agent_id:             {e_t['missing_agent_id']:,}")
    print(f"  • Source System Distribution:  {e_t['source_system_distribution']}")

    print(f"\n[FOREIGN KEY INTEGRITY]")
    for fk in report["foreign_key_checks"]:
        status = "PASSED" if fk["is_valid"] else f"FAILED ({fk['unmatched_rows_count']} unmatched rows)"
        print(f"  • {fk['relationship']}: {status}")
        if not fk["is_valid"]:
            print(f"    Sample unmatched keys: {fk['unmatched_sample']}")

    print("\n[TIMESTAMP VALIDATION]")
    for key, ts_info in report["timestamp_checks"].items():
        print(f"  • {key}: unparseable={ts_info['unparseable_count']} | range=[{ts_info['min_date']} to {ts_info['max_date']}]")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    report = audit_all_data()
    save_audit_report(report)
    print_terminal_summary(report)
