"""Add durable Backblaze storage key for image job outputs (background/thumbnail).

Revision ID: 079_image_job_storage_key
Revises: 078_merge_pipeline_complete_and_distrokid
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "079_image_job_storage_key"
down_revision = "078_merge_pipeline_complete_and_distrokid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_jobs",
        sa.Column("storage_key", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_jobs", "storage_key")
