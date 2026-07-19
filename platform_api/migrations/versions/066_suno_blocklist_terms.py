"""Create suno_blocklist_terms table for admin-managed Suno lyrics blocklist."""

from __future__ import annotations

from alembic import op

revision = "066_suno_blocklist_terms"
down_revision = "065_suno_task_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS suno_blocklist_terms (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            term VARCHAR(120) NOT NULL,
            replacement VARCHAR(120),
            severity VARCHAR(16) NOT NULL DEFAULT 'block',
            source VARCHAR(16) NOT NULL DEFAULT 'manual',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_suno_blocklist_severity
                CHECK (severity IN ('block', 'warn')),
            CONSTRAINT chk_suno_blocklist_source
                CHECK (source IN ('manual', 'learned'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_suno_blocklist_terms_term_lower
        ON suno_blocklist_terms (LOWER(term))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_blocklist_terms_enabled
        ON suno_blocklist_terms (enabled, severity, LOWER(term))
        """
    )
    op.execute(
        """
        INSERT INTO suno_blocklist_terms (term, replacement, severity, source, enabled, notes)
        SELECT
            'lowlight',
            'afterglow',
            'block',
            'manual',
            TRUE,
            'Seeded from static Suno producer-tag fallback'
        WHERE NOT EXISTS (
            SELECT 1 FROM suno_blocklist_terms WHERE LOWER(term) = 'lowlight'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS suno_blocklist_terms")
