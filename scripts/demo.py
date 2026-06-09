"""Guided, end-to-end walkthrough of the AML / KYC / CFT platform.

Runs the whole compliance workflow against a fresh in-memory demo so any
employee can SEE the system work without a browser:

    onboard -> CRR + screening -> ingest -> monitor -> triage
            -> escalate to case -> investigate -> file SAR -> dashboard

Run with:  python -m scripts.demo
"""

from __future__ import annotations

import json
import os

# Use an isolated demo database (created fresh each run).
os.environ.setdefault("AML_DATABASE_URL", "sqlite:///./aml_demo.db")

from fastapi.testclient import TestClient  # noqa: E402

from aml_platform.api.main import app  # noqa: E402
from aml_platform.db.database import Base, SessionLocal, engine, init_db  # noqa: E402
from aml_platform.db.seed import load_watchlist  # noqa: E402

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def title(n: int, text: str) -> None:
    print(f"\n{C}{B}{'═' * 78}\n STEP {n}.  {text}\n{'═' * 78}{X}")


def show(label: str, data) -> None:
    print(f"{Y}{label}{X}")
    print(json.dumps(data, indent=2, default=str))


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        load_watchlist(db)
    finally:
        db.close()


def main() -> None:
    reset_db()
    client = TestClient(app)

    print(f"{B}{C}Oracle AML / KYC / CFT Compliance Platform — live walkthrough{X}")
    print("A fresh demo database has been initialised with the sanctions/PEP watchlist.")

    # ── 1. Onboard a clean low-risk customer ────────────────────────────────
    title(1, "ONBOARD a low-risk retail customer (KYC + CRR + screening)")
    r = client.post("/customers/onboard", json={
        "customer_ref": "CUST-2001", "full_name": "Alice Johnson",
        "customer_type": "INDIVIDUAL", "nationality": "GB",
        "residence_country": "GB", "occupation": "teacher",
        "onboarding_channel": "BRANCH", "products": ["savings_account"],
    }).json()
    print(f"{G}→ Risk rating: {r['crr']['risk_level']} "
          f"(score {r['crr']['overall_score']}), "
          f"due diligence: {r['crr']['due_diligence']}{X}")
    print(f"{G}→ Screening matches: {len(r['screening']['matches'])}{X}")

    # ── 2. Onboard a high-risk customer that hits a sanctions list ──────────
    title(2, "ONBOARD a high-risk customer — note CRR escalation + sanctions hit")
    r = client.post("/customers/onboard", json={
        "customer_ref": "CUST-2002", "full_name": "Viktor Petrov",
        "customer_type": "INDIVIDUAL", "date_of_birth": "1968-04-12",
        "nationality": "RU", "residence_country": "RU",
        "occupation": "crypto_exchange", "onboarding_channel": "ONLINE",
        "products": ["crypto_custody"],
    }).json()
    print(f"{R}→ Risk rating: {r['crr']['risk_level']} "
          f"(score {r['crr']['overall_score']}){X}")
    print(f"{Y}→ CRR escalation overrides:{X}")
    for o in r["crr"]["overrides"]:
        print(f"   • {o}")
    if r["screening"]["matches"]:
        m = r["screening"]["matches"][0]
        print(f"{R}→ SANCTIONS HIT: '{m['subject_name']}' ~ '{m['matched_name']}' "
              f"= {m['score']}% on {m['entry']['source']} "
              f"({m['entry']['program']}){X}")

    # ── 3. Ingest transactions for a suspicious corporate ───────────────────
    title(3, "INGEST transactions for a corporate customer")
    client.post("/customers/onboard", json={
        "customer_ref": "CUST-2003", "full_name": "Funnel Trading Co",
        "customer_type": "CORPORATE", "incorporation_country": "AE",
        "industry": "import_export", "expected_monthly_turnover": 20000,
    })
    txns = [
        {"txn_ref": "T-1", "customer_ref": "CUST-2003",
         "timestamp": "2026-05-01T09:00:00", "amount": 50000,
         "direction": "CREDIT", "txn_type": "WIRE_IN", "is_cross_border": True,
         "counterparty_country": "IR", "counterparty_name": "Tehran Imports"},
        {"txn_ref": "T-2", "customer_ref": "CUST-2003",
         "timestamp": "2026-05-01T16:00:00", "amount": 47000,
         "direction": "DEBIT", "txn_type": "WIRE_OUT", "is_cross_border": True,
         "counterparty_country": "KP", "counterparty_name": "Unknown"},
        {"txn_ref": "T-3", "customer_ref": "CUST-2003",
         "timestamp": "2026-05-02T10:00:00", "amount": 15000,
         "direction": "CREDIT", "txn_type": "CASH_DEPOSIT", "is_cash": True},
    ]
    for t in txns:
        client.post("/transactions", json=t)
    print(f"{G}→ Ingested {len(txns)} transactions for CUST-2003{X}")

    # ── 4. Run transaction monitoring ───────────────────────────────────────
    title(4, "RUN transaction monitoring — detection scenarios fire")
    mon = client.post("/transactions/monitor/CUST-2003").json()
    print(f"{G}→ {mon['transactions_evaluated']} txns evaluated, "
          f"{len(mon['detections'])} detections{X}")
    for d in mon["detections"]:
        col = R if d["severity"] in ("HIGH", "CRITICAL") else Y
        print(f"   {col}[{d['severity']:>8}] {d['scenario']:<22} {d['description']}{X}")

    # ── 5. Triage alerts ────────────────────────────────────────────────────
    title(5, "TRIAGE — analyst picks up the open alerts")
    alerts = client.get("/alerts", params={"alert_type": "TM"}).json()
    tm_alert_ids = [a["id"] for a in alerts if a["scenario"] == "HIGH_RISK_GEOGRAPHY"]
    client.post(f"/alerts/{tm_alert_ids[0]}/assign", json={"analyst": "analyst.amal"})
    print(f"{G}→ {len(alerts)} TM alerts open; assigned alert "
          f"#{tm_alert_ids[0]} to analyst.amal{X}")

    # ── 6. Escalate to a case ───────────────────────────────────────────────
    title(6, "ESCALATE related alerts into an investigation case")
    case = client.post("/cases", json={
        "alert_ids": tm_alert_ids,
        "title": "High-risk geography pass-through (IR inflow / KP outflow)",
        "actor": "analyst.amal",
        "summary": "Funds received from Iran and rapidly forwarded to DPRK.",
    }).json()
    print(f"{G}→ Opened {case['case_ref']} (status {case['status']}, "
          f"priority {case['priority']}){X}")

    # ── 7. Investigate + file a SAR ─────────────────────────────────────────
    title(7, "INVESTIGATE and file a SAR/STR (MLRO)")
    client.post(f"/cases/{case['id']}/events", json={
        "actor": "investigator.omar", "action": "EVIDENCE_ADDED",
        "note": "No commercial rationale for IR->KP corridor; counterparties unverified.",
    })
    client.post(f"/cases/{case['id']}/file-sar", json={
        "actor": "mlro.sara", "sar_reference": "SAR-2026-0007",
        "note": "Filed with the FIU.",
    })
    draft = client.get(f"/reporting/sar-draft/{case['id']}").json()
    print(f"{G}→ SAR draft generated for {draft['case_ref']}:{X}")
    print(f"   Subject : {draft['subject']['name']} "
          f"({draft['subject']['risk_level']})")
    print(f"   Grounds for suspicion:")
    for g in draft["grounds_for_suspicion"]:
        print(f"     {g}")

    detail = client.get(f"/cases/{case['id']}").json()
    print(f"{Y}→ Immutable audit trail:{X}")
    for e in detail["audit_trail"]:
        print(f"   {e['at'][:19]}  {e['actor']:<18} {e['action']}")

    # ── 8. Management dashboard ─────────────────────────────────────────────
    title(8, "MIS DASHBOARD — the compliance manager's view")
    dash = client.get("/reporting/dashboard").json()
    print(f"   Customers          : {dash['customers']}")
    print(f"   Risk distribution  : {dash['risk_distribution']}")
    print(f"   Open alerts        : {dash['open_alerts']}")
    print(f"   Open cases         : {dash['open_cases']}")
    print(f"   SARs filed         : {dash['sars_filed']}")
    print(f"   Alert KPIs         : {dash['alert_kpis']}")

    ctr = client.get("/reporting/ctr").json()
    print(f"   CTR-reportable txns: {ctr['count']} (threshold {ctr['threshold']:,.0f})")

    print(f"\n{G}{B}Walkthrough complete.{X} Start the interactive API anytime with:")
    print(f"   {C}uvicorn aml_platform.api.main:app --reload{X}   →  open /docs\n")


if __name__ == "__main__":
    main()
