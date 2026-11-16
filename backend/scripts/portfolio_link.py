import argparse
from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import generate_token, utcnow
from app.db.models import ApplicationSetting, User, UserRole
from app.domain.portfolio_access import PORTFOLIO_USERNAME, invitation_key


def issue_link(hours: int) -> str:
    if settings.app_env != "portfolio":
        raise SystemExit("Portfolio links can only be issued from the portfolio environment")

    token = generate_token("portfolio")
    with SessionLocal.begin() as db:
        user = db.scalar(select(User.id).where(
            User.username == PORTFOLIO_USERNAME, User.role == UserRole.OPERATOR.value, User.is_active.is_(True)
        ))
        if not user:
            raise SystemExit("Initialize the portfolio workspace before issuing a link")
        db.add(ApplicationSetting(
            key=invitation_key(token),
            value={"expires_at": int((utcnow() + timedelta(hours=hours)).timestamp())},
        ))
    return f"{settings.app_public_base_url.rstrip('/')}/login#invite={token}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a one-use Axyro portfolio sign-in link")
    parser.add_argument("--hours", type=int, default=24, metavar="1-168")
    args = parser.parse_args()
    if not 1 <= args.hours <= 168:
        parser.error("--hours must be between 1 and 168")
    print(issue_link(args.hours))
