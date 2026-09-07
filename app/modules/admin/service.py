import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ACCOUNT_DISABLED_MESSAGE, AppError
from app.core.pagination import Page, offset_for, paginate
from app.modules.admin import repository
from app.modules.auth import service as auth_service
from app.modules.auth.models import Role
from app.modules.auth.repository import get_by_id
from app.modules.auth.schemas import AuthResult, UserPublic

STAFF_ROLES = {Role.ADMIN, Role.SUPER_ADMIN}
NOT_AUTHORIZED_MESSAGE = "Not authorized"


async def login(db: AsyncSession, *, email: str, password: str) -> AuthResult:
    return await auth_service.admin_login(db, email=email, password=password)


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> UserPublic:
    user = await get_by_id(db, user_id)
    if user is None or user.role not in STAFF_ROLES:
        raise AppError("Not authenticated", 401)
    if not user.is_active:
        raise AppError(ACCOUNT_DISABLED_MESSAGE, 403)
    return UserPublic.model_validate(user)


async def logout(
    db: AsyncSession,
    session_token: str | None,
    renewal_token: str | None,
) -> None:
    user = await auth_service.resolve_session_user(db, session_token, renewal_token)
    if user is None:
        return
    if user.role not in STAFF_ROLES:
        raise AppError(NOT_AUTHORIZED_MESSAGE, 403)
    await auth_service.logout(db, session_token, renewal_token)


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    search: str | None = None,
) -> Page[UserPublic]:
    query = search.strip() if search else None
    users, total_count = await repository.list_users(
        db,
        limit=limit,
        offset=offset_for(page, limit),
        search=query or None,
    )
    return paginate(
        [UserPublic.model_validate(user) for user in users],
        page=page,
        limit=limit,
        total_count=total_count,
    )
