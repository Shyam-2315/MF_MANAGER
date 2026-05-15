"""update user auth fields

Revision ID: 0002_update_user_auth_fields
Revises: 0001_create_users
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_update_user_auth_fields"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.alter_column(
        "users",
        "hashed_password",
        new_column_name="password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.execute(
        """
        UPDATE users
        SET role = CASE
            WHEN role = 'admin' THEN 'SUPER_ADMIN'
            WHEN role = 'user' THEN 'CUSTOMER'
            ELSE role
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role = CASE
            WHEN role = 'SUPER_ADMIN' THEN 'admin'
            ELSE 'user'
        END
        """
    )
    op.alter_column(
        "users",
        "password_hash",
        new_column_name="hashed_password",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.drop_column("users", "phone")
