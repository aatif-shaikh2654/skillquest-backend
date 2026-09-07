"""add instructors table for become-instructor wizard

Revision ID: 006_instructors
Revises: 005_user_instructor
Create Date: 2026-09-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_instructors"
down_revision: Union[str, None] = "005_user_instructor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

teaching_experience = postgresql.ENUM(
    "IN_PERSON_INFORMAL",
    "IN_PERSON_PROFESSIONAL",
    "ONLINE",
    "OTHER",
    name="teaching_experience",
)
video_experience = postgresql.ENUM(
    "BEGINNER",
    "SOME_KNOWLEDGE",
    "EXPERIENCED",
    "VIDEOS_READY",
    name="video_experience",
)
audience_size = postgresql.ENUM(
    "NONE",
    "SMALL",
    "SUFFICIENT",
    "LARGE",
    name="audience_size",
)
teaching_topic = postgresql.ENUM(
    "TECHNOLOGY",
    "DESIGN",
    "BUSINESS",
    "MARKETING",
    "PERSONAL_DEVELOPMENT",
    "MUSIC",
    "HEALTH_FITNESS",
    "LIFESTYLE",
    "EDUCATION",
    "OTHER",
    name="teaching_topic",
)


def upgrade() -> None:
    teaching_experience.create(op.get_bind(), checkfirst=True)
    video_experience.create(op.get_bind(), checkfirst=True)
    audience_size.create(op.get_bind(), checkfirst=True)
    teaching_topic.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "instructors",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "teaching_experience",
            postgresql.ENUM(name="teaching_experience", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "video_experience",
            postgresql.ENUM(name="video_experience", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "audience_size",
            postgresql.ENUM(name="audience_size", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "teaching_topic",
            postgresql.ENUM(name="teaching_topic", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("instructors")
    teaching_topic.drop(op.get_bind(), checkfirst=True)
    audience_size.drop(op.get_bind(), checkfirst=True)
    video_experience.drop(op.get_bind(), checkfirst=True)
    teaching_experience.drop(op.get_bind(), checkfirst=True)
