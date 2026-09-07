import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ACCOUNT_DISABLED_MESSAGE, AppError
from app.modules.auth import repository as auth_repository
from app.modules.auth.models import Role, User
from app.modules.auth.schemas import UserPublic
from app.modules.instructor import repository
from app.modules.instructor.models import Instructor
from app.modules.instructor.schemas import BecomeInstructorRequest, InstructorPublic

ALREADY_INSTRUCTOR_MESSAGE = "Already an instructor"
STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE = "Staff accounts cannot become instructors"


def _to_public(user: User, instructor: Instructor) -> InstructorPublic:
    return InstructorPublic(
        **UserPublic.model_validate(user).model_dump(),
        teaching_experience=instructor.teaching_experience,
        video_experience=instructor.video_experience,
        audience_size=instructor.audience_size,
        teaching_topic=instructor.teaching_topic,
    )


async def become_instructor(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: BecomeInstructorRequest,
) -> InstructorPublic:
    user = await auth_repository.get_by_id(db, user_id)
    if user is None:
        raise AppError("Not authenticated", 401)
    if not user.is_active:
        raise AppError(ACCOUNT_DISABLED_MESSAGE, 403)
    if user.role != Role.USER:
        raise AppError(STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE, 403)
    if user.is_instructor:
        raise AppError(ALREADY_INSTRUCTOR_MESSAGE, 409)

    try:
        instructor = await repository.create_for_user(db, user, **payload.model_dump())
    except IntegrityError as exc:
        raise AppError(ALREADY_INSTRUCTOR_MESSAGE, 409) from exc

    return _to_public(user, instructor)
