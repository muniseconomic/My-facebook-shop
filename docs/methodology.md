# AML / KYC / CFT Methodology

This document describes how the platform's engines work so that the compliance
unit, internal audit, model validation and the regulator can understand and
challenge the logic. Everything is intentionally **transparent and explainable**
— there are no opaque black-box models.

> All thresholds, weights and lists below are *defaults*. They must be reviewed,
> calibrated and independently validated against the institution's risk appetite,
> product set and local regulatory requirements before production use.

---

## 1. Customer Risk Rating (CRR)

Implements a risk-based approach (FATF Recommendation 1). Each customer is scored
across independent **risk factors**, each producing a 0-100 sub-score derived from
a qualitative band (Low=15, Medium=45, High=75, Critical=100).

| Factor | Default weight | Drivers |
|--------|---------------:|---------|
| Customer type | 0.15 | Individual / corporate / trust / NPO / FI inherent risk |
| Geography | 0.25 | Worst-case of nationality, residence, incorporation, operating countries vs FATF lists |
| Occupation / industry | 0.15 | Cash-intensive, gatekeeper, VASP, high-value-goods activities |
| Product / service | 0.15 | Trade finance, correspondent, private banking, crypto custody, etc. |
| Channel | 0.10 | Face-to-face vs non-face-to-face / introduced |
| PEP exposure | 0.12 | PEP, or family / close associate of a PEP |
| Adverse media | 0.08 | Negative news identified |

**Overall score** = Σ(sub-score × weight) ÷ Σ(weights), mapped to a band:

```
score ≥ 80  → CRITICAL      35 ≤ score < 60 → MEDIUM
60 ≤ score < 80 → HIGH       score < 35     → LOW
```

### Mandatory escalation floors

A pure weighted average can dilute a single extreme factor, so non-negotiable
floors are applied **on top** of the average:

- PEP → minimum **HIGH**
- Exposure to a FATF call-for-action jurisdiction → **CRITICAL**
- Adverse media → minimum **HIGH**
- Any single **CRITICAL**-band factor → minimum **HIGH**
- Two or more **HIGH**-or-above factors → minimum **HIGH**

Every applied floor is recorded in the assessment's `overrides`, and every factor
carries a human-readable `rationale`.

### Due diligence & review cadence

| Rating | Due diligence | Default review cadence |
|--------|---------------|------------------------|
| LOW | Simplified (SDD) | 36 months |
| MEDIUM | Standard (CDD) | 24 months |
| HIGH / CRITICAL | Enhanced (EDD) | 12 months |

---

## 2. Transaction Monitoring (TM)

A library of independent, parameterised detection scenarios run over a customer's
transactions. Each produces explainable `Detection` records with a severity and a
0-100 indicative score.

| Scenario | Typology | Default trigger |
|----------|----------|-----------------|
| `STRUCTURING` | Placement / smurfing | ≥3 cash txns in 7 days, each 50–100% of the CTR threshold, aggregating ≥ threshold |
| `LARGE_CASH_CTR` | Reporting obligation | Single cash txn ≥ CTR threshold (10,000) |
| `RAPID_MOVEMENT` | Layering | Inflow with ≥80% flowing out within 72h |
| `HIGH_RISK_GEOGRAPHY` | Geographic risk | Counterparty in FATF grey/black or secrecy jurisdiction |
| `VELOCITY` | Unusual activity | Monthly throughput ≥ 3× expected turnover |
| `ROUND_AMOUNTS` | Structuring indicator | ≥3 round-number (×1,000) transactions |
| `DORMANT_REACTIVATION` | Account takeover / mule | ≥180 days dormant then a ≥5,000 transaction |
| `RAPID_PASS_THROUGH` | Funnel / mule account | High two-way turnover retaining <10% over 30 days |

All thresholds live in `TMConfig` and can be tuned per institution without code
changes.

---

## 3. Customer Behaviour Detection

Two complementary statistical techniques, both reported with the underlying
z-score so an investigator can defend the alert:

- **Self-baseline deviation** — current-period volume / frequency / new
  counterparty geographies compared to the customer's own rolling baseline using
  a z-score (default trigger |z| ≥ 2.5).
- **Peer-group comparison** — the customer compared to the distribution of a
  peer segment; flags statistical outliers (z ≥ 2.5) even when internally
  consistent. Peer groups smaller than 5 are ignored as non-significant.

---

## 4. Sanctions / PEP / Watchlist Screening

Fuzzy name matching of a subject against OFAC / UN / EU / internal / PEP lists.

1. **Normalisation** — case-fold, strip diacritics and punctuation, remove
   corporate (`ltd`, `llc`, …) and honorific noise tokens.
2. **Similarity** — the strongest of token-set, token-sort and partial ratios
   (handles reordered name parts, middle names, transliteration and typos).
3. **Alias expansion** — every alias on a list entry is screened; best score wins.
4. **DoB corroboration** — a matching date of birth adds an 8-point confidence
   boost.
5. **Thresholding** — default auto-hit threshold 82; ≥90 is treated as a strong
   match. A sanctions strong match → CRITICAL screening risk.
6. **Whitelisting** — previously cleared (subject, entry) pairs are suppressed to
   control false positives.

---

## 5. Alerts, Cases and Reporting

```
Detection ─► Alert (OPEN) ─► triage (IN_REVIEW)
                              ├─► close FALSE / TRUE positive
                              └─► escalate ─► Case (UNDER_INVESTIGATION)
                                               ├─► SAR/STR filed
                                               └─► closed no action
```

Every case state change is written as an immutable `CaseEvent` (actor, action,
note, timestamp), giving a complete audit trail. The reporting module produces a
CTR feed, a structured SAR/STR draft from a case, and an MIS dashboard
(portfolio risk distribution, alert/case KPIs, false-positive rate).
