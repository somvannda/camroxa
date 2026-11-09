"""Register SLAI's ``cx/gpt-6-sol-image`` for pricing and routing.

The model is added to the registry in the same release, which makes it
selectable in AI Routing and in the Credits form. Live installations also need
the database rows, so this migration:

  - clones the SLAI ``cx/gpt-image-2.5`` ``credit_pricing`` rows onto the new
    model (same operation, same sell/cost units), keeping whichever Global
    Credit Value the install has configured;
  - clones the matching ``ai_model_costs`` rows, and falls back to the registry
    cost tier (~$0.0067/img) when no sibling row exists;
  - inserts the model into the stored image fallback chain right after the
    existing SLAI image entry, so it can take over when that model fails.

It is idempotent: re-running inserts nothing that already exists.

Revision ID: 184
Revises: 183
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "184"
down_revision = "183"
branch_labels = None
depends_on = None

_NEW_MODEL = "cx/gpt-6-sol-image"
_SIBLING_MODEL = "cx/gpt-image-2.5"
_IMAGE_CHAIN_KEY = "ai_routing_image_fallback_chain"
_IMAGE_OPERATIONS = (
    "channel_logo",
    "channel_cover",
    "background_image",
    "thumbnail_image",
)
_DEFAULT_COST_USD = 0.0067


def _clone_pricing() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO credit_pricing (
                ai_service,
                operation_type,
                sub_model,
                credits_per_operation,
                external_cost_cents,
                needs_review
            )
            SELECT
                sibling.ai_service,
                sibling.operation_type,
                :new_model,
                sibling.credits_per_operation,
                sibling.external_cost_cents,
                sibling.needs_review
            FROM credit_pricing AS sibling
            WHERE sibling.ai_service = 'slai'
              AND sibling.sub_model = :sibling_model
              AND NOT EXISTS (
                  SELECT 1
                  FROM credit_pricing AS existing
                  WHERE existing.ai_service = 'slai'
                    AND existing.operation_type = sibling.operation_type
                    AND existing.sub_model = :new_model
              )
            """
        ).bindparams(new_model=_NEW_MODEL, sibling_model=_SIBLING_MODEL)
    )


def _clone_model_costs() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO ai_model_costs (
                ai_service,
                sub_model,
                operation_type,
                cost_usd,
                notes,
                source
            )
            SELECT
                'slai',
                :new_model,
                sibling.operation_type,
                sibling.cost_usd,
                COALESCE(sibling.notes, 'Cloned from cx/gpt-image-2.5'),
                'registry'
            FROM ai_model_costs AS sibling
            WHERE sibling.ai_service = 'slai'
              AND sibling.sub_model = :sibling_model
              AND NOT EXISTS (
                  SELECT 1
                  FROM ai_model_costs AS existing
                  WHERE existing.ai_service = 'slai'
                    AND existing.sub_model = :new_model
                    AND existing.operation_type = sibling.operation_type
              )
            """
        ).bindparams(new_model=_NEW_MODEL, sibling_model=_SIBLING_MODEL)
    )

    # Fresh install with no sibling rows: seed the registry estimate so the
    # Credits page can still generate a price.
    for operation in _IMAGE_OPERATIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO ai_model_costs (
                    ai_service,
                    sub_model,
                    operation_type,
                    cost_usd,
                    notes,
                    source
                )
                SELECT
                    'slai',
                    :new_model,
                    :operation,
                    :cost_usd,
                    'Auto-estimated from registry cost tier',
                    'registry'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM ai_model_costs AS existing
                    WHERE existing.ai_service = 'slai'
                      AND existing.sub_model = :new_model
                      AND existing.operation_type = :operation
                )
                """
            ).bindparams(
                new_model=_NEW_MODEL,
                operation=operation,
                cost_usd=_DEFAULT_COST_USD,
            )
        )


def _insert_into_image_chain() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT value FROM system_settings WHERE key = :key"),
        {"key": _IMAGE_CHAIN_KEY},
    ).fetchone()
    if row is None or row[0] is None:
        return

    raw = row[0]
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    if not isinstance(data, list):
        return

    if any(
        isinstance(entry, dict)
        and str(entry.get("sub_model") or "").strip() == _NEW_MODEL
        for entry in data
    ):
        return

    insert_at = len(data)
    for index, entry in enumerate(data):
        if (
            isinstance(entry, dict)
            and str(entry.get("provider") or "").strip() == "slai"
        ):
            insert_at = index + 1
            break

    data.insert(
        insert_at,
        {"provider": "slai", "sub_model": _NEW_MODEL, "is_active": True},
    )
    bind.execute(
        sa.text(
            "UPDATE system_settings SET value = :value, updated_at = NOW() "
            "WHERE key = :key"
        ),
        {"key": _IMAGE_CHAIN_KEY, "value": json.dumps(data)},
    )


def upgrade() -> None:
    _clone_pricing()
    _clone_model_costs()
    _insert_into_image_chain()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM credit_pricing "
            "WHERE ai_service = 'slai' AND sub_model = :new_model"
        ).bindparams(new_model=_NEW_MODEL)
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_model_costs "
            "WHERE ai_service = 'slai' AND sub_model = :new_model"
        ).bindparams(new_model=_NEW_MODEL)
    )

    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT value FROM system_settings WHERE key = :key"),
        {"key": _IMAGE_CHAIN_KEY},
    ).fetchone()
    if row is None or row[0] is None:
        return
    raw = row[0]
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    if not isinstance(data, list):
        return
    pruned = [
        entry
        for entry in data
        if not (
            isinstance(entry, dict)
            and str(entry.get("sub_model") or "").strip() == _NEW_MODEL
        )
    ]
    if pruned != data:
        bind.execute(
            sa.text(
                "UPDATE system_settings SET value = :value, updated_at = NOW() "
                "WHERE key = :key"
            ),
            {"key": _IMAGE_CHAIN_KEY, "value": json.dumps(pruned)},
        )
