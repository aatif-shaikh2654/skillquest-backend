from pydantic import BaseModel, Field

from app.core.pagination import Page
from app.modules.auth.schemas import LowerEmail, UserPublic


class AdminLoginRequest(BaseModel):
    email: LowerEmail
    password: str = Field(min_length=8, max_length=72)


class UserListResponse(BaseModel):
    success: bool = True
    message: str
    data: Page[UserPublic]
