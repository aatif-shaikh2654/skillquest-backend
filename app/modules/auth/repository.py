from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import EmailOtp, RefreshToken, Role, User
from app.modules.auth.schemas import normalize_email


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_by_google_id(db: AsyncSession, google_id: str) -> User | None:
    result = await db.execute(select(User).where(User.google_id == google_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    role: Role,
    password_hash: str | None = None,
    google_id: str | None = None,
    phone_number: str | None = None,
    email_verified: bool = False,
) -> User:
    user = User(
        email=normalize_email(email),
        full_name=full_name,
        role=role,
        password_hash=password_hash,
        google_id=google_id,
        phone_number=phone_number,
        email_verified=email_verified,
        is_instructor=False,
        session_version=0,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def set_password_hash(db: AsyncSession, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    await db.flush()


async def clear_password_hash(db: AsyncSession, user: User) -> None:
    user.password_hash = None
    await db.flush()


async def set_google_id(db: AsyncSession, user: User, google_id: str) -> None:
    user.google_id = google_id
    await db.flush()


async def mark_email_verified(db: AsyncSession, user: User) -> None:
    user.email_verified = True
    await db.flush()


async def set_is_instructor(db: AsyncSession, user: User) -> None:
    user.is_instructor = True
    await db.flush()


async def increment_session_version(db: AsyncSession, user: User) -> int:
    user.session_version += 1
    await db.flush()
    return user.session_version


async def create_refresh_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(refresh_token)
    await db.flush()
    return refresh_token


async def get_refresh_token_for_update(
    db: AsyncSession, token_hash: str
) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token_row(db: AsyncSession, refresh_token: RefreshToken) -> None:
    if refresh_token.revoked_at is None:
        refresh_token.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def create_email_otp(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    code_hash: str,
    expires_at: datetime,
) -> EmailOtp:
    otp = EmailOtp(
        user_id=user_id,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    db.add(otp)
    await db.flush()
    return otp


async def invalidate_unused_email_otps(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(EmailOtp)
        .where(EmailOtp.user_id == user_id, EmailOtp.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )


async def get_valid_email_otp(
    db: AsyncSession, user_id: uuid.UUID, code_hash: str
) -> EmailOtp | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EmailOtp).where(
            EmailOtp.user_id == user_id,
            EmailOtp.code_hash == code_hash,
            EmailOtp.used_at.is_(None),
            EmailOtp.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def mark_email_otp_used(db: AsyncSession, otp: EmailOtp) -> None:
    otp.used_at = datetime.now(timezone.utc)
    await db.flush()


async def get_latest_email_otp(db: AsyncSession, user_id: uuid.UUID) -> EmailOtp | None:
    result = await db.execute(
        select(EmailOtp)
        .where(EmailOtp.user_id == user_id)
        .order_by(EmailOtp.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_email_otps_since(
    db: AsyncSession, user_id: uuid.UUID, since: datetime
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(EmailOtp)
        .where(EmailOtp.user_id == user_id, EmailOtp.created_at >= since)
    )
    return int(result.scalar_one())
