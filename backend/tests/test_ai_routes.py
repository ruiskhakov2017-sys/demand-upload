from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy.sql.dml import Delete, Update

from app.api.deps import get_current_user, require_csrf
from app.api.routes.ai_analyst import _ordinary_editor_path, _validate_draft_targets, get_my_usage
from app.api.routes.ai_analyst import router as ai_router
from app.jobs import ai_tasks


class ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class UsageDb:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return ScalarRows(self.rows)


def _dependency_calls(dependant):
    calls = {dependant.call}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def test_every_ai_route_requires_a_server_session_and_mutations_require_csrf() -> None:
    routes = [
        route
        for route in ai_router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/ai")
    ]

    assert routes
    for route in routes:
        calls = _dependency_calls(route.dependant)
        assert get_current_user in calls, f"Missing server-side session guard: {route.path}"
        if route.methods.intersection({"POST", "PATCH", "PUT", "DELETE"}):
            assert require_csrf in calls, f"Missing CSRF guard: {route.path}"


def test_personal_usage_is_filtered_by_user_and_returns_only_that_users_totals() -> None:
    user_id = uuid4()
    row = SimpleNamespace(
        usage_date=date(2026, 8, 4),
        user_id=user_id,
        model_id="test-model",
        requests=2,
        input_tokens=100,
        output_tokens=25,
        estimated_cost_usd=Decimal("0.0125"),
        tool_calls=3,
        errors=1,
        latency_ms_total=240,
    )
    db = UsageDb([row])

    result = get_my_usage(days=30, db=db, user=SimpleNamespace(id=user_id))

    assert result["totals"] == {
        "requests": 2,
        "input_tokens": 100,
        "output_tokens": 25,
        "estimated_cost_usd": 0.0125,
        "tool_calls": 3,
        "errors": 1,
    }
    compiled = db.statement.compile()
    assert "ai_usage_daily.user_id" in str(compiled)
    assert user_id in compiled.params.values()


def test_retention_marks_open_drafts_expired_before_later_deletion(monkeypatch) -> None:
    class Result:
        rowcount = 1

    class EmptyScalars:
        @staticmethod
        def all():
            return []

    class RetentionDb:
        def __init__(self):
            self.statements = []
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            self.statements.append(statement)
            return Result()

        @staticmethod
        def scalars(_statement):
            return EmptyScalars()

        def commit(self):
            self.committed = True

    db = RetentionDb()
    monkeypatch.setattr(ai_tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(ai_tasks, "effective_ai_settings", lambda _db: {"retention_days": 30})

    result = ai_tasks.cleanup_ai_retention.run()

    assert isinstance(db.statements[0], Update)
    assert isinstance(db.statements[1], Delete)
    assert result["drafts_marked_expired"] == 1
    assert db.committed is True


def test_ai_migration_is_additive_and_seeds_json_with_typed_bulk_insert() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "202608030011_ai_analyst_full.py"
    ).read_text(encoding="utf-8")
    upgrade = migration.split("def downgrade", 1)[0]

    assert "op.bulk_insert" in upgrade
    assert "INSERT INTO ai_model_profiles" not in upgrade
    assert "op.drop_" not in upgrade
    assert "TRUNCATE" not in upgrade.upper()
    assert "DELETE FROM" not in upgrade.upper()


def test_preview_draft_target_set_cannot_be_expanded_or_escape_scope() -> None:
    allowed = uuid4()
    draft = SimpleNamespace(
        scope={"account_ids": [str(allowed)]},
        source_snapshot={"target_set_locked": True, "locked_account_ids": [str(allowed)]},
    )
    _validate_draft_targets(draft, {"account_ids": [str(allowed)]})
    escaped = uuid4()
    with pytest.raises(HTTPException, match="AI_SCOPE_ESCAPE"):
        _validate_draft_targets(draft, {"account_ids": [str(escaped)]})


def test_preview_draft_target_lock_applies_even_when_scope_means_all() -> None:
    locked = uuid4()
    draft = SimpleNamespace(
        scope={"account_ids": []},
        source_snapshot={"target_set_locked": True, "locked_account_ids": [str(locked)]},
    )
    with pytest.raises(HTTPException, match="AI_DRAFT_TARGET_EXPANSION"):
        _validate_draft_targets(draft, {"account_ids": [str(uuid4())]})


def test_ai_drafts_link_to_their_existing_ordinary_editors() -> None:
    draft_id = uuid4()
    upload_id = uuid4()
    plan_id = uuid4()

    class Db:
        @staticmethod
        def get(_model, requested_id):
            assert requested_id == plan_id
            return SimpleNamespace(upload_id=upload_id)

    demand_path = _ordinary_editor_path(
        Db(),
        SimpleNamespace(id=draft_id, draft_type="DEMAND_GEN_PLAN"),
        {"upload_id": str(upload_id)},
    )
    schedule_path = _ordinary_editor_path(
        Db(),
        SimpleNamespace(id=draft_id, draft_type="SCHEDULE"),
        {"deployment_plan_id": str(plan_id)},
    )

    assert demand_path == f"/uploads/{upload_id}?ai_draft={draft_id}"
    assert schedule_path == f"/uploads/{upload_id}?ai_draft={draft_id}&step=schedule"
