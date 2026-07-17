"""Scope user prompt name uniqueness to active rows only (soft-delete support)."""

from alembic import op

revision = "021_user_prompt_soft_delete"
down_revision = "020_add_music_prompt_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("music_descriptions", "music_structures"):
        op.execute(f"DROP INDEX IF EXISTS ux_{table}_user_name")
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_user_active_name
            ON {table} (user_id, name)
            WHERE user_id IS NOT NULL AND is_active = TRUE
            """
        )


def downgrade() -> None:
    for table in ("music_descriptions", "music_structures"):
        op.execute(f"DROP INDEX IF EXISTS ux_{table}_user_active_name")
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_user_name
            ON {table} (user_id, name)
            WHERE user_id IS NOT NULL
            """
        )
