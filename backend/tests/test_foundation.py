import pytest
from starlette.responses import Response

from app.api.routes.auth import logout
from app.api.schemas import normalize_customer_id
from app.core.security import decrypt_json, encrypt_json, redact
from app.google_ads.capability_registry import get_demand_gen_capabilities


def test_normalize_customer_id_strips_dashes_and_spaces() -> None:
    assert normalize_customer_id("123-456-7890") == "1234567890"
    assert normalize_customer_id(" 123 456 7890 ") == "1234567890"


def test_normalize_customer_id_rejects_short_values() -> None:
    with pytest.raises(ValueError):
        normalize_customer_id("123")


def test_encrypt_json_roundtrip() -> None:
    payload = {"developer_token": "secret", "nested": {"value": 42}}
    encrypted = encrypt_json(payload)
    assert encrypted != str(payload).encode()
    assert decrypt_json(encrypted) == payload


def test_redact_removes_sensitive_values() -> None:
    data = {
        "developer_token": "abc",
        "client_secret": "def",
        "safe": "visible",
        "nested": {"refresh_token": "ghi"},
    }
    assert redact(data) == {
        "developer_token": "***REDACTED***",
        "client_secret": "***REDACTED***",
        "safe": "visible",
        "nested": {"refresh_token": "***REDACTED***"},
    }


def test_demand_gen_capabilities_are_paused_only() -> None:
    capabilities = get_demand_gen_capabilities()
    assert capabilities.supports_image_multi_asset is True
    assert capabilities.supports_video_responsive is True
    assert capabilities.campaign_create_status == "PAUSED"
    assert capabilities.max_headlines == 5


def test_logout_response_has_explicit_no_content_status() -> None:
    class RequestState:
        user_session = None

    class RequestStub:
        state = RequestState()

    response = logout(RequestStub(), Response(), db=None, user=None)
    assert response.status_code == 204
    assert "session" in response.headers["set-cookie"]
