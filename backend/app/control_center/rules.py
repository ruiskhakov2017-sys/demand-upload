from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationSetting

RULE_KILL_SWITCH_KEY = "control_center.rule_kill_switch"


class RuleExecutionBlocked(RuntimeError):
    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f"Автоправила остановлены глобальным выключателем: {phase}")


def rule_kill_switch_active(db: Session) -> bool:
    setting = db.scalar(
        select(ApplicationSetting)
        .where(ApplicationSetting.key == RULE_KILL_SWITCH_KEY)
        .execution_options(populate_existing=True)
    )
    return True if setting is None else bool((setting.value or {}).get("active", True))


def require_rules_enabled(db: Session, phase: str) -> None:
    if rule_kill_switch_active(db):
        raise RuleExecutionBlocked(phase)
