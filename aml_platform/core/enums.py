"""Shared enumerations used across the AML platform."""

from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    """Standard four-band risk classification used by CRR, screening and TM."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]

    @classmethod
    def from_score(cls, score: float) -> "RiskLevel":
        """Map a normalised 0-100 risk score to a band."""
        if score >= 80:
            return cls.CRITICAL
        if score >= 60:
            return cls.HIGH
        if score >= 35:
            return cls.MEDIUM
        return cls.LOW


class CustomerType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR"
    CORPORATE = "CORPORATE"
    TRUST = "TRUST"
    NPO = "NPO"  # non-profit organisation
    FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION"
    GOVERNMENT = "GOVERNMENT"


class DueDiligenceLevel(str, Enum):
    SIMPLIFIED = "SIMPLIFIED"  # SDD
    STANDARD = "STANDARD"  # CDD
    ENHANCED = "ENHANCED"  # EDD


class Channel(str, Enum):
    BRANCH = "BRANCH"  # face-to-face
    ONLINE = "ONLINE"
    MOBILE = "MOBILE"
    ATM = "ATM"
    AGENT = "AGENT"
    CORRESPONDENT = "CORRESPONDENT"
    INTRODUCED = "INTRODUCED"  # third-party introduced / non-face-to-face


class TransactionType(str, Enum):
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    WIRE_IN = "WIRE_IN"
    WIRE_OUT = "WIRE_OUT"
    TRANSFER = "TRANSFER"
    CARD_PAYMENT = "CARD_PAYMENT"
    CHEQUE = "CHEQUE"
    FX = "FX"
    LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT"
    LOAN_REPAYMENT = "LOAN_REPAYMENT"


class Direction(str, Enum):
    CREDIT = "CREDIT"  # money in
    DEBIT = "DEBIT"  # money out


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    CLOSED_FALSE_POSITIVE = "CLOSED_FALSE_POSITIVE"
    CLOSED_TRUE_POSITIVE = "CLOSED_TRUE_POSITIVE"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    PENDING_MLRO = "PENDING_MLRO"
    SAR_FILED = "SAR_FILED"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"


class ScreeningListType(str, Enum):
    SANCTIONS = "SANCTIONS"
    PEP = "PEP"
    ADVERSE_MEDIA = "ADVERSE_MEDIA"
    INTERNAL_BLACKLIST = "INTERNAL_BLACKLIST"


class Severity(str, Enum):
    """Severity attached to a monitoring alert / detection hit."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
