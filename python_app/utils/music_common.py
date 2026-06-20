from __future__ import annotations

import psycopg2


def connect_db(cfg, *, autocommit: bool = False, database: str | None = None):
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        dbname=database or cfg.database,
        connect_timeout=8,
    )
    conn.autocommit = bool(autocommit)
    try:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout = %s", ("8000",))
    except Exception:
        pass
    return conn


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split()).strip()


def db_identity_key(cfg) -> str:
    return f"{cfg.user}@{cfg.host}:{cfg.port}/{cfg.database}"


def opening2_lines(lyrics: str) -> str:
    def is_header(line: str) -> bool:
        text = str(line or "").strip()
        return bool(text.startswith("[") and text.endswith("]"))

    lines = [
        line.strip()
        for line in str(lyrics or "").splitlines()
        if line.strip() and not is_header(line)
    ][:2]
    return "\n".join(lines)
