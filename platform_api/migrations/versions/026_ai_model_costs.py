"""Add ai_model_costs for admin-managed per-model USD costs."""

from alembic import op

revision = "026_ai_model_costs"
down_revision = "025_credit_pricing_sub_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_model_costs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ai_service VARCHAR(100) NOT NULL,
            sub_model VARCHAR(120) NOT NULL DEFAULT '',
            operation_type VARCHAR(50) NOT NULL,
            cost_usd_cents INTEGER NOT NULL CHECK (cost_usd_cents >= 0),
            notes TEXT,
            source VARCHAR(30) NOT NULL DEFAULT 'manual',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_ai_model_costs_service_model_op
                UNIQUE (ai_service, sub_model, operation_type)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_model_costs_service
        ON ai_model_costs (ai_service, operation_type)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_model_costs")
