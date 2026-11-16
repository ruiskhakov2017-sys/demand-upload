from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.schemas import LoginIn, PortfolioLinkIn, SessionOut, UserOut
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    expires_in,
    generate_token,
    hash_token,
    utcnow,
    verify_password,
)
from app.db.models import ApplicationSetting, AuditLog, User, UserRole, UserSession
from app.domain.portfolio_access import (
    PORTFOLIO_USERNAME,
    PUBLIC_SESSION_PREFIX,
    invitation_key,
    require_prepared_public_workspace,
    reserve_guest_entry,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, raw_session_token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        raw_session_token,
        max_age=settings.session_ttl_minutes * 60,
        path=settings.session_cookie_path,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.post("/login", response_model=SessionOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    return create_session(db, request, response, user, "auth.login")


@router.post("/portfolio-link", response_model=SessionOut)
def portfolio_link(
    payload: PortfolioLinkIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionOut:
    if settings.app_env != "portfolio":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user = db.scalar(select(User).where(
        User.username == PORTFOLIO_USERNAME, User.role == UserRole.OPERATOR.value, User.is_active.is_(True)
    ))
    invitation = db.scalar(select(ApplicationSetting).where(
        ApplicationSetting.key == invitation_key(payload.token)
    ).with_for_update())
    if not user or not invitation or invitation.value.get("expires_at", 0) <= utcnow().timestamp():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ссылка уже использована или истекла")

    db.delete(invitation)
    response.headers["Cache-Control"] = "no-store"
    return create_session(db, request, response, user, "auth.portfolio_link")


@router.post("/portfolio-guest", response_model=SessionOut)
def portfolio_guest(request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    if settings.app_env != "portfolio" or not settings.portfolio_public_access_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    public_url = urlsplit(settings.app_public_base_url)
    if request.headers.get("origin") != f"{public_url.scheme}://{public_url.netloc}":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимый источник входа")
    # Fail closed if a deployment points the public entry at operational data.
    require_prepared_public_workspace(db)
    user = db.scalar(select(User).where(
        User.username == PORTFOLIO_USERNAME, User.role == UserRole.OPERATOR.value,
        User.is_active.is_(True), User.is_setup_admin.is_(False),
    ))
    if not user:
        raise HTTPException(status_code=503, detail="Публичный кабинет ещё не подготовлен")
    response.headers["Cache-Control"] = "no-store"
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(select(UserSession).where(
            UserSession.user_id == user.id, UserSession.token_hash == hash_token(token),
            UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow(),
        ))
        if session:
            return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)
    reserve_guest_entry()
    return create_session(db, request, response, user, "auth.portfolio_guest", token_prefix=PUBLIC_SESSION_PREFIX)


def create_session(
    db: Session, request: Request, response: Response, user: User, audit_action: str,
    *, token_prefix: str = "dgu_session",
) -> SessionOut:
    raw_session_token = generate_token(token_prefix)
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
            action=audit_action,
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
    response.delete_cookie(settings.session_cookie_name, path=settings.session_cookie_path)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=SessionOut)
def me(request: Request, user: User = Depends(get_current_user)) -> SessionOut:
    session: UserSession = request.state.user_session
    return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)
