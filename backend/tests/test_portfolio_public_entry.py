"""Acceptance coverage for public entry into the isolated portfolio database."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from redis import RedisError
from sqlalchemy import func, select

from app.api.routes import auth
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_token, utcnow
from app.db.models import ApplicationSetting, GoogleConnection, GoogleCredential, UserSession
from app.domain import portfolio_access
from app.main import app

pytestmark = pytest.mark.skipif(
    settings.app_env != "portfolio" or engine.url.database != "axyro_portfolio_reporting_test",
    reason="Requires the dedicated, seeded portfolio fixture database",
)


@pytest.fixture
def public_client(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_public_access_enabled", True)
    monkeypatch.setattr(settings, "app_public_base_url", "https://axyro.tech/portfolio")
    monkeypatch.setattr(auth, "reserve_guest_entry", lambda: None)
    with TestClient(app, headers={"Origin": "https://axyro.tech"}) as client:
        yield client


def test_guest_receives_operator_session_with_real_api_and_csrf(public_client):
    response = public_client.post("/api/auth/portfolio-guest", json={})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "OPERATOR"
    assert response.json()["user"]["username"] == "portfolio"
    assert response.headers["Cache-Control"] == "no-store"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert public_client.get("/api/auth/me").status_code == 200
    account = public_client.get("/api/control-center/accounts", params={"quick_filter": "all"}).json()["items"][0]
    assert public_client.patch(f"/api/control-center/accounts/{account['id']}", json={
        "current_note": "must not be saved without CSRF",
    }).status_code == 403


def test_guest_reuses_its_valid_session(public_client, monkeypatch):
    first = public_client.post("/api/auth/portfolio-guest", json={})
    assert first.status_code == 200
    cookie = public_client.cookies.get(settings.session_cookie_name)
    monkeypatch.setattr(auth, "reserve_guest_entry", lambda: pytest.fail("Existing session must not use a new slot"))
    second = public_client.post("/api/auth/portfolio-guest", json={})
    assert second.status_code == 200
    assert second.json()["csrf_token"] == first.json()["csrf_token"]
    assert public_client.cookies.get(settings.session_cookie_name) == cookie
    assert "set-cookie" not in second.headers


def test_expired_guest_gets_a_new_session(public_client):
    assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 200
    cookie = public_client.cookies.get(settings.session_cookie_name)
    with SessionLocal.begin() as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(cookie)))
        session.expires_at = utcnow() - timedelta(seconds=1)
    assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 200
    assert public_client.cookies.get(settings.session_cookie_name) != cookie


@pytest.mark.parametrize("origin", ["https://unrelated.example", "null", ""])
def test_guest_rejects_other_origins_without_creating_sessions(public_client, origin):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(UserSession))
    response = public_client.post("/api/auth/portfolio-guest", json={}, headers={"Origin": origin})
    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(UserSession)) == before


@pytest.mark.parametrize("environment,enabled", [("production", True), ("portfolio", False)])
def test_guest_is_closed_outside_explicit_public_portfolio(public_client, monkeypatch, environment, enabled):
    monkeypatch.setattr(settings, "app_env", environment)
    monkeypatch.setattr(settings, "portfolio_public_access_enabled", enabled)
    assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 404


def test_guest_rejects_a_database_with_operational_connections(public_client):
    assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 200
    with SessionLocal.begin() as db:
        connection = db.scalar(select(GoogleConnection))
        connection_id, original = connection.id, connection.connection_mode
        connection.connection_mode = "PRODUCTION"
    try:
        assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 503
        assert public_client.get("/api/control-center/accounts").status_code == 503
    finally:
        with SessionLocal.begin() as db:
            db.get(GoogleConnection, connection_id).connection_mode = original


def test_guest_rejects_a_database_with_external_credentials(public_client):
    with SessionLocal.begin() as db:
        credential = GoogleCredential(kind="UNIT_TEST", encrypted_payload=b"not-a-real-credential")
        db.add(credential)
        db.flush()
        credential_id = credential.id
    try:
        assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 503
    finally:
        with SessionLocal.begin() as db:
            db.delete(db.get(GoogleCredential, credential_id))


def test_guest_rejects_unprepared_data(public_client):
    with SessionLocal.begin() as db:
        prepared = db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == "portfolio.related_dataset.v1"))
        setting_id = prepared.id
        prepared.key = "portfolio.test.unprepared"
    try:
        assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 503
    finally:
        with SessionLocal.begin() as db:
            db.get(ApplicationSetting, setting_id).key = "portfolio.related_dataset.v1"


@pytest.mark.parametrize("limit_error", [False, True])
def test_guest_fails_closed_when_limited_or_limiter_is_unavailable(public_client, monkeypatch, limit_error):
    class FakeRedis:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def eval(self, *args):
            if limit_error:
                raise RedisError("unavailable")
            return settings.portfolio_guest_rate_limit_per_minute + 1

    monkeypatch.setattr(portfolio_access.Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    monkeypatch.setattr(auth, "reserve_guest_entry", portfolio_access.reserve_guest_entry)
    response = public_client.post("/api/auth/portfolio-guest", json={})
    assert response.status_code == (503 if limit_error else 429)
    if not limit_error:
        assert response.headers["Retry-After"] == "60"


def test_public_status_follows_runtime_flag(public_client, monkeypatch):
    assert public_client.post("/api/auth/portfolio-guest", json={}).status_code == 200
    assert public_client.get("/api/setup/status").json()["portfolio_public_access_enabled"] is True
    monkeypatch.setattr(settings, "portfolio_public_access_enabled", False)
    assert public_client.get("/api/setup/status").json()["portfolio_public_access_enabled"] is False
    assert public_client.get("/api/auth/me").status_code == 401


def test_public_cookie_is_confined_to_portfolio(public_client, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    monkeypatch.setattr(settings, "session_cookie_path", "/portfolio/")
    response = public_client.post("/api/auth/portfolio-guest", json={})
    assert response.status_code == 200
    header = response.headers["set-cookie"]
    assert "Path=/portfolio/" in header and "Secure" in header and "HttpOnly" in header
