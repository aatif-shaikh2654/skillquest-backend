from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeachingExperience(str, Enum):
    IN_PERSON_INFORMAL = "IN_PERSON_INFORMAL"
    IN_PERSON_PROFESSIONAL = "IN_PERSON_PROFESSIONAL"
    ONLINE = "ONLINE"
    OTHER = "OTHER"


class VideoExperience(str, Enum):
    BEGINNER = "BEGINNER"
    SOME_KNOWLEDGE = "SOME_KNOWLEDGE"
    EXPERIENCED = "EXPERIENCED"
    VIDEOS_READY = "VIDEOS_READY"


class AudienceSize(str, Enum):
    NONE = "NONE"
    SMALL = "SMALL"
    SUFFICIENT = "SUFFICIENT"
    LARGE = "LARGE"


class TeachingTopic(str, Enum):
    TECHNOLOGY = "TECHNOLOGY"
    DESIGN = "DESIGN"
    BUSINESS = "BUSINESS"
    MARKETING = "MARKETING"
    PERSONAL_DEVELOPMENT = "PERSONAL_DEVELOPMENT"
    MUSIC = "MUSIC"
    HEALTH_FITNESS = "HEALTH_FITNESS"
    LIFESTYLE = "LIFESTYLE"
    EDUCATION = "EDUCATION"
    OTHER = "OTHER"


def _pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda items: [item.value for item in items],
    )


TEACHING_EXPERIENCE_ENUM = _pg_enum(TeachingExperience, "teaching_experience")
VIDEO_EXPERIENCE_ENUM = _pg_enum(VideoExperience, "video_experience")
AUDIENCE_SIZE_ENUM = _pg_enum(AudienceSize, "audience_size")
TEACHING_TOPIC_ENUM = _pg_enum(TeachingTopic, "teaching_topic")


class Instructor(Base):
    __tablename__ = "instructors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    teaching_experience: Mapped[TeachingExperience] = mapped_column(TEACHING_EXPERIENCE_ENUM)
    video_experience: Mapped[VideoExperience] = mapped_column(VIDEO_EXPERIENCE_ENUM)
    audience_size: Mapped[AudienceSize] = mapped_column(AUDIENCE_SIZE_ENUM)
    teaching_topic: Mapped[TeachingTopic] = mapped_column(TEACHING_TOPIC_ENUM)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
