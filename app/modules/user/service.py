import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ACCOUNT_DISABLED_MESSAGE, AppError
from app.modules.auth.schemas import UserPublic
from app.modules.user import repository


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> UserPublic:
    user = await repository.get_by_id(db, user_id)
    if user is None:
        raise AppError("Not authenticated", 401)
    if not user.is_active:
        raise AppError(ACCOUNT_DISABLED_MESSAGE, 403)
    return UserPublic.model_validate(user)
