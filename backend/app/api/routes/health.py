from fastapi import APIRouter
from redis import Redis

from app.core.config import settings
from app.core.database import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | None]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version_sha": settings.app_version_sha,
        "release_tag": settings.app_release_tag,
        "deployed_at": settings.app_deployed_at,
    }


@router.get("/version")
def version() -> dict[str, str | None]:
    return {
        "version_sha": settings.app_version_sha,
        "release_tag": settings.app_release_tag,
        "deployed_at": settings.app_deployed_at,
        "environment": settings.app_env,
    }


@router.get("/ready")
def ready() -> dict[str, str]:
    check_database()
    redis = Redis.from_url(settings.redis_url)
    redis.ping()
    return {"status": "ready"}
