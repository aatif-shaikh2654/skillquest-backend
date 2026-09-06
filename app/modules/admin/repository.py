from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.modules.auth.models import Role, User


def _ilike_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _user_filters(search: str | None) -> ColumnElement[bool]:
    filters = User.role == Role.USER
    if not search:
        return filters
    pattern = _ilike_pattern(search)
    return filters & or_(
        User.email.ilike(pattern, escape="\\"),
        User.full_name.ilike(pattern, escape="\\"),
        User.phone_number.ilike(pattern, escape="\\"),
    )


async def list_users(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: str | None = None,
) -> tuple[list[User], int]:
    filters = _user_filters(search)
    total_result = await db.execute(select(func.count()).select_from(User).where(filters))
    result = await db.execute(
        select(User)
        .where(filters)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total_result.scalar_one())
