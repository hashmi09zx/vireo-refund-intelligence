# Vireo Refund Intelligence — Submission Form

## 1. What did you build, and what business outcome does it move? State the number and the money.

We built an evidence-backed refund reconciliation and control-review intelligence system that converts corrupted support helpdesk exports into a single source of truth canonical refund ledger, explains the empirical drivers of refund growth, and prioritizes policy exceptions for targeted operational review.

### The Numbers & The Money:
* **Canonical Financial Reconciliation:** Reconciled raw support ticket exports (unnormalized sum approximately ₹23.01 Crore) down to a canonical source of truth of **₹67,09,932.00** across **2,340 canonical cases** (scaling legacy Freshdesk amounts by 100 and deduplicating 125 migrated refund records).
* **Refund Growth Explanation:** Proved that quarterly refund outlay growth (**+109.95%**, from ₹6,09,583.00 in 2025Q1 to ₹12,79,823.00 in 2026Q2) was driven by **+116.24% support ticket volume growth** (1,053 to 2,277 tickets), while the overall refund rate remained flat (**+0.64 percentage points**, moving from 20.13% to 20.77%). Frontline refund propensity did not deteriorate.
* **Observed Control-Review Exposure:** Identified **₹8,24,245.00** in combined gross non-overlapping policy exceptions requiring operational review:
  * **R1 — Refund + Replacement:** 166 cases = ₹5,74,191.00 (refund issued AND replacement unit sent for same order).
  * **R2 — Refund Exceeds Order Value:** 98 unique orders = ₹2,50,054.00 deduplicated excess refund over original order value.

**Business Outcome:** The system provides Finance with auditable financial truth and a prioritized control-review queue to investigate potential operational leakage. We explicitly label ₹8.24L as *Observed Control-Review Exposure*, requiring operational verification, rather than speculating on unverified future savings or confirmed losses.

---

## 2. What does one run cost, and what would a month cost at Vireo's volume (roughly 650 tickets a week)? Show the arithmetic. If you used no paid calls, say so.

### Vireo Volume Arithmetic:
* **Weekly Volume:** Approximately 650 tickets / week.
* **Monthly Volume:** 650 tickets/week * 52 / 12 = 2,817 total tickets / month.
* **Monthly Refund Tickets (20.17% observed rate):** 2,817 * 20.17% = 568 refund tickets / month.

### Pipeline Cost & LLM Call Estimation:
The system uses a hybrid architecture: Stage 1 Regex pre-classifies approximately 47% of tickets deterministically (₹0.00 API cost). Stage 2 invokes the Groq API (`openai/gpt-oss-120b`) for messy free-text classification.

* **Full Historical Dataset Run (2,340 refund cases):** Approximately 1,243 LLM calls * (400 input + 100 output tokens per call) = 497k input tokens + 124k output tokens. Estimated model cost is **$0.39 USD (approximately ₹33 INR)**.
* **Monthly Incremental Volume (approximately 568 refund cases):** Approximately 302 LLM calls = 121k input tokens + 30k output tokens. Estimated model cost is **$0.095 USD (approximately ₹8 INR) / month**.
* **Billing Status:** Estimated from stated token/pricing assumptions; actual cost depends on current Groq pricing and the number of LLM calls. If operating under Groq's developer free tier (up to 14,400 daily requests), actual paid API outlay is **₹0.00**.

---

## 3. How do you know it works? Sample size, how you checked, error rate, and the kind of case it gets wrong.

* **Automated Code & Invariant Tests:** 26 passing Pytest automated unit and integration tests (`pytest -v`) covering schema audit, legacy monetary division (/100), helpdesk deduplication, entity resolution hierarchy, policy threshold evaluations, multi-ticket order R2 exposure deduplication, and dashboard artifact loading.
* **Financial Invariants:** 100% of canonical tickets have unique IDs, non-negative refund amounts, and validated foreign keys.
* **Manual Validation:** 20 random R4 reason-mismatch tickets (`GW-OTHER` vs. true customer reason text) were manually spot-checked during development with 100% agreement on true reason assignment.
* **Empirical LLM Error Rate Disclosure:** There is no formal annotated ground-truth dataset for LLM text classification, so we do **NOT** claim an empirical LLM accuracy percentage or "100% accuracy". The 26 passing Pytest tests validate code logic, accounting invariants, and regression behavior, NOT model precision/recall.
* **Known Failure Modes:** The LLM text classifier can be uncertain when customer or agent notes are extremely short, ambiguous, or conversational (e.g. *"thanks"*, *"resolved on call"*), or when customers report multiple distinct defects simultaneously. The system handles this safely by falling back to `UNKNOWN` or Stage 1 regex classification.

---

## 4. Did you change, narrow, or push back on the client's ask? What, when, and why?

1. **Reconstructed a Canonical Refund Ledger:** Pushed back on blindly accepting the raw helpdesk export. Normalized legacy Freshdesk values (`/100`), deduplicated 125 migrated records, and established an auditable baseline of ₹67.10L.
2. **Deterministic Financial Math:** Kept all monetary math, legacy division, deduplication, order joins, and policy exposure calculations 100% in deterministic Python code. Refused to use probabilistic LLMs for numeric calculations.
3. **Contextual Within-Team Agent Benchmarks:** Rejected naive agent ranking across teams. Implemented a within-team threshold ($\ge 30$ tickets and rate $\ge \text{team rate} + 5.0\text{ pp}$) so specialized units like Returns Desk (who handle 100% refund cases by design) are not falsely penalized.
4. **Non-Blind Goodwill Evaluation (R5):** Refused to flag `GW-OTHER` dropdown codes blindly. Required AI true reason = `GOODWILL` AND refund $> \text{₹}500$.
5. **Strict High-Confidence R2 Matching:** Evaluated over-refunds only on Level 1 `HIGH_CONFIDENCE` explicit order matches to prevent false positives from ambiguous customer/SKU fallback joins.
6. **Observed Exposure Labeling:** Refused to label unverified operational exceptions as "confirmed loss" or "fraud". Labeled the ₹8.24L total as *Observed Control-Review Exposure*.

---

## 5. What is wrong with what you are handing us? Bugs, shortcuts, known limitations.

1. **No Annotated Ground-Truth Benchmark Dataset:** LLM classification relies on invariant test coverage and 20 manual spot-checks rather than a statistically formal ground-truth test set.
2. **Ambiguous Free-Text Edge Cases:** Extremely short or uninformative ticket text (e.g., *"cx requested update"*) cannot be conclusively classified into a specific root cause and defaults to `UNKNOWN`.
3. **Unverified Operational Exceptions:** Policy findings (R1 & R2 totaling ₹8.24L) represent operational control review signals, not confirmed cash loss, until verified by support operations.
4. **Analytical Prototype Scope:** Built as an analytical decision-support and review tool rather than a production transactional accounting system.

---

## 6. What did you deliberately leave out, and why that rather than something else?

We deliberately excluded Vector DB / RAG pipelines, multi-agent frameworks, predictive machine learning models, customer-facing chatbots, and real-time streaming infrastructure.

**Rationale:** The task was a 5-hour finance and control investigation. Auditable deterministic financial truth plus narrowly scoped AI for messy free text provided maximum value and reproducibility without introducing non-deterministic latency or infrastructure complexity.

---

## 7. Anything you built or found that nobody asked for?

1. **Ticket-Level Evidence Explorer (UI Page 5):** An interactive Streamlit component allowing Finance to click any control finding and inspect the underlying ticket ID, order ID, original customer text, agent note, policy clause, and calculation formula.
2. **Hybrid Stage 1 Regex + Stage 2 LLM Classifier:** Pre-filters approximately 47% of tickets deterministically before calling Groq, minimizing API latency and cost.
3. **Reason Mismatch Taxonomy (`GW-OTHER` Breakdown):** Automatically maps generic `GW-OTHER` dropdown selections into true underlying categories (Defect, Delay, Buyer Remorse, Goodwill).

---

## 8. What did you use AI for? Which tools and models, where they helped, where they wasted time, what you threw away.

* **AI Used to Build the Project:** Antigravity / Gemini AI coding assistant was used for writing Python code, refactoring data audit engines, creating Pytest suites, drafting README documentation, and structuring Streamlit UI components.
* **AI Used Inside Product:** Groq API running model **`openai/gpt-oss-120b`** for free-text customer message and agent note reason classification.
* **Where AI Helped:** Accelerating code generation, structuring Pandas data transformations, and extracting true intent from ambiguous support text.
* **Where AI Was NOT Trusted:** Financial calculations, legacy monetary scaling, deduplication, order joins, policy threshold evaluations, and exposure aggregation were kept 100% deterministic.
* **What Was Discarded:** Initial RAG vector database prototype was discarded as unnecessary overhead.

---

## 9. Three-minute screen recording link.

https://drive.google.com/file/d/1VvhiLxX_ePRTO6_EPAbqf5dJCbiu5g97/view?usp=sharing

---

## 10. Public Google Drive link.

https://drive.google.com/file/d/1VvhiLxX_ePRTO6_EPAbqf5dJCbiu5g97/view?usp=sharing

---

## 11. Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. **Reconciliation Baseline:** The canonical refund ledger (`outputs/canonical_refund_ledger.csv`, ₹67,09,932.00 across 2,340 cases) is the single source of financial truth. Never use raw helpdesk export sums directly.
2. **Control Exposure Definition:** ₹8.24L is *Observed Control-Review Exposure* requiring operational verification. Do not report it to the board pack as confirmed financial loss or fraud.
3. **Pipeline & Fail-Safe Execution:** The pipeline is 100% deterministic for financial truth and uses Groq (`openai/gpt-oss-120b`) via `GROQ_API_KEY` in `.env` for free text. If unconfigured, the system automatically falls back to Stage 1 regex classification without crashing.

---

## 12. Honest hours spent. One number.

4.5

---

## 13. Github Repo Link.

https://github.com/hashmi09zx/vireo-refund-intelligence

