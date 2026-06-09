"""Shared test fixtures. Points the platform at an isolated temporary database
before any aml_platform module is imported."""

import os

import pytest

# Must be set before aml_platform.config is first imported. Kept inside the
# repo working tree (it is git-ignored) to avoid sandbox /tmp write quirks.
_TMP_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aml_test.db")
os.environ["AML_DATABASE_URL"] = f"sqlite:///{_TMP_DB}"


@pytest.fixture()
def client():
    """A FastAPI TestClient backed by a freshly-reset temp database.

    We drop and recreate the schema (rather than deleting the file) so the
    singleton engine's pooled connections never point at an unlinked inode.
    """
    from fastapi.testclient import TestClient

    from aml_platform.api.main import app
    from aml_platform.db.database import Base, SessionLocal, engine, init_db

    Base.metadata.drop_all(bind=engine)
    init_db()

    from aml_platform.db.seed import load_watchlist

    db = SessionLocal()
    try:
        load_watchlist(db)
    finally:
        db.close()

    with TestClient(app) as c:
        yield c
