"""End-to-end API test exercising the full compliance workflow:
onboard -> screen -> ingest -> monitor -> alert -> case -> SAR."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_onboarding_triggers_crr_and_screening(client):
    payload = {
        "customer_ref": "CUST-9001",
        "full_name": "Viktor Petrov",
        "customer_type": "INDIVIDUAL",
        "date_of_birth": "1968-04-12",
        "nationality": "RU",
        "residence_country": "RU",
        "occupation": "crypto_exchange",
        "onboarding_channel": "ONLINE",
        "products": ["crypto_custody"],
    }
    r = client.post("/customers/onboard", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    # High-risk profile (RU + crypto) -> elevated rating + EDD
    assert body["crr"]["risk_level"] in ("HIGH", "CRITICAL")
    # Sanctions screening should flag the OFAC test entry.
    assert body["screening"]["matches"], "expected a sanctions match"
    assert body["screening"]["alerts_created"]


def test_full_monitoring_to_sar_workflow(client):
    # 1. Onboard a corporate customer.
    client.post("/customers/onboard", json={
        "customer_ref": "CUST-9002",
        "full_name": "Funnel Co",
        "customer_type": "CORPORATE",
        "incorporation_country": "AE",
        "industry": "import_export",
        "expected_monthly_turnover": 20000,
    })

    # 2. Ingest transactions that should trip monitoring (high-risk geography).
    txns = [
        {"txn_ref": "WX-1", "customer_ref": "CUST-9002",
         "timestamp": "2026-05-01T09:00:00", "amount": 50000,
         "direction": "CREDIT", "txn_type": "WIRE_IN",
         "counterparty_country": "IR"},
        {"txn_ref": "WX-2", "customer_ref": "CUST-9002",
         "timestamp": "2026-05-01T15:00:00", "amount": 48000,
         "direction": "DEBIT", "txn_type": "WIRE_OUT",
         "counterparty_country": "KP"},
    ]
    for t in txns:
        assert client.post("/transactions", json=t).status_code == 200

    # 3. Run monitoring.
    r = client.post("/transactions/monitor/CUST-9002")
    assert r.status_code == 200
    result = r.json()
    scenarios = {d["scenario"] for d in result["detections"]}
    assert "HIGH_RISK_GEOGRAPHY" in scenarios
    assert result["alerts_created"]

    # 4. Pull alerts, escalate to a case.
    alerts = client.get("/alerts", params={"alert_type": "TM"}).json()
    alert_ids = [a["id"] for a in alerts][:2]
    case = client.post("/cases", json={
        "alert_ids": alert_ids,
        "title": "Suspicious high-risk geography flows",
        "actor": "analyst.amal",
    }).json()
    assert case["status"] == "UNDER_INVESTIGATION"

    # 5. File a SAR and verify the audit trail.
    filed = client.post(f"/cases/{case['id']}/file-sar", json={
        "actor": "mlro.sara", "sar_reference": "SAR-2026-0001",
    }).json()
    assert filed["sar_reference"] == "SAR-2026-0001"

    detail = client.get(f"/cases/{case['id']}").json()
    actions = {e["action"] for e in detail["audit_trail"]}
    assert {"CASE_OPENED", "SAR_FILED"} <= actions

    # 6. SAR draft generation.
    draft = client.get(f"/reporting/sar-draft/{case['id']}").json()
    assert draft["case_ref"] == case["case_ref"]
    assert draft["grounds_for_suspicion"]


def test_screening_endpoint_direct(client):
    r = client.post("/screening/name", json={"name": "Global Horizon Trading"})
    assert r.status_code == 200
    body = r.json()
    assert body["match_count"] >= 1
    assert body["risk_level"] in ("HIGH", "CRITICAL")


def test_dashboard_reports(client):
    client.post("/customers/onboard", json={
        "customer_ref": "CUST-9003", "full_name": "Clean Person",
        "nationality": "GB", "residence_country": "GB",
        "occupation": "teacher", "onboarding_channel": "BRANCH",
        "products": ["savings_account"],
    })
    r = client.get("/reporting/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["customers"] >= 1
    assert "risk_distribution" in body
