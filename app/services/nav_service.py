from datetime import date
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.portfolio import MutualFundNAV
from app.models.user import User, UserRole
from app.repositories.portfolio_repository import MutualFundNAVRepository, MutualFundSchemeRepository
from app.schemas.nav import NAVCreate, NAVUpdate


class MutualFundNAVService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.navs = MutualFundNAVRepository(db)
        self.schemes = MutualFundSchemeRepository(db)

    async def create_nav(self, current_user: User, payload: NAVCreate) -> MutualFundNAV:
        self._assert_can_mutate(current_user)
        await self._validate_scheme(payload.scheme_id)
        if await self.navs.get_by_scheme_and_date(scheme_id=payload.scheme_id, nav_date=payload.nav_date):
            raise BadRequestException("NAV already exists for this scheme and date")
        try:
            nav = await self.navs.create(payload.model_dump())
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("NAV already exists for this scheme and date") from exc
        await self.db.refresh(nav)
        return nav

    async def get_nav(self, current_user: User, nav_id: UUID) -> MutualFundNAV:
        self._assert_can_read(current_user)
        nav = await self.navs.get_by_id(nav_id)
        if nav is None:
            raise NotFoundException("NAV not found")
        return nav

    async def list_navs(
        self,
        current_user: User,
        *,
        scheme_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MutualFundNAV]:
        self._assert_can_read(current_user)
        return await self.navs.list_by_scheme(
            scheme_id=scheme_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    async def update_nav(self, current_user: User, nav_id: UUID, payload: NAVUpdate) -> MutualFundNAV:
        self._assert_can_mutate(current_user)
        nav = await self.get_nav(current_user, nav_id)
        update_data = payload.model_dump(exclude_unset=True)
        scheme_id = nav.scheme_id
        nav_date = update_data.get("nav_date", nav.nav_date)
        if (
            ("nav_date" in update_data)
            and await self.navs.get_by_scheme_and_date(scheme_id=scheme_id, nav_date=nav_date)
            and nav_date != nav.nav_date
        ):
            raise BadRequestException("NAV already exists for this scheme and date")
        try:
            updated = await self.navs.update(nav, update_data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("NAV already exists for this scheme and date") from exc
        await self.db.refresh(updated)
        return updated

    async def delete_nav(self, current_user: User, nav_id: UUID) -> None:
        self._assert_can_mutate(current_user)
        nav = await self.get_nav(current_user, nav_id)
        await self.navs.soft_delete(nav)
        await self.db.commit()

    async def _validate_scheme(self, scheme_id: UUID) -> None:
        if await self.schemes.get_by_id(scheme_id) is None:
            raise NotFoundException("Scheme not found")

    def _assert_can_read(self, current_user: User) -> None:
        if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.ADVISOR, UserRole.COMPLIANCE}:
            raise ForbiddenException("Insufficient permissions")

    def _assert_can_mutate(self, current_user: User) -> None:
        if current_user.role != UserRole.SUPER_ADMIN:
            raise ForbiddenException("Insufficient permissions")
