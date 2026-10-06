from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class RefundReasonTaxonomy(str, Enum):
    GOODWILL = "GOODWILL"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    CANCELLATION = "CANCELLATION"
    WARRANTY = "WARRANTY"
    DOA = "DOA"
    RETURN = "RETURN"
    DELIVERY = "DELIVERY"
    LOST_TRANSIT = "LOST_TRANSIT"
    PRICE_ADJUSTMENT = "PRICE_ADJUSTMENT"
    REFUND_DELAY = "REFUND_DELAY"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class RefundClassificationResult(BaseModel):
    true_reason: RefundReasonTaxonomy = Field(..., description="The true underlying refund reason derived from free text")
    evidence: str = Field(..., description="Short quote or exact snippet from the text supporting the classification")
    code_matches_text: bool = Field(..., description="True if original dropdown reason code matches derived true reason")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
