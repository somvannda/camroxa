"""Add reservation metadata for shared content-pool rows."""

from alembic import op

revision = "010_content_pool_reservations"
down_revision = "009_content_pool_preset_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("title_pool", "album_pool", "opening_pairs"):
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS reservation_token TEXT
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS reserved_at TIMESTAMPTZ
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS reserved_by TEXT
            """
        )
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_reservation
                ON {table_name}(reservation_token, reserved_at)
            """
        )


def downgrade() -> None:
    for table_name in ("title_pool", "album_pool", "opening_pairs"):
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_reservation")
        op.execute(
            f"""
            ALTER TABLE {table_name}
            DROP COLUMN IF EXISTS reserved_by
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            DROP COLUMN IF EXISTS reserved_at
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            DROP COLUMN IF EXISTS reservation_token
            """
        )
