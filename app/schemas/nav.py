from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NAVCreate(BaseModel):
    scheme_id: UUID
    nav_date: date
    nav_value: Decimal = Field(gt=0)
    source: str | None = Field(default=None, max_length=255)


class NAVUpdate(BaseModel):
    nav_date: date | None = None
    nav_value: Decimal | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class NAVRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scheme_id: UUID
    nav_date: date
    nav_value: Decimal
    source: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NAVListItem(NAVRead):
    pass
