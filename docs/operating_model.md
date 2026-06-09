# Compliance Unit Operating Model

How the different roles in the compliance / financial intelligence unit (FIU)
use the platform day to day. The platform is the single end-to-end system for
the activities below.

## Roles

| Role | Responsibilities | Primary endpoints |
|------|------------------|-------------------|
| **Onboarding / KYC officer** | Capture CDD data, run CRR and onboarding screening, request EDD where required | `POST /customers/onboard`, `POST /customers/{ref}/screen` |
| **TM analyst (L1)** | Triage transaction-monitoring & behaviour alerts, clear false positives, escalate genuine ones | `GET /alerts`, `POST /alerts/{id}/assign`, `POST /alerts/{id}/close` |
| **Investigator (L2)** | Investigate escalated cases, gather evidence, record findings | `POST /cases`, `GET /cases/{id}`, `POST /cases/{id}/events` |
| **MLRO** | Review cases, decide on SAR/STR filing, sign-off | `GET /reporting/sar-draft/{id}`, `POST /cases/{id}/file-sar`, `POST /cases/{id}/close` |
| **Compliance manager** | Monitor KPIs, portfolio risk, productivity, false-positive rates | `GET /reporting/dashboard` |
| **Screening officer** | Ad-hoc and payment-time name screening | `POST /screening/name` |

## End-to-end workflow

1. **Onboard** a customer (`/customers/onboard`). The system persists the
   record, computes the **CRR** (assigning SDD/CDD/EDD and a review date) and
   runs **sanctions/PEP screening**, raising screening alerts for strong matches.
2. **Ingest transactions** (`/transactions`) from core banking / payments —
   typically a batch feed.
3. **Run monitoring** (`/transactions/monitor` for the whole book, nightly, or
   `/transactions/monitor/{ref}` ad hoc). TM scenarios and behaviour analytics
   generate **alerts**.
4. **Triage** alerts (`/alerts`): assign to an analyst, then close as a false
   positive (with rationale) or escalate.
5. **Escalate** related alerts into a **case** (`/cases`). All linked alerts move
   to `ESCALATED` and a `CASE_OPENED` audit event is recorded.
6. **Investigate**: append findings as audit events (`/cases/{id}/events`).
7. **Decide**: the MLRO generates a **SAR/STR draft** (`/reporting/sar-draft`),
   then either files it (`/cases/{id}/file-sar`, recording the FIU reference) or
   closes the case with no action.
8. **Report**: management monitors the **MIS dashboard** and the **CTR feed**.

## Suggested batch schedule

| Job | Frequency | Call |
|-----|-----------|------|
| Portfolio transaction monitoring | Nightly | `POST /transactions/monitor` |
| Periodic CRR refresh | On review-date / event-driven | `POST /customers/{ref}/reassess` |
| Watchlist re-screening of the book | On list update | `POST /customers/{ref}/screen` per customer |
| CTR extract | Daily | `GET /reporting/ctr` |

## Controls & governance

- **Explainability** — every rating, detection and screening hit carries its
  rationale / score, supporting the four-eyes principle and examiner challenge.
- **Audit trail** — case events are immutable and attributed to an actor.
- **Tuning & validation** — risk weights (`crr.DEFAULT_WEIGHTS`), TM thresholds
  (`TMConfig`) and screening thresholds (`settings.screening_threshold`) are
  externalised for periodic calibration and independent model validation.
- **Segregation** — onboarding, monitoring/triage and SAR decisioning are
  distinct steps with distinct endpoints, supporting role-based access control
  when deployed behind the institution's IAM/gateway.
