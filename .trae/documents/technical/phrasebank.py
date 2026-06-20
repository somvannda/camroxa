from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


Kind = Literal["opening_line", "title_phrase"]


@dataclass(frozen=True)
class Phrase:
    id: int
    kind: Kind
    language: str
    text: str
    used_count: int


class PhraseBank:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS phrase_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    language TEXT NOT NULL,
                    text TEXT NOT NULL,
                    norm TEXT NOT NULL,
                    used_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_phrase_bank_kind_lang_norm ON phrase_bank(kind, language, norm)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_phrase_bank_kind_lang_used ON phrase_bank(kind, language, used_count, id)"
            )

    def normalize(self, text: str) -> str:
        t = str(text or "").strip().lower()
        t = re.sub(r"\s+", " ", t)
        return t

    def count(self, *, kind: Kind, language: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(1) AS c FROM phrase_bank WHERE kind = ? AND language = ?",
                (kind, language),
            ).fetchone()
            return int(row["c"]) if row else 0

    def count_unused(self, *, kind: Kind, language: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(1) AS c FROM phrase_bank WHERE kind = ? AND language = ? AND used_count = 0",
                (kind, language),
            ).fetchone()
            return int(row["c"]) if row else 0

    def insert_many(self, *, kind: Kind, language: str, texts: list[str]) -> int:
        if not texts:
            return 0
        with self._connect() as conn:
            cur = conn.cursor()
            inserted = 0
            for text in texts:
                text = str(text or "").strip()
                if not text:
                    continue
                norm = self.normalize(text)
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO phrase_bank(kind, language, text, norm) VALUES (?, ?, ?, ?)",
                        (kind, language, text, norm),
                    )
                except Exception:
                    continue
                inserted += cur.rowcount
            return inserted

    def pick(self, *, kind: Kind, language: str, n: int) -> list[Phrase]:
        n = int(n)
        if n <= 0:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, language, text, used_count
                FROM phrase_bank
                WHERE kind = ? AND language = ? AND used_count = 0
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (kind, language, n),
            ).fetchall()
            if len(rows) < n:
                rows = conn.execute(
                    """
                    SELECT id, kind, language, text, used_count
                    FROM phrase_bank
                    WHERE kind = ? AND language = ?
                    ORDER BY used_count ASC, RANDOM()
                    LIMIT ?
                    """,
                    (kind, language, n),
                ).fetchall()
            return [
                Phrase(
                    id=int(r["id"]),
                    kind=str(r["kind"]),  # type: ignore[arg-type]
                    language=str(r["language"]),
                    text=str(r["text"]),
                    used_count=int(r["used_count"]),
                )
                for r in rows
            ]

    def mark_used(self, *, ids: list[int]) -> None:
        if not ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "UPDATE phrase_bank SET used_count = used_count + 1 WHERE id = ?",
                [(int(i),) for i in ids],
            )
