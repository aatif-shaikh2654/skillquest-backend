from urllib.parse import urlparse

from fastapi import Request

from app.core.config import FRONTEND_ORIGINS
from app.core.exceptions import AppError
from app.db.session import get_db
from app.modules.auth.models import Role
from app.modules.auth.schemas import CurrentUser

STAFF_ROLES = {Role.ADMIN, Role.SUPER_ADMIN}


def _origin_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value.rstrip("/")


def _request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return _origin_from_url(origin)
    referer = request.headers.get("referer")
    if referer:
        return _origin_from_url(referer)
    return None


async def require_same_origin(request: Request) -> None:
    incoming = _request_origin(request)
    allowed = {
        _origin_from_url(origin) for origin in FRONTEND_ORIGINS
    }
    allowed.add(f"{request.url.scheme}://{request.url.netloc}")
    if incoming is None or incoming not in allowed:
        raise AppError("Invalid request origin", 403)


async def get_current_user(request: Request) -> CurrentUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise AppError("Not authenticated", 401)
    return user


async def require_admin(request: Request) -> CurrentUser:
    user = await get_current_user(request)
    if user.role not in STAFF_ROLES:
        raise AppError("Not authorized", 403)
    return user


__all__ = ["get_db", "get_current_user", "require_admin", "require_same_origin"]
