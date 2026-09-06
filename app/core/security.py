from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import secrets
from urllib.parse import urlparse
import uuid

from fastapi import Request, Response
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_DAYS,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SAMESITE_VALUES = {"lax", "strict", "none"}


class TokenType(str, Enum):
    SESSION = "session"
    RENEWAL = "renewal"


@dataclass(frozen=True)
class TokenPayload:
    user_id: uuid.UUID
    session_version: int


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _cookie_samesite() -> str:
    if COOKIE_SAMESITE in SAMESITE_VALUES:
        return COOKIE_SAMESITE
    return "lax"


def _is_cross_site_request(request: Request | None) -> bool:
    if request is None:
        return False
    origin = request.headers.get("origin")
    origin_host = urlparse(origin).hostname if origin else None
    api_host = request.url.hostname
    return bool(origin_host and api_host and origin_host.lower() != api_host.lower())


def _cookie_kwargs(request: Request | None = None) -> dict[str, str | bool]:
    samesite = _cookie_samesite()
    secure = COOKIE_SECURE
    partitioned = False
    if _is_cross_site_request(request):
        samesite = "none"
        secure = True
        partitioned = True
    if samesite == "none":
        secure = True
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": "/",
        "partitioned": partitioned,
    }


def _create_token(
    user_id: uuid.UUID,
    token_type: TokenType,
    days: int,
    session_version: int,
) -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "typ": token_type.value,
        "sv": session_version,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=days)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_session_token(user_id: uuid.UUID, session_version: int) -> str:
    return _create_token(user_id, TokenType.SESSION, ACCESS_TOKEN_EXPIRE_DAYS, session_version)


def create_renewal_token(user_id: uuid.UUID, session_version: int) -> str:
    return _create_token(user_id, TokenType.RENEWAL, REFRESH_TOKEN_EXPIRE_DAYS, session_version)


def decode_token(token: str, expected_type: TokenType) -> TokenPayload | None:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("typ") != expected_type.value or not payload.get("sub"):
            return None
        return TokenPayload(
            user_id=uuid.UUID(str(payload["sub"])),
            session_version=int(payload.get("sv") or 0),
        )
    except (InvalidTokenError, ValueError, TypeError):
        return None


def set_auth_cookies(
    response: Response,
    session_token: str,
    renewal_token: str,
    request: Request | None = None,
) -> None:
    cookie_kwargs = _cookie_kwargs(request)
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        session_token,
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 86400,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        renewal_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **cookie_kwargs,
    )


def clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    cookie_kwargs = _cookie_kwargs(request)
    response.set_cookie(ACCESS_COOKIE_NAME, "", max_age=0, **cookie_kwargs)
    response.set_cookie(REFRESH_COOKIE_NAME, "", max_age=0, **cookie_kwargs)
