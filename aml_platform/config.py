"""Application configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AML_", env_file=".env", extra="ignore")

    app_name: str = "Oracle AML / KYC / CFT Platform"
    database_url: str = "sqlite:///./aml_platform.db"
    base_currency: str = "USD"

    # Screening
    screening_threshold: float = 82.0

    # CRR review cadence (days) by risk band
    review_days_high: int = 365
    review_days_medium: int = 730
    review_days_low: int = 1095


settings = Settings()
