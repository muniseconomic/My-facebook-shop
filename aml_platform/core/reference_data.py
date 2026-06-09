"""AML reference data: country, occupation, product and channel risk tables.

The tables below are a pragmatic, illustrative baseline that mirrors how a
compliance unit encodes a risk-based approach. They MUST be reviewed and
calibrated by the MLRO against current FATF publications, the institution's
risk appetite and local regulatory guidance.

Country risk follows the FATF public statements:
  * "call for action" (black list)  -> CRITICAL
  * "increased monitoring" (grey)    -> HIGH
  * other higher-risk jurisdictions  -> HIGH / MEDIUM (corruption, secrecy)
ISO-3166 alpha-2 codes are used as keys.
"""

from __future__ import annotations

from .enums import Channel, RiskLevel

# --------------------------------------------------------------------------- #
# Country / jurisdiction risk
# --------------------------------------------------------------------------- #

# FATF "Call for Action" (high-risk jurisdictions subject to a call for action).
FATF_CALL_FOR_ACTION: set[str] = {"KP", "IR", "MM"}  # DPRK, Iran, Myanmar

# FATF "Increased Monitoring" (grey list) - illustrative snapshot.
FATF_INCREASED_MONITORING: set[str] = {
    "SY", "YE", "SS", "VE", "HT", "ML", "MZ", "BF", "CD", "TZ",
    "NG", "ZA", "AE", "PH", "VN", "BG", "HR", "MC", "NA",
}

# Jurisdictions with elevated corruption / financial-secrecy concerns.
HIGHER_RISK_SECRECY: set[str] = {
    "PA", "KY", "VG", "BS", "SC", "BZ", "LB", "AF", "SO", "LY",
    "IQ", "SD", "ZW", "CU", "RU", "BY",
}


def country_risk(country_code: str | None) -> tuple[RiskLevel, str]:
    """Return the risk band and rationale for an ISO alpha-2 country code."""
    if not country_code:
        return RiskLevel.MEDIUM, "Country unknown / not provided"
    cc = country_code.strip().upper()
    if cc in FATF_CALL_FOR_ACTION:
        return RiskLevel.CRITICAL, "FATF call-for-action jurisdiction"
    if cc in FATF_INCREASED_MONITORING:
        return RiskLevel.HIGH, "FATF increased-monitoring (grey list) jurisdiction"
    if cc in HIGHER_RISK_SECRECY:
        return RiskLevel.HIGH, "Higher-risk corruption / secrecy jurisdiction"
    return RiskLevel.LOW, "No elevated country risk identified"


# --------------------------------------------------------------------------- #
# Occupation / business-activity risk
# --------------------------------------------------------------------------- #
# Cash-intensive, high-value, or otherwise higher-ML-risk activities.
HIGH_RISK_OCCUPATIONS: dict[str, str] = {
    "money_services_business": "Cash-intensive, layering risk",
    "msb": "Money services business",
    "casino": "Gambling - high cash, placement risk",
    "gambling": "Gambling / betting",
    "precious_metals_dealer": "High-value, portable store of value",
    "jewellery": "High-value goods, cash-intensive",
    "art_dealer": "Opaque valuation, layering risk",
    "real_estate": "High-value, integration risk",
    "cash_intensive_retail": "Placement risk (e.g. car wash, restaurant)",
    "import_export": "Trade-based money laundering risk",
    "crypto_exchange": "Virtual asset service provider",
    "vasp": "Virtual asset service provider",
    "arms_dealer": "Dual-use / proliferation risk",
    "defence_contractor": "Proliferation / sanctions risk",
    "ngo": "Potential TF diversion risk",
    "charity": "Potential TF diversion risk",
    "politician": "PEP - corruption risk",
    "lawyer": "Gatekeeper / trust-account risk",
    "accountant": "Gatekeeper risk",
    "company_formation_agent": "Shell-company / opacity risk",
}

LOW_RISK_OCCUPATIONS: set[str] = {
    "salaried_employee", "teacher", "nurse", "engineer", "student",
    "retired", "civil_servant", "doctor",
}


def occupation_risk(occupation: str | None) -> tuple[RiskLevel, str]:
    if not occupation:
        return RiskLevel.MEDIUM, "Occupation not provided"
    key = occupation.strip().lower().replace(" ", "_")
    if key in HIGH_RISK_OCCUPATIONS:
        return RiskLevel.HIGH, HIGH_RISK_OCCUPATIONS[key]
    if key in LOW_RISK_OCCUPATIONS:
        return RiskLevel.LOW, "Lower-risk occupation"
    return RiskLevel.MEDIUM, "Occupation not classified as low risk"


# --------------------------------------------------------------------------- #
# Product / service risk
# --------------------------------------------------------------------------- #
PRODUCT_RISK: dict[str, RiskLevel] = {
    "savings_account": RiskLevel.LOW,
    "current_account": RiskLevel.LOW,
    "term_deposit": RiskLevel.LOW,
    "salary_account": RiskLevel.LOW,
    "personal_loan": RiskLevel.LOW,
    "mortgage": RiskLevel.MEDIUM,
    "credit_card": RiskLevel.MEDIUM,
    "trade_finance": RiskLevel.HIGH,
    "correspondent_banking": RiskLevel.HIGH,
    "private_banking": RiskLevel.HIGH,
    "wealth_management": RiskLevel.HIGH,
    "cross_border_remittance": RiskLevel.HIGH,
    "prepaid_card": RiskLevel.HIGH,
    "crypto_custody": RiskLevel.CRITICAL,
    "private_investment_company": RiskLevel.HIGH,
}


def product_risk(product: str | None) -> tuple[RiskLevel, str]:
    if not product:
        return RiskLevel.MEDIUM, "Product not provided"
    key = product.strip().lower().replace(" ", "_")
    level = PRODUCT_RISK.get(key)
    if level is None:
        return RiskLevel.MEDIUM, "Product not classified"
    return level, f"Product '{key}' baseline risk = {level.value}"


# --------------------------------------------------------------------------- #
# Channel / delivery risk
# --------------------------------------------------------------------------- #
CHANNEL_RISK: dict[Channel, RiskLevel] = {
    Channel.BRANCH: RiskLevel.LOW,  # face-to-face
    Channel.ATM: RiskLevel.LOW,
    Channel.ONLINE: RiskLevel.MEDIUM,
    Channel.MOBILE: RiskLevel.MEDIUM,
    Channel.AGENT: RiskLevel.MEDIUM,
    Channel.INTRODUCED: RiskLevel.HIGH,  # non-face-to-face / third-party
    Channel.CORRESPONDENT: RiskLevel.HIGH,
}


def channel_risk(channel: Channel | None) -> tuple[RiskLevel, str]:
    if channel is None:
        return RiskLevel.MEDIUM, "Channel not provided"
    level = CHANNEL_RISK.get(channel, RiskLevel.MEDIUM)
    return level, f"Onboarding channel '{channel.value}' risk = {level.value}"


# Regulatory / operational thresholds (illustrative, in account base currency).
CTR_THRESHOLD = 10_000.0          # Currency Transaction Report threshold
STRUCTURING_BAND = 0.90           # transactions >= 90% of CTR threshold are "near"
LARGE_CASH_THRESHOLD = 10_000.0
