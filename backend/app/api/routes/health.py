from fastapi import APIRouter
from redis import Redis

from app.core.config import settings
from app.core.database import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
def ready() -> dict[str, str]:
    check_database()
    redis = Redis.from_url(settings.redis_url)
    redis.ping()
    return {"status": "ready"}
