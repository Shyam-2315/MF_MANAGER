import logging

from app.config import Settings
from app.database import AsyncSessionLocal
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.security import get_password_hash

logger = logging.getLogger("app.bootstrap")


async def bootstrap_first_admin(settings: Settings) -> None:
    if not settings.first_admin_email or not settings.first_admin_password:
        return

    async with AsyncSessionLocal() as db:
        users = UserRepository(db)
        email = str(settings.first_admin_email)
        existing_user = await users.get_by_email(email)

        if existing_user is not None:
            changed = False
            if existing_user.role != UserRole.SUPER_ADMIN:
                existing_user.role = UserRole.SUPER_ADMIN
                changed = True
            if not existing_user.is_active:
                existing_user.is_active = True
                changed = True
            if changed:
                await db.commit()
                logger.info("first_admin_updated", extra={"email": email})
            return

        await users.create(
            email=email,
            password_hash=get_password_hash(settings.first_admin_password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        await db.commit()
        logger.info("first_admin_created", extra={"email": email})
