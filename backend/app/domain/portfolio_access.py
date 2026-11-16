from fastapi import HTTPException
from redis import Redis, RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token
from app.db.models import ApplicationSetting, GoogleConnection, GoogleCredential

PORTFOLIO_USERNAME = "portfolio"
PUBLIC_SESSION_PREFIX = "portfolio_guest"


def invitation_key(token: str) -> str:
    return f"portfolio_invitation:{hash_token(token)}"


def require_prepared_public_workspace(db: Session) -> None:
    prepared = db.scalar(select(ApplicationSetting.id).where(
        ApplicationSetting.key == "portfolio.related_dataset.v1"
    ))
    external_connection = db.scalar(select(GoogleConnection.id).where(
        GoogleConnection.connection_mode != "SIMULATION"
    ).limit(1))
    credential = db.scalar(select(GoogleCredential.id).limit(1))
    if not prepared or external_connection or credential:
        raise HTTPException(status_code=503, detail="Публичный кабинет ещё не подготовлен")


def reserve_guest_entry() -> None:
    """Bound public session creation without relying on visitor-supplied IPs."""
    try:
        with Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2) as redis:
            count = redis.eval(
                "local n = redis.call('INCR', KEYS[1]); "
                "if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end; return n",
                1, "axyro:portfolio:guest-entries",
            )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Кабинет временно недоступен. Попробуйте позже.") from exc
    if int(count) > settings.portfolio_guest_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Слишком много входов. Попробуйте через минуту.",
                            headers={"Retry-After": "60"})
