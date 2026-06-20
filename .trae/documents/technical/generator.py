from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from zlib import crc32

from .deepseek_client import DeepSeekClient


@dataclass(frozen=True)
class Song:
    title: str
    lyrics: str
    content_hash: str


def _normalize_text(s: str) -> str:
    s = s.strip()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def compute_song_hash(title: str, lyrics: str) -> str:
    payload = (_normalize_text(title) + "\n---\n" + _normalize_text(lyrics)).lower()
    return sha256(payload.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    t = _normalize_text(title).lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def prepare_title_norms(titles: list[str]) -> list[str]:
    return [normalize_title(t) for t in titles]


def prepare_lyrics_fingerprints(existing_lyrics: list[str]) -> tuple[list[str], list[str], list[int]]:
    norms = [_normalize_for_compare(x) for x in existing_lyrics]
    openings = [_normalize_for_compare(_extract_opening(x)) for x in existing_lyrics]
    sigs = [_simhash64_from_normalized(x) for x in norms]
    return norms, openings, sigs


def fingerprint_lyrics(lyrics: str) -> tuple[str, str, int]:
    n = _normalize_for_compare(lyrics)
    o = _normalize_for_compare(_extract_opening(lyrics))
    sig = _simhash64_from_normalized(n) if n else 0
    return n, o, int(sig)


def is_lyric_similarity_at_least_with_loader(
    lyrics: str,
    *,
    threshold: float,
    existing_song_ids: list[int],
    existing_lyrics_simhash: list[int],
    load_existing_lyrics_by_ids: Callable[[list[int]], dict[int, str]],
    max_simhash_distance: int = 16,
    max_candidates: int = 120,
) -> bool:
    base = _normalize_for_compare(lyrics)
    if not base:
        return False
    base_sig = _simhash64_from_normalized(base)
    if not base_sig:
        return False

    cutoff = float(threshold)
    candidates: list[tuple[int, int]] = []
    for idx, sig in enumerate(existing_lyrics_simhash):
        if idx >= len(existing_song_ids):
            break
        dist = int((base_sig ^ int(sig)).bit_count())
        if dist <= int(max_simhash_distance):
            candidates.append((dist, int(existing_song_ids[idx])))
    if not candidates:
        return False

    candidates.sort(key=lambda x: x[0])
    if len(candidates) > int(max_candidates):
        candidates = candidates[: int(max_candidates)]

    ids = [song_id for _dist, song_id in candidates]
    lyrics_map = load_existing_lyrics_by_ids(ids)
    base_len = len(base)
    for song_id in ids:
        other = lyrics_map.get(int(song_id), "")
        if not other:
            continue
        other_n = _normalize_for_compare(other)
        if not other_n:
            continue
        other_len = len(other_n)
        if base_len and other_len:
            upper = (2.0 * float(min(base_len, other_len))) / float(base_len + other_len)
            if upper < cutoff:
                continue
        if SequenceMatcher(None, base, other_n).ratio() >= cutoff:
            return True
    return False


def _title_starter(title: str) -> str:
    t = normalize_title(title)
    if not t:
        return ""
    w = t.split(" ", 1)[0].strip()
    w = re.sub(r"[^\w]+", "", w)
    if w in {"youre"}:
        return "you"
    if w in {"im"}:
        return "i"
    return w


def _starter_used_recently(title: str, existing_titles: list[str], *, recent: int = 20) -> bool:
    starter = _title_starter(title)
    if not starter:
        return False
    recent_starters = [_title_starter(t) for t in existing_titles[: max(0, int(recent))]]
    return starter in {s for s in recent_starters if s}


def _max_title_similarity(
    title: str,
    existing_titles: list[str],
    *,
    early_exit_at: float = 0.95,
    existing_titles_norm: list[str] | None = None,
) -> float:
    base = normalize_title(title)
    if not base:
        return 0.0
    best = 0.0
    norms = existing_titles_norm
    if norms is None:
        norms = [normalize_title(t) for t in existing_titles]
    for o in norms:
        if not o:
            continue
        r = SequenceMatcher(None, base, o).ratio()
        if r > best:
            best = r
            if best >= float(early_exit_at):
                return best
    return best


def _title_prefix_taken(title: str, existing_titles: list[str], *, words: int = 2) -> bool:
    base = [w for w in normalize_title(title).split(" ") if w]
    if len(base) < words:
        return False
    prefix = " ".join(base[:words])
    for other in existing_titles:
        o = [w for w in normalize_title(other).split(" ") if w]
        if len(o) < words:
            continue
        if " ".join(o[:words]) == prefix:
            return True
    return False


def _normalize_for_compare(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _simhash64_from_normalized(s: str, *, max_tokens: int = 220) -> int:
    tokens = [t for t in s.split(" ") if t]
    if not tokens:
        return 0
    tokens = tokens[: max(1, int(max_tokens))]
    v = [0] * 64
    for tok in tokens:
        b = tok.encode("utf-8", errors="ignore")
        h1 = crc32(b, 0) & 0xFFFFFFFF
        h2 = crc32(b, 0x9E3779B9) & 0xFFFFFFFF
        h = (h1 << 32) | h2
        for i in range(64):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1
    out = 0
    for i, score in enumerate(v):
        if score >= 0:
            out |= 1 << i
    return out


def _max_lyric_similarity(
    lyrics: str,
    existing_lyrics: list[str],
    *,
    early_exit_at: float = 0.98,
    existing_lyrics_norm: list[str] | None = None,
) -> float:
    base = _normalize_for_compare(lyrics)
    if not base:
        return 0.0
    best = 0.0
    norms = existing_lyrics_norm
    if norms is None:
        norms = [_normalize_for_compare(x) for x in existing_lyrics]
    base_len = len(base)
    cutoff = float(early_exit_at)
    for other_n in norms:
        if not other_n:
            continue
        other_len = len(other_n)
        if base_len and other_len:
            upper = (2.0 * float(min(base_len, other_len))) / float(base_len + other_len)
            if upper <= best:
                continue
        r = SequenceMatcher(None, base, other_n).ratio()
        if r > best:
            best = r
            if best >= cutoff:
                return best
    return best


def _is_lyric_similarity_at_least(
    lyrics: str,
    existing_lyrics: list[str],
    *,
    threshold: float,
    existing_lyrics_norm: list[str] | None = None,
    existing_lyrics_simhash: list[int] | None = None,
    max_simhash_distance: int = 16,
) -> bool:
    base = _normalize_for_compare(lyrics)
    if not base:
        return False
    norms = existing_lyrics_norm
    if norms is None:
        norms = [_normalize_for_compare(x) for x in existing_lyrics]
    base_sig = _simhash64_from_normalized(base)
    sigs = existing_lyrics_simhash
    base_len = len(base)
    cutoff = float(threshold)
    for idx, other_n in enumerate(norms):
        if not other_n:
            continue
        if sigs is not None and base_sig and idx < len(sigs):
            dist = int((base_sig ^ int(sigs[idx])).bit_count())
            if dist > int(max_simhash_distance):
                continue
        other_len = len(other_n)
        if base_len and other_len:
            upper = (2.0 * float(min(base_len, other_len))) / float(base_len + other_len)
            if upper < cutoff:
                continue
        if SequenceMatcher(None, base, other_n).ratio() >= cutoff:
            return True
    return False


def _extract_opening(lyrics: str) -> str:
    lines = [ln.strip() for ln in _normalize_text(lyrics).split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""

    def is_header(ln: str) -> bool:
        t = re.sub(r"\s+", " ", ln.strip().lower())
        t = t.strip("[](){}").strip()
        t = re.sub(r"[:\-–—]+$", "", t).strip()
        return bool(
            re.fullmatch(r"(verse|chorus|bridge|intro|pre[- ]?chorus|hook)(\s*\d+)?", t)
        )

    out: list[str] = []
    for ln in lines:
        if not out and is_header(ln):
            continue
        out.append(ln)
        if len(out) >= 4:
            break
    return "\n".join(out).strip()


def _first_lyric_lines(lyrics: str, *, n: int = 4) -> list[str]:
    lines = [ln.strip() for ln in _normalize_text(lyrics).split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return []

    def is_header(ln: str) -> bool:
        t = re.sub(r"\s+", " ", ln.strip().lower())
        t = t.strip("[](){}").strip()
        t = re.sub(r"[:\-–—]+$", "", t).strip()
        return bool(re.fullmatch(r"(verse|chorus|bridge|intro|pre[- ]?chorus|hook)(\s*\d+)?", t))

    out: list[str] = []
    for ln in lines:
        if not out and is_header(ln):
            continue
        out.append(ln)
        if len(out) >= max(1, int(n)):
            break
    return out


def _opening_prefix(line: str, *, words: int = 4) -> str:
    t = _normalize_for_compare(line)
    parts = [p for p in t.split(" ") if p]
    if not parts:
        return ""
    return " ".join(parts[: max(1, int(words))]).strip()


def _build_overused_opening_prefixes(
    existing_lyrics: list[str],
    *,
    words: int = 4,
    min_count: int = 3,
    max_items: int = 10,
) -> list[str]:
    counts: dict[str, int] = {}
    for lyr in existing_lyrics[:500]:
        first = _first_lyric_lines(lyr, n=1)
        if not first:
            continue
        pref = _opening_prefix(first[0], words=words)
        if not pref:
            continue
        if len(pref) < 6:
            continue
        counts[pref] = counts.get(pref, 0) + 1
    items = [(k, v) for k, v in counts.items() if v >= int(min_count)]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _v in items[: max(0, int(max_items))]]

def _build_recent_opening_lines(
    existing_lyrics: list[str],
    *,
    limit: int = 50,
    max_chars: int = 140,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for lyr in existing_lyrics[: max(0, int(limit))]:
        first = _first_lyric_lines(lyr, n=1)
        if not first:
            continue
        line = re.sub(r"\s+", " ", first[0]).strip()
        if not line:
            continue
        line = line[: max(20, int(max_chars))].strip()
        key = _normalize_for_compare(line)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _max_opening_line_similarity(
    line: str,
    avoid_lines: list[str],
    *,
    early_exit_at: float = 0.99,
    avoid_lines_norm: list[str] | None = None,
) -> float:
    a = _normalize_for_compare(line)
    if not a:
        return 0.0
    best = 0.0
    norms = avoid_lines_norm
    if norms is None:
        norms = [_normalize_for_compare(b) for b in avoid_lines]
    cutoff = float(early_exit_at)
    for bn in norms:
        if not bn:
            continue
        r = SequenceMatcher(None, a, bn).ratio()
        if r > best:
            best = r
            if best >= cutoff:
                return best
    return float(best)


def _build_recent_opening_pairs(
    existing_lyrics: list[str],
    *,
    limit: int = 50,
    max_chars: int = 140,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for lyr in existing_lyrics[: max(0, int(limit))]:
        first2 = _first_lyric_lines(lyr, n=2)
        if len(first2) < 2:
            continue
        a = re.sub(r"\s+", " ", first2[0]).strip()
        b = re.sub(r"\s+", " ", first2[1]).strip()
        if not a or not b:
            continue
        a = a[: max(20, int(max_chars))].strip()
        b = b[: max(20, int(max_chars))].strip()
        key = _normalize_for_compare(a + "\n" + b)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((a, b))
    return out


def _max_opening_pair_similarity(
    lines2: tuple[str, str],
    avoid_pairs: list[tuple[str, str]],
    *,
    early_exit_at: float = 0.99,
    avoid_pairs_norm: list[str] | None = None,
) -> float:
    a = _normalize_for_compare(lines2[0] + "\n" + lines2[1])
    if not a:
        return 0.0
    best = 0.0
    norms = avoid_pairs_norm
    if norms is None:
        norms = [_normalize_for_compare(str(x) + "\n" + str(y)) for x, y in avoid_pairs]
    cutoff = float(early_exit_at)
    for b in norms:
        if not b:
            continue
        r = SequenceMatcher(None, a, b).ratio()
        if r > best:
            best = r
            if best >= cutoff:
                return best
    return float(best)


def _opening_lines_match(lyrics: str, forced: list[str]) -> bool:
    forced_clean = [ln.strip() for ln in forced if str(ln).strip()]
    if not forced_clean:
        return True
    opening = _extract_opening(lyrics)
    lines = [ln.strip() for ln in opening.split("\n") if ln.strip()]
    if len(lines) < len(forced_clean):
        return False
    for i, ln in enumerate(forced_clean):
        if lines[i] != ln.strip():
            return False
    return True


def _apply_forced_opening_lines(lyrics: str, forced: list[str]) -> str:
    forced_clean = [str(ln).strip() for ln in forced if str(ln).strip()]
    if not forced_clean:
        return lyrics

    raw_lines = _normalize_text(lyrics).split("\n")

    def is_header(ln: str) -> bool:
        t = re.sub(r"\s+", " ", ln.strip().lower())
        t = t.strip("[](){}").strip()
        t = re.sub(r"[:\-–—]+$", "", t).strip()
        return bool(re.fullmatch(r"(verse|chorus|bridge|intro|pre[- ]?chorus|hook)(\s*\d+)?", t))

    idxs: list[int] = []
    for i, ln in enumerate(raw_lines):
        if not ln.strip():
            continue
        if is_header(ln):
            if idxs:
                break
            continue
        idxs.append(i)
        if len(idxs) >= len(forced_clean):
            break

    if len(idxs) < len(forced_clean):
        insert_at = 0
        for i, ln in enumerate(raw_lines):
            if ln.strip() and is_header(ln):
                insert_at = i + 1
                continue
            if ln.strip():
                break
        for j, fl in enumerate(forced_clean):
            raw_lines.insert(insert_at + j, fl)
        return "\n".join(raw_lines).strip()

    for j, fl in enumerate(forced_clean):
        raw_lines[idxs[j]] = fl
    return "\n".join(raw_lines).strip()


def _max_opening_similarity(
    lyrics: str,
    existing_lyrics: list[str],
    *,
    early_exit_at: float = 0.95,
    existing_openings_norm: list[str] | None = None,
) -> float:
    opening = _normalize_for_compare(_extract_opening(lyrics))
    if not opening:
        return 0.0
    best = 0.0
    norms = existing_openings_norm
    if norms is None:
        norms = [_normalize_for_compare(_extract_opening(x)) for x in existing_lyrics]
    cutoff = float(early_exit_at)
    for other_open in norms:
        if not other_open:
            continue
        r = SequenceMatcher(None, opening, other_open).ratio()
        if r > best:
            best = r
            if best >= cutoff:
                return best
    return best


def _ai_reason(lyrics: str) -> str | None:
    t = _normalize_text(lyrics).lower()
    patterns = [
        r"\b(in this moment|here in this moment)\b",
        r"\b(we\s*'?ll\s*find\s*our\s*way|find our way back)\b",
        r"\b(stars?\s*(above|align|collide)|under the stars)\b",
        r"\b(neon\s+lights?)\b",
        r"\b(echo(es|ing)?\b)",
        r"\b(shadows?\b)",
        r"\b(dancing\s+in\s+the\s+moonlight)\b",
        r"\b(heart\s+of\s+gold)\b",
        r"\b(hold\s+me\s+close)\b",
        r"\b(lost\s+in\s+your\s+eyes)\b",
        r"\b(soul\s*(mate|ties?))\b",
        r"\b(time\s+stands\s+still)\b",
        r"\b(through\s+the\s+storms?)\b",
        r"\b(our\s+love\s+will\s+(never\s+die|last\s+forever))\b",
    ]
    hits = 0
    for p in patterns:
        if re.search(p, t):
            hits += 1
            if hits >= 3:
                return "Contains multiple common AI/cliché lyric phrases"
    return None


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Model did not return JSON")
    val = json.loads(m.group(0))
    if not isinstance(val, dict):
        raise ValueError("Model JSON is not an object")
    return val


def generate_song(
    client: DeepSeekClient,
    *,
    style: str,
    language: str,
    existing_titles: list[str],
    extra_instruction: str | None = None,
    temperature: float = 1.1,
    structure: str = "Verse 1\nChorus\nVerse 2\nChorus\nBridge\nFinal Chorus",
    forced_opening_lines: list[str] | None = None,
    title_hint: str | None = None,
    forced_title: str | None = None,
) -> Song:
    seed = str(uuid.uuid4())
    titles_block = "\n".join(f"- {t}" for t in existing_titles[:100])
    messages = [
        {
            "role": "system",
            "content": (
                "You write original songs that feel human-written and singable."
                " Prefer concrete images, natural phrasing, and emotional specificity over abstract poetry."
                " Vary line length and cadence, avoid repetitive clichés, and avoid AI-sounding filler."
                " Write like a real songwriter: specific scene, small details, and believable voice."
                " Never write generic motivational platitudes."
                " Output must be strictly a single JSON object with keys: title, lyrics."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Hidden randomness seed (do not print): {seed}\n\n"
                f"Write a NEW original song in {language}.\n"
                "Description:\n"
                f"{style.strip()}\n\n"
                "Rules:\n"
                "- Title must be unique and not reused.\n"
                "- Title must feel romantic and emotionally resonant (a love phrase), not weird or random.\n"
                "- Title should be 2–7 words, natural, and easy to sing.\n"
                "- Avoid titles that are mostly objects/places (e.g., 'Glitter in the Gutter').\n"
                "- Vary the first word of the title across songs (avoid repeating the same opener).\n"
                "- Avoid starting with 'I', 'You', or 'Your' unless explicitly requested.\n"
                "- Good title vibes: 'Hold Me After Midnight', 'Kiss Me in the Quiet', 'Between Us, Always'.\n"
                "- Avoid reusing title templates like 'Hold Me ...' or 'You're the ...' across songs.\n"
                f"{('Title MUST be exactly: ' + forced_title.strip() + chr(10)) if forced_title else ''}"
                f"{('Title hint (use as inspiration, but still unique): ' + title_hint.strip() + chr(10)) if title_hint else ''}"
                "- Lyrics must be unique and not reused.\n"
                "- Keep it human: conversational, not over-explained, not generic.\n"
                "- Include a clear hook in the Chorus that can be sung.\n"
                "- Use fresh imagery; avoid common lyrical clichés.\n"
                "- The opening lines must be clearly different from your other songs; do not reuse typical openings.\n"
                "- Start with a specific, grounded scene (time/place/action) in the first 2 lines.\n"
                "- Avoid these overused phrases and words: neon lights, echoes, shadows, stars align, time stands still, soulmate, lost in your eyes.\n"
                "- Avoid abstract filler like 'this feeling', 'this moment', 'our destiny', 'forever and always' unless made specific.\n"
                f"{('In Verse 1, the first two NON-HEADER lyric lines must be EXACTLY these (verbatim, same punctuation):' + chr(10) + chr(10).join(forced_opening_lines) + chr(10)) if forced_opening_lines else ''}"
                "- Use this song structure in this order (include section headers):\n"
                f"{structure.strip()}\n"
                "- No markdown, no code fences.\n"
                "- Return ONLY JSON.\n\n"
                f"{(extra_instruction.strip() + chr(10) + chr(10)) if extra_instruction else ''}"
                "Avoid these previous titles (do not reuse them):\n"
                f"{titles_block if titles_block else '- (none)'}\n"
            ),
        },
    ]
    raw = client.chat_completion(messages=messages, temperature=temperature)
    obj = _extract_json_object(raw)
    title = _normalize_text(str(obj.get("title", "")))
    lyrics = _normalize_text(str(obj.get("lyrics", "")))
    if not title or not lyrics:
        raise ValueError("Model returned empty title or lyrics")
    if forced_title:
        ft = _normalize_text(forced_title)
        if title != ft:
            raise ValueError("Model did not follow required title")
    return Song(title=title, lyrics=lyrics, content_hash=compute_song_hash(title, lyrics))


def generate_title(
    client: DeepSeekClient,
    *,
    style: str,
    language: str,
    existing_titles: list[str],
    extra_instruction: str | None = None,
    temperature: float = 1.0,
) -> str:
    seed = str(uuid.uuid4())
    titles_block = "\n".join(f"- {t}" for t in existing_titles[:100])
    messages = [
        {
            "role": "system",
            "content": (
                "You write romantic, emotionally resonant song titles that feel human-written."
                " Output must be strictly a single JSON object with key: title."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Hidden randomness seed (do not print): {seed}\n\n"
                f"Write a NEW romantic song title in {language}.\n"
                "Description:\n"
                f"{style.strip()}\n\n"
                "Rules:\n"
                "- Title must be unique and not reused.\n"
                "- Title must feel romantic and emotionally resonant (a love phrase), not weird or random.\n"
                "- Title should be 2–7 words, natural, and easy to sing.\n"
                "- Vary the first word of the title across songs (avoid repeating the same opener).\n"
                "- Avoid starting with 'I', 'You', or 'Your' unless explicitly requested.\n"
                "- Avoid reusing title templates like 'Hold Me ...' or 'You're the ...' across songs.\n"
                "- Return ONLY JSON.\n\n"
                f"{(extra_instruction.strip() + chr(10) + chr(10)) if extra_instruction else ''}"
                "Avoid these previous titles (do not reuse them):\n"
                f"{titles_block if titles_block else '- (none)'}\n"
            ),
        },
    ]
    raw = client.chat_completion(messages=messages, temperature=temperature, max_tokens=120)
    obj = _extract_json_object(raw)
    title = _normalize_text(str(obj.get("title", "")))
    if not title:
        raise ValueError("Model returned empty title")
    return title


def generate_unique_title(
    client: DeepSeekClient,
    *,
    style: str,
    language: str,
    existing_titles: list[str],
    is_title_taken: Callable[[str], bool],
    max_title_similarity: float = 0.78,
    max_attempts: int = 12,
    temperature: float = 1.0,
) -> str:
    last_rejection: str | None = None
    for _attempt in range(1, max_attempts + 1):
        title = generate_title(
            client,
            style=style,
            language=language,
            existing_titles=existing_titles,
            extra_instruction=last_rejection,
            temperature=temperature,
        )

        if existing_titles:
            if _starter_used_recently(title, existing_titles, recent=20):
                last_rejection = (
                    "The last attempt reused a common title opener."
                    " Pick a different first word than your recent titles."
                    " Avoid starting with I/You/Your unless explicitly requested."
                )
                continue
            title_sim = _max_title_similarity(title, existing_titles)
            if title_sim >= max_title_similarity or _title_prefix_taken(title, existing_titles, words=2):
                last_rejection = (
                    "The last attempt produced a title that is too similar to existing titles."
                    " Create a completely different romantic title with a different phrasing pattern."
                    " Avoid starting with the same first words as other titles."
                )
                continue

        if is_title_taken(normalize_title(title)):
            last_rejection = (
                "The last attempt reused an existing title from the database."
                " Create a completely new title and avoid similar phrasing."
            )
            continue

        return title
    raise RuntimeError(
        "Could not generate a unique title after multiple attempts"
        f" (last rejection: {last_rejection or 'unknown'})"
    )


def generate_album_name(
    client: DeepSeekClient,
    *,
    description: str,
    language: str,
    song_titles: list[str] | None = None,
    avoid_album_names: list[str] | None = None,
    temperature: float = 0.9,
) -> str:
    seed = str(uuid.uuid4())
    titles = [t.strip() for t in (song_titles or []) if str(t).strip()]
    avoid = [a.strip() for a in (avoid_album_names or []) if str(a).strip()]
    messages = [
        {
            "role": "system",
            "content": (
                "You create album names that feel human and marketable."
                " Output must be strictly a single JSON object with key: album_name."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Hidden randomness seed (do not print): {seed}\n\n"
                f"Create an album name in {language} that matches the vibe and themes.\n\n"
                "Context:\n"
                f"- Description: {_normalize_text(description)}\n"
                f"{('- Song titles from this batch:' + chr(10) + chr(10).join('- ' + t for t in titles) + chr(10)) if titles else ''}"
                f"{('- Avoid these album names (already used):' + chr(10) + chr(10).join('- ' + a for a in avoid[:25]) + chr(10)) if avoid else ''}"
                "\n"
                "Rules:\n"
                "- 2–6 words.\n"
                "- Easy to remember, not weird.\n"
                "- Reflect the batch themes; borrow imagery from the song titles.\n"
                "- Avoid starting with I/You/Your.\n"
                "- Avoid repeating words like 'Love', 'Heart', 'Forever' unless made specific.\n"
                "- Return ONLY JSON.\n"
            ),
        },
    ]
    raw = client.chat_completion(messages=messages, temperature=temperature, max_tokens=60)
    obj = _extract_json_object(raw)
    name = _normalize_text(str(obj.get("album_name", "")))
    if not name:
        raise ValueError("Model returned empty album name")
    return name


def polish_lyrics(
    client: DeepSeekClient,
    *,
    title: str,
    lyrics: str,
    language: str,
    structure: str,
    preserve_opening_lines: int = 2,
    strength: float = 0.8,
) -> str:
    title = _normalize_text(title)
    lyrics = _normalize_text(lyrics)
    if not title or not lyrics:
        raise ValueError("Missing title or lyrics to polish")

    opening = _extract_opening(lyrics)
    opening_lines = [ln for ln in opening.split("\n") if ln.strip()][:preserve_opening_lines]
    opening_block = "\n".join(opening_lines)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional lyric editor. Rewrite lyrics to sound more human-written and singable."
                " Keep meaning and emotional arc, but improve cadence, clarity, and phrasing."
                " Output must be strictly a single JSON object with key: lyrics."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Language: {language}\n"
                f"Title (keep unchanged): {title}\n\n"
                "Constraints:\n"
                "- Keep the same section headers and section order.\n"
                "- Keep the chorus hook clear and memorable.\n"
                "- Remove clichés and AI-sounding filler.\n"
                "- Keep a believable voice; use specific details.\n"
                f"- Keep the first {len(opening_lines)} opening line(s) EXACTLY as-is (verbatim):\n"
                f"{opening_block if opening_block else '(no opening detected)'}\n\n"
                "Target structure:\n"
                f"{structure.strip()}\n\n"
                "Original lyrics:\n"
                f"{lyrics}\n\n"
                f"Polish strength: {strength} (0.2 light edits, 1.2 stronger rewrite).\n"
                "Return ONLY JSON.\n"
            ),
        },
    ]

    raw = client.chat_completion(messages=messages, temperature=0.7, max_tokens=1200)
    obj = _extract_json_object(raw)
    out = _normalize_text(str(obj.get("lyrics", "")))
    if not out:
        raise ValueError("Model returned empty polished lyrics")
    if opening_lines:
        out_open = _extract_opening(out)
        out_lines = [ln for ln in out_open.split("\n") if ln.strip()][: len(opening_lines)]
        if [ln.strip() for ln in out_lines] != [ln.strip() for ln in opening_lines]:
            raise ValueError("Polish step changed the required opening lines")
    return out


def generate_unique_song(
    client: DeepSeekClient,
    *,
    style: str,
    language: str,
    existing_titles: list[str],
    is_hash_taken: Callable[[str], bool],
    is_title_taken: Callable[[str], bool] | None = None,
    existing_lyrics: list[str] | None = None,
    existing_titles_norm: list[str] | None = None,
    existing_lyrics_norm: list[str] | None = None,
    existing_openings_norm: list[str] | None = None,
    existing_lyrics_simhash: list[int] | None = None,
    existing_song_ids: list[int] | None = None,
    load_existing_lyrics_by_ids: Callable[[list[int]], dict[int, str]] | None = None,
    avoid_lyrics: list[str] | None = None,
    max_lyric_similarity: float = 0.92,
    max_opening_similarity: float = 0.65,
    max_title_similarity: float = 0.82,
    max_attempts: int = 10,
    temperature: float = 1.1,
    structure: str = "Verse 1\nChorus\nVerse 2\nChorus\nBridge\nFinal Chorus",
    forced_opening_lines: list[str] | None = None,
    title_hint: str | None = None,
    forced_title: str | None = None,
) -> Song:
    last_hash: str | None = None
    last_rejection: str | None = None
    avoid_prefixes: list[str] = []
    avoid_opening_lines: list[str] = []
    avoid_opening_pairs: list[tuple[str, str]] = []
    avoid_src = avoid_lyrics if avoid_lyrics is not None else existing_lyrics
    if avoid_src:
        avoid_prefixes = _build_overused_opening_prefixes(avoid_src, words=4, min_count=3, max_items=10)
        avoid_opening_lines = _build_recent_opening_lines(avoid_src, limit=50, max_chars=140)
        avoid_opening_pairs = _build_recent_opening_pairs(avoid_src, limit=50, max_chars=140)
    avoid_prefix_set = set(avoid_prefixes)

    existing_titles_norm_local = existing_titles_norm
    if existing_titles_norm_local is None and existing_titles:
        existing_titles_norm_local = [normalize_title(t) for t in existing_titles]

    existing_lyrics_norm_local = existing_lyrics_norm
    existing_openings_norm_local = existing_openings_norm
    existing_lyrics_simhash_local = existing_lyrics_simhash
    if existing_lyrics:
        if existing_lyrics_norm_local is None:
            existing_lyrics_norm_local = [_normalize_for_compare(x) for x in existing_lyrics]
        if existing_openings_norm_local is None:
            existing_openings_norm_local = [
                _normalize_for_compare(_extract_opening(x)) for x in existing_lyrics
            ]
        if existing_lyrics_simhash_local is None and existing_lyrics_norm_local is not None:
            existing_lyrics_simhash_local = [
                _simhash64_from_normalized(x) for x in existing_lyrics_norm_local
            ]

    avoid_opening_lines_norm: list[str] | None = None
    if avoid_opening_lines:
        avoid_opening_lines_norm = [_normalize_for_compare(x) for x in avoid_opening_lines]

    avoid_opening_pairs_norm: list[str] | None = None
    if avoid_opening_pairs:
        avoid_opening_pairs_norm = [_normalize_for_compare(a + "\n" + b) for a, b in avoid_opening_pairs]
    avoid_instruction = ""
    if avoid_prefixes:
        avoid_instruction = (
            "Avoid starting Verse 1 with any of these overused opening patterns (do not reuse even with minor punctuation changes):\n"
            + "\n".join(f"- {p}" for p in avoid_prefixes)
        )
    avoid_opening_instruction = ""
    if avoid_opening_lines:
        avoid_opening_instruction = (
            "Avoid starting with any of these recent opening lines from your own songs (do not reuse or lightly paraphrase):\n"
            + "\n".join(f"- {ln}" for ln in avoid_opening_lines)
        )
    avoid_opening_pairs_instruction = ""
    if avoid_opening_pairs:
        avoid_opening_pairs_instruction = (
            "Avoid starting with any of these recent TWO-LINE openings from your own songs (do not reuse or lightly paraphrase either line):\n"
            + "\n".join(f"- {a} / {b}" for a, b in avoid_opening_pairs)
        )
    for attempt in range(1, max_attempts + 1):
        extra = last_rejection
        if avoid_instruction:
            extra = (extra + "\n\n" + avoid_instruction) if extra else avoid_instruction
        if avoid_opening_instruction:
            extra = (extra + "\n\n" + avoid_opening_instruction) if extra else avoid_opening_instruction
        if avoid_opening_pairs_instruction:
            extra = (extra + "\n\n" + avoid_opening_pairs_instruction) if extra else avoid_opening_pairs_instruction
        song = generate_song(
            client,
            style=style,
            language=language,
            existing_titles=existing_titles,
            extra_instruction=extra,
            temperature=temperature,
            structure=structure,
            forced_opening_lines=forced_opening_lines,
            title_hint=title_hint,
            forced_title=forced_title,
        )
        if forced_opening_lines and not _opening_lines_match(song.lyrics, forced_opening_lines):
            patched = _apply_forced_opening_lines(song.lyrics, forced_opening_lines)
            song = Song(title=song.title, lyrics=patched, content_hash=compute_song_hash(song.title, patched))
        opening_lines = _first_lyric_lines(song.lyrics, n=2)
        if avoid_opening_pairs and len(opening_lines) >= 2:
            sim2 = _max_opening_pair_similarity(
                (opening_lines[0], opening_lines[1]),
                avoid_opening_pairs,
                early_exit_at=0.88,
                avoid_pairs_norm=avoid_opening_pairs_norm,
            )
            if sim2 >= 0.88:
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt started too similarly to one of your recent TWO-LINE openings."
                    " Start with a different scene, action, and phrasing in the first two lines."
                )
                continue
        if avoid_opening_lines and opening_lines:
            sim = _max_opening_line_similarity(
                opening_lines[0],
                avoid_opening_lines,
                early_exit_at=0.88,
                avoid_lines_norm=avoid_opening_lines_norm,
            )
            if sim >= 0.88:
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt started too similarly to one of your recent song openings."
                    " Start with a different scene, action, and phrasing."
                )
                continue
        if avoid_prefixes and opening_lines:
            pref = _opening_prefix(opening_lines[0], words=4)
            if pref and pref in avoid_prefix_set:
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt started with an opening pattern you've used too often."
                    " Rewrite the first lines with a different scene, action, and phrasing."
                )
                continue
        if existing_titles:
            if forced_title is None and _starter_used_recently(song.title, existing_titles, recent=20):
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt reused a common title opener."
                    " Choose a different first word than your recent titles."
                    " Avoid starting with I/You/Your unless explicitly requested."
                )
                continue
            title_sim = _max_title_similarity(
                song.title,
                existing_titles,
                early_exit_at=float(max_title_similarity),
                existing_titles_norm=existing_titles_norm_local,
            )
            if title_sim >= max_title_similarity or _title_prefix_taken(song.title, existing_titles, words=2):
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt produced a title that is too similar to existing titles."
                    " Create a completely different romantic title with a different phrasing pattern."
                    " Avoid starting with the same first words as your other titles."
                )
                continue
        if is_title_taken:
            if is_title_taken(normalize_title(song.title)):
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt reused an existing title from the database."
                    " Create a completely new title and make the song clearly different in theme and imagery."
                )
                continue
        has_opening_history = bool(existing_openings_norm_local)
        has_lyrics_history = bool(existing_lyrics)
        has_sig_history = bool(existing_lyrics_simhash_local)
        if has_opening_history or has_lyrics_history or has_sig_history:
            opening_sim = _max_opening_similarity(
                song.lyrics,
                existing_lyrics or [],
                early_exit_at=float(max_opening_similarity),
                existing_openings_norm=existing_openings_norm_local,
            )
            if opening_sim >= max_opening_similarity:
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt started too similarly to an existing song."
                    " Rewrite the first 2–4 lines to be totally different in wording, imagery, and situation."
                    " Do not reuse common openings."
                )
                continue
            reason = _ai_reason(song.lyrics)
            if reason:
                last_hash = song.content_hash
                last_rejection = (
                    "The last attempt sounded generic/AI-like."
                    " Rewrite using a specific real-world scene, fewer clichés, and more natural phrasing."
                    " Avoid stock phrases like 'neon lights', 'echoes', 'shadows', 'stars align', 'time stands still'."
                )
                continue
            if (
                existing_song_ids
                and existing_lyrics_simhash_local
                and load_existing_lyrics_by_ids is not None
            ):
                if is_lyric_similarity_at_least_with_loader(
                    song.lyrics,
                    threshold=float(max_lyric_similarity),
                    existing_song_ids=existing_song_ids,
                    existing_lyrics_simhash=existing_lyrics_simhash_local,
                    load_existing_lyrics_by_ids=load_existing_lyrics_by_ids,
                ):
                    last_hash = song.content_hash
                    last_rejection = (
                        "The last attempt was too similar to an existing song's lyrics."
                        " Write a new song with different scenes, phrasing, hook, and progression."
                    )
                    continue
            elif existing_lyrics:
                if _is_lyric_similarity_at_least(
                    song.lyrics,
                    existing_lyrics,
                    threshold=float(max_lyric_similarity),
                    existing_lyrics_norm=existing_lyrics_norm_local,
                    existing_lyrics_simhash=existing_lyrics_simhash_local,
                ):
                    last_hash = song.content_hash
                    last_rejection = (
                        "The last attempt was too similar to an existing song's lyrics."
                        " Write a new song with different scenes, phrasing, hook, and progression."
                    )
                    continue
        if not is_hash_taken(song.content_hash):
            return song
        last_hash = song.content_hash
        last_rejection = (
            "The last attempt matched an existing song in the database."
            " Make the new song clearly different in title, theme, imagery, and structure."
        )
    raise RuntimeError(
        "Could not generate a unique song after multiple attempts"
        f" (last rejection: {last_rejection or 'unknown'})"
    )

