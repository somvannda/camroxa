"""Point SLAI image routing/pricing at the provider's renamed model.

SLAI (``api.slai.shop``) retired the image model id ``slai/gpt-image-2`` in
favor of ``cx/gpt-image-2.5``. The registry/client defaults ship in the same
release; this migration moves the live database rows so existing installs keep
generating images and charging credits after the code swap:

  - ``system_settings.ai_routing_assignments`` image ops (background/thumbnail,
    channel_logo/cover if pointed at SLAI)
  - ``system_settings.ai_routing_image_fallback_chain``
  - ``credit_pricing`` rows for ``ai_service='slai'``
  - ``ai_model_costs`` rows for ``ai_service='slai'``

Revision ID: 125_slai_image_model_cx_gpt_image_2_5
Revises: 124_free_local_video_merge
Create Date: 2026-10-02
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "125_slai_image_model_cx_gpt_image_2_5"
down_revision = "124_free_local_video_merge"
branch_labels = None
depends_on = None

_OLD_MODEL = "slai/gpt-image-2"
_NEW_MODEL = "cx/gpt-image-2.5"

_ASSIGNMENTS_KEY = "ai_routing_assignments"
_IMAGE_CHAIN_KEY = "ai_routing_image_fallback_chain"
_SETTINGS_KEYS = (_ASSIGNMENTS_KEY, _IMAGE_CHAIN_KEY)


def _migrate_settings(*, old_model: str, new_model: str) -> None:
    bind = op.get_bind()
    for key in _SETTINGS_KEYS:
        row = bind.execute(
            sa.text("SELECT value FROM system_settings WHERE key = :key"),
            {"key": key},
        ).fetchone()
        if row is None or row[0] is None:
            continue
        raw = row[0]
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, (dict, list)):
            continue
        changed = False
        if key == _ASSIGNMENTS_KEY:
            if not isinstance(data, dict):
                continue
            for entry in data.values():
                if (
                    isinstance(entry, dict)
                    and str(entry.get("sub_model") or "").strip() == old_model
                ):
                    entry["sub_model"] = new_model
                    changed = True
        else:
            if not isinstance(data, list):
                continue
            for entry in data:
                if (
                    isinstance(entry, dict)
                    and str(entry.get("sub_model") or "").strip() == old_model
                ):
                    entry["sub_model"] = new_model
                    changed = True
        if changed:
            bind.execute(
                sa.text(
                    "UPDATE system_settings SET value = :value, updated_at = NOW() "
                    "WHERE key = :key"
                ),
                {"key": key, "value": json.dumps(data)},
            )


def _migrate_pricing_and_costs(*, old_model: str, new_model: str) -> None:
    for table in ("credit_pricing", "ai_model_costs"):
        # Drop a stale old row when the target row already exists for the same
        # operation, so the unique (service, operation, model) index holds.
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table} AS stale
                WHERE stale.ai_service = 'slai'
                  AND stale.sub_model = :old_model
                  AND EXISTS (
                      SELECT 1 FROM {table} AS fresh
                      WHERE fresh.ai_service = 'slai'
                        AND fresh.sub_model = :new_model
                        AND fresh.operation_type = stale.operation_type
                  )
                """
            ).bindparams(old_model=old_model, new_model=new_model)
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET sub_model = :new_model, updated_at = NOW()
                WHERE ai_service = 'slai' AND sub_model = :old_model
                """
            ).bindparams(old_model=old_model, new_model=new_model)
        )


def upgrade() -> None:
    _migrate_settings(old_model=_OLD_MODEL, new_model=_NEW_MODEL)
    _migrate_pricing_and_costs(old_model=_OLD_MODEL, new_model=_NEW_MODEL)


def downgrade() -> None:
    _migrate_settings(old_model=_NEW_MODEL, new_model=_OLD_MODEL)
    _migrate_pricing_and_costs(old_model=_NEW_MODEL, new_model=_OLD_MODEL)
