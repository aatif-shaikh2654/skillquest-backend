from pydantic import BaseModel

from app.modules.auth.schemas import UserPublic
from app.modules.instructor.models import (
    AudienceSize,
    TeachingExperience,
    TeachingTopic,
    VideoExperience,
)


class BecomeInstructorRequest(BaseModel):
    teaching_experience: TeachingExperience
    video_experience: VideoExperience
    audience_size: AudienceSize
    teaching_topic: TeachingTopic


class InstructorPublic(UserPublic):
    teaching_experience: TeachingExperience
    video_experience: VideoExperience
    audience_size: AudienceSize
    teaching_topic: TeachingTopic


class InstructorResponse(BaseModel):
    success: bool = True
    message: str
    data: InstructorPublic
