import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.models import AuditLog, User, UserRole
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AI_DB_INTEGRATION") != "1",
    reason="AI PostgreSQL integration acceptance is opt-in",
)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_ai_routes_enforce_session_csrf_role_ownership_and_archive_lifecycle() -> None:
    suffix = uuid4().hex[:12]
    password = f"Ai-acceptance-{suffix}!"
    admin = User(
        username=f"ai_admin_{suffix}",
        password_hash=hash_password(password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    viewer = User(
        username=f"ai_viewer_{suffix}",
        password_hash=hash_password(password),
        role=UserRole.VIEWER.value,
        is_active=True,
    )
    with SessionLocal() as db:
        db.add_all([admin, viewer])
        db.commit()
        admin_id = admin.id
        viewer_id = viewer.id

    try:
        with TestClient(app, base_url="http://localhost") as anonymous:
            assert anonymous.get("/api/ai/capabilities").status_code == 401

        with TestClient(app, base_url="http://localhost") as admin_client:
            admin_csrf = _login(admin_client, admin.username, password)
            assert admin_client.get("/api/ai/capabilities").status_code == 200
            assert admin_client.post("/api/ai/conversations", json={"title": "No CSRF"}).status_code == 403

            created = admin_client.post(
                "/api/ai/conversations",
                headers={"X-CSRF-Token": admin_csrf},
                json={
                    "title": "Integration conversation",
                    "authority_mode": "READ_ONLY",
                    "google_environment": "SIMULATION",
                    "scope": {},
                    "locale": "en",
                    "time_zone": "UTC",
                },
            )
            assert created.status_code == 201, created.text
            conversation_id = created.json()["id"]

            exported = admin_client.get(f"/api/ai/conversations/{conversation_id}/export")
            assert exported.status_code == 200
            assert "attachment" in exported.headers["content-disposition"]

            archived = admin_client.patch(
                f"/api/ai/conversations/{conversation_id}",
                headers={"X-CSRF-Token": admin_csrf},
                json={"archived": True},
            )
            assert archived.status_code == 200
            assert archived.json()["archived_at"] is not None
            assert all(item["id"] != conversation_id for item in admin_client.get("/api/ai/conversations").json())
            assert any(
                item["id"] == conversation_id
                for item in admin_client.get("/api/ai/conversations?archived=true").json()
            )

            restored = admin_client.patch(
                f"/api/ai/conversations/{conversation_id}",
                headers={"X-CSRF-Token": admin_csrf},
                json={"archived": False},
            )
            assert restored.status_code == 200
            assert restored.json()["archived_at"] is None
            assert admin_client.get("/api/ai/usage?days=30").status_code == 200
            assert admin_client.get("/api/ai/admin/usage?days=30").status_code == 200

            with TestClient(app, base_url="http://localhost") as viewer_client:
                viewer_csrf = _login(viewer_client, viewer.username, password)
                assert viewer_client.get(f"/api/ai/conversations/{conversation_id}").status_code == 404
                assert viewer_client.get(f"/api/ai/conversations/{conversation_id}/export").status_code == 404
                forbidden_mode = viewer_client.post(
                    "/api/ai/conversations",
                    headers={"X-CSRF-Token": viewer_csrf},
                    json={"title": "Forbidden", "authority_mode": "DRAFT_ONLY"},
                )
                assert forbidden_mode.status_code == 403
                assert viewer_client.get("/api/ai/admin/usage").status_code == 403
                assert viewer_client.get("/api/ai/usage").status_code == 200

            removed = admin_client.delete(
                f"/api/ai/conversations/{conversation_id}",
                headers={"X-CSRF-Token": admin_csrf},
            )
            assert removed.status_code == 204
            assert admin_client.get(f"/api/ai/conversations/{conversation_id}").status_code == 404
    finally:
        with SessionLocal() as db:
            user_ids = [admin_id, viewer_id]
            db.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()
