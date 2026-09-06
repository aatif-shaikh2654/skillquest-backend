"""add email_otps for OTP auth

Revision ID: 004_email_otps
Revises: 003_auth_hardening
Create Date: 2026-09-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_email_otps"
down_revision: Union[str, None] = "003_auth_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_otps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_otps_user_id"), "email_otps", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_otps_code_hash"), "email_otps", ["code_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_otps_code_hash"), table_name="email_otps")
    op.drop_index(op.f("ix_email_otps_user_id"), table_name="email_otps")
    op.drop_table("email_otps")
