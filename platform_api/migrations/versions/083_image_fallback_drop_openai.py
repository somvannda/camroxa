"""Remove unused OpenAI hop from image fallback chain settings.

Revision ID: 083_image_fallback_drop_openai
Revises: 082_batch_song_count_allow_zero
Create Date: 2026-08-08
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "083_image_fallback_drop_openai"
down_revision = "082_batch_song_count_allow_zero"
branch_labels = None
depends_on = None

_KEY = "ai_routing_image_fallback_chain"


def upgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT value FROM system_settings WHERE key = :key"),
        {"key": _KEY},
    ).fetchone()
    if row is None or row[0] is None:
        return
    raw = row[0]
    try:
        chain = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    if not isinstance(chain, list):
        return
    filtered = [
        item
        for item in chain
        if not (
            isinstance(item, dict)
            and str(item.get("provider") or "").strip().lower() == "openai"
        )
    ]
    if filtered == chain:
        return
    if not filtered:
        filtered = [
            {"provider": "slai", "sub_model": "slai/gpt-image-2", "is_active": True},
            {"provider": "fal", "sub_model": "flux-pro", "is_active": True},
        ]
    bind.execute(
        sa.text(
            """
            UPDATE system_settings
            SET value = :value, updated_at = NOW()
            WHERE key = :key
            """
        ),
        {"key": _KEY, "value": json.dumps(filtered)},
    )


def downgrade() -> None:
    # Non-destructive: do not re-insert OpenAI into live routing.
    return
