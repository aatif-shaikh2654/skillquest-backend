from datetime import datetime, timedelta, timezone
import asyncio
import uuid

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    FRONTEND_ORIGINS,
    GOOGLE_CLIENT_ID,
    OTP_EXPIRE_MINUTES,
    OTP_RATE_LIMIT_MAX,
    OTP_RATE_LIMIT_WINDOW_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.email import send_email
from app.emails.render import render_email
from app.core.exceptions import AppError
from app.core.security import (
    TokenType,
    create_renewal_token,
    create_session_token,
    decode_token,
    generate_otp,
    hash_token,
    verify_password,
)
from app.modules.auth import repository
from app.modules.auth.models import Role, User
from app.modules.auth.schemas import AuthResult, UserPublic, normalize_email

PUBLIC_LOGIN_ROLES = {Role.USER}
ADMIN_LOGIN_ROLES = {Role.ADMIN, Role.SUPER_ADMIN}
GENERIC_ADMIN_AUTH_FAILURE = "Invalid email or password"
ACCOUNT_EXISTS_MESSAGE = "An account with this email already exists"
UNIQUE_CONFLICT_MESSAGE = "An account with this email already exists"
ACCOUNT_NOT_FOUND_MESSAGE = "No account found for that email."
OTP_SENT_MESSAGE = "A verification code has been sent."
SIGNUP_OTP_MESSAGE = "Signed up successfully. Check your email for a verification code."
INVALID_OTP_MESSAGE = "Invalid or expired verification code"
OTP_COOLDOWN_MESSAGE = "Please wait before requesting another code."
OTP_RATE_LIMIT_MESSAGE = "Too many verification codes requested. Try again later."
ALREADY_INSTRUCTOR_MESSAGE = "Already an instructor"
STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE = "Staff accounts cannot become instructors"


def _to_public_user(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


async def _issue_auth_result(db: AsyncSession, user: User) -> AuthResult:
    session_token = create_session_token(user.id, user.session_version)
    renewal_token = create_renewal_token(user.id, user.session_version)
    await repository.create_refresh_token(
        db,
        user_id=user.id,
        token_hash=hash_token(renewal_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return AuthResult(
        session_token=session_token,
        renewal_token=renewal_token,
        user=_to_public_user(user),
    )


async def _invalidate_sessions(db: AsyncSession, user: User) -> None:
    await repository.revoke_all_refresh_tokens(db, user.id)
    await repository.increment_session_version(db, user)


async def _issue_otp(db: AsyncSession, user: User) -> None:
    now = datetime.now(timezone.utc)
    latest = await repository.get_latest_email_otp(db, user.id)
    if latest is not None and latest.created_at > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        raise AppError(OTP_COOLDOWN_MESSAGE, 429)

    sent_in_window = await repository.count_email_otps_since(
        db,
        user.id,
        now - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES),
    )
    if sent_in_window >= OTP_RATE_LIMIT_MAX:
        raise AppError(OTP_RATE_LIMIT_MESSAGE, 429)

    await repository.invalidate_unused_email_otps(db, user.id)
    code = generate_otp()
    await repository.create_email_otp(
        db,
        user_id=user.id,
        code_hash=hash_token(code),
        expires_at=now + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    first_name = user.full_name.strip().split()[0] if user.full_name.strip() else "there"
    text, html = render_email(
        "otp",
        first_name=first_name,
        code=code,
        expire_minutes=OTP_EXPIRE_MINUTES,
        contact_url=FRONTEND_ORIGINS[0],
    )
    await send_email(user.email, "Your SkillQuest verification code", text, html)


def _verify_google_token(token: str) -> dict[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise AppError("Google login is not configured", 400)
    try:
        info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError as exc:
        raise AppError("Invalid Google token", 400) from exc

    email = info.get("email")
    google_id = info.get("sub")
    if not email or not google_id:
        raise AppError("Invalid Google token", 400)
    if info.get("email_verified") is False:
        raise AppError("Google email is not verified", 400)

    return {
        "google_id": str(google_id),
        "email": normalize_email(str(email)),
        "full_name": str(info.get("name") or str(email).split("@")[0]),
    }


async def signup(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
) -> UserPublic:
    normalized_email = normalize_email(email)
    if await repository.get_by_email(db, normalized_email) is not None:
        raise AppError(ACCOUNT_EXISTS_MESSAGE, 409)

    try:
        user = await repository.create_user(
            db,
            email=normalized_email,
            full_name=full_name.strip(),
            role=Role.USER,
            email_verified=False,
        )
    except IntegrityError as exc:
        raise AppError(UNIQUE_CONFLICT_MESSAGE, 409) from exc

    await _issue_otp(db, user)
    return _to_public_user(user)


async def request_login_otp(db: AsyncSession, *, email: str) -> None:
    user = await repository.get_by_email(db, normalize_email(email))
    if user is None or not user.is_active or user.role not in PUBLIC_LOGIN_ROLES:
        raise AppError(ACCOUNT_NOT_FOUND_MESSAGE, 404)
    await _issue_otp(db, user)


async def verify_otp(db: AsyncSession, *, email: str, code: str) -> AuthResult:
    user = await repository.get_by_email(db, normalize_email(email))
    stored = (
        await repository.get_valid_email_otp(db, user.id, hash_token(code))
        if user is not None
        else None
    )
    if user is None or not user.is_active or stored is None or user.role not in PUBLIC_LOGIN_ROLES:
        raise AppError(INVALID_OTP_MESSAGE, 400)

    await repository.mark_email_verified(db, user)
    await repository.mark_email_otp_used(db, stored)
    await repository.invalidate_unused_email_otps(db, user.id)
    return await _issue_auth_result(db, user)


async def admin_login(db: AsyncSession, *, email: str, password: str) -> AuthResult:
    user = await repository.get_by_email(db, normalize_email(email))
    if (
        user is None
        or not user.is_active
        or user.password_hash is None
        or user.role not in ADMIN_LOGIN_ROLES
        or not verify_password(password, user.password_hash)
    ):
        raise AppError(GENERIC_ADMIN_AUTH_FAILURE, 401)
    return await _issue_auth_result(db, user)


async def social_login(db: AsyncSession, *, raw_id_token: str) -> AuthResult:
    google_user = await asyncio.to_thread(_verify_google_token, raw_id_token)
    existing = await repository.get_by_google_id(db, google_user["google_id"])
    if existing is not None:
        if not existing.is_active:
            raise AppError("Account is inactive", 401)
        return await _issue_auth_result(db, existing)

    existing_email = await repository.get_by_email(db, google_user["email"])
    if existing_email is not None:
        if not existing_email.is_active:
            raise AppError("Account is inactive", 401)
        if existing_email.google_id and existing_email.google_id != google_user["google_id"]:
            raise AppError("This email is already linked to another account", 409)
        if existing_email.email_verified:
            raise AppError(
                "An account with this email already exists. Sign in with the email code, then link Google.",
                409,
            )
        await repository.set_google_id(db, existing_email, google_user["google_id"])
        await repository.mark_email_verified(db, existing_email)
        await repository.clear_password_hash(db, existing_email)
        await _invalidate_sessions(db, existing_email)
        return await _issue_auth_result(db, existing_email)

    try:
        user = await repository.create_user(
            db,
            email=google_user["email"],
            full_name=google_user["full_name"],
            role=Role.USER,
            google_id=google_user["google_id"],
            email_verified=True,
        )
    except IntegrityError as exc:
        raise AppError(UNIQUE_CONFLICT_MESSAGE, 409) from exc
    return await _issue_auth_result(db, user)


async def link_google(db: AsyncSession, *, user_id: uuid.UUID, raw_id_token: str) -> UserPublic:
    user = await repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AppError("Not authenticated", 401)
    if not user.email_verified:
        raise AppError("Please verify your email before logging in", 401)

    google_user = await asyncio.to_thread(_verify_google_token, raw_id_token)
    if google_user["email"] != normalize_email(user.email):
        raise AppError("Google account email does not match this user", 400)
    existing_google = await repository.get_by_google_id(db, google_user["google_id"])
    if existing_google is not None and existing_google.id != user.id:
        raise AppError("This Google account is already linked to another user", 409)
    if user.google_id and user.google_id != google_user["google_id"]:
        raise AppError("This email is already linked to another account", 409)

    await repository.set_google_id(db, user, google_user["google_id"])
    return _to_public_user(user)


async def become_instructor(db: AsyncSession, *, user_id: uuid.UUID) -> UserPublic:
    user = await repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AppError("Not authenticated", 401)
    if user.role != Role.USER:
        raise AppError(STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE, 403)
    if user.is_instructor:
        raise AppError(ALREADY_INSTRUCTOR_MESSAGE, 409)
    await repository.set_is_instructor(db, user)
    return _to_public_user(user)


async def refresh_session(db: AsyncSession, renewal_token: str | None) -> AuthResult:
    payload = decode_token(renewal_token, TokenType.RENEWAL) if renewal_token else None
    stored = (
        await repository.get_refresh_token_for_update(db, hash_token(renewal_token))
        if renewal_token
        else None
    )
    now = datetime.now(timezone.utc)
    user = await repository.get_by_id(db, payload.user_id) if payload is not None else None
    if (
        payload is None
        or stored is None
        or stored.user_id != payload.user_id
        or stored.revoked_at is not None
        or stored.expires_at <= now
        or user is None
        or not user.is_active
        or payload.session_version != user.session_version
    ):
        raise AppError("Invalid or expired token", 401)

    await repository.revoke_refresh_token_row(db, stored)
    return await _issue_auth_result(db, user)


async def resolve_session_user(
    db: AsyncSession,
    session_token: str | None,
    renewal_token: str | None,
) -> User | None:
    if session_token:
        payload = decode_token(session_token, TokenType.SESSION)
        if payload is not None:
            user = await repository.get_by_id(db, payload.user_id)
            if user is not None:
                return user

    if renewal_token:
        stored = await repository.get_refresh_token_for_update(db, hash_token(renewal_token))
        if stored is not None:
            return await repository.get_by_id(db, stored.user_id)

    return None


async def logout(
    db: AsyncSession,
    session_token: str | None,
    renewal_token: str | None,
) -> None:
    user = await resolve_session_user(db, session_token, renewal_token)
    if user is not None:
        await _invalidate_sessions(db, user)
