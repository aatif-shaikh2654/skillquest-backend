from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, EmailStr, Field

from app.modules.auth.models import Role


def normalize_email(email: str) -> str:
    return email.strip().lower()


LowerEmail = Annotated[EmailStr, BeforeValidator(normalize_email)]


class SignupRequest(BaseModel):
    email: LowerEmail
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: LowerEmail


class ResendOtpRequest(BaseModel):
    email: LowerEmail


class VerifyOtpRequest(BaseModel):
    email: LowerEmail
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class SocialLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class LinkGoogleRequest(BaseModel):
    id_token: str = Field(min_length=1)


class UserPublic(BaseModel):
    id: UUID
    email: LowerEmail
    full_name: str
    phone_number: str | None
    role: Role
    is_instructor: bool
    is_active: bool
    email_verified: bool

    model_config = {"from_attributes": True}


CurrentUser = UserPublic


class AuthResult(BaseModel):
    session_token: str
    renewal_token: str
    user: UserPublic


class AuthResponse(BaseModel):
    success: bool = True
    message: str
    data: UserPublic


class MessageResponse(BaseModel):
    success: bool = True
    message: str
