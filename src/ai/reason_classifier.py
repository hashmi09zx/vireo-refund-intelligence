import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np

from src.config import OUTPUT_DIR
from src.ai.groq_client import classify_text_with_groq

logger = logging.getLogger(__name__)

CACHE_FILE_PATH = OUTPUT_DIR / "refund_text_classifications.csv"

# Original dropdown reason code to normalized taxonomy mapping
REASON_CODE_TO_TAXONOMY = {
    "GW-OTHER": "GOODWILL",
    "DOA-REPL": "DOA",
    "LOST-TRANSIT": "LOST_TRANSIT",
    "DUP-PAYMENT": "DUPLICATE_PAYMENT",
    "CANCEL": "CANCELLATION",
    "PRICE-ADJ": "PRICE_ADJUSTMENT",
    "RETURN-QC-OK": "RETURN",
    "WTY-BUYBACK": "WARRANTY",
}


def classify_deterministically(row: pd.Series) -> Optional[Dict[str, Any]]:
    """Stage 1: Deterministic keyword & regex text classification."""
    msg = (str(row.get("customer_message") or "") + " " + str(row.get("agent_notes") or "")).lower()
    orig_code = str(row.get("original_reason_code") or row.get("refund_reason_code") or "").strip()
    mapped_orig = REASON_CODE_TO_TAXONOMY.get(orig_code, "OTHER")

    # Match rules
    rules: List[Tuple[List[str], str, str]] = [
        (
            ["duplicate payment", "charged twice", "charged two times", "double charged", "twice charged", "duplicate charge", "double payment"],
            "DUPLICATE_PAYMENT",
            "Duplicate payment referenced in ticket text"
        ),
        (
            ["cancellation request", "cancel order", "cancelled before", "canceled before", "cancellation", "cancelled order", "cancel request"],
            "CANCELLATION",
            "Cancellation referenced in ticket text"
        ),
        (
            ["lost in transit", "never delivered", "package lost", "transit lost", "not delivered", "lost pkg", "lost in shipment"],
            "LOST_TRANSIT",
            "Lost in transit referenced in ticket text"
        ),
        (
            ["dead on arrival", "doa", "arrived broken", "damaged on arrival", "defective on arrival", "received broken"],
            "DOA",
            "DOA or damaged on arrival referenced in ticket text"
        ),
        (
            ["warranty claim", "rma status", "under warranty", "warranty replacement", "claim warranty"],
            "WARRANTY",
            "Warranty claim referenced in ticket text"
        ),
        (
            ["return received", "returned product", "reverse pkp qc", "reverse pickup", "returned unit", "return request"],
            "RETURN",
            "Return or QC inspection referenced in ticket text"
        ),
        (
            ["price drop", "price match", "price difference", "price adjustment"],
            "PRICE_ADJUSTMENT",
            "Price adjustment referenced in ticket text"
        ),
        (
            ["goodwill gesture", "apology credit", "token of appreciation", "goodwill credit"],
            "GOODWILL",
            "Explicit goodwill gesture referenced in ticket text"
        ),
        (
            ["rfnd delay", "refund pending", "rfnd not credited", "refund delay", "delay in refund", "refund status"],
            "REFUND_DELAY",
            "Refund delay or pending credit referenced in ticket text"
        ),
    ]

    for keywords, taxonomy_reason, snippet in rules:
        if any(k in msg for k in keywords):
            code_matches = bool(mapped_orig == taxonomy_reason)
            return {
                "true_reason": taxonomy_reason,
                "evidence": snippet,
                "code_matches_text": code_matches,
                "confidence": 0.95,
                "classification_method": "DETERMINISTIC",
            }

    return None


def classify_single_ticket(row: pd.Series, allow_groq: bool = True) -> Dict[str, Any]:
    """Classifies a single ticket using hybrid pipeline (Stage 1 Deterministic -> Stage 2 Groq)."""
    orig_code = str(row.get("original_reason_code") or row.get("refund_reason_code") or "").strip()
    mapped_orig = REASON_CODE_TO_TAXONOMY.get(orig_code, "OTHER")

    # Stage 1: Deterministic
    det_res = classify_deterministically(row)
    if det_res is not None:
        return det_res

    # Stage 2: Groq LLM (if allowed/enabled)
    if allow_groq:
        groq_res = classify_text_with_groq(
            original_reason_code=orig_code,
            refund_amount_inr=float(row.get("refund_amount_inr", 0.0)),
            customer_message=str(row.get("customer_message") or ""),
            agent_notes=str(row.get("agent_notes") or ""),
            product_sku=str(row.get("product_sku") or ""),
            replacement_issued=str(row.get("replacement_issued") or "")
        )
        return groq_res

    # Fallback if Groq not allowed
    return {
        "true_reason": "UNKNOWN",
        "evidence": "Ambiguous text without LLM classification",
        "code_matches_text": False,
        "confidence": 0.3,
        "classification_method": "UNKNOWN",
    }


def classify_all_refund_tickets(
    ledger_df: pd.DataFrame,
    max_groq_cases: Optional[int] = None
) -> pd.DataFrame:
    """Classifies all canonical refund tickets with local caching to avoid duplicate Groq calls.
    
    Returns outputs/refund_text_classifications.csv DataFrame.
    """
    df = ledger_df.copy()

    # Load cache if available
    cache: Dict[str, Dict[str, Any]] = {}
    if CACHE_FILE_PATH.exists():
        try:
            cached_df = pd.read_csv(CACHE_FILE_PATH)
            cache = cached_df.set_index("ticket_id").to_dict(orient="index")
            logger.info(f"Loaded {len(cache)} cached text classifications from {CACHE_FILE_PATH}")
        except Exception as e:
            logger.warning(f"Could not load classification cache: {e}")

    results = []
    groq_calls_made = 0

    for _, row in df.iterrows():
        tid = str(row["ticket_id"])
        orig_code = str(row.get("original_reason_code") or row.get("refund_reason_code") or "")

        if tid in cache:
            # Reuse cache
            res = cache[tid]
            results.append({
                "ticket_id": tid,
                "original_reason_code": orig_code,
                "true_reason": res.get("true_reason", "UNKNOWN"),
                "evidence": res.get("evidence", ""),
                "code_matches_text": bool(res.get("code_matches_text", False)),
                "confidence": float(res.get("confidence", 0.0)),
                "classification_method": res.get("classification_method", "CACHE"),
            })
        else:
            # Check Stage 1
            det_res = classify_deterministically(row)
            if det_res is not None:
                det_res["ticket_id"] = tid
                det_res["original_reason_code"] = orig_code
                results.append(det_res)
            else:
                # Stage 2: Groq
                allow_groq = max_groq_cases is None or groq_calls_made < max_groq_cases
                res = classify_single_ticket(row, allow_groq=allow_groq)
                res["ticket_id"] = tid
                res["original_reason_code"] = orig_code
                results.append(res)
                if res["classification_method"] == "GROQ":
                    groq_calls_made += 1

    out_df = pd.DataFrame(results)
    cols = ["ticket_id", "original_reason_code", "true_reason", "evidence", "code_matches_text", "confidence", "classification_method"]
    out_df = out_df[cols].copy()

    # Save cache
    out_df.to_csv(CACHE_FILE_PATH, index=False)
    logger.info(f"Saved {len(out_df)} text classifications to {CACHE_FILE_PATH}")

    return out_df
