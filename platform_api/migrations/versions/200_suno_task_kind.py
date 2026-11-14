"""suno_tasks.kind: distinguish songs from sound effects

Revision ID: 200_suno_task_kind
Revises: 199_studio_upload_suno_clip
Create Date: 2026-11-14

The web Create page has a Sounds workspace. Both kinds share the queue, the
charge, the poll loop and the library row shape, so the only extra state is which
provider call to make on submit. Existing rows are songs by definition.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "200_suno_task_kind"
down_revision = "199_studio_upload_suno_clip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suno_tasks",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="music"),
    )
    op.create_check_constraint(
        "ck_suno_tasks_kind",
        "suno_tasks",
        "kind IN ('music', 'sounds')",
    )
    op.create_index("ix_suno_tasks_kind", "suno_tasks", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_suno_tasks_kind", table_name="suno_tasks")
    op.drop_constraint("ck_suno_tasks_kind", "suno_tasks", type_="check")
    op.drop_column("suno_tasks", "kind")
