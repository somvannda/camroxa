"""Store model costs as fractional USD (sub-cent precision)."""

from alembic import op

revision = "027_model_cost_usd_precision"
down_revision = "026_ai_model_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ai_model_costs
        ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(14, 8)
    """)
    op.execute("""
        UPDATE ai_model_costs
        SET cost_usd = COALESCE(cost_usd_cents, 0)::numeric / 100.0
        WHERE cost_usd IS NULL
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        ALTER COLUMN cost_usd SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        DROP COLUMN IF EXISTS cost_usd_cents
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        ADD CONSTRAINT chk_ai_model_costs_cost_usd_nonneg
        CHECK (cost_usd >= 0)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ai_model_costs
        DROP CONSTRAINT IF EXISTS chk_ai_model_costs_cost_usd_nonneg
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        ADD COLUMN IF NOT EXISTS cost_usd_cents INTEGER
    """)
    op.execute("""
        UPDATE ai_model_costs
        SET cost_usd_cents = GREATEST(0, CEIL(cost_usd * 100)::integer)
        WHERE cost_usd_cents IS NULL
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        ALTER COLUMN cost_usd_cents SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE ai_model_costs
        DROP COLUMN IF EXISTS cost_usd
    """)
