from aml_platform.core.crr import CRREngine
from aml_platform.core.enums import (
    Channel,
    CustomerType,
    DueDiligenceLevel,
    RiskLevel,
)
from aml_platform.core.models import CustomerProfile


def test_low_risk_individual():
    profile = CustomerProfile(
        customer_id="C1", full_name="Jane Doe",
        customer_type=CustomerType.INDIVIDUAL, nationality="GB",
        residence_country="GB", occupation="teacher",
        onboarding_channel=Channel.BRANCH, products=["savings_account"],
    )
    result = CRREngine().assess(profile)
    assert result.risk_level == RiskLevel.LOW
    assert result.due_diligence == DueDiligenceLevel.SIMPLIFIED
    assert not result.requires_edd


def test_pep_forces_minimum_high():
    profile = CustomerProfile(
        customer_id="C2", full_name="Some Minister", is_pep=True,
        nationality="GB", residence_country="GB", occupation="teacher",
        onboarding_channel=Channel.BRANCH, products=["savings_account"],
    )
    result = CRREngine().assess(profile)
    assert result.risk_level.rank >= RiskLevel.HIGH.rank
    assert result.requires_edd
    assert any("PEP" in o for o in result.overrides)


def test_call_for_action_jurisdiction_is_critical():
    profile = CustomerProfile(
        customer_id="C3", full_name="Test Entity",
        customer_type=CustomerType.CORPORATE, incorporation_country="IR",
        countries_of_operation=["KP"], industry="import_export",
    )
    result = CRREngine().assess(profile)
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.requires_edd


def test_factors_are_explainable():
    profile = CustomerProfile(customer_id="C4", full_name="X", nationality="GB")
    result = CRREngine().assess(profile)
    names = {f.name for f in result.factors}
    assert {"customer_type", "geography", "occupation", "product",
            "channel", "pep", "adverse_media"} <= names
    for f in result.factors:
        assert f.rationale  # every factor has a rationale


def test_weighted_average_is_normalised():
    profile = CustomerProfile(customer_id="C5", full_name="X", nationality="GB")
    result = CRREngine().assess(profile)
    assert 0 <= result.overall_score <= 100
