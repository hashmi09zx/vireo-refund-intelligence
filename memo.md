# Executive Memo: Refund Reconciliation & Control Review

**To:** Arjun Mehta, Finance Controller  
**From:** Support Data & Financial Intelligence Team  
**Date:** October 7, 2026  
**Subject:** Reconciled refund totals, growth driver analysis, and control-review exposure  

---

## 1. Executive Takeaway

The raw support helpdesk export contained significant data corruption—including unnormalized legacy Freshdesk currency values and duplicate migrated ticket records—making initial export sums unreliable. 

By constructing an auditable canonical refund ledger, we established Vireo's single source of truth: **total actual refunds across the 18-month period were ₹67,09,932.00 across 2,340 canonical cases**.

### Key Findings on Refund Outlay Growth:
* **Outlay Growth:** Quarterly refund outlay grew **+109.95%** (from ₹6,09,583.00 in Q1 2025 to ₹12,79,823.00 in Q2 2026).
* **Ticket Volume Growth:** Support ticket volume grew **+116.24%** (from 1,053 to 2,277 tickets/quarter).
* **Refund Rate Propensity:** The frontline refund rate remained essentially flat (**+0.64 percentage points**, moving from 20.13% to 20.77%).
* **Value per Ticket:** Average refund value per ticket decreased slightly (**-2.91%**, from ₹578.90 to ₹562.07).

**Conclusion:** Rising refund outlay was driven almost entirely by **ticket volume growth**, not by frontline agents becoming lenient or giving away money. Frontline refund behavior remained consistent.

---

## 2. Refund Reason Analysis

The largest single dropdown reason code by financial value is **`Goodwill / Other` (`GW-OTHER`)**, accounting for **₹29,07,036.00 (43.3% of total refund outlay)** across 1,029 cases.

Because `GW-OTHER` is the top option in the helpdesk dropdown menu, agents frequently select it as a default for diverse customer inquiries. Free-text analysis reveals that `GW-OTHER` tickets include genuine product defects, shipping delays, and buyer remorse alongside legitimate goodwill gestures. Generic dropdown selections should **not** be interpreted as automatic policy violations.

---

## 3. Control-Review Findings & Exposure

Our policy control engine evaluated support tickets against operating policy rules, identifying **₹8,24,245.00** in combined gross non-overlapping policy control review exposure:

| Control Rule | Identified Scope | Financial Value / Excess | Operational Signal |
| :--- | :--- | :--- | :--- |
| **R1 — Refund + Replacement** | 166 cases | **₹5,74,191.00** | Refund raised AND replacement unit issued for same order |
| **R2 — Refund Exceeds Order Value** | 98 orders | **₹2,50,054.00** | Deduplicated excess refund over original order value |
| **Total Review Exposure** | **253 unique tickets** | **₹8,24,245.00** | **Observed Control-Review Exposure** |

> ⚠️ **Important Accounting Caveat:** These figures represent **Observed Control-Review Exposure**, not confirmed financial loss or fraud. Operations must verify underlying tickets (e.g. checking whether replacements were authorized warranty exchanges or partial order adjustments) before treating items as cash leakage.

---

## 4. Recommended Actions for Finance & Operations

1. **Prioritize R1 & R2 Operational Audit:** Focus immediate manual review on the 166 R1 cases (₹5.74L) and 98 R2 orders (₹2.50L) using the interactive Evidence Explorer.
2. **Adopt Canonical Reporting Baseline:** Align future board pack reporting with the canonical refund ledger (averaging ~₹11.18L/quarter) rather than raw unnormalized export sums.
3. **Enforce Refund + Replacement Controls:** Implement system guards in the helpdesk software requiring team lead approval before a refund and replacement can be issued on the same order.
4. **Refine Intake Dropdown Taxonomy:** Restructure helpdesk dropdown reason codes to reduce reliance on generic `GW-OTHER` selections.
5. **Separate Volume from Propensity:** Monitor support ticket volume and refund rate as separate metrics in executive dashboards.

---

## 5. Method & Confidence

* **Financial Reliability:** 100% of financial math, legacy unit conversions (/100), deduplication, order joins, and exposure aggregations are calculated using deterministic code, validated by **26 automated Pytest tests**.
* **Audit Trail:** Every control finding is linked to ticket ID, resolved order ID, agent ID, original customer text, agent notes, and policy reference.
* **Narrow AI Usage:** Artificial intelligence was used strictly for interpreting messy free-text notes. Ambiguous cases default to manual review queues.
