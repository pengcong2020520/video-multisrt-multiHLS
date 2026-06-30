from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/api-test.sqlite3",
        public_url_base="http://objects.test",
        storage_secret="test-secret",
        signed_url_ttl_seconds=600,
        auth_required=True,
        create_schema=True,
    )
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"X-User-Id": "user_001"}


@pytest.fixture
def db_session(app):
    with app.state.session_factory() as db:
        yield db
