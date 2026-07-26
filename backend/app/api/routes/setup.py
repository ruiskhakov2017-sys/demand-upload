from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import BootstrapAdminIn, SessionOut, SetupStatusOut, UserOut
from app.core.config import settings
from app.core.database import get_db
from app.core.security import expires_in, generate_token, hash_password, hash_token, utcnow
from app.db.models import AuditLog, User, UserRole, UserSession

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusOut)
def setup_status(db: Session = Depends(get_db)) -> SetupStatusOut:
    users_count = db.scalar(select(func.count()).select_from(User)) or 0
    return SetupStatusOut(setup_required=users_count == 0, users_count=users_count)


@router.post("/bootstrap", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(
    payload: BootstrapAdminIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    users_count = db.scalar(select(func.count()).select_from(User)) or 0
    if users_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Администратор уже создан")
    if settings.setup_token and payload.setup_token != settings.setup_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный setup token")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        is_active=True,
        is_setup_admin=True,
    )
    db.add(user)
    db.flush()

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
            action="setup.bootstrap_admin",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=request.client.host if request.client else None,
            summary={"username": user.username},
        )
    )
    db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        raw_session_token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_token)
