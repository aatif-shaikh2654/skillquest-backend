from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.dependencies import get_current_user, require_same_origin
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.db.session import get_db
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import (
    AuthResponse,
    CurrentUser,
    LinkGoogleRequest,
    LoginRequest,
    MessageResponse,
    ResendOtpRequest,
    SignupRequest,
    SocialLoginRequest,
    VerifyOtpRequest,
) 

router = APIRouter(prefix="/auth", tags=["Auth"])


def _auth_response(
    message: str,
    result: auth_service.AuthResult,
    response: Response,
    request: Request,
) -> AuthResponse:
    set_auth_cookies(response, result.session_token, result.renewal_token, request)
    return AuthResponse(message=message, data=result.user)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    user = await auth_service.signup(
        db,
        email=payload.email,
        full_name=payload.full_name,
    )
    return AuthResponse(message=auth_service.SIGNUP_OTP_MESSAGE, data=user)


@router.post("/login", response_model=MessageResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.request_login_otp(db, email=payload.email)
    return MessageResponse(message=auth_service.OTP_SENT_MESSAGE)


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(
    payload: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.request_login_otp(db, email=payload.email)
    return MessageResponse(message=auth_service.OTP_SENT_MESSAGE)


@router.post("/verify-otp", response_model=AuthResponse, dependencies=[Depends(require_same_origin)])
async def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    result = await auth_service.verify_otp(db, email=payload.email, code=payload.code)
    return _auth_response("Logged in successfully", result, response, request)


@router.post("/social-login", response_model=AuthResponse, dependencies=[Depends(require_same_origin)])
async def social_login(
    payload: SocialLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    result = await auth_service.social_login(db, raw_id_token=payload.id_token)
    return _auth_response("Logged in successfully", result, response, request)


@router.post("/link-google", response_model=AuthResponse)
async def link_google(
    payload: LinkGoogleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    user = await auth_service.link_google(
        db,
        user_id=current_user.id,
        raw_id_token=payload.id_token,
    )
    return AuthResponse(message="Google account linked successfully", data=user)


@router.post("/become-instructor", response_model=AuthResponse)
async def become_instructor(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    user = await auth_service.become_instructor(db, user_id=current_user.id)
    return AuthResponse(message="You are now an instructor", data=user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    renewal_token = request.cookies.get(REFRESH_COOKIE_NAME)
    result = await auth_service.refresh_session(db, renewal_token)
    return _auth_response("Session refreshed", result, response, request)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout(
        db,
        request.cookies.get(ACCESS_COOKIE_NAME),
        request.cookies.get(REFRESH_COOKIE_NAME),
    )
    clear_auth_cookies(response, request)
    return MessageResponse(message="Logged out successfully")
