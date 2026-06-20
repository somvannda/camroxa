from __future__ import annotations

from pathlib import Path
import random
import time
from typing import Any

from ..utils.music_common import connect_db, normalize_text
from .persistence import DbCfg


def pools_stats(cfg: DbCfg) -> dict:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from opening_pairs")
            openings = cur.fetchone() or (0, 0)
            cur.execute("select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from title_pool")
            titles = cur.fetchone() or (0, 0)
            cur.execute("select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from album_pool")
            albums = cur.fetchone() or (0, 0)
        return {
            "openings": {"total": int(openings[0] or 0), "unused": int(openings[1] or 0)},
            "titles": {"total": int(titles[0] or 0), "unused": int(titles[1] or 0)},
            "albums": {"total": int(albums[0] or 0), "unused": int(albums[1] or 0)},
        }
    finally:
        conn.close()


def _chunked_insert(conn: Any, query_prefix: str, rows: list[tuple[str, ...]]) -> int:
    inserted = 0
    chunk_size = 1000
    with conn.cursor() as cur:
        for idx in range(0, len(rows), chunk_size):
            chunk = rows[idx : idx + chunk_size]
            values = []
            params: list[str] = []
            p = 1
            for row in chunk:
                values.append("(" + ", ".join(f"%s" for _ in row) + ")")
                params.extend(row)
                p += len(row)
            cur.execute(query_prefix + ", ".join(values), params)
            inserted += int(cur.rowcount or 0)
    return inserted


def import_titles(cfg: DbCfg, titles: list[str]) -> dict:
    rows = []
    for title in titles:
        text = str(title or "").strip()
        norm = normalize_text(text)
        if text and norm:
            rows.append((text, norm))
    if not rows:
        return {"inserted": 0}
    conn = connect_db(cfg)
    try:
        with conn:
            inserted = _chunked_insert(
                conn,
                "insert into title_pool(title, norm) values ",
                rows,
            )
            with conn.cursor() as cur:
                cur.execute("select 1")
        return {"inserted": inserted}
    except Exception:
        conn.rollback()
        inserted = 0
        with conn:
            with conn.cursor() as cur:
                chunk_size = 1000
                for idx in range(0, len(rows), chunk_size):
                    chunk = rows[idx : idx + chunk_size]
                    values = []
                    params: list[str] = []
                    for row in chunk:
                        values.append("(%s, %s)")
                        params.extend(row)
                    cur.execute(
                        "insert into title_pool(title, norm) values "
                        + ", ".join(values)
                        + " on conflict (norm) do nothing",
                        params,
                    )
                    inserted += int(cur.rowcount or 0)
        return {"inserted": inserted}
    finally:
        conn.close()


def import_albums(cfg: DbCfg, albums: list[str]) -> dict:
    rows = []
    for album in albums:
        text = str(album or "").strip()
        norm = normalize_text(text)
        if text and norm:
            rows.append((text, norm))
    if not rows:
        return {"inserted": 0}
    conn = connect_db(cfg)
    try:
        inserted = 0
        with conn:
            with conn.cursor() as cur:
                chunk_size = 1000
                for idx in range(0, len(rows), chunk_size):
                    chunk = rows[idx : idx + chunk_size]
                    values = []
                    params: list[str] = []
                    for row in chunk:
                        values.append("(%s, %s)")
                        params.extend(row)
                    cur.execute(
                        "insert into album_pool(album, norm) values "
                        + ", ".join(values)
                        + " on conflict (norm) do nothing",
                        params,
                    )
                    inserted += int(cur.rowcount or 0)
        return {"inserted": inserted}
    finally:
        conn.close()


def import_openings(cfg: DbCfg, pairs: list[dict]) -> dict:
    rows = []
    for pair in pairs:
        line1 = str((pair or {}).get("line1", "")).strip()
        line2 = str((pair or {}).get("line2", "")).strip()
        norm = normalize_text(f"{line1} {line2}")
        if line1 and line2 and norm:
            rows.append((line1, line2, norm))
    if not rows:
        return {"inserted": 0}
    conn = connect_db(cfg)
    try:
        inserted = 0
        with conn:
            with conn.cursor() as cur:
                chunk_size = 1000
                for idx in range(0, len(rows), chunk_size):
                    chunk = rows[idx : idx + chunk_size]
                    values = []
                    params: list[str] = []
                    for row in chunk:
                        values.append("(%s, %s, %s)")
                        params.extend(row)
                    cur.execute(
                        "insert into opening_pairs(line1, line2, norm) values "
                        + ", ".join(values)
                        + " on conflict (norm) do nothing",
                        params,
                    )
                    inserted += int(cur.rowcount or 0)
        return {"inserted": inserted}
    finally:
        conn.close()


def _pick(arr: list[str]) -> str:
    return random.choice(arr)


_ADJECTIVES = [
    "neon", "midnight", "electric", "golden", "silver", "crystal", "velvet", "static", "hollow", "distant",
    "bright", "blurred", "wild", "quiet", "loud", "tender", "broken", "unspoken", "secret", "reckless",
    "restless", "glowing", "fading", "burning", "frozen", "sunlit", "moonlit", "stormy", "rainy", "endless",
    "timeless", "digital", "analog", "city", "lunar", "solar", "magnetic", "cosmic", "chromatic", "sapphire",
    "amber", "violet", "scarlet", "obsidian", "emerald", "steel", "soft", "heavy", "weightless", "retro",
    "glitch", "fearless", "urgent", "hidden", "parallel", "spiral", "silent", "wired", "radio", "liquid",
    "solid", "sunset", "dawn", "twilight", "late-night", "glimmering", "drifting", "steady", "wavering",
    "electric-summer", "winter", "spring", "autumn", "radiant", "dim", "synth", "bass", "darkwave", "dream",
    "soft-focus", "hard-edge", "glass", "neon-lit", "street", "ocean", "sky", "underground", "electric-heart",
]

_NOUNS = [
    "city", "night", "dream", "static", "signal", "pulse", "echo", "shadow", "light", "glow", "storm", "rain",
    "thunder", "sky", "ocean", "river", "street", "avenue", "highway", "mirror", "window", "key", "heart",
    "voice", "silence", "noise", "fire", "ice", "ember", "spark", "star", "moon", "sun", "orbit", "gravity",
    "comet", "circuit", "wire", "frequency", "wave", "bassline", "melody", "hook", "chorus", "verse", "break",
    "drop", "build", "nightfall", "afterglow", "midnight", "dawn", "rush", "kiss", "truth", "promise",
    "secret", "memory", "moment", "road", "edge", "horizon", "arcade", "station", "radio", "camera", "story",
    "chapter", "refrain", "heartbeat", "breath", "glimmer", "pattern", "kick", "snare", "groove", "tempo",
    "hotel", "rooftop", "bridge", "tunnel", "coast", "harbor", "dust", "smoke", "chrome", "pixel", "glitch",
    "drift", "loop", "strobe", "laser", "fog", "constellation", "satellite", "nightdrive",
]

_VERBS = [
    "chase", "follow", "forget", "remember", "hold", "leave", "find", "lose", "burn", "freeze", "drift", "run",
    "hide", "show", "turn", "fade", "glow", "fall", "rise", "wait", "breathe", "call", "answer", "promise",
    "break", "build", "dance", "move", "stay", "go",
]

_PLACES = [
    "on the rooftop", "in the hallway", "by the river", "under streetlights", "in the backseat", "at the station",
    "in the club", "on the coastline", "beneath the neon", "under the moon", "in the quiet room", "inside the static",
    "between the lines", "in the dark", "in the blue hour",
]

_FEELINGS = [
    "like home", "for the first time", "like we never left", "until the morning", "without a warning",
    "in perfect sync", "on repeat", "in slow motion", "in the afterglow", "in the silence", "in the noise",
    "under my skin",
]


def generate_title_candidates(count: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    target = max(1, int(count or 1))
    attempts = 0
    while len(out) < target and attempts < target * 30:
        attempts += 1
        a = _pick(_ADJECTIVES)
        n = _pick(_NOUNS)
        n2 = _pick(_NOUNS)
        v = _pick(_VERBS)
        place = _pick(_PLACES)
        feel = _pick(_FEELINGS)
        pattern = attempts % 12
        text = (
            f"When the {a} {n} calls" if pattern == 0 else
            f"{a} {n}" if pattern == 1 else
            f"Echoes of the {a} {n}" if pattern == 2 else
            f"After the {a} {n}" if pattern == 3 else
            f"Under the {a} {n}" if pattern == 4 else
            f"Between {a} {n} and {n2}" if pattern == 5 else
            f"This is how it feels {feel}" if pattern == 6 else
            f"I {v} {place}" if pattern == 7 else
            f"We {v} through the {a} {n}" if pattern == 8 else
            f"Don't let the {a} {n} fade" if pattern == 9 else
            f"I {v} and you stay {feel}" if pattern == 10 else
            f"Under streetlights, we {v} again"
        )
        norm = normalize_text(text)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(text)
    return out


def generate_album_candidates(count: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    target = max(1, int(count or 1))
    attempts = 0
    while len(out) < target and attempts < target * 30:
        attempts += 1
        a = _pick(_ADJECTIVES)
        n = _pick(_NOUNS)
        n2 = _pick(_NOUNS)
        pattern = attempts % 6
        text = (
            f"Stories from the {a} {n}" if pattern == 0 else
            f"Letters in the {a} {n}" if pattern == 1 else
            f"The {a} {n} Collection" if pattern == 2 else
            f"{a} {n} and {n2}" if pattern == 3 else
            f"Inside the {a} {n}" if pattern == 4 else
            f"Between {a} {n} and {n2}"
        )
        norm = normalize_text(text)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(text)
    return out


def generate_opening_pairs(count: int) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    target = max(1, int(count or 1))
    attempts = 0
    whos = ["I", "We", "You", "Tonight", "Somewhere", "In my head", "In your eyes", "Under the neon", "After midnight"]
    moods = ["love", "heartbreak", "longing", "regret", "hope", "jealousy", "desire", "nostalgia", "loneliness", "euphoria"]
    times = ["tonight", "right now", "in the morning", "after midnight", "before dawn", "all summer", "all winter", "for one more hour"]
    while len(out) < target and attempts < target * 40:
        attempts += 1
        a = _pick(_ADJECTIVES)
        n = _pick(_NOUNS)
        v = _pick(_VERBS)
        place = _pick(_PLACES)
        who = _pick(whos)
        mood = _pick(moods)
        time_label = _pick(times)
        line1 = (
            f"{who} {v} the {a} {n} {place}."
            if who in {"I", "We", "You"}
            else f"{who}, the {a} {n} feels too close {time_label}."
        )
        line2 = _pick(
            [
                f"My {mood} is louder than the kick drum {time_label}.",
                f"Your voice turns into static, and I still hear it {time_label}.",
                f"I taste the goodbye in the air, sweet and cruel {time_label}.",
                f"We promised we'd be fearless, then we blinked {time_label}.",
                f"I keep the truth on mute, but it leaks through {time_label}.",
                f"Hold me like a secret you can't keep {time_label}.",
                f"If this is love, why does it hurt so clean {time_label}?",
                f"I miss the version of us that never breaks {time_label}.",
                f"Tell me it's real, even if it's only for the chorus {time_label}.",
                f"I let the night decide who we are {time_label}.",
            ]
        )
        norm = normalize_text(f"{line1} {line2}")
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append({"line1": line1, "line2": line2})
    return out


def generate_and_insert(cfg: DbCfg, kind: str, count: int) -> dict:
    target = max(1, min(200000, int(count or 1)))
    inserted = 0
    rounds = 0
    while inserted < target and rounds < 40:
        rounds += 1
        remaining = target - inserted
        batch = min(5000, remaining)
        if str(kind) == "titles":
            inserted += int(import_titles(cfg, generate_title_candidates(batch * 2)).get("inserted", 0) or 0)
        elif str(kind) == "albums":
            inserted += int(import_albums(cfg, generate_album_candidates(batch * 2)).get("inserted", 0) or 0)
        else:
            inserted += int(import_openings(cfg, generate_opening_pairs(batch * 2)).get("inserted", 0) or 0)
        if rounds >= 6 and inserted == 0:
            break
    return {"inserted": inserted}


def list_pool(cfg: DbCfg, kind: str, limit: int, offset: int) -> dict:
    limit_n = max(1, min(500, int(limit or 100)))
    offset_n = max(0, int(offset or 0))
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            if str(kind) == "titles":
                cur.execute(
                    'select id, title as text, used_count as "usedCount", created_at as "createdAt" from title_pool order by id desc limit %s offset %s',
                    (limit_n, offset_n),
                )
                rows = [{"id": int(x[0]), "text": str(x[1]), "usedCount": int(x[2]), "createdAt": str(x[3])} for x in cur.fetchall()]
                return {"kind": "titles", "rows": rows}
            if str(kind) == "albums":
                cur.execute(
                    'select id, album as text, used_count as "usedCount", created_at as "createdAt" from album_pool order by id desc limit %s offset %s',
                    (limit_n, offset_n),
                )
                rows = [{"id": int(x[0]), "text": str(x[1]), "usedCount": int(x[2]), "createdAt": str(x[3])} for x in cur.fetchall()]
                return {"kind": "albums", "rows": rows}
            cur.execute(
                'select id, line1, line2, used_count as "usedCount", created_at as "createdAt" from opening_pairs order by id desc limit %s offset %s',
                (limit_n, offset_n),
            )
            rows = [
                {"id": int(x[0]), "line1": str(x[1]), "line2": str(x[2]), "usedCount": int(x[3]), "createdAt": str(x[4])}
                for x in cur.fetchall()
            ]
            return {"kind": "openings", "rows": rows}
    finally:
        conn.close()


def clear_pool(cfg: DbCfg, kind: str) -> dict:
    conn = connect_db(cfg)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("set local lock_timeout = '3s'")
                cur.execute("set local statement_timeout = '20s'")
                if str(kind) == "titles":
                    cur.execute("truncate table title_pool restart identity")
                elif str(kind) == "albums":
                    cur.execute("truncate table album_pool restart identity")
                else:
                    cur.execute("truncate table opening_pairs restart identity")
        return {"ok": True}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc)}
    finally:
        conn.close()


def clear_generated(cfg: DbCfg) -> dict:
    conn = connect_db(cfg)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("set local lock_timeout = '3s'")
                cur.execute("set local statement_timeout = '20s'")
                cur.execute("truncate table images restart identity cascade")
                cur.execute("truncate table history restart identity cascade")
                cur.execute("truncate table songs restart identity cascade")
        return {"ok": True, "message": "Cleared songs + history"}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc)}
    finally:
        conn.close()


def parse_openings_text(raw_text: str) -> list[dict]:
    lines = [line.rstrip("\r") for line in str(raw_text or "").splitlines()]
    non_empty = [line.strip() for line in lines if line.strip()]
    out: list[dict] = []
    tab_pairs = [line for line in non_empty if "\t" in line]
    if tab_pairs and len(tab_pairs) >= max(1, len(non_empty) // 2):
        for line in non_empty:
            parts = [part.strip() for part in line.split("\t", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                out.append({"line1": parts[0], "line2": parts[1]})
        return out
    for idx in range(0, len(non_empty), 2):
        if idx + 1 >= len(non_empty):
            break
        out.append({"line1": non_empty[idx], "line2": non_empty[idx + 1]})
    return out


def parse_text_file(file_path: str) -> list[str]:
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_openings_file(file_path: str) -> list[dict]:
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    return parse_openings_text(text)
