"""add music recognition attempts

Revision ID: 0003_music_recognition_attempts
Revises: 0002_music_searches
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_music_recognition_attempts"
down_revision: str | None = "0002_music_searches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "music_recognition_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("music_search_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["music_search_id"], ["music_searches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_music_recognition_attempts_music_search_id"),
        "music_recognition_attempts",
        ["music_search_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_music_recognition_attempts_provider"),
        "music_recognition_attempts",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_music_recognition_attempts_status"),
        "music_recognition_attempts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_music_recognition_attempts_status"),
        table_name="music_recognition_attempts",
    )
    op.drop_index(
        op.f("ix_music_recognition_attempts_provider"),
        table_name="music_recognition_attempts",
    )
    op.drop_index(
        op.f("ix_music_recognition_attempts_music_search_id"),
        table_name="music_recognition_attempts",
    )
    op.drop_table("music_recognition_attempts")
