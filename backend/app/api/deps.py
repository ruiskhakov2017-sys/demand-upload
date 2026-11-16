from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_token
from app.db.models import User, UserRole, UserSession
from app.domain.portfolio_access import PORTFOLIO_USERNAME, PUBLIC_SESSION_PREFIX, require_prepared_public_workspace


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")

    session = db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == hash_token(token))
        .where(UserSession.revoked_at.is_(None))
        .where(UserSession.expires_at > datetime.now(UTC))
    )
    if not session or not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия недействительна")

    if token.startswith(f"{PUBLIC_SESSION_PREFIX}_"):
        if settings.app_env != "portfolio" or not settings.portfolio_public_access_enabled:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Публичный вход отключён")
        if session.user.username != PORTFOLIO_USERNAME or session.user.role != UserRole.OPERATOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимая роль посетителя")
        require_prepared_public_workspace(db)

    request.state.user_session = session
    return session.user


def require_csrf(request: Request, user: User = Depends(get_current_user)) -> User:
    session: UserSession | None = getattr(request.state, "user_session", None)
    header = request.headers.get("x-csrf-token")
    if not session or not header or header != session.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token не совпадает")
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    allowed = {role.value for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для этого действия",
            )
        return user

    return dependency
