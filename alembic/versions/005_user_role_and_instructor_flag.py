"""collapse public roles to USER and add is_instructor

Revision ID: 005_user_instructor
Revises: 004_email_otps
Create Date: 2026-09-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_user_instructor"
down_revision: Union[str, None] = "004_email_otps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

new_user_role = postgresql.ENUM(
    "USER",
    "ADMIN",
    "SUPER_ADMIN",
    name="user_role_new",
)
old_user_role = postgresql.ENUM(
    "STUDENT",
    "INSTRUCTOR",
    "ADMIN",
    "SUPER_ADMIN",
    name="user_role_old",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_instructor", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE users SET is_instructor = true WHERE role = 'INSTRUCTOR'")
    op.alter_column("users", "is_instructor", server_default=None)

    new_user_role.create(op.get_bind(), checkfirst=True)
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role_new
        USING (
            CASE
                WHEN role::text IN ('STUDENT', 'INSTRUCTOR') THEN 'USER'
                ELSE role::text
            END
        )::user_role_new
        """
    )
    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_new RENAME TO user_role")


def downgrade() -> None:
    old_user_role.create(op.get_bind(), checkfirst=True)
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role_old
        USING (
            CASE
                WHEN role::text = 'USER' AND is_instructor THEN 'INSTRUCTOR'
                WHEN role::text = 'USER' THEN 'STUDENT'
                ELSE role::text
            END
        )::user_role_old
        """
    )
    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_old RENAME TO user_role")
    op.drop_column("users", "is_instructor")
