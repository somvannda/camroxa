"""Suno lyrics risk detection — keep in sync with platform_api/services/suno_lyrics_sanitize.py."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

_DEFAULT_REPLACEMENTS: dict[str, str] = {
    "lowlight": "afterglow",
}


@dataclass(frozen=True)
class SunoPlatformBlocklist:
    replacements: dict[str, str]
    block_terms: frozenset[str]
    warn_terms: frozenset[str]

_BLOCKED_TERM_STOPWORDS = frozenset(
    {
        "again",
        "our",
        "the",
        "please",
        "change",
        "your",
        "lyrics",
        "try",
        "and",
    }
)

_BLOCKED_TERM_PATTERNS = (
    re.compile(r"producer tag\s+([a-z0-9][a-z0-9 _-]*)", re.IGNORECASE),
    re.compile(r"lyrics contain(?:s)?\s+(?:producer tag\s+)?([a-z0-9][a-z0-9 _-]*)", re.IGNORECASE),
    re.compile(r"reference(?:s)? specific artists[^.]*\b([a-z0-9][a-z0-9 _-]*)\b", re.IGNORECASE),
)

_WARN_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\bfeat\.?\b", re.IGNORECASE),
        "feat.",
        "Remove featured-artist references (use neutral wording instead).",
    ),
    (
        re.compile(r"\bft\.?\b", re.IGNORECASE),
        "ft.",
        "Remove featured-artist references (use neutral wording instead).",
    ),
    (
        re.compile(r"\bfeaturing\b", re.IGNORECASE),
        "featuring",
        "Remove featured-artist references (use neutral wording instead).",
    ),
    (
        re.compile(r"@\w+", re.IGNORECASE),
        "@handle",
        "Remove @ social handles and artist tags.",
    ),
    (
        re.compile(r"\bproduced by\b", re.IGNORECASE),
        "produced by",
        "Remove producer credits from lyrics.",
    ),
    (
        re.compile(r"\bprod\.?\s+by\b", re.IGNORECASE),
        "prod. by",
        "Remove producer credits from lyrics.",
    ),
    (
        re.compile(r"\bproducer tag\b", re.IGNORECASE),
        "producer tag",
        "Remove producer tag references.",
    ),
)


@dataclass(frozen=True)
class SunoLyricsRiskHit:
    term: str
    severity: Literal["block", "warn"]
    start: int
    end: int
    suggestion: str


@dataclass(frozen=True)
class SunoSanitizeReplacement:
    field: str
    source: str
    target: str


def extract_blocked_terms_from_suno_error(error_message: object) -> list[str]:
    text = str(error_message or "").strip()
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()
    for pattern in _BLOCKED_TERM_PATTERNS:
        for match in pattern.finditer(text):
            token = str(match.group(1) or "").strip().lower()
            token = re.split(r"[\s,;]+", token)[0]
            if not token or token in seen or token in _BLOCKED_TERM_STOPWORDS:
                continue
            seen.add(token)
            found.append(token)
    return found


def _block_suggestion(term: str, replacements: dict[str, str]) -> str:
    replacement = replacements.get(term.lower())
    if replacement:
        return f"Replace with '{replacement}'."
    return "Remove or rephrase this token before submitting to Suno."


def _merge_platform_blocklist(
    *,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> dict[str, str]:
    mapping = dict(_DEFAULT_REPLACEMENTS)
    if platform_blocklist is not None:
        mapping.update(platform_blocklist.replacements)
    if extra_replacements:
        mapping.update({str(k).lower(): str(v) for k, v in extra_replacements.items()})
    if replacements:
        mapping.update({str(k).lower(): str(v) for k, v in replacements.items()})
    return mapping


def _collect_block_terms(
    *,
    mapping: dict[str, str],
    blocked_terms: Iterable[str] | None = None,
    learned_terms: Iterable[str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> set[str]:
    terms = set(mapping)
    if platform_blocklist is not None:
        terms.update(platform_blocklist.block_terms)
    for source in (blocked_terms, learned_terms, extra_block_terms):
        for term in source or ():
            normalized = str(term or "").strip().lower()
            if normalized:
                terms.add(normalized)
                mapping.setdefault(normalized, "echo")
    return terms


def _collect_warn_terms(
    *,
    extra_warn_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> set[str]:
    terms: set[str] = set()
    if platform_blocklist is not None:
        terms.update(platform_blocklist.warn_terms)
    for term in extra_warn_terms or ():
        normalized = str(term or "").strip().lower()
        if normalized:
            terms.add(normalized)
    return terms


def _build_replacement_mapping(
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> tuple[set[str], dict[str, str]]:
    mapping = _merge_platform_blocklist(
        replacements=replacements,
        extra_replacements=extra_replacements,
        platform_blocklist=platform_blocklist,
    )
    terms = _collect_block_terms(
        mapping=mapping,
        blocked_terms=blocked_terms,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )
    return terms, mapping


def find_suno_risk_terms_in_text(
    text: object,
    *,
    learned_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    extra_warn_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> list[SunoLyricsRiskHit]:
    normalized_text = str(text or "")
    if not normalized_text.strip():
        return []

    mapping = _merge_platform_blocklist(
        replacements=replacements,
        extra_replacements=extra_replacements,
        platform_blocklist=platform_blocklist,
    )
    block_terms = _collect_block_terms(
        mapping=mapping,
        learned_terms=learned_terms,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )
    warn_terms = _collect_warn_terms(
        extra_warn_terms=extra_warn_terms,
        platform_blocklist=platform_blocklist,
    )

    hits: list[SunoLyricsRiskHit] = []
    seen_spans: set[tuple[int, int]] = set()

    for term in sorted(block_terms, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(term)}\b", normalized_text, flags=re.IGNORECASE):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            hits.append(
                SunoLyricsRiskHit(
                    term=match.group(0),
                    severity="block",
                    start=match.start(),
                    end=match.end(),
                    suggestion=_block_suggestion(term, mapping),
                )
            )

    for term in sorted(warn_terms, key=len, reverse=True):
        if term in block_terms:
            continue
        for match in re.finditer(rf"\b{re.escape(term)}\b", normalized_text, flags=re.IGNORECASE):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            suggestion = _block_suggestion(term, mapping)
            if suggestion.startswith("Remove or rephrase"):
                suggestion = "Review this term before submitting to Suno."
            hits.append(
                SunoLyricsRiskHit(
                    term=match.group(0),
                    severity="warn",
                    start=match.start(),
                    end=match.end(),
                    suggestion=suggestion,
                )
            )

    for pattern, label, suggestion in _WARN_PATTERNS:
        for match in pattern.finditer(normalized_text):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            hits.append(
                SunoLyricsRiskHit(
                    term=match.group(0) or label,
                    severity="warn",
                    start=match.start(),
                    end=match.end(),
                    suggestion=suggestion,
                )
            )

    hits.sort(key=lambda hit: (hit.start, hit.end, hit.severity))
    return hits


def find_suno_risk_terms_in_lyrics(
    lyrics: object,
    *,
    learned_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    extra_warn_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> list[SunoLyricsRiskHit]:
    return find_suno_risk_terms_in_text(
        lyrics,
        learned_terms=learned_terms,
        replacements=replacements,
        extra_replacements=extra_replacements,
        extra_block_terms=extra_block_terms,
        extra_warn_terms=extra_warn_terms,
        platform_blocklist=platform_blocklist,
    )


def sanitize_text_for_suno_with_changes(
    text: object,
    *,
    field: str = "text",
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> tuple[str, list[SunoSanitizeReplacement]]:
    original = str(text or "")
    if not original.strip():
        return original, []

    terms, mapping = _build_replacement_mapping(
        blocked_terms=blocked_terms,
        replacements=replacements,
        extra_replacements=extra_replacements,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )

    result = original
    changes: list[SunoSanitizeReplacement] = []
    for term in sorted(terms, key=len, reverse=True):
        replacement = mapping.get(term, "echo")

        def _replacer(match: re.Match[str], *, replacement_value: str = replacement) -> str:
            changes.append(
                SunoSanitizeReplacement(
                    field=field,
                    source=match.group(0),
                    target=replacement_value,
                )
            )
            return replacement_value

        result = re.sub(
            rf"\b{re.escape(term)}\b",
            _replacer,
            result,
            flags=re.IGNORECASE,
        )
    return result, changes


def sanitize_text_for_suno(
    text: object,
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> str:
    cleaned, _ = sanitize_text_for_suno_with_changes(
        text,
        blocked_terms=blocked_terms,
        replacements=replacements,
        extra_replacements=extra_replacements,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )
    return cleaned


def sanitize_lyrics_for_suno_with_changes(
    lyrics: object,
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> tuple[str, list[SunoSanitizeReplacement]]:
    return sanitize_text_for_suno_with_changes(
        lyrics,
        field="lyrics",
        blocked_terms=blocked_terms,
        replacements=replacements,
        extra_replacements=extra_replacements,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )


def sanitize_lyrics_for_suno(
    lyrics: object,
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    extra_replacements: dict[str, str] | None = None,
    extra_block_terms: Iterable[str] | None = None,
    platform_blocklist: SunoPlatformBlocklist | None = None,
) -> str:
    return sanitize_text_for_suno(
        lyrics,
        blocked_terms=blocked_terms,
        replacements=replacements,
        extra_replacements=extra_replacements,
        extra_block_terms=extra_block_terms,
        platform_blocklist=platform_blocklist,
    )


def format_suno_replacements(replacements: Iterable[SunoSanitizeReplacement]) -> str:
    items = list(replacements)
    if not items:
        return ""
    parts = [f"{item.source} → {item.target}" for item in items[:5]]
    if len(items) > 5:
        parts.append(f"+{len(items) - 5} more")
    return ", ".join(parts)


def infer_suno_replacements_from_learned_terms(
    *,
    title: object = "",
    lyrics: object = "",
    learned_terms: Iterable[str] | None = None,
) -> list[SunoSanitizeReplacement]:
    combined = f"{str(title or '')}\n{str(lyrics or '')}"
    if not combined.strip():
        return []

    mapping = dict(_DEFAULT_REPLACEMENTS)
    for term in learned_terms or ():
        normalized = str(term or "").strip().lower()
        if normalized:
            mapping.setdefault(normalized, "echo")

    inferred: list[SunoSanitizeReplacement] = []
    for term, target in mapping.items():
        if re.search(rf"\b{re.escape(term)}\b", combined, flags=re.IGNORECASE):
            continue
        if re.search(rf"\b{re.escape(target)}\b", combined, flags=re.IGNORECASE):
            inferred.append(
                SunoSanitizeReplacement(
                    field="text",
                    source=term,
                    target=target,
                )
            )
    return inferred
