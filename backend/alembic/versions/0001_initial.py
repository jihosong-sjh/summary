"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "recordings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(op.f("ix_recordings_status"), "recordings", ["status"], unique=False)
    op.create_index(op.f("ix_recordings_user_id"), "recordings", ["user_id"], unique=False)

    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recording_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transcripts_recording_id"), "transcripts", ["recording_id"], unique=True)

    op.create_table(
        "summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recording_id", sa.String(length=36), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("edited_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_summaries_recording_id"), "summaries", ["recording_id"], unique=True)

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recording_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_processing_jobs_recording_id"), "processing_jobs", ["recording_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_processing_jobs_recording_id"), table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index(op.f("ix_summaries_recording_id"), table_name="summaries")
    op.drop_table("summaries")
    op.drop_index(op.f("ix_transcripts_recording_id"), table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index(op.f("ix_recordings_user_id"), table_name="recordings")
    op.drop_index(op.f("ix_recordings_status"), table_name="recordings")
    op.drop_table("recordings")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

