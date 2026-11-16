from app.core.security import hash_token

PORTFOLIO_USERNAME = "portfolio"


def invitation_key(token: str) -> str:
    return f"portfolio_invitation:{hash_token(token)}"
