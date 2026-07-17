"""Add user ownership to music descriptions and structures."""

from alembic import op

revision = "019_user_music_prompts"
down_revision = "018_client_log_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("music_descriptions", "music_structures"):
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table}
            DROP CONSTRAINT IF EXISTS {table}_name_key
            """
        )
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_global_name
            ON {table} (name)
            WHERE user_id IS NULL
            """
        )
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_user_name
            ON {table} (user_id, name)
            WHERE user_id IS NOT NULL
            """
        )
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_user_id
            ON {table} (user_id)
            """
        )


def downgrade() -> None:
    for table in ("music_descriptions", "music_structures"):
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_user_id")
        op.execute(f"DROP INDEX IF EXISTS ux_{table}_user_name")
        op.execute(f"DROP INDEX IF EXISTS ux_{table}_global_name")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS user_id")
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {table}_name_key UNIQUE (name)
            """
        )
