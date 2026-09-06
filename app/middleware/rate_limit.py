from urllib.parse import urlparse
import time

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import FRONTEND_ORIGINS
from app.core.exceptions import error_response

AUTH_PATHS = {
    "/auth/signup",
    "/auth/login",
    "/auth/resend-otp",
    "/auth/verify-otp",
    "/auth/social-login",
    "/admin/login",
}

SKIP_PATHS = {"/"}
SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
AUTH_MAX = 10
AUTH_WINDOW_SECONDS = 60
API_MAX = 60
API_WINDOW_SECONDS = 60
TOO_MANY_REQUESTS_MESSAGE = "Too many requests. Try again later."


def rate_limit_enabled_for_origin(origin: str) -> bool:
    parsed = urlparse(origin.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return False
    if host in LOCAL_HOSTS or host.endswith(".localhost"):
        return False
    return bool(host)


def allow_request(
    hits: list[float],
    now: float,
    window_seconds: int,
    max_hits: int,
) -> tuple[bool, list[float]]:
    remaining = [stamp for stamp in hits if stamp > now - window_seconds]
    if len(remaining) >= max_hits:
        return False, remaining
    remaining.append(now)
    return True, remaining


def decide_rate_limit(
    enabled: bool,
    hits: list[float],
    now: float,
    window_seconds: int,
    max_hits: int,
) -> tuple[bool, list[float]]:
    if not enabled:
        return True, hits
    return allow_request(hits, now, window_seconds, max_hits)


def _client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


def _normalized_path(request: Request) -> str:
    return request.url.path.rstrip("/") or "/"


def _is_skipped(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    path = _normalized_path(request)
    if path in SKIP_PATHS:
        return True
    return any(request.url.path.startswith(prefix) for prefix in SKIP_PREFIXES)


def _bucket_for(path: str) -> tuple[str, int, int]:
    if path in AUTH_PATHS:
        return "auth", AUTH_MAX, AUTH_WINDOW_SECONDS
    return "api", API_MAX, API_WINDOW_SECONDS


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._hits: dict[tuple[str, str], list[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        enabled = any(rate_limit_enabled_for_origin(origin) for origin in FRONTEND_ORIGINS)
        if scope["type"] != "http" or not enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if _is_skipped(request):
            await self.app(scope, receive, send)
            return

        bucket, max_hits, window_seconds = _bucket_for(_normalized_path(request))
        key = (bucket, _client_ip(request))
        allowed, self._hits[key] = decide_rate_limit(
            enabled,
            self._hits.get(key, []),
            time.monotonic(),
            window_seconds,
            max_hits,
        )
        if not allowed:
            await error_response(429, TOO_MANY_REQUESTS_MESSAGE)(scope, receive, send)
            return

        await self.app(scope, receive, send)
