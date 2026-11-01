"""Kimlik ve rol bağımlılıkları: tek giriş kapısının bekçileri."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth.roles import Role
from ..auth.tokens import TokenError, verify_token
from ..config import get_settings

_auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_auth_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer [REDACTED]ç yok"
        )
    try:
        user = verify_token(get_settings().secret_key, credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    revoked = getattr(request.app.state, "revoked_tokens", None)
    if revoked is not None and revoked.is_revoked(user.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="iptal edilmiş belirteç"
        )
    return user


def require_roles(*roles: Role):
    wanted = {role.value for role in roles}

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if wanted.isdisjoint(user.get("roles", [])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="rol yetkisi yetersiz"
            )
        return user

    return checker
