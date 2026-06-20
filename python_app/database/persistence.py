from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.music_common import connect_db
from ..models.music_model import DEFAULT_SETTINGS, REMOVED_API_KEY_FIELDS, default_music_app_data, normalize_profile, normalize_saved_text
from ..models.spectrum_model import VideoTemplate


APP_DATA_KEY = "app_data_v1"
DB_SETTING_KEYS = {"dbHost", "dbPort", "dbUser", "dbPassword", "dbName"}
ENV_DB_KEYS = {
    "host": ("MG_DB_HOST", "DB_HOST", "POSTGRES_HOST", "PGHOST"),
    "port": ("MG_DB_PORT", "DB_PORT", "POSTGRES_PORT", "PGPORT"),
    "user": ("MG_DB_USER", "DB_USER", "POSTGRES_USER", "PGUSER"),
    "password": ("MG_DB_PASSWORD", "DB_PASSWORD", "POSTGRES_PASSWORD", "PGPASSWORD"),
    "database": ("MG_DB_NAME", "MG_DB_DATABASE", "DB_NAME", "POSTGRES_DB", "PGDATABASE"),
}


@dataclass(frozen=True)
class DbCfg:
    host: str
    port: int
    user: str
    password: str
    database: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_paths() -> list[Path]:
    return [
        _project_root() / ".env.example",
        _project_root() / ".env",
        _project_root() / "python_app" / ".env.example",
        _project_root() / "python_app" / ".env",
        Path.cwd() / ".env",
    ]


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = str(line or "").strip()
    if not text or text.startswith("#") or "=" not in text:
        return None
    if text.lower().startswith("export "):
        text = text[7:].strip()
    key, value = text.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    seen: set[Path] = set()
    for path in _env_paths():
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                parsed = _parse_env_line(line)
                if parsed:
                    values[parsed[0]] = parsed[1]
        except Exception:
            continue
    for key, value in os.environ.items():
        values[key] = value
    return values


def _first_env(values: dict[str, str], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = str(values.get(key, "")).strip()
        if value:
            return value
    return default


def db_cfg_from_env() -> DbCfg | None:
    values = load_dotenv_values()
    host = _first_env(values, ENV_DB_KEYS["host"])
    user = _first_env(values, ENV_DB_KEYS["user"])
    database = _first_env(values, ENV_DB_KEYS["database"])
    password = _first_env(values, ENV_DB_KEYS["password"])
    try:
        port = int(_first_env(values, ENV_DB_KEYS["port"], "5432"))
    except Exception:
        port = 5432
    if not host or not user or not database or port <= 0:
        return None
    return DbCfg(host=host, port=port, user=user, password=password, database=database)


def db_cfg_env_status() -> dict[str, object]:
    values = load_dotenv_values()
    found = {
        name: next((key for key in keys if str(values.get(key, "")).strip()), "")
        for name, keys in ENV_DB_KEYS.items()
    }
    return {
        "ok": bool(db_cfg_from_env()),
        "paths": [str(path) for path in _env_paths()],
        "found": found,
    }


def _setting_to_storage(value: Any) -> str:
    if isinstance(value, (dict, list, bool, int, float)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _setting_from_storage(value: Any) -> Any:
    if value is None:
        return ""
    text = str(value)
    stripped = text.strip()
    if stripped in {"", "null"}:
        return None if stripped == "null" else ""
    if stripped[0:1] in {"{", "[", '"'} or stripped in {"true", "false"}:
        try:
            return json.loads(stripped)
        except Exception:
            return text
    try:
        if "." not in stripped and stripped.lstrip("-").isdigit():
            return int(stripped)
    except Exception:
        pass
    return text


def _public_db_settings(cfg: DbCfg | None) -> dict:
    if not cfg:
        return {"dbHost": "", "dbPort": 5432, "dbUser": "", "dbPassword": "", "dbName": ""}
    return {"dbHost": cfg.host, "dbPort": cfg.port, "dbUser": cfg.user, "dbPassword": "", "dbName": cfg.database}


def _strip_db_setting_keys(settings: dict) -> dict:
    return {str(k): v for k, v in dict(settings or {}).items() if str(k) not in DB_SETTING_KEYS}


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def db_cfg_from_settings(settings: dict) -> DbCfg | None:
    if not isinstance(settings, dict):
        return None
    host = str(settings.get("dbHost", "")).strip()
    user = str(settings.get("dbUser", "")).strip()
    database = str(settings.get("dbName", "")).strip()
    password = str(settings.get("dbPassword", "") or "")
    try:
        port = int(settings.get("dbPort", 5432))
    except Exception:
        port = 5432
    if not host or not user or not database or port <= 0:
        return None
    return DbCfg(host=host, port=port, user=user, password=password, database=database)


def db_get_app_data(cfg: DbCfg) -> dict | None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select value from app_json where key = %s", (APP_DATA_KEY,))
            row = cur.fetchone()
            if not row:
                return None
            return row[0]
    finally:
        conn.close()


def db_set_app_data(cfg: DbCfg, app_data: dict) -> None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into app_json(key, value, updated_at) values (%s, %s::jsonb, now()) "
                "on conflict (key) do update set value = excluded.value, updated_at = now()",
                (APP_DATA_KEY, json.dumps(app_data, ensure_ascii=False)),
            )
    finally:
        conn.close()


def local_music_app_data_path() -> Path:
    return Path(__file__).with_name("music_app_data_local.json")


def read_local_music_app_data() -> dict | None:
    p = local_music_app_data_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def write_local_music_app_data(app_data: dict) -> None:
    _atomic_write_json(local_music_app_data_path(), app_data)


def read_music_app_data(db_cfg: DbCfg | None) -> dict | None:
    if db_cfg:
        try:
            stored = db_get_app_data(db_cfg)
            if isinstance(stored, dict):
                return stored
        except Exception:
            pass
    return read_local_music_app_data()


def write_music_app_data(db_cfg: DbCfg | None, app_data: dict) -> None:
    if db_cfg:
        try:
            db_set_app_data(db_cfg, app_data)
            return
        except Exception:
            pass
    write_local_music_app_data(app_data)


def db_get_settings(cfg: DbCfg) -> dict:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select key, value from app_settings")
            settings = {str(key): _setting_from_storage(value) for key, value in cur.fetchall()}
            return _strip_db_setting_keys(settings)
    finally:
        conn.close()


def db_patch_settings(cfg: DbCfg, patch: dict) -> dict | None:
    clean_patch = _strip_db_setting_keys(patch if isinstance(patch, dict) else {})
    if not clean_patch:
        return db_get_settings(cfg)
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            for key, value in clean_patch.items():
                cur.execute(
                    "insert into app_settings(key, value, updated_at) values (%s, %s, now()) "
                    "on conflict (key) do update set value = excluded.value, updated_at = now()",
                    (str(key), _setting_to_storage(value)),
                )
    finally:
        conn.close()
    return db_get_settings(cfg)


def db_delete_settings(cfg: DbCfg, keys: list[str]) -> None:
    clean_keys = [str(key).strip() for key in keys if str(key).strip() and str(key).strip() not in DB_SETTING_KEYS]
    if not clean_keys:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from app_settings where key = any(%s)", (clean_keys,))
    finally:
        conn.close()


def db_list_profiles(cfg: DbCfg) -> list[dict]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select uid, name, folder_name, run_prefix, logo_path, video_template_id, image_config, "
                "output_resolution, reel_template_id, "
                "youtube_visibility_mode, youtube_publish_at, youtube_publish_time, youtube_category_id, youtube_playlist_id, youtube_tags, "
                "youtube_title_template, youtube_description_template, youtube_made_for_kids, youtube_contains_synthetic_media, youtube_oauth_app_id, "
                "created_at, updated_at "
                "from profiles order by name asc, created_at asc"
            )
            rows: list[dict] = []
            for (
                uid,
                name,
                folder_name,
                run_prefix,
                logo_path,
                video_template_id,
                image_config,
                output_resolution,
                reel_template_id,
                youtube_visibility_mode,
                youtube_publish_at,
                youtube_publish_time,
                youtube_category_id,
                youtube_playlist_id,
                youtube_tags,
                youtube_title_template,
                youtube_description_template,
                youtube_made_for_kids,
                youtube_contains_synthetic_media,
                youtube_oauth_app_id,
                created_at,
                updated_at,
            ) in cur.fetchall():
                rows.append(
                    normalize_profile(
                        {
                            "id": str(uid or ""),
                            "name": str(name or ""),
                            "folderName": str(folder_name or ""),
                            "runPrefix": str(run_prefix or ""),
                            "logoPath": str(logo_path or ""),
                            "videoTemplateId": str(video_template_id or ""),
                            "reelTemplateId": str(reel_template_id or ""),
                            "outputResolution": str(output_resolution or ""),
                            "imageConfig": image_config if isinstance(image_config, dict) else (json.loads(image_config or "{}") if isinstance(image_config, str) else {}),
                            "youtubeVisibilityMode": str(youtube_visibility_mode or ""),
                            "youtubePublishAt": str(youtube_publish_time or "").strip()
                            or (youtube_publish_at.isoformat(timespec="seconds") if hasattr(youtube_publish_at, "isoformat") else str(youtube_publish_at or "")),
                            "youtubeCategoryId": str(youtube_category_id or ""),
                            "youtubePlaylistId": str(youtube_playlist_id or ""),
                            "youtubeTags": str(youtube_tags or ""),
                            "youtubeTitleTemplate": str(youtube_title_template or ""),
                            "youtubeDescriptionTemplate": str(youtube_description_template or ""),
                            "youtubeMadeForKids": bool(youtube_made_for_kids),
                            "youtubeContainsSyntheticMedia": bool(youtube_contains_synthetic_media),
                            "youtubeOauthAppId": str(youtube_oauth_app_id or ""),
                            "createdAt": created_at.isoformat(timespec="seconds") if hasattr(created_at, "isoformat") else str(created_at or ""),
                            "updatedAt": updated_at.isoformat(timespec="seconds") if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                        }
                    )
                )
            return rows
    finally:
        conn.close()


def db_get_profile_image_config(cfg: DbCfg, profile_id: str) -> dict:
    uid = str(profile_id or "").strip()
    if not uid:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select image_config from profiles where uid = %s", (uid,))
            row = cur.fetchone()
            if not row:
                return {}
            value = row[0]
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value or "{}")
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}
    finally:
        conn.close()


def db_get_profile_output_resolution(cfg: DbCfg, profile_id: str) -> str:
    uid = str(profile_id or "").strip()
    if not uid:
        return ""
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select output_resolution from profiles where uid = %s", (uid,))
            row = cur.fetchone()
            if not row:
                return ""
            return str(row[0] or "").strip()
    finally:
        conn.close()


def db_upsert_profile(cfg: DbCfg, profile: dict) -> dict:
    row = normalize_profile(profile if isinstance(profile, dict) else {})
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into profiles(uid, name, folder_name, run_prefix, logo_path, video_template_id, reel_template_id, image_config, output_resolution, "
                "youtube_visibility_mode, youtube_publish_at, youtube_publish_time, youtube_category_id, youtube_playlist_id, youtube_tags, "
                "youtube_title_template, youtube_description_template, youtube_made_for_kids, youtube_contains_synthetic_media, youtube_oauth_app_id, "
                "created_at, updated_at) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::timestamp, %s, %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s::timestamp, now()), coalesce(%s::timestamp, now())) "
                "on conflict (uid) do update set "
                "name = excluded.name, folder_name = excluded.folder_name, run_prefix = excluded.run_prefix, "
                "logo_path = excluded.logo_path, video_template_id = excluded.video_template_id, reel_template_id = excluded.reel_template_id, "
                "image_config = excluded.image_config, "
                "output_resolution = excluded.output_resolution, "
                "youtube_visibility_mode = excluded.youtube_visibility_mode, youtube_publish_at = excluded.youtube_publish_at, youtube_publish_time = excluded.youtube_publish_time, "
                "youtube_category_id = excluded.youtube_category_id, youtube_playlist_id = excluded.youtube_playlist_id, youtube_tags = excluded.youtube_tags, "
                "youtube_title_template = excluded.youtube_title_template, youtube_description_template = excluded.youtube_description_template, "
                "youtube_made_for_kids = excluded.youtube_made_for_kids, youtube_contains_synthetic_media = excluded.youtube_contains_synthetic_media, "
                "youtube_oauth_app_id = excluded.youtube_oauth_app_id, updated_at = excluded.updated_at",
                (
                    row["id"],
                    row["name"],
                    row["folderName"],
                    row["runPrefix"],
                    row["logoPath"],
                    row.get("videoTemplateId", ""),
                    row.get("reelTemplateId", ""),
                    json.dumps(row.get("imageConfig") if isinstance(row.get("imageConfig"), dict) else {}),
                    str(row.get("outputResolution", "")).strip(),
                    row.get("youtubeVisibilityMode", "unlisted"),
                    (row.get("youtubePublishAt") or None) if "T" in str(row.get("youtubePublishAt") or "") else None,
                    (str(row.get("youtubePublishAt") or "").strip() if re.match(r"^\d{1,2}:\d{2}$", str(row.get("youtubePublishAt") or "").strip()) else ""),
                    row.get("youtubeCategoryId", ""),
                    str(row.get("youtubePlaylistId", "")).strip(),
                    row.get("youtubeTags", ""),
                    row.get("youtubeTitleTemplate", ""),
                    row.get("youtubeDescriptionTemplate", ""),
                    bool(row.get("youtubeMadeForKids", False)),
                    bool(row.get("youtubeContainsSyntheticMedia", False)),
                    str(row.get("youtubeOauthAppId", "")).strip(),
                    row["createdAt"] or None,
                    row["updatedAt"] or None,
                ),
            )
    finally:
        conn.close()
    return row


def db_delete_profile(cfg: DbCfg, profile_id: str) -> None:
    uid = str(profile_id or "").strip()
    if not uid:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from profiles where uid = %s", (uid,))
    finally:
        conn.close()


def _saved_text_table(kind: str) -> tuple[str, str]:
    text = str(kind or "").strip().lower()
    if text.startswith("struct"):
        return "song_structures", "struct"
    return "song_descriptions", "desc"


def db_list_saved_texts(cfg: DbCfg, kind: str) -> list[dict]:
    table, prefix = _saved_text_table(kind)
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"select uid, name, content, match_key, updated_at from {table} order by name asc, updated_at desc"
            )
            rows: list[dict] = []
            for uid, name, content, match_key, updated_at in cur.fetchall():
                rows.append(
                    normalize_saved_text(
                        {
                            "id": str(uid or ""),
                            "name": str(name or ""),
                            "content": str(content or ""),
                            "matchKey": str(match_key or ""),
                            "updatedAt": updated_at.isoformat(timespec="seconds") if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                        },
                        prefix,
                    )
                )
            return rows
    finally:
        conn.close()


def db_upsert_saved_text(cfg: DbCfg, kind: str, item: dict) -> dict:
    table, prefix = _saved_text_table(kind)
    row = normalize_saved_text(item if isinstance(item, dict) else {}, prefix)
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"insert into {table}(uid, name, content, match_key, updated_at) "
                "values (%s, %s, %s, %s, coalesce(%s::timestamp, now())) "
                "on conflict (uid) do update set name = excluded.name, content = excluded.content, "
                "match_key = excluded.match_key, updated_at = excluded.updated_at",
                (row["id"], row["name"], row["content"], row["matchKey"], row["updatedAt"] or None),
            )
    finally:
        conn.close()
    return row


def db_delete_saved_text(cfg: DbCfg, kind: str, item_id: str) -> None:
    table, _prefix = _saved_text_table(kind)
    uid = str(item_id or "").strip()
    if not uid:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"delete from {table} where uid = %s", (uid,))
    finally:
        conn.close()


def db_load_music_app_data(cfg: DbCfg | None) -> dict:
    data = default_music_app_data()
    if cfg is None:
        data["settings"] = {**_strip_db_setting_keys(DEFAULT_SETTINGS), **_public_db_settings(None)}
        # Silently discard removed API key fields
        for key in REMOVED_API_KEY_FIELDS:
            data["settings"].pop(key, None)
        return data
    # Always merge from BOTH storage sources:
    # 1. Start with defaults
    settings = {**_strip_db_setting_keys(DEFAULT_SETTINGS)}
    # 2. Layer in old app_json blob (backwards compatibility)
    try:
        blob = db_get_app_data(cfg)
        if isinstance(blob, dict):
            blob_settings = blob.get("settings") if isinstance(blob.get("settings"), dict) else {}
            settings = {**settings, **_strip_db_setting_keys(blob_settings)}
    except Exception:
        pass
    # 3. Layer in new key-value app_settings table (takes precedence)
    settings = {**settings, **db_get_settings(cfg), **_public_db_settings(cfg)}
    # Silently discard removed API key fields
    for key in REMOVED_API_KEY_FIELDS:
        settings.pop(key, None)
    descriptions = db_list_saved_texts(cfg, "descriptions")
    structures = db_list_saved_texts(cfg, "structures")
    profiles = db_list_profiles(cfg)
    data["settings"] = settings
    if descriptions:
        data["descriptions"] = descriptions
    if structures:
        data["structures"] = structures
    data["profiles"] = profiles
    return data


def db_seed_music_app_data(cfg: DbCfg, app_data: dict) -> None:
    if not isinstance(app_data, dict):
        return
    settings = app_data.get("settings") if isinstance(app_data.get("settings"), dict) else {}
    db_patch_settings(cfg, settings)
    for row in app_data.get("profiles") or []:
        if isinstance(row, dict):
            db_upsert_profile(cfg, row)
    for row in app_data.get("descriptions") or []:
        if isinstance(row, dict):
            db_upsert_saved_text(cfg, "descriptions", row)
    for row in app_data.get("structures") or []:
        if isinstance(row, dict):
            db_upsert_saved_text(cfg, "structures", row)


def db_list_video_templates(cfg: DbCfg, kind: str = "video") -> list[VideoTemplate]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select uid, name, source, template, updated_at from video_templates where kind = %s order by name asc",
                (kind,),
            )
            out: list[VideoTemplate] = []
            for uid, name, source, template, updated_at in cur.fetchall():
                out.append(
                    VideoTemplate(
                        id=str(uid),
                        name=str(name or ""),
                        source="builtin" if str(source or "user") == "builtin" else "user",
                        template=template if isinstance(template, dict) else {},
                        updated_at=str(updated_at),
                    )
                )
            return out
    finally:
        conn.close()


def db_get_video_template(cfg: DbCfg, template_id: str) -> VideoTemplate | None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select uid, name, source, template, updated_at from video_templates where uid = %s", (template_id,))
            row = cur.fetchone()
            if not row:
                return None
            uid, name, source, template, updated_at = row
            return VideoTemplate(
                id=str(uid),
                name=str(name or ""),
                source="builtin" if str(source or "user") == "builtin" else "user",
                template=template if isinstance(template, dict) else {},
                updated_at=str(updated_at),
            )
    finally:
        conn.close()


def db_upsert_video_template(cfg: DbCfg, template_id: str, name: str, template: dict, *, kind: str = "video") -> None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into video_templates(uid, name, source, template, kind, created_at, updated_at) "
                "values (%s,%s,%s,%s::jsonb,%s, now(), now()) "
                "on conflict (uid) do update set name = excluded.name, source = excluded.source, template = excluded.template, kind = excluded.kind, updated_at = now()",
                (template_id, name, "user", json.dumps(template, ensure_ascii=False), kind),
            )
    finally:
        conn.close()


def db_delete_video_template(cfg: DbCfg, template_id: str) -> None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from video_templates where uid = %s", (template_id,))
    finally:
        conn.close()


def local_templates_path() -> Path:
    return Path(__file__).resolve().parents[1] / "video_templates_local.json"


def read_local_templates() -> list[VideoTemplate]:
    p = local_templates_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        out: list[VideoTemplate] = []
        for x in raw:
            if not isinstance(x, dict):
                continue
            out.append(
                VideoTemplate(
                    id=str(x.get("id", "")),
                    name=str(x.get("name", "")),
                    source=str(x.get("source", "user")),
                    template=x.get("template") if isinstance(x.get("template"), dict) else {},
                    updated_at=str(x.get("updated_at", "")),
                )
            )
        return out
    except Exception:
        return []


def write_local_templates(rows: list[VideoTemplate]) -> None:
    _atomic_write_json(
        local_templates_path(),
        [
            {
                "id": r.id,
                "name": r.name,
                "source": r.source,
                "template": r.template,
                "updated_at": r.updated_at,
            }
            for r in rows
        ],
    )
