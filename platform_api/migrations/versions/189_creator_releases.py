"""Creator releases: draft -> review -> published catalog.

Revision ID: 189
Revises: 188
"""

from __future__ import annotations

from alembic import op

revision = "189"
down_revision = "188"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_releases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_type VARCHAR(30) NOT NULL DEFAULT 'web_music_generation'
                CHECK (source_type IN ('web_music_generation','upload','desktop_batch')),
            source_task_id UUID,
            source_variant VARCHAR(8) NOT NULL DEFAULT 'ok',
            album_id UUID REFERENCES stream_albums(id) ON DELETE SET NULL,
            track_id UUID REFERENCES stream_tracks(id) ON DELETE SET NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft','submitted','in_review','changes_requested','approved','scheduled','published','taken_down','rejected')),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            ai_disclosure VARCHAR(20) NOT NULL DEFAULT 'none'
                CHECK (ai_disclosure IN ('none','ai_assisted','ai_artist')),
            origin VARCHAR(20) NOT NULL DEFAULT 'ai_generated'
                CHECK (origin IN ('original','ai_assisted','ai_generated')),
            scheduled_for TIMESTAMPTZ,
            submitted_at TIMESTAMPTZ,
            sla_due_at TIMESTAMPTZ,
            reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            takedown_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_releases_creator "
        "ON creator_releases (creator_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_releases_status "
        "ON creator_releases (status, submitted_at DESC NULLS LAST)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_release_source "
        "ON creator_releases (creator_id, source_type, source_task_id, source_variant) "
        "WHERE source_task_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_releases_track "
        "ON creator_releases (track_id) WHERE track_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS creator_releases CASCADE")
