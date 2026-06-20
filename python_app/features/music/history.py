"""Music history data coordinator.

Separates data fetching/transformation from QTableWidget population.
"""

from __future__ import annotations

import re
from typing import Any


class MusicHistoryCoordinator:
    """Coordinates music history data fetching and transformation.

    Returns structured row data for UI population without touching widgets.
    """

    def load_history_rows(
        self,
        *,
        db_cfg: Any | None,
        music_data: dict,
        from_ymd: str,
        to_ymd: str,
        limit: int = 5000,
        latest_batch_only: bool,
        list_songs_for_history_fn=None,
        list_latest_suno_tasks_by_song_uids_fn=None,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Fetch and transform history data.

        This is the thin public entry point. Delegates to ``build_history_rows``
        internally so callers get a single method for the data-loading step.

        Args:
            db_cfg: Database configuration (None if offline mode).
            music_data: Fallback music data dict with "songs" key.
            from_ymd: Start date filter (YYYY-MM-DD).
            to_ymd: End date filter (YYYY-MM-DD).
            limit: Max rows when querying database.
            latest_batch_only: If True, only return the latest batch.
            list_songs_for_history_fn: DB query function.
            list_latest_suno_tasks_by_song_uids_fn: DB query function for Suno tasks.

        Returns:
            (table_rows, suno_latest) where table_rows is a list of dicts
            (including separator rows with __separator__=True) and
            suno_latest is a dict mapping song_id -> suno task data.
        """
        return self.build_history_rows(
            db_cfg=db_cfg,
            music_data=music_data,
            from_ymd=from_ymd,
            to_ymd=to_ymd,
            limit=limit,
            latest_batch_only=latest_batch_only,
            list_songs_for_history_fn=list_songs_for_history_fn,
            list_latest_suno_tasks_by_song_uids_fn=list_latest_suno_tasks_by_song_uids_fn,
        )

    def build_history_rows(
        self,
        *,
        db_cfg: Any | None,
        music_data: dict,
        from_ymd: str,
        to_ymd: str,
        limit: int = 5000,
        latest_batch_only: bool,
        list_songs_for_history_fn=None,
        list_latest_suno_tasks_by_song_uids_fn=None,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Build history rows and suno lookup data.

        Args:
            db_cfg: Database configuration (None if offline mode).
            music_data: Fallback music data dict with "songs" key.
            from_ymd: Start date filter (YYYY-MM-DD).
            to_ymd: End date filter (YYYY-MM-DD).
            limit: Max rows when querying database.
            latest_batch_only: If True, only return the latest batch.
            list_songs_for_history_fn: DB query function.
            list_latest_suno_tasks_by_song_uids_fn: DB query function for Suno tasks.

        Returns:
            (table_rows, suno_latest) where table_rows is a list of dicts
            (including separator rows with __separator__=True) and
            suno_latest is a dict mapping song_id -> suno task data.
        """
        list_songs_fn = list_songs_for_history_fn or _noop_list_songs
        list_suno_fn = list_latest_suno_tasks_by_song_uids_fn or _noop_list_suno

        rows = self._fetch_rows(
            db_cfg=db_cfg,
            music_data=music_data,
            from_ymd=from_ymd,
            to_ymd=to_ymd,
            limit=limit,
            latest_batch_only=latest_batch_only,
            list_songs_fn=list_songs_fn,
        )

        table_rows = self._group_into_batches(rows)

        suno_latest: dict[str, dict] = {}
        if db_cfg:
            try:
                song_uids = [str((x or {}).get("songUid", "")).strip() for x in rows if isinstance(x, dict)]
                suno_latest = list_suno_fn(db_cfg, song_uids)
            except Exception:
                suno_latest = {}

        return table_rows, suno_latest

    def _fetch_rows(
        self,
        *,
        db_cfg: Any | None,
        music_data: dict,
        from_ymd: str,
        to_ymd: str,
        limit: int,
        latest_batch_only: bool,
        list_songs_fn,
    ) -> list[dict]:
        """Fetch and filter raw song rows."""
        if db_cfg:
            try:
                rows = list_songs_fn(
                    db_cfg,
                    from_ymd=from_ymd,
                    to_ymd=to_ymd,
                    limit=limit,
                    latest_batch_only=False,
                )
            except Exception as exc:
                rows = []
                import sys
                print(f"[HISTORY ERROR] DB query failed: {exc}", file=sys.stderr, flush=True)
        else:
            songs = music_data.get("songs") if isinstance(music_data.get("songs"), list) else []
            rows = [dict(song) for song in songs if isinstance(song, dict)]

            def _effective_history_ymd(song_row: dict) -> str:
                run_date = str(song_row.get("runDate", "")).strip()
                if not run_date:
                    batch_id = str(song_row.get("batchId", "")).strip()
                    m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})", batch_id)
                    run_date = str(m.group(1)) if m else ""
                created = str(song_row.get("createdAt", "")).strip()
                return (run_date or created[:10]).strip()

            if from_ymd:
                rows = [s for s in rows if _effective_history_ymd(s) >= from_ymd]
            if to_ymd:
                rows = [s for s in rows if _effective_history_ymd(s) <= to_ymd]

            rows.sort(key=self._history_sort_key, reverse=True)

        if latest_batch_only and rows:
            latest_batch = str(rows[0].get("batchId", "")).strip()
            if latest_batch:
                rows = [s for s in rows if str(s.get("batchId", "")).strip() == latest_batch]

        return rows

    def _group_into_batches(self, rows: list[dict]) -> list[dict]:
        """Group rows by batch and interleave separator rows."""
        def _resolve_batch_id(song_row: dict) -> str:
            return str(song_row.get("batchId", "")).strip()

        def _created_key(song_row: dict) -> str:
            return str((song_row or {}).get("createdAt", "")).strip()

        def _resolve_run_date(song_row: dict) -> str:
            run_date = str(song_row.get("runDate", "")).strip()
            if run_date:
                return run_date
            batch_id = str(song_row.get("batchId", "")).strip()
            m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})", batch_id)
            return str(m.group(1)) if m else ""

        batches: dict[str, list[dict]] = {}
        for song in rows:
            if not isinstance(song, dict):
                continue
            batch_id = _resolve_batch_id(song) or "(no batch)"
            batches.setdefault(batch_id, []).append(song)

        batch_order: list[tuple[str, str]] = []
        for batch_id, songs_in_batch in batches.items():
            max_created = max((_created_key(x) for x in songs_in_batch if _created_key(x)), default="")
            batch_order.append((batch_id, max_created))
        batch_order.sort(key=lambda x: (x[1] or "", x[0]), reverse=True)

        table_rows: list[dict] = []
        for batch_id, max_created in batch_order:
            songs_in_batch = list(batches.get(batch_id) or [])
            songs_in_batch.sort(
                key=lambda x: (_created_key(x) or "", str((x or {}).get("id", "")).strip()),
                reverse=True,
            )
            first_song = songs_in_batch[0] if songs_in_batch else {}
            table_rows.append(
                {
                    "__separator__": True,
                    "batchId": batch_id,
                    "runDate": _resolve_run_date(first_song),
                    "generatedAt": max_created,
                }
            )
            table_rows.extend(songs_in_batch)

        return table_rows

    @staticmethod
    def _history_sort_key(song_row: dict) -> tuple:
        created = str(song_row.get("createdAt", "")).strip()
        return (created or "", str(song_row.get("id", "")).strip())


def _noop_list_suno_tasks_by_song_uids(db_cfg, song_uids):
    return {}


def _noop_list_songs(db_cfg, from_ymd=None, to_ymd=None, limit=None, latest_batch_only=None):
    return []
