import logging

from app.core.config import ADMIN_EMAIL, ADMIN_FULL_NAME, ADMIN_PASSWORD
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.auth import repository
from app.modules.auth.models import Role

logger = logging.getLogger(__name__)


async def seed_super_admin() -> None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return
    if len(ADMIN_PASSWORD) < 8:
        logger.warning("ADMIN_PASSWORD is shorter than 8 characters; skipped super-admin seed")
        return

    async with SessionLocal() as db:
        existing = await repository.get_by_email(db, ADMIN_EMAIL)
        if existing is not None:
            return
        await repository.create_user(
            db,
            email=ADMIN_EMAIL,
            full_name=ADMIN_FULL_NAME,
            role=Role.SUPER_ADMIN,
            password_hash=hash_password(ADMIN_PASSWORD),
            email_verified=True,
        )
        await db.commit()
        logger.info("Seeded SUPER_ADMIN %s", ADMIN_EMAIL)
