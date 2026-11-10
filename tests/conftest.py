import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def legacy_local_access(monkeypatch):
    # Existing service tests exercise API-key/local access; login tests opt back in.
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "COMMANDCODE_PLAN", "catalog")
