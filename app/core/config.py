from dotenv import load_dotenv
import os

load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

def parse_origins(raw: str) -> list[str]:
    cleaned = raw.strip().strip('"').strip("'")
    origins: list[str] = []
    for part in cleaned.split(","):
        origin = part.strip().strip('"').strip("'").rstrip("/")
        if origin:
            origins.append(origin)
    return origins


FRONTEND_ORIGINS = parse_origins(os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")) or [
    "http://localhost:3000"
]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "Admin").strip() or "Admin"

ACCESS_TOKEN_EXPIRE_DAYS = max(1, _int("ACCESS_TOKEN_EXPIRE_DAYS", "1"))
REFRESH_TOKEN_EXPIRE_DAYS = max(1, _int("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
OTP_EXPIRE_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_RATE_LIMIT_WINDOW_MINUTES = 60
OTP_RATE_LIMIT_MAX = 5

ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "quest_session")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "quest_renewal")
COOKIE_SECURE = _bool("COOKIE_SECURE", "false")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_STARTTLS = _bool("SMTP_STARTTLS", "true")


def async_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    if DATABASE_URL.startswith("postgresql://"):
        return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    if DATABASE_URL.startswith("postgres://"):
        return DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    return DATABASE_URL
