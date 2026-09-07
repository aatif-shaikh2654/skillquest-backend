import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.instructor.models import (
    AudienceSize,
    Instructor,
    TeachingExperience,
    TeachingTopic,
    VideoExperience,
)


async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Instructor | None:
    result = await db.execute(select(Instructor).where(Instructor.user_id == user_id))
    return result.scalar_one_or_none()


async def create_for_user(
    db: AsyncSession,
    user: User,
    *,
    teaching_experience: TeachingExperience,
    video_experience: VideoExperience,
    audience_size: AudienceSize,
    teaching_topic: TeachingTopic,
) -> Instructor:
    instructor = Instructor(
        user_id=user.id,
        teaching_experience=teaching_experience,
        video_experience=video_experience,
        audience_size=audience_size,
        teaching_topic=teaching_topic,
    )
    user.is_instructor = True
    db.add(instructor)
    await db.flush()
    return instructor
