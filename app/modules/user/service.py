import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.auth.schemas import UserPublic
from app.modules.user import repository


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> UserPublic:
    user = await repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AppError("Not authenticated", 401)
    return UserPublic.model_validate(user)
