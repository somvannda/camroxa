"""Add sub_model to credit_pricing for per-model billing."""

from alembic import op

revision = "025_credit_pricing_sub_model"
down_revision = "024_credit_pricing_needs_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE credit_pricing
        ADD COLUMN IF NOT EXISTS sub_model VARCHAR(120) NOT NULL DEFAULT ''
    """)
    op.execute("""
        ALTER TABLE credit_pricing
        DROP CONSTRAINT IF EXISTS credit_pricing_model_identifier_operation_type_key
    """)
    op.execute("""
        ALTER TABLE credit_pricing
        DROP CONSTRAINT IF EXISTS credit_pricing_ai_service_operation_type_key
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_pricing_service_op_model
        ON credit_pricing (ai_service, operation_type, sub_model)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_pricing_service_op_model")
    op.execute("""
        ALTER TABLE credit_pricing
        DROP COLUMN IF EXISTS sub_model
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_pricing_ai_service_operation_type
        ON credit_pricing (ai_service, operation_type)
    """)
