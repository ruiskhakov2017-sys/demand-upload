from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.schemas import LoginIn, SessionOut, UserOut
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    expires_in,
    generate_token,
    hash_token,
    utcnow,
    verify_password,
)
from app.db.models import AuditLog, User, UserSession

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, raw_session_token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        raw_session_token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.post("/login", response_model=SessionOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    raw_session_token = generate_token("dgu_session")
    csrf_token = generate_token("dgu_csrf")
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_session_token),
        csrf_token=csrf_token,
        expires_at=expires_in(settings.session_ttl_minutes),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.add(
        AuditLog(
            created_at=utcnow(),
            actor_user_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=request.client.host if request.client else None,
            summary={"username": user.username},
        )
    )
    db.commit()
    set_session_cookie(response, raw_session_token)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> Response:
    session: UserSession | None = getattr(request.state, "user_session", None)
    if session:
        session.revoked_at = datetime.now(UTC)
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=user.id,
                action="auth.logout",
                entity_type="user",
                entity_id=str(user.id),
                ip_address=request.client.host if request.client else None,
                summary={},
            )
        )
        db.commit()
    response.delete_cookie(settings.session_cookie_name)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=SessionOut)
def me(request: Request, user: User = Depends(get_current_user)) -> SessionOut:
    session: UserSession = request.state.user_session
    return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)
