from pydantic import BaseModel

from app.modules.auth.schemas import UserPublic


class UserResponse(BaseModel):
    success: bool = True
    message: str
    data: UserPublic
