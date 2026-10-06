import pytest
import pandas as pd
from src.ingestion.audit import audit_dataframe, validate_foreign_keys, audit_all_data


def test_audit_dataframe():
    data = {
        "id": [1, 2, 2, 3],
        "value": ["A", "B", None, "D"],
    }
    df = pd.DataFrame(data)
    result = audit_dataframe(df, filename="test.csv", primary_key="id")

    assert result["row_count"] == 4
    assert result["column_count"] == 2
    assert result["null_counts"]["value"] == 1
    assert result["pk_unique_count"] == 3
    assert result["pk_duplicate_rows_count"] == 2


def test_validate_foreign_keys():
    source_df = pd.DataFrame({"cust_id": [101, 102, 103, None]})
    target_df = pd.DataFrame({"id": [101, 102]})

    result = validate_foreign_keys(
        source_df=source_df,
        source_col="cust_id",
        target_df=target_df,
        target_col="id",
        relationship_name="test_rel"
    )

    assert result["total_source_non_null"] == 3
    assert result["total_missing_in_source"] == 1
    assert result["unmatched_rows_count"] == 1
    assert result["unmatched_unique_keys_count"] == 1
    assert result["is_valid"] is False


def test_full_audit_integrity():
    report = audit_all_data()

    assert report["summary"]["tickets_rows"] == 12238
    assert report["summary"]["tickets_unique_ids"] == 11600
    assert report["summary"]["tickets_duplicate_ids"] == 638
    assert report["summary"]["customers_rows"] == 9500
    assert report["summary"]["orders_rows"] == 15000
    assert report["summary"]["products_rows"] == 14
    assert report["summary"]["agents_unique"] == 44

    # All foreign keys should pass
    for fk in report["foreign_key_checks"]:
        assert fk["is_valid"] is True, f"Foreign key check failed: {fk['relationship']}"
