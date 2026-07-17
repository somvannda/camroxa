"""Marketplace-related database queries for the local video_templates table.

Provides CRUD operations for marketplace-installed templates using synchronous
psycopg2 connections following the same pattern as the legacy persistence layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg2


@dataclass(frozen=True)
class DbConfig:
    """Database connection configuration."""

    host: str
    port: int
    user: str
    password: str
    database: str


def _connect(cfg: DbConfig) -> Any:
    """Create a psycopg2 connection with sensible defaults."""
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        dbname=cfg.database,
        connect_timeout=8,
    )
    conn.autocommit = True
    return conn


def insert_installed_template(
    cfg: DbConfig,
    *,
    uid: str,
    name: str,
    source: str,
    template_json: dict[str, Any],
    kind: str,
    user_id: str,
    marketplace_item_id: str,
) -> None:
    """Insert a new marketplace-installed template into video_templates.

    Creates a record with the given fields. The source should be 'marketplace'
    for templates installed from the marketplace catalog.
    """
    conn = _connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO video_templates"
                "(uid, name, source, template, kind, user_id, marketplace_item_id, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, now(), now())",
                (
                    uid,
                    name,
                    source,
                    json.dumps(template_json, ensure_ascii=False),
                    kind,
                    user_id,
                    marketplace_item_id,
                ),
            )
    finally:
        conn.close()


def get_by_marketplace_item_id(
    cfg: DbConfig,
    *,
    marketplace_item_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """Check if a template from a specific marketplace item is already installed.

    Returns the installed template record as a dict if found, or None if
    no matching record exists for the given marketplace_item_id and user_id.
    """
    conn = _connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid, name, source, template, kind, user_id, "
                "marketplace_item_id, created_at, updated_at "
                "FROM video_templates "
                "WHERE marketplace_item_id = %s AND user_id = %s",
                (marketplace_item_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "uid": str(row[0]),
                "name": str(row[1] or ""),
                "source": str(row[2] or ""),
                "template": row[3] if isinstance(row[3], dict) else {},
                "kind": str(row[4] or ""),
                "user_id": str(row[5] or ""),
                "marketplace_item_id": str(row[6] or ""),
                "created_at": row[7],
                "updated_at": row[8],
            }
    finally:
        conn.close()


def update_installed_template(
    cfg: DbConfig,
    *,
    uid: str,
    name: str,
    template_json: dict[str, Any],
    kind: str,
    updated_at: datetime | None = None,
) -> None:
    """Update an installed marketplace template (for reinstall).

    Updates the template JSON, name, kind, and updated_at timestamp while
    preserving the original uid and created_at.
    """
    conn = _connect(cfg)
    try:
        with conn.cursor() as cur:
            if updated_at is not None:
                cur.execute(
                    "UPDATE video_templates "
                    "SET name = %s, template = %s::jsonb, kind = %s, updated_at = %s "
                    "WHERE uid = %s",
                    (
                        name,
                        json.dumps(template_json, ensure_ascii=False),
                        kind,
                        updated_at,
                        uid,
                    ),
                )
            else:
                cur.execute(
                    "UPDATE video_templates "
                    "SET name = %s, template = %s::jsonb, kind = %s, updated_at = now() "
                    "WHERE uid = %s",
                    (
                        name,
                        json.dumps(template_json, ensure_ascii=False),
                        kind,
                        uid,
                    ),
                )
    finally:
        conn.close()


def delete_template(cfg: DbConfig, *, uid: str) -> None:
    """Delete a template record by uid."""
    conn = _connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM video_templates WHERE uid = %s",
                (uid,),
            )
    finally:
        conn.close()
