from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import ACCESS_COOKIE_NAME
from app.core.exceptions import ACCOUNT_DISABLED_MESSAGE, error_response
from app.core.security import TokenType, decode_token
from app.db.session import SessionLocal
from app.modules.auth.repository import get_by_id
from app.modules.auth.schemas import CurrentUser

PUBLIC_EXACT_PATHS = {
    "/",
    "/auth/signup",
    "/auth/login",
    "/auth/resend-otp",
    "/auth/verify-otp",
    "/auth/social-login",
    "/auth/refresh",
    "/auth/logout",
    "/admin/login",
    "/admin/logout",
}

PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def _is_public(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    path = request.url.path.rstrip("/") or "/"
    if path in PUBLIC_EXACT_PATHS:
        return True
    return any(request.url.path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if _is_public(request):
            await self.app(scope, receive, send)
            return

        token = request.cookies.get(ACCESS_COOKIE_NAME)
        payload = decode_token(token, TokenType.SESSION) if token else None
        if payload is None:
            await error_response(401, "Not authenticated")(scope, receive, send)
            return

        async with SessionLocal() as db:
            user = await get_by_id(db, payload.user_id)
            if user is None or not user.email_verified or user.session_version != payload.session_version:
                await error_response(401, "Not authenticated")(scope, receive, send)
                return
            if not user.is_active:
                await error_response(403, ACCOUNT_DISABLED_MESSAGE)(scope, receive, send)
                return
            request.state.user = CurrentUser.model_validate(user)

        await self.app(scope, receive, send)
