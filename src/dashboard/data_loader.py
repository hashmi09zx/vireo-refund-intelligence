import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
from typing import Dict, Any, Tuple

import pandas as pd
from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def get_artifact_path(filename: str) -> Path:
    """Returns absolute path to an output artifact and verifies existence."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required artifact '{filename}' not found in outputs directory! Please run pipeline modules first.")
    return path


def load_canonical_ledger() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("canonical_refund_ledger.csv"))


def load_monthly_analysis() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("monthly_refund_analysis.csv"))


def load_quarterly_analysis() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("quarterly_refund_analysis.csv"))


def load_growth_decomposition() -> Dict[str, Any]:
    with open(get_artifact_path("refund_growth_decomposition.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_reason_analysis() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("refund_reason_analysis.csv"))


def load_team_analysis() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("team_refund_analysis.csv"))


def load_agent_analysis() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("agent_refund_analysis.csv"))


def load_text_classifications() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("refund_text_classifications.csv"))


def load_control_findings() -> pd.DataFrame:
    return pd.read_csv(get_artifact_path("control_findings.csv"))


def load_control_summary() -> Dict[str, Any]:
    with open(get_artifact_path("control_summary.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_artifacts() -> Dict[str, Any]:
    """Loads all 10 core generated artifacts into a unified data dictionary."""
    return {
        "ledger": load_canonical_ledger(),
        "monthly": load_monthly_analysis(),
        "quarterly": load_quarterly_analysis(),
        "growth": load_growth_decomposition(),
        "reasons": load_reason_analysis(),
        "teams": load_team_analysis(),
        "agents": load_agent_analysis(),
        "classifications": load_text_classifications(),
        "findings": load_control_findings(),
        "control_summary": load_control_summary(),
    }
