import pytest
import pandas as pd
from pathlib import Path

from src.dashboard.data_loader import (
    load_all_artifacts,
    load_canonical_ledger,
    load_control_summary,
    get_artifact_path,
)


def test_data_loader_loads_all_artifacts():
    artifacts = load_all_artifacts()

    assert "ledger" in artifacts
    assert "monthly" in artifacts
    assert "quarterly" in artifacts
    assert "growth" in artifacts
    assert "reasons" in artifacts
    assert "teams" in artifacts
    assert "agents" in artifacts
    assert "classifications" in artifacts
    assert "findings" in artifacts
    assert "control_summary" in artifacts

    # Check non-empty
    assert len(artifacts["ledger"]) == 2340
    assert len(artifacts["findings"]) == 1334
    assert len(artifacts["classifications"]) == 2340


def test_data_loader_raises_error_on_missing_file():
    with pytest.raises(FileNotFoundError):
        get_artifact_path("non_existent_file_999.csv")


def test_no_hardcoded_kpi_values():
    ledger = load_canonical_ledger()
    control_sum = load_control_summary()

    canon_val = float(ledger["refund_amount_inr"].sum())
    cases_count = len(ledger)
    exposure_val = float(control_sum["non_overlapping_review_exposure"]["value_inr"])

    # Verify dynamic values match exact calculations
    assert round(canon_val, 2) == 6709932.0
    assert cases_count == 2340
    assert round(exposure_val, 2) == 824245.0


def test_dashboard_module_imports():
    import src.dashboard.data_loader
    import src.dashboard.components
    import src.dashboard.app

    assert src.dashboard.data_loader.load_all_artifacts is not None
    assert src.dashboard.app.main is not None
