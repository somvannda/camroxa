"""Add API key pool tables.

Revision ID: 002_add_api_key_pool
Revises: 001_initial_schema
Create Date: 2024-01-15 00:00:00.000000+00:00

Creates tables for the API Key Pool feature:
- key_pool_configs: per-provider pool configuration (strategy, cooldown)
- api_key_entries: individual encrypted API key entries with usage counters
- key_status_events: immutable log of key status transitions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_api_key_pool"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Provider-level Pool Configuration ──────────────────────────────────
    op.execute("""
        CREATE TABLE key_pool_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider VARCHAR(50) NOT NULL UNIQUE,
            selection_strategy VARCHAR(20) NOT NULL DEFAULT 'priority',
            cooldown_seconds INTEGER NOT NULL DEFAULT 60
                CHECK (cooldown_seconds BETWEEN 10 AND 3600),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Individual API Key Entries ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE api_key_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider VARCHAR(50) NOT NULL,
            label VARCHAR(100) NOT NULL,
            encrypted_key_value BYTEA NOT NULL,
            priority INTEGER NOT NULL DEFAULT 50
                CHECK (priority BETWEEN 1 AND 100),
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            total_requests INTEGER NOT NULL DEFAULT 0,
            daily_requests INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            rate_limit_hits INTEGER NOT NULL DEFAULT 0,
            last_used_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            rate_limited_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(provider, label)
        )
    """)

    op.execute("""
        CREATE INDEX idx_key_entries_provider_status
            ON api_key_entries(provider, status)
    """)

    op.execute("""
        CREATE INDEX idx_key_entries_provider_priority
            ON api_key_entries(provider, priority)
    """)

    # ─── Status Transition Event Log ────────────────────────────────────────
    op.execute("""
        CREATE TABLE key_status_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_id UUID NOT NULL REFERENCES api_key_entries(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            key_label VARCHAR(100) NOT NULL,
            previous_status VARCHAR(20) NOT NULL,
            new_status VARCHAR(20) NOT NULL,
            trigger_reason VARCHAR(100) NOT NULL,
            http_status_code INTEGER,
            response_summary TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX idx_key_events_provider_created
            ON key_status_events(provider, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_key_events_key_id
            ON key_status_events(key_id, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS key_status_events CASCADE")
    op.execute("DROP TABLE IF EXISTS api_key_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS key_pool_configs CASCADE")
