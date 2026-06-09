# Oracle AML / KYC / CFT Compliance Platform

An in-house, end-to-end Anti-Money Laundering (AML), Know-Your-Customer (KYC)
and Counter-Financing-of-Terrorism (CFT) platform built to cover the day-to-day
work of a financial institution's **Compliance / Financial Intelligence Unit (FIU)**.

It is designed around the FATF 40 Recommendations and a risk-based approach (RBA),
and provides the working tooling an analyst, investigator, MLRO and compliance
officer need in one system.

## What it does

| Capability | Module | Description |
|------------|--------|-------------|
| **KYC / CDD / EDD** | `core/crr.py`, `db/models.py` | Customer onboarding, due-diligence data model, beneficial ownership, PEP flags. |
| **Customer Risk Rating (CRR)** | `core/crr.py` | Weighted, multi-factor risk scoring (customer, geography, product, channel, behaviour) producing Low / Medium / High / Critical ratings and EDD triggers. |
| **Transaction Monitoring (TM)** | `core/transaction_monitoring.py` | Configurable detection scenarios: structuring/smurfing, rapid movement of funds, large cash, high-risk geography, velocity spikes, round-amounts, dormant reactivation, threshold/CTR. |
| **Customer Behaviour Detection** | `core/behavior.py` | Statistical profiling vs. a customer's own baseline (z-score) and peer-group comparison to surface anomalous activity. |
| **Sanctions / PEP / Watchlist Screening** | `core/sanctions.py` | Fuzzy name matching (token + Jaro-Winkler) against OFAC/UN/EU/PEP lists with alias handling, configurable thresholds and whitelisting. |
| **Alerts & Case Management** | `services/case_management.py` | Alert lifecycle, investigation cases, dispositions, SAR/STR drafting, full audit trail. |
| **Regulatory Reporting** | `services/reporting.py` | CTR / SAR-STR generation, MIS dashboards and compliance metrics. |
| **REST API + Dashboard** | `api/` | FastAPI service exposing every capability to compliance-unit users, with OpenAPI docs. |

## Architecture

```
                +-------------------------------------------------------+
                |                  FastAPI service (api/)               |
                |  customers | screening | monitoring | alerts | cases  |
                +-----------------------------+-------------------------+
                                              |
                +-----------------------------v-------------------------+
                |                  Services / orchestration             |
                |   onboarding · screening · monitoring · case mgmt     |
                +-----------------------------+-------------------------+
                                              |
        +-----------------+-----------------+-+---------------+-----------------+
        |                 |                 |                 |                 |
   +----v----+      +-----v-----+     +-----v-----+     +-----v-----+    +------v------+
   |   CRR   |      |    TM     |     | Behaviour |     | Sanctions |    | Reference   |
   | engine  |      | scenarios |     | analytics |     | screening |    | data (FATF) |
   +---------+      +-----------+     +-----------+     +-----------+    +-------------+
                                              |
                                    +---------v---------+
                                    |  SQLAlchemy / DB  |
                                    +-------------------+
```

The **core engines are pure Python** (no framework/DB dependency) so they can be
unit-tested, embedded in batch jobs, or called from the API interchangeably.

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. See the whole platform work end-to-end in your terminal (no browser needed)
python -m scripts.demo

# 3. Seed the database with reference data + demo customers/transactions
python -m aml_platform.db.seed

# 4. Run the API
uvicorn aml_platform.api.main:app --reload

# 5. Open the interactive docs and use every capability from the browser
#    http://127.0.0.1:8000/docs
```

`python -m scripts.demo` runs the full compliance workflow — onboard a customer,
compute the CRR, screen against sanctions/PEP lists, ingest transactions, run
monitoring, triage alerts, escalate to a case, file a SAR and view the MIS
dashboard — printing each step's real output.

Run the test suite:

```bash
pytest -q
```

## Repository layout

```
aml_platform/
  core/                 # framework-free AML engines (the compliance IP)
    enums.py            # shared enumerations
    reference_data.py   # FATF country risk, occupation/product risk tables
    models.py           # domain dataclasses
    crr.py              # Customer Risk Rating engine
    transaction_monitoring.py
    behavior.py         # behavioural / anomaly analytics
    sanctions.py        # name-screening engine
  db/                   # SQLAlchemy ORM + seed data
  services/             # orchestration, case management, reporting
  api/                  # FastAPI app + routers + schemas
  data/                 # sample watchlists & reference tables
tests/                  # pytest suite
docs/                   # methodology & operating documentation
```

## Documentation

- [`docs/methodology.md`](docs/methodology.md) — risk-scoring & detection methodology
- [`docs/operating_model.md`](docs/operating_model.md) — how the compliance unit uses the system

> **Disclaimer:** This platform is a working reference implementation. Detection
> thresholds, risk weights and watchlists must be calibrated, validated and
> independently tested against your institution's risk appetite and local
> regulator's requirements before production use.
