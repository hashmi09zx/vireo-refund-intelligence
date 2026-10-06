import json
import logging
import os
from typing import Dict, Any, Optional

from src.ai.prompts import CLASSIFIER_SYSTEM_PROMPT, build_user_prompt
from src.ai.schemas import RefundClassificationResult, RefundReasonTaxonomy

logger = logging.getLogger(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def classify_text_with_groq(
    original_reason_code: str,
    refund_amount_inr: float,
    customer_message: str,
    agent_notes: str,
    product_sku: str = "",
    replacement_issued: str = ""
) -> Dict[str, Any]:
    """Calls Groq LLM API to classify refund text safely.
    
    If Groq fails (missing API key, rate limit, timeout, invalid JSON), handles error gracefully
    and returns fallback UNKNOWN classification without crashing the financial pipeline.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or not api_key.strip():
        logger.debug("GROQ_API_KEY not set. Returning GROQ_ERROR fallback.")
        return {
            "true_reason": "UNKNOWN",
            "evidence": "GROQ_API_KEY not configured",
            "code_matches_text": False,
            "confidence": 0.0,
            "classification_method": "GROQ_ERROR",
        }

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        user_prompt = build_user_prompt(
            original_reason_code=original_reason_code,
            refund_amount_inr=refund_amount_inr,
            customer_message=customer_message,
            agent_notes=agent_notes,
            product_sku=product_sku,
            replacement_issued=replacement_issued
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=300,
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)

        # Validate with Pydantic schema
        true_reason_str = str(parsed.get("true_reason", "UNKNOWN")).upper()
        if true_reason_str not in RefundReasonTaxonomy.__members__:
            true_reason_str = "UNKNOWN"

        result = RefundClassificationResult(
            true_reason=RefundReasonTaxonomy[true_reason_str],
            evidence=str(parsed.get("evidence", "No snippet provided"))[:200],
            code_matches_text=bool(parsed.get("code_matches_text", False)),
            confidence=float(max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))),
        )

        return {
            "true_reason": result.true_reason.value,
            "evidence": result.evidence,
            "code_matches_text": result.code_matches_text,
            "confidence": result.confidence,
            "classification_method": "GROQ",
        }

    except Exception as e:
        logger.warning(f"Groq classification call failed: {e}. Falling back safely.")
        return {
            "true_reason": "UNKNOWN",
            "evidence": f"Groq error: {str(e)[:100]}",
            "code_matches_text": False,
            "confidence": 0.0,
            "classification_method": "GROQ_ERROR",
        }
