from __future__ import annotations

from typing import Any

from ..utils.music_common import connect_db
from .persistence import DbCfg


# Column names for the text_style_presets table (excluding id, created_at, updated_at)
_PRESET_COLUMNS = [
    "name",
    "font_path",
    "font_size",
    "primary_color",
    "position",
    "glow_color",
    "glow_radius",
    "shadow_offset_x",
    "shadow_offset_y",
    "shadow_color",
    "stroke_width",
    "stroke_color",
    "gradient_enabled",
    "gradient_start_color",
    "gradient_end_color",
    "line_spacing",
    "alignment",
    "max_text_width_pct",
    "vertical_padding_pct",
]

_ALL_COLUMNS = [
    "id",
    *_PRESET_COLUMNS,
    "used_count",
    "used_at",
    "created_at",
    "updated_at",
]


def _row_to_dict(row: tuple) -> dict[str, Any]:
    """Convert a full row tuple to a dict using _ALL_COLUMNS."""
    return {col: row[i] for i, col in enumerate(_ALL_COLUMNS)}


def _normalize_key(key: str) -> str:
    """Convert camelCase key to snake_case."""
    import re
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", key).lower()


def create_text_style_presets_table(cfg: DbCfg) -> None:
    """Create text_style_presets table if not exists. Called during app migration."""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists text_style_presets (
                    id              serial primary key,
                    name            text not null unique,
                    font_path       text not null default '',
                    font_size       integer not null default 72,
                    primary_color   text not null default '#FFFFFFFF',
                    position        text not null default 'center',

                    glow_color      text not null default '#00000000',
                    glow_radius     integer not null default 0,
                    shadow_offset_x integer not null default 0,
                    shadow_offset_y integer not null default 0,
                    shadow_color    text not null default '#00000080',
                    stroke_width    integer not null default 0,
                    stroke_color    text not null default '#000000FF',

                    gradient_enabled boolean not null default false,
                    gradient_start_color text not null default '#FFFFFFFF',
                    gradient_end_color   text not null default '#000000FF',

                    line_spacing        real not null default 1.4,
                    alignment           text not null default 'center',
                    max_text_width_pct  integer not null default 80,
                    vertical_padding_pct integer not null default 10,

                    used_count      integer not null default 0,
                    used_at         timestamp,

                    created_at      timestamp not null default now(),
                    updated_at      timestamp not null default now()
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


def seed_default_presets(cfg: DbCfg) -> None:
    """Insert built-in presets (Neon Glow, Bold Modern, Streetwear) if not already present."""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into text_style_presets(
                    name, font_size, primary_color, position,
                    glow_color, glow_radius,
                    stroke_width, stroke_color,
                    gradient_enabled, gradient_start_color, gradient_end_color
                ) values
                (
                    'Neon Glow', 72, '#00FFFFFF', 'bottom',
                    '#00FFFFFF', 15,
                    0, '#000000FF',
                    false, '#FFFFFFFF', '#000000FF'
                ),
                (
                    'Bold Modern', 96, '#FFFFFFFF', 'center',
                    '#00000000', 0,
                    3, '#000000FF',
                    false, '#FFFFFFFF', '#000000FF'
                ),
                (
                    'Streetwear', 84, '#FFFFFFFF', 'bottom',
                    '#00000000', 0,
                    0, '#000000FF',
                    true, '#FF6B35FF', '#F7C948FF'
                )
                on conflict (name) do nothing;
                """
            )
        conn.commit()
    finally:
        conn.close()


def upsert_text_style_preset(cfg: DbCfg, preset: dict) -> dict:
    """Insert or update preset by name. Returns the saved record."""
    # Normalize keys to snake_case
    data: dict[str, Any] = {}
    for k, v in preset.items():
        data[_normalize_key(k)] = v

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Preset name is required")

    # Build column values for insert/update (exclude id, used_count, used_at, created_at, updated_at)
    col_values: dict[str, Any] = {"name": name}
    for col in _PRESET_COLUMNS:
        if col == "name":
            continue
        if col in data:
            col_values[col] = data[col]

    columns = list(col_values.keys())
    placeholders = [f"%s" for _ in columns]
    values = [col_values[c] for c in columns]

    # Build the ON CONFLICT update clause (update all columns except name)
    update_cols = [c for c in columns if c != "name"]
    update_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
    update_clause += ", updated_at=now()"

    col_str = ", ".join(columns)
    ph_str = ", ".join(placeholders)

    sql = f"""
        insert into text_style_presets ({col_str})
        values ({ph_str})
        on conflict (name) do update set {update_clause}
        returning {', '.join(_ALL_COLUMNS)}
    """

    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            row = cur.fetchone()
        conn.commit()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_text_style_preset(cfg: DbCfg, preset_id: int) -> None:
    """Remove preset by ID."""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from text_style_presets where id=%s", (int(preset_id),))
        conn.commit()
    finally:
        conn.close()


def list_text_style_presets(cfg: DbCfg) -> list[dict]:
    """Return all presets ordered by name ASC (case-insensitive)."""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"select {', '.join(_ALL_COLUMNS)} from text_style_presets order by lower(name) asc, id asc"
            )
            rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def pick_least_used_text_preset(cfg: DbCfg, exclude_ids: list[int] | None = None) -> dict | None:
    """Select the preset with the lowest used_count for rotation.
    Increments used_count and sets used_at after selection."""
    exclude = [int(x) for x in (exclude_ids or []) if x]
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            exclude_clause = " where id <> all(%s)" if exclude else ""
            params: tuple = (exclude,) if exclude else ()
            cur.execute(
                f"""
                select {', '.join(_ALL_COLUMNS)}
                from text_style_presets
                {exclude_clause}
                order by used_count asc, used_at asc nulls first, id asc
                limit 1
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                return None
            preset = _row_to_dict(row)
            preset_id = int(preset["id"])
            cur.execute(
                "update text_style_presets set used_count=used_count+1, used_at=now() where id=%s",
                (preset_id,),
            )
        conn.commit()
        return preset
    finally:
        conn.close()


def migrate_text_style_presets(cfg: DbCfg) -> None:
    """Run table creation and seed defaults. Called from the application migration pathway."""
    create_text_style_presets_table(cfg)
    seed_default_presets(cfg)
