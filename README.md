# Vireo Refund Truth & Leakage Intelligence

> **One-Line Problem Statement:** Support ticket refund data cannot initially be trusted due to duplicate migrated tickets and legacy monetary scaling, while rising refund outlay is frequently misinterpreted as bad agent behavior rather than ticket volume growth.

---

## Executive Summary & Key Results

This evidence-backed refund intelligence system reconstructs a trustworthy canonical refund ledger, explains whether refund growth is driven by ticket volume or refund behavior, and identifies policy-inconsistent or duplicate-compensation cases with ticket-level evidence.

| Business Question | Empirical Finding | Key Metric / Result |
| :--- | :--- | :--- |
| **Q1. How much did Vireo actually refund?** | Reconciled ~₹23.01 Cr raw export sum down to single source of truth | **₹67,09,932.00** across **2,340 canonical cases** |
| **Q2. Why did refund value increase?** | Outlay grew +109.95% as Ticket Volume grew +116.24%; Refund Rate remained flat (+0.64 pp) | Primary Driver: **`VOLUME`** |
| **Q3. Where are the control-review signals?** | Identified R1–R5 policy exceptions with direct ticket-level evidence | **1,334 findings** across 5 control rules |
| **Q4. Can every conclusion be traced to evidence?** | Full audit trail linking findings to ticket ID, order ID, text snippet, and calculation | **100% auditable evidence chain** in UI & CSV |

---

## Core Product Philosophy: Hybrid Deterministic + Narrow AI

```text
DETERMINISTIC TRUTH
      +
NARROW AI INTERPRETATION
      +
EXPLICIT EVIDENCE
```

* **Deterministic Code:** Owns all financial calculations, legacy unit conversions (`legacy_fd` $\div 100$), deduplication, joins, statistical aggregations, and policy threshold rules.
* **Narrow AI Interpretation:** Used exclusively for free-text interpretation of customer messages and agent notes to classify underlying true reasons and detect reason-code mismatches.
* **Explicit Boundary Notice:** *The LLM does not calculate financial truth or policy exposure. It only interprets ambiguous free text.*

---

## System Architecture & Conceptual Flow

```text
                     RAW SUPPORT DATAPACK (8 files)
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ 1. DATA AUDIT (P0)    │
                       │   Schema & Nulls      │
                       │   FK Integrity        │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ 2. RECONCILIATION (P1)│
                       │   Legacy /100         │
                       │   Deduplication       │
                       │   Entity Resolution   │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ CANONICAL REFUND      │
                       │ LEDGER (₹67.10 Lakh)  │
                       └───────────┬───────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
 ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
 │ 3. TREND     │           │ 4. POLICY    │           │ 5. NARROW AI │
 │   ANALYTICS  │           │   ENGINE     │           │   INTERPRETER│
 │              │           │              │           │              │
 │ Volume vs    │           │ R1: Ref+Rep  │           │ Stage 1 Regex│
 │ Behavior     │           │ R2: Over-ref │           │ Stage 2 Groq │
 │ Breakdown    │           │ R3: Multi-ref│           │ Classifications│
 └──────┬───────┘           └──────┬───────┘           └──────┬───────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
                       ┌───────────────────────┐
                       │ 6. EVIDENCE LAYER     │
                       │   outputs/control_    │
                       │   findings.csv        │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ 7. STREAMLIT UI (P4)  │
                       │   Dashboard & Evidence│
                       │   Explorer            │
                       └───────────────────────┘
```

---

## Detailed Control Findings & Review Exposure

| Rule ID | Rule Description | Cases / Orders | Financial Value / Excess | Audit & Policy Reference |
| :--- | :--- | :--- | :--- | :--- |
| **R1** | **Refund + Replacement** | **166 cases** | **₹5,74,191.00** (~₹5.74 L) | Policy §4 — Prohibited on same order |
| **R2** | **Refund Exceeds Order Value** | **98 orders** | **₹2,50,054.00** (~₹2.50 L) | Policy §3 — High confidence explicit orders only |
| **R3** | **Multiple Refunds per Order** | **170 orders** | **₹9,36,052.00** (~₹9.36 L) | Policy §3 — Process review signal |
| **R4** | **Reason Code Mismatch** | **620 cases** | **₹18,56,086.00** (~₹18.56 L) | Policy §5 — Dropdown code vs text mismatch |
| **R5** | **Goodwill Cap Review** | **0 cases** | **₹0.00** | Policy §5.1 — Goodwill > ₹500 review |

### Non-Overlapping Exposure Methodology & Derivation
* **Gross R1 Refund Exposure:** ₹5,74,191.00
* **Gross R2 Excess Exposure:** ₹2,50,054.00
* **Deduplication:** Sums gross R1 ticket exposure (₹5,74,191.00) and gross R2 excess deduplicated per resolved_order_id (₹2,50,054.00).
* **TOTAL NON-OVERLAPPING REVIEW EXPOSURE:** **₹8,24,245.00** (**~₹8.24 Lakh**)
* **Official Accounting Label:** `OBSERVED REVIEW EXPOSURE — NOT CONFIRMED FINANCIAL LOSS`

---

## Technology Stack

* **Language & Runtime:** Python 3.9+
* **Data Processing:** Pandas 2.0+
* **Dashboard Framework:** Streamlit 1.28+
* **AI Text Classifier:** Groq LLM API (`openai/gpt-oss-120b` / `groq`)
* **Schema Validation:** Pydantic 2.0+
* **Testing & Invariants:** Pytest 7.0+

---

## Repository Structure

```text
vireo-refund-intelligence/
├── raw/                               # Raw data CSVs and PDF policy
├── outputs/                           # Reconciled canonical & analytical outputs
│   ├── canonical_refund_ledger.csv    # SINGLE SOURCE OF TRUTH (2,340 cases)
│   ├── control_findings.csv           # 1,334 detailed control findings
│   ├── control_summary.json           # Machine-readable policy summary
│   ├── refund_text_classifications.csv# AI text classification cache
│   ├── agent_refund_analysis.csv      # Corrected 5.0 pp agent analysis
│   ├── monthly_refund_analysis.csv
│   ├── quarterly_refund_analysis.csv
│   ├── refund_growth_decomposition.json
│   ├── refund_reason_analysis.csv
│   └── team_refund_analysis.csv
├── src/
│   ├── config.py                      # Path & environment configuration
│   ├── ingestion/
│   │   └── audit.py                   # Phase 0 Data Audit engine
│   ├── reconciliation/                # Phase 1 Refund Truth Engine
│   │   ├── loader.py
│   │   ├── deduplication.py
│   │   ├── entity_resolution.py
│   │   ├── ledger.py
│   │   └── reconcile.py
│   ├── analytics/                     # Phase 2 Refund Explanation Engine
│   │   ├── metrics.py
│   │   ├── reasons.py
│   │   ├── agents.py                  # Threshold = 5.0 pp
│   │   └── trends.py
│   ├── ai/                            # Narrow Groq Text Intelligence
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── groq_client.py             # Fail-safe Groq client
│   │   └── reason_classifier.py       # Hybrid Stage 1 + Stage 2 classifier
│   ├── policy/                        # Deterministic Policy Engine
│   │   ├── rules.py                   # R1 - R5 rule evaluation
│   │   ├── exposure.py                # Non-overlapping exposure calculator
│   │   ├── findings.py                # Auditable Evidence Object formatter
│   │   └── engine.py                  # Policy Engine CLI runner
│   └── dashboard/                     # Phase 4 Finance Dashboard
│       ├── data_loader.py
│       ├── components.py
│       └── app.py                     # Streamlit dashboard application
├── tests/                             # Comprehensive Pytest suite (25 tests)
│   ├── test_audit.py
│   ├── test_reconciliation.py
│   ├── test_analytics.py
│   ├── test_policy.py
│   ├── test_ai_classifier.py
│   └── test_dashboard.py
├── .env.example                       # Template containing GROQ_API_KEY=
├── .gitignore                         # Virtualenv, cache, and env ignore
├── pytest.ini                         # Pytest configuration
├── requirements.txt                   # Project dependencies
└── README.md                          # Project documentation
```

---

## Instructions: How to Run

### 1. Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optionally set `GROQ_API_KEY=your_key` in `.env` to enable Groq LLM API calls. If unconfigured, the system runs safely using Stage 1 deterministic classification + fail-safe fallbacks).*

### 3. Run End-to-End Pipeline
```bash
# Run Data Audit (Phase 0)
python -m src.ingestion.audit

# Run Refund Truth Engine (Phase 1)
python -m src.reconciliation.reconcile

# Run Refund Explanation Engine (Phase 2)
python -m src.analytics.trends

# Run Refund Control & AI Engine (Phase 3)
python -m src.policy.engine
```

### 4. Run Pytest Test Suite
```bash
pytest -v
```

### 5. Launch Streamlit Finance Dashboard (Phase 4)
```bash
streamlit run src.dashboard.app
```

---

## Key Assumptions & Methodological Notices

1. **Legacy Monetary Unit Normalization:** `helpdesk` native INR values are unchanged; `legacy_fd` values are divided by 100 (`monetary_normalization_rule = "LEGACY_DIVIDED_BY_100"`).
2. **Duplicate Ticket Resolution:** Migrated tickets appearing in both `helpdesk` and `legacy_fd` prefer the `helpdesk` record as canonical (`canonicalization_reason = "CANONICAL_HELPDESK_RECORD_PREFERRED"`).
3. **Entity Resolution Hierarchy:** Order matching uses Level 1 `EXPLICIT_ORDER_ID` (`HIGH_CONFIDENCE`) and Level 2 `CUSTOMER_SKU_UNIQUE` (`MEDIUM_CONFIDENCE`). Ambiguous matches with $>1$ candidate order are set to `None` (`AMBIGUOUS`).
4. **Support Ticket Refunds vs Cash Settlement:** Support tickets record operational refund decisions raised by frontline agents. Actual banking / gateway settlement occurs in downstream financial systems.
5. **GW-OTHER Heterogeneity:** `GW-OTHER` is a catch-all dropdown code. R5 Goodwill Cap review requires AI-derived `true_reason == "GOODWILL"` AND `refund > 500`. `GW-OTHER` alone is never blindly flagged.
6. **Non-Punitive Agent Review Signals:** Agent rate signals ($\ge 30$ tickets and rate $\ge \text{team rate} + 5.0\text{ pp}$) are operational review indicators, not evidence of individual misconduct.
