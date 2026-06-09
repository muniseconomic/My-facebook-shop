"""FastAPI application entry point for the AML / KYC / CFT platform."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ..config import settings
from ..db.database import init_db
from .routers import alerts, cases, customers, reporting, screening, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "In-house AML / KYC / CFT compliance platform providing customer "
        "due diligence, customer risk rating, transaction monitoring, "
        "behaviour detection, sanctions/PEP screening, alert & case "
        "management and regulatory reporting."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["System"], summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return """
    <html><head><title>AML / KYC / CFT Platform</title>
    <style>
      body{font-family:system-ui,sans-serif;margin:3rem auto;max-width:760px;color:#1a2332}
      h1{color:#0b3d91} code{background:#eef;padding:2px 6px;border-radius:4px}
      li{margin:.4rem 0} a{color:#0b3d91}
    </style></head><body>
    <h1>Oracle AML / KYC / CFT Compliance Platform</h1>
    <p>End-to-end tooling for the compliance / financial intelligence unit.</p>
    <ul>
      <li><b>KYC / CDD / EDD</b> &amp; <b>Customer Risk Rating</b> &mdash; <code>/customers</code></li>
      <li><b>Transaction Monitoring</b> &amp; <b>Behaviour detection</b> &mdash; <code>/transactions</code></li>
      <li><b>Sanctions / PEP / Watchlist screening</b> &mdash; <code>/screening</code></li>
      <li><b>Alerts</b> &mdash; <code>/alerts</code> &nbsp; <b>Case management</b> &mdash; <code>/cases</code></li>
      <li><b>Reporting / MIS / CTR / SAR</b> &mdash; <code>/reporting</code></li>
    </ul>
    <p>Explore the full API at <a href="/docs">/docs</a> (Swagger) or
       <a href="/redoc">/redoc</a>.</p>
    </body></html>
    """


app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(screening.router)
app.include_router(alerts.router)
app.include_router(cases.router)
app.include_router(reporting.router)
