from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from ..utils.music_common import normalize_text, opening2_lines

if TYPE_CHECKING:
    from python_app.services.generation_proxy import GenerationProxy


def _extract_json(text: str) -> dict | None:
    raw = str(text or "")
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_text_format_draft(text: str) -> dict | None:
    """Fallback parser for LLM responses in text format instead of JSON.
    
    Handles patterns like:
        Title: Some Title
        Album: Some Album
        [Verse 1]
        Lyrics line 1...
    """
    import re
    raw = str(text or "")
    title_match = re.search(r"(?:^|\n)\s*(?:Title|Song\s*Title)\s*[:：]\s*(.+)", raw, re.IGNORECASE)
    album_match = re.search(r"(?:^|\n)\s*(?:Album|Album\s*Name)\s*[:：]\s*(.+)", raw, re.IGNORECASE)
    if not title_match or not album_match:
        return None
    title = str(title_match.group(1)).strip().strip('"').strip("'").strip()
    album = str(album_match.group(1)).strip().strip('"').strip("'").strip()
    if not title or not album:
        return None
    # Extract lyrics: everything after the album line, or from first [section header]
    lyrics = ""
    bracket_match = re.search(r"(\[.+?\])", raw)
    if bracket_match:
        lyrics = raw[bracket_match.start():].strip()
    else:
        # Take everything after the album line
        album_end = album_match.end()
        lyrics = raw[album_end:].strip()
    if not lyrics:
        return None
    return {"title": title, "album": album, "lyrics": lyrics}


def opening2(lyrics: str) -> str:
    return opening2_lines(lyrics)

def inject_opening(lyrics: str, opening: str) -> str:
    return _inject_opening(lyrics, opening)


def _lyric_stats(lyrics: str) -> dict[str, int]:
    def is_header(line: str) -> bool:
        s = str(line or "").strip()
        return bool(s.startswith("[") and s.endswith("]"))

    lines = [line.strip() for line in str(lyrics or "").splitlines()]
    content_lines = [line for line in lines if line and not is_header(line)]
    headers = [line for line in lines if line and is_header(line)]
    header_text = [line.lower() for line in headers]
    return {
        "contentLineCount": len(content_lines),
        "headerCount": len(headers),
        "verseCount": len([x for x in header_text if "verse" in x]),
        "chorusCount": len([x for x in header_text if "chorus" in x]),
        "bridgeCount": len([x for x in header_text if "bridge" in x]),
    }


def _inject_opening(lyrics: str, opening: str) -> str:
    wanted = [line.strip() for line in str(opening or "").splitlines() if line.strip()][:2]
    if len(wanted) < 2:
        return str(lyrics or "")

    def is_header(line: str) -> bool:
        s = str(line or "").strip()
        return bool(s.startswith("[") and s.endswith("]"))

    lines = str(lyrics or "").splitlines()
    out: list[str] = []
    replaced = 0
    for line in lines:
        if replaced < 2 and line.strip() and not is_header(line):
            out.append(wanted[replaced] if replaced < len(wanted) else line)
            replaced += 1
        else:
            out.append(line)
    if replaced < 2:
        return f"{wanted[0]}\n{wanted[1]}\n\n{str(lyrics or '').strip()}".strip()
    return "\n".join(out)


def _parse_structure_headers(structure: str) -> list[str]:
    return [
        line.strip()
        for line in str(structure or "").splitlines()
        if line.strip().startswith("[") and line.strip().endswith("]")
    ]


def _extract_headers_in_lyrics(lyrics: str) -> list[str]:
    return [
        line.strip()
        for line in str(lyrics or "").splitlines()
        if line.strip().startswith("[") and line.strip().endswith("]")
    ]


def _has_content_before_first_header(lyrics: str) -> bool:
    for line in [x.strip() for x in str(lyrics or "").splitlines()]:
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            return False
        return True
    return False


def _chat_completion(
    *,
    api_url: str,
    api_key: str,
    model: str,
    temperature: float,
    messages: list[dict[str, str]],
    timeout_sec: int = 90,
    on_log: Any = None,
    log_label: str = "",
    force_json: bool = False,
    max_tokens: int | None = None,
) -> str:
    if callable(on_log):
        safe_label = str(log_label or "").strip()
        on_log(f"{safe_label}HTTP start: model={model} timeout={int(timeout_sec)}s url={api_url}")
    started = time.monotonic()
    body = ""
    req_body = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "stream": False,
    }
    if isinstance(max_tokens, int) and max_tokens > 0:
        req_body["max_tokens"] = int(max_tokens)
    if bool(force_json):
        req_body["response_format"] = {"type": "json_object"}

    def _send(payload: dict) -> str:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            return response.read().decode("utf-8", errors="replace")

    try:
        body = _send(req_body)
    except urllib.error.HTTPError as exc:
        preview = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        if bool(force_json) and int(getattr(exc, "code", 0) or 0) == 400 and "response_format" in preview:
            req_body.pop("response_format", None)
            try:
                body = _send(req_body)
            except Exception as exc2:
                if callable(on_log):
                    elapsed = time.monotonic() - started
                    safe_label = str(log_label or "").strip()
                    on_log(f"{safe_label}HTTP exception: elapsed={elapsed:.2f}s error={exc2}")
                raise RuntimeError(str(exc2)) from exc2
        else:
            if callable(on_log):
                elapsed = time.monotonic() - started
                safe_label = str(log_label or "").strip()
                on_log(f"{safe_label}HTTP error: status={exc.code} elapsed={elapsed:.2f}s preview={preview[:160]}")
            raise RuntimeError(f"API error {exc.code}: {preview[:400]}") from exc
    except Exception as exc:
        if callable(on_log):
            elapsed = time.monotonic() - started
            safe_label = str(log_label or "").strip()
            on_log(f"{safe_label}HTTP exception: elapsed={elapsed:.2f}s error={exc}")
        raise RuntimeError(str(exc)) from exc
    if callable(on_log):
        elapsed = time.monotonic() - started
        safe_label = str(log_label or "").strip()
        on_log(f"{safe_label}HTTP ok: elapsed={elapsed:.2f}s bytes={len(body)}")

    try:
        parsed = json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"Invalid API JSON response: {body[:240]}") from exc

    content = (
        parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(parsed, dict)
        else ""
    )
    if not content:
        raise RuntimeError("API returned empty content")
    return str(content).strip()

def _generate_title_album_generic(
    *,
    api_url: str,
    api_key: str,
    model: str,
    provider_label: str,
    language: str,
    creativity: int,
    description: str,
    structure: str,
    seed_title: str,
    seed_album: str,
    forced_album: str = "",
    avoid_titles: list[str] | None = None,
    avoid_albums: list[str] | None = None,
    strict_level: int = 3,
    timeout_sec: int = 30,
    max_attempts: int = 6,
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict[str, str]:
    titles = [str(x).strip() for x in (avoid_titles or []) if str(x).strip()][:200]
    albums = [str(x).strip() for x in (avoid_albums or []) if str(x).strip()][:200]
    avoid_title_set = {normalize_text(x) for x in titles if normalize_text(x)}
    avoid_album_set = {normalize_text(x) for x in albums if normalize_text(x)}
    forced_album_value = str(forced_album or "").strip()
    forced_album_norm = normalize_text(forced_album_value) if forced_album_value else ""
    strict = int(strict_level or 3)
    attempts_total = max(1, min(20, int(max_attempts or 6)))
    base_temp = min(1.2, max(0.2, float(creativity) / 85.0))
    temperature = min(0.8, base_temp) if str(provider_label).upper() == "SLAI" else base_temp
    reject_log: list[str] = []
    # Extract overused words from recent titles to explicitly forbid repeating them
    import re as _re
    _stop_words = {"the", "a", "an", "of", "in", "on", "to", "and", "or", "for", "is", "it", "my", "by", "at", "no", "so", "up", "if"}
    _word_freq: dict[str, int] = {}
    for _t in titles[-30:]:
        for _w in _re.findall(r"[a-z]+", _t.lower()):
            if _w not in _stop_words and len(_w) > 2:
                _word_freq[_w] = _word_freq.get(_w, 0) + 1
    _overused = sorted([w for w, c in _word_freq.items() if c >= 3], key=lambda w: -_word_freq[w])[:12]
    overused_words_line = f"- Heavily avoid these overused words in titles: {', '.join(_overused)}" if _overused else ""
    for attempt in range(1, attempts_total + 1):
        if callable(should_cancel) and bool(should_cancel()):
            raise InterruptedError("Cancelled")
        try:
            raw = _chat_completion(
                api_url=api_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                timeout_sec=int(timeout_sec),
                log_label=f"{provider_label} title/album: ",
                force_json=True,
                messages=[
                    {
                        "role": "system",
                        "content": "Output MUST be strict JSON with keys: title, album. No markdown, no extra text. You are a creative music naming expert who avoids all repetition. Each title and album must feel completely different from previous ones — use varied vocabulary, imagery, and structure.",
                    },
                    {
                        "role": "user",
                        "content": "\n".join(
                            [
                                f"Attempt: {attempt}/{attempts_total}",
                                f"Language: {language}",
                                "Task: Create a NEW unique song title and album name." if not forced_album_value else "Task: Create a NEW unique song title for the provided album name.",
                                "Constraints:",
                                "- Title max 80 chars",
                                "- Album max 80 chars" if not forced_album_value else f"- Album must be exactly: {forced_album_value}",
                                "- Do not repeat existing titles or albums (avoid exact repeats AND similar word patterns)." if not forced_album_value else "- Do not repeat existing titles (avoid exact repeats AND similar word patterns).",
                                "- Use DIFFERENT vocabulary, metaphors, and word patterns from the forbidden list below.",
                                "- Do NOT reuse prominent nouns or adjectives from recent titles.",
                                overused_words_line,
                                "",
                                f"Seed title inspiration (use as loose thematic guide only, do NOT copy words): {seed_title}",
                                f"Seed album inspiration (use as loose thematic guide only, do NOT copy words): {seed_album}" if not forced_album_value else f"Album (fixed): {forced_album_value}",
                                "",
                                "Context:",
                                f"- Theme/Description: {description}",
                                f"- Structure: {structure}",
                                "",
                                "Forbidden titles (avoid exact repeats AND similar word patterns):",
                                "\n".join(["- " + x for x in titles[:60]]) if titles else "- (none)",
                                "",
                                "Forbidden album names (avoid exact repeats):" if not forced_album_value else "Forbidden album names (ignore; album is fixed):",
                                "\n".join(["- " + x for x in albums[:60]]) if albums else "- (none)",
                            ]
                        ),
                    },
                ],
            )
        except Exception as exc:
            reason = str(exc).strip()
            reject_log.append(f"#{attempt} api_error: {reason[:160]}")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} title/album attempt {attempt}/{attempts_total}: rejected (api_error) — {reason[:200]}")
            continue
        parsed = _extract_json(raw)
        if not parsed:
            reject_log.append(f"#{attempt} bad_json")
            reject_log[:] = reject_log[-24:]
            continue
        title = str(parsed.get("title") or parsed.get("songTitle") or parsed.get("name") or "").strip()
        album = str(parsed.get("album") or parsed.get("albumName") or parsed.get("collection") or "").strip()
        if not title or not album:
            reject_log.append(f"#{attempt} missing_keys")
            reject_log[:] = reject_log[-24:]
            continue
        if forced_album_norm and normalize_text(album) != forced_album_norm:
            reject_log.append(f"#{attempt} album_mismatch")
            reject_log[:] = reject_log[-24:]
            continue
        if forced_album_value:
            album = forced_album_value
        if len(title) > 80 or len(album) > 80:
            reject_log.append(f"#{attempt} too_long")
            reject_log[:] = reject_log[-24:]
            continue
        if strict >= 2 and normalize_text(title) in avoid_title_set:
            reject_log.append(f"#{attempt} duplicate_title")
            reject_log[:] = reject_log[-24:]
            continue
        if strict >= 3 and (not forced_album_norm) and normalize_text(album) in avoid_album_set:
            reject_log.append(f"#{attempt} duplicate_album")
            reject_log[:] = reject_log[-24:]
            continue
        # Reject titles that share too many significant words with recent titles
        if strict >= 2 and _overused:
            title_words = set(_re.findall(r"[a-z]+", title.lower())) - _stop_words
            overused_overlap = title_words & set(_overused[:6])
            if len(overused_overlap) >= 2:
                reject_log.append(f"#{attempt} word_overlap({','.join(overused_overlap)})")
                reject_log[:] = reject_log[-24:]
                continue
        return {"title": title, "album": album}
    tail = " | ".join(reject_log[-8:])
    raise RuntimeError(f"{provider_label} title/album rejected after {attempts_total} tries. Recent reasons: {tail or '(no details)'}")


def generate_title_album_with_deepseek(
    *,
    api_key: str,
    language: str,
    creativity: int,
    description: str,
    structure: str,
    seed_title: str,
    seed_album: str,
    forced_album: str = "",
    model: str = "deepseek-chat",
    avoid_titles: list[str] | None = None,
    avoid_albums: list[str] | None = None,
    strict_level: int = 3,
    timeout_sec: int = 30,
    max_attempts: int = 6,
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict[str, str]:
    return _generate_title_album_generic(
        api_url="https://api.deepseek.com/v1/chat/completions",
        api_key=api_key,
        model=model or "deepseek-chat",
        provider_label="DeepSeek",
        language=language,
        creativity=creativity,
        description=description,
        structure=structure,
        seed_title=seed_title,
        seed_album=seed_album,
        forced_album=forced_album,
        avoid_titles=avoid_titles,
        avoid_albums=avoid_albums,
        strict_level=strict_level,
        timeout_sec=timeout_sec,
        max_attempts=max_attempts,
        should_cancel=should_cancel,
        on_log=on_log,
    )


def generate_title_album_with_slai(
    *,
    api_key: str,
    language: str,
    creativity: int,
    description: str,
    structure: str,
    seed_title: str,
    seed_album: str,
    forced_album: str = "",
    model: str = "gpt-5.5",
    avoid_titles: list[str] | None = None,
    avoid_albums: list[str] | None = None,
    strict_level: int = 3,
    timeout_sec: int = 30,
    max_attempts: int = 6,
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict[str, str]:
    return _generate_title_album_generic(
        api_url="https://api.slai.shop/v1/chat/completions",
        api_key=api_key,
        model=model or "gpt-5.5",
        provider_label="SLAI",
        language=language,
        creativity=creativity,
        description=description,
        structure=structure,
        seed_title=seed_title,
        seed_album=seed_album,
        forced_album=forced_album,
        avoid_titles=avoid_titles,
        avoid_albums=avoid_albums,
        strict_level=strict_level,
        timeout_sec=timeout_sec,
        max_attempts=max_attempts,
        should_cancel=should_cancel,
        on_log=on_log,
    )


def _generate_song_draft_generic(
    *,
    api_url: str,
    api_key: str,
    model: str,
    provider_label: str,
    language: str,
    creativity: int,
    description: str,
    structure: str,
    unique_opening: bool = False,
    strict_level: int = 3,
    avoid_titles: list[str] | None = None,
    avoid_albums: list[str] | None = None,
    avoid_openings: list[str] | None = None,
    forced_title: str = "",
    forced_album: str = "",
    forced_opening: str = "",
    timeout_sec: int = 30,
    max_attempts: int = 8,
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict[str, str]:
    is_slai = str(provider_label).upper() == "SLAI"
    avoid_limit = 40 if is_slai else 120
    titles = [str(x).strip() for x in (avoid_titles or []) if str(x).strip()][:avoid_limit]
    albums = [str(x).strip() for x in (avoid_albums or []) if str(x).strip()][:avoid_limit]
    openings = [str(x).strip() for x in (avoid_openings or []) if str(x).strip()][:avoid_limit]
    strict = int(strict_level or 3)
    unique = bool(unique_opening)

    avoid_title_set = {normalize_text(x) for x in titles if normalize_text(x)}
    avoid_album_set = {normalize_text(x) for x in albums if normalize_text(x)}
    avoid_opening_set = {normalize_text(x) for x in openings if normalize_text(x)}
    expected_headers = _parse_structure_headers(structure or "")
    min_content_lines = max(16, len(expected_headers) * 4) if expected_headers else 32

    avoid_block: list[str] = []
    if strict >= 2 and titles:
        avoid_block.append("Forbidden titles (avoid exact repeats):\n- " + "\n- ".join(titles))
    if strict >= 3 and albums:
        avoid_block.append("Forbidden album names (avoid exact repeats):\n- " + "\n- ".join(albums))
    if (strict >= 1 or unique) and openings:
        avoid_block.append("Forbidden lyric openings (first two lines; avoid exact repeats):\n- " + "\n- ".join(openings))

    reject_log: list[str] = []
    attempts_total = max(1, int(max_attempts or 8))
    for attempt in range(1, attempts_total + 1):
        if callable(should_cancel) and bool(should_cancel()):
            raise InterruptedError("Cancelled")
        if callable(on_log):
            on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: start")
        fixed: list[str] = []
        if forced_title:
            fixed.append(f"- Use EXACT title: {forced_title}")
        if forced_album:
            fixed.append(f"- Use EXACT album name: {forced_album}")
        if forced_opening:
            fixed.append(f"- The first two non-empty lyric lines must be EXACTLY:\n{forced_opening}")

        try:
            base_temp = min(1.2, max(0.2, float(creativity) / 85.0))
            temperature = min(0.8, base_temp) if str(provider_label).upper() == "SLAI" else base_temp
            raw = _chat_completion(
                api_url=api_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": "You generate music metadata and lyrics. Output MUST be strict JSON with keys: title, album, lyrics. No markdown, no extra text.",
                    },
                    {
                        "role": "user",
                        "content": "\n".join(
                            [
                                f"Attempt: {attempt}/{attempts_total}",
                                f"Language: {language}",
                                f"Creativity: {int(creativity)}/100",
                                "Song description:",
                                description or "(empty)",
                                "Song structure:",
                                structure or "(empty)",
                                "Avoid list:" if avoid_block else "",
                                "\n\n".join(avoid_block) if avoid_block else "",
                                "Fixed values:" if fixed else "",
                                "\n".join(fixed) if fixed else "",
                                "Constraints:",
                                (
                                    "\n".join(
                                        [
                                            "- Use EXACT section headers and EXACT order from Song structure (one header per line)",
                                            *[f"  {header}" for header in expected_headers],
                                            "- Do NOT add Intro/Outro unless Song structure includes them",
                                            "- Do NOT add any extra section headers that are not in Song structure",
                                            "- Do NOT write any lyrics before the first header",
                                        ]
                                    )
                                    if expected_headers
                                    else "- Lyrics must include section labels like [Verse], [Chorus], [Bridge]"
                                ),
                                "- Write a FULL song, not a sketch",
                                "- Each section should have 4-8 lyric lines (excluding section labels)",
                                f"- Total non-empty lyric lines (excluding section labels) must be at least {min_content_lines}",
                                "- Title should be short and catchy",
                                "- Album name should be plausible",
                                "- Do NOT output any forbidden exact titles/albums/openings",
                                "- The first two non-empty lyric lines must be distinctive",
                            ]
                        ).strip(),
                    },
                ],
                timeout_sec=max(10, min(120, int(timeout_sec or 30))),
                on_log=on_log,
                log_label=f"{provider_label} ",
                force_json=True,
                max_tokens=(1400 if is_slai else None),
            )
        except Exception as exc:
            reason = str(exc).strip()
            label = "api_error" if "API error" in reason or "timed out" in reason.lower() else "exception"
            reject_log.append(f"#{attempt} {label}: {reason[:160]}")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected ({label})")
            continue

        if callable(on_log):
            on_log(f"{provider_label} raw preview: {str(raw).replace(chr(10), ' ')[:180]}")
        parsed = _extract_json(raw)
        if not parsed:
            # Fallback: try to parse text format like "Title: X\nAlbum: Y\n[Verse 1]..."
            parsed = _extract_text_format_draft(raw)
        if not parsed:
            reject_log.append(f"#{attempt} bad_json_or_missing_keys")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (bad_json_or_missing_keys)")
            continue

        title = forced_title or str(parsed.get("title") or parsed.get("songTitle") or parsed.get("name") or "").strip()
        album = forced_album or str(parsed.get("album") or parsed.get("albumName") or parsed.get("collection") or "").strip()
        lyrics_src = str(parsed.get("lyrics") or parsed.get("lyric") or parsed.get("lyricsRaw") or parsed.get("text") or "").strip()
        if not title or not album or not lyrics_src:
            reject_log.append(f"#{attempt} bad_json_or_missing_keys")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} parsed keys: {', '.join(list(parsed.keys())[:12])}")
                on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (bad_json_or_missing_keys)")
            continue

        lyrics = _inject_opening(lyrics_src, forced_opening) if forced_opening else lyrics_src
        stats = _lyric_stats(lyrics)
        if stats["contentLineCount"] < min_content_lines:
            reject_log.append(f"#{attempt} too_short: contentLines={stats['contentLineCount']} min={min_content_lines}")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (too_short)")
            continue

        if expected_headers:
            if _has_content_before_first_header(lyrics):
                reject_log.append(f"#{attempt} content_before_first_header")
                reject_log[:] = reject_log[-24:]
                if callable(on_log):
                    on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (content_before_first_header)")
                continue
            got_headers = _extract_headers_in_lyrics(lyrics)
            if len(got_headers) != len(expected_headers):
                reject_log.append(f"#{attempt} header_count_mismatch: got={len(got_headers)} expected={len(expected_headers)}")
                reject_log[:] = reject_log[-24:]
                if callable(on_log):
                    on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (header_count_mismatch)")
                continue
            mismatch = next((i for i, value in enumerate(got_headers) if value.strip() != expected_headers[i].strip()), -1)
            if mismatch >= 0:
                reject_log.append(f"#{attempt} header_mismatch_at={mismatch}")
                reject_log[:] = reject_log[-24:]
                if callable(on_log):
                    on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (header_mismatch)")
                continue

        violates_opening = (strict >= 1 or unique) and normalize_text(opening2(lyrics)) in avoid_opening_set
        violates_title = strict >= 2 and normalize_text(title) in avoid_title_set
        violates_album = strict >= 3 and normalize_text(album) in avoid_album_set
        if violates_opening or violates_title or violates_album:
            parts: list[str] = []
            if violates_title:
                parts.append("duplicate_title")
            if violates_album:
                parts.append("duplicate_album")
            if violates_opening:
                parts.append("duplicate_opening")
            reject_log.append(f"#{attempt} avoid_list_violation: {', '.join(parts)}")
            reject_log[:] = reject_log[-24:]
            if callable(on_log):
                on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: rejected (avoid_list_violation)")
            continue

        if callable(on_log):
            on_log(f"{provider_label} draft attempt {attempt}/{attempts_total}: accepted")
        return {
            "title": title,
            "album": album,
            "lyricsRaw": str(lyrics).strip(),
        }

    tail = " | ".join(reject_log[-8:])
    raise RuntimeError(f"{provider_label} draft rejected after {attempts_total} tries. Recent reasons: {tail or '(no details)'}")


def generate_song_draft(
    *,
    generation_proxy: GenerationProxy,
    language: str,
    creativity: int,
    description: str,
    structure: str,
    avoid_titles: list[str] | None = None,
    avoid_albums: list[str] | None = None,
    avoid_openings: list[str] | None = None,
    forced_title: str = "",
    forced_album: str = "",
    forced_opening: str = "",
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict[str, str]:
    """Unified draft generation via Platform API.

    Delegates to GenerationProxy.generate_song_draft() which handles
    authentication, token refresh, and error translation.

    Returns: {"title": ..., "album": ..., "lyrics": ...}
    """
    return generation_proxy.generate_song_draft(
        language=language,
        creativity_level=creativity,
        description=description,
        structure=structure,
        avoid_titles=avoid_titles,
        avoid_albums=avoid_albums,
        avoid_openings=avoid_openings,
        forced_title=forced_title,
        forced_album=forced_album,
        forced_opening=forced_opening,
        on_log=on_log,
        should_cancel=should_cancel,
    )


def polish_lyrics_with_openai(*, api_key: str, lyrics: str, strength: int, model: str = "gpt-4o-mini") -> str:
    temperature = 0.15 + (max(0, min(100, int(strength))) / 100.0) * 0.55
    content = _chat_completion(
        api_url="https://api.openai.com/v1/chat/completions",
        api_key=api_key,
        model=model or "gpt-4o-mini",
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "Polish song lyrics: improve flow, rhythm, and clarity while preserving meaning. Keep section labels like [Verse], [Chorus] and keep line breaks. Return ONLY the polished lyrics text.",
            },
            {"role": "user", "content": str(lyrics or "")},
        ],
    )
    return str(content).strip()
