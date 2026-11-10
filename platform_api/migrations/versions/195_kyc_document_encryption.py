"""Record how each KYC document is stored.

Revision ID: 195
Revises: 194
"""

from __future__ import annotations

from alembic import op

revision = "195"
down_revision = "194"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Media type of each stored document, so the review console can serve the
    # bytes with the right Content-Type after decryption.
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS id_document_type VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS selfie_type VARCHAR(100)"
    )
    # False on legacy rows whose object is still plaintext in the bucket.
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS documents_encrypted BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE creator_kyc DROP COLUMN IF EXISTS documents_encrypted"
    )
    op.execute("ALTER TABLE creator_kyc DROP COLUMN IF EXISTS selfie_type")
    op.execute("ALTER TABLE creator_kyc DROP COLUMN IF EXISTS id_document_type")
