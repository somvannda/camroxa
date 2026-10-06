"""Dedup backstop: one pending capture per Suno task+variant.

Re-delivered Suno callbacks and desktop reconcile created duplicate
``stream_upload_jobs`` rows for the same track; the application guard added
alongside this migration prevents the common case, and this partial unique index
is the DB-level backstop against concurrent inserts. Existing duplicate pending
rows are marked failed first so the index can be created.

Revision ID: 134_streaming_upload_job_dedup
Revises: 133_credit_grant_claims
Create Date: 2026-10-06
"""

from __future__ import annotations

from alembic import op

revision = "134_streaming_upload_job_dedup"
down_revision = "133_credit_grant_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Collapse any duplicate pending captures (keep the newest per task+variant)
    # so the unique index below can be created. Older siblings are failed, not
    # deleted, so the audit trail survives.
    op.execute(
        """
        UPDATE stream_upload_jobs j
        SET status = 'failed',
            permanent_failed = true,
            error = COALESCE(NULLIF(j.error, ''), 'Superseded duplicate pending capture'),
            updated_at = NOW()
        WHERE j.status = 'pending'
          AND j.kind IN ('mp3_ok', 'mp3_alt')
          AND EXISTS (
            SELECT 1
            FROM stream_upload_jobs newer
            WHERE newer.suno_task_id = j.suno_task_id
              AND newer.kind = j.kind
              AND newer.status = 'pending'
              AND (newer.created_at, newer.id) > (j.created_at, j.id)
          )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_stream_upload_jobs_pending_task_kind
        ON stream_upload_jobs (suno_task_id, kind)
        WHERE status = 'pending' AND kind IN ('mp3_ok', 'mp3_alt')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_stream_upload_jobs_pending_task_kind")
