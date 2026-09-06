from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.dependencies import require_admin, require_same_origin
from app.core.pagination import DEFAULT_LIMIT, DEFAULT_PAGE, Limit, PageNumber, SearchQuery
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.db.session import get_db
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import AdminLoginRequest, UserListResponse
from app.modules.auth.schemas import AuthResponse, AuthResult, CurrentUser, MessageResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


def _auth_response(
    message: str,
    result: AuthResult,
    response: Response,
    request: Request,
) -> AuthResponse:
    set_auth_cookies(response, result.session_token, result.renewal_token, request)
    return AuthResponse(message=message, data=result.user)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(require_same_origin)])
async def login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    result = await admin_service.login(db, email=payload.email, password=payload.password)
    return _auth_response("Logged in successfully", result, response, request)


@router.get("/me", response_model=AuthResponse)
async def get_me(
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    user = await admin_service.get_me(db, current_user.id)
    return AuthResponse(message="Admin fetched successfully", data=user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await admin_service.logout(
        db,
        request.cookies.get(ACCESS_COOKIE_NAME),
        request.cookies.get(REFRESH_COOKIE_NAME),
    )
    clear_auth_cookies(response, request)
    return MessageResponse(message="Logged out successfully")


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    page: PageNumber = DEFAULT_PAGE,
    limit: Limit = DEFAULT_LIMIT,
    search: SearchQuery = None,
) -> UserListResponse:
    data = await admin_service.list_users(db, page=page, limit=limit, search=search)
    return UserListResponse(message="Users fetched successfully", data=data)
