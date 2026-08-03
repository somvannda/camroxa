"""Sanitize lyrics before Suno submit and extract blocked terms from provider errors."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

# Suno treats some common English words as producer tags; map to safe alternatives.
_DEFAULT_REPLACEMENTS: dict[str, str] = {
    "lowlight": "afterglow",
}
DEFAULT_REPLACEMENTS = _DEFAULT_REPLACEMENTS


@dataclass(frozen=True)
class SunoRuntimeBlocklist:
    replacements: dict[str, str] = field(default_factory=dict)
    block_terms: frozenset[str] = frozenset()
    warn_terms: frozenset[str] = frozenset()

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
    (
        re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
        "Capitalized Name",
        "Possible artist-name pattern (warn-only; may false-positive on ordinary phrases).",
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
    """Parse Suno failure text for tokens the provider flagged."""
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


def _alnum_core(term: str) -> str:
    """Letters/digits only — used so ``low-light`` / ``low light`` map to ``lowlight``."""
    return "".join(ch for ch in str(term or "").lower() if ch.isalnum())


def blocked_term_pattern(term: str) -> str:
    """Regex that matches a block term plus spaced/hyphenated variants.

    Suno may flag ``lowlight`` even when lyrics write ``low-light`` or ``low light``.
    Whole-word ``\\blowlight\\b`` misses those forms. For terms of length >= 3 we allow
    optional space/hyphen/underscore between letters; short terms stay strict to avoid
    false positives (``at``, ``by``, …).
    """
    core = _alnum_core(term)
    if not core:
        escaped = re.escape(str(term or "").strip())
        return rf"\b{escaped}\b" if escaped else r"(?!)"
    if len(core) <= 2:
        return rf"(?<![A-Za-z0-9]){re.escape(core)}(?![A-Za-z0-9])"
    body = r"[\s\-_]*".join(re.escape(ch) for ch in core)
    return rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])"


def _merge_runtime_blocklist(
    *,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> dict[str, str]:
    mapping = dict(_DEFAULT_REPLACEMENTS)
    if runtime_config is not None:
        mapping.update(runtime_config.replacements)
    if replacements:
        mapping.update({str(k).lower(): str(v) for k, v in replacements.items()})
    return mapping


def _collect_block_terms(
    *,
    mapping: dict[str, str],
    blocked_terms: Iterable[str] | None = None,
    learned_terms: Iterable[str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> set[str]:
    terms = set(mapping)
    if runtime_config is not None:
        terms.update(runtime_config.block_terms)
    for source in (blocked_terms, learned_terms):
        for term in source or ():
            normalized = str(term or "").strip().lower()
            if normalized:
                terms.add(normalized)
                mapping.setdefault(normalized, "echo")
    return terms


def _build_replacement_mapping(
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> tuple[set[str], dict[str, str]]:
    mapping = _merge_runtime_blocklist(
        replacements=replacements,
        runtime_config=runtime_config,
    )
    terms = _collect_block_terms(
        mapping=mapping,
        blocked_terms=blocked_terms,
        runtime_config=runtime_config,
    )
    return terms, mapping


def find_suno_risk_terms_in_text(
    text: object,
    *,
    learned_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> list[SunoLyricsRiskHit]:
    """Scan arbitrary text for Suno hard blocks and risky patterns."""
    normalized_text = str(text or "")
    if not normalized_text.strip():
        return []

    mapping = _merge_runtime_blocklist(
        replacements=replacements,
        runtime_config=runtime_config,
    )
    block_terms = _collect_block_terms(
        mapping=mapping,
        learned_terms=learned_terms,
        runtime_config=runtime_config,
    )
    warn_terms: set[str] = set()
    if runtime_config is not None:
        warn_terms.update(runtime_config.warn_terms)

    hits: list[SunoLyricsRiskHit] = []
    seen_spans: set[tuple[int, int]] = set()

    for term in sorted(block_terms, key=len, reverse=True):
        pattern = blocked_term_pattern(term)
        for match in re.finditer(pattern, normalized_text, flags=re.IGNORECASE):
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
        pattern = blocked_term_pattern(term)
        for match in re.finditer(pattern, normalized_text, flags=re.IGNORECASE):
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
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> list[SunoLyricsRiskHit]:
    """Scan lyrics for Suno hard blocks and risky patterns."""
    return find_suno_risk_terms_in_text(
        lyrics,
        learned_terms=learned_terms,
        replacements=replacements,
        runtime_config=runtime_config,
    )


def sanitize_text_for_suno_with_changes(
    text: object,
    *,
    field: str = "text",
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> tuple[str, list[SunoSanitizeReplacement]]:
    """Replace Suno-blocked tokens with safe wording and return replacements made."""
    original = str(text or "")
    if not original.strip():
        return original, []

    terms, mapping = _build_replacement_mapping(
        blocked_terms=blocked_terms,
        replacements=replacements,
        runtime_config=runtime_config,
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
            blocked_term_pattern(term),
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
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> str:
    """Replace Suno-blocked tokens with safe wording (case-insensitive; spaced/hyphen OK)."""
    cleaned, _ = sanitize_text_for_suno_with_changes(
        text,
        blocked_terms=blocked_terms,
        replacements=replacements,
        runtime_config=runtime_config,
    )
    return cleaned


def sanitize_lyrics_for_suno_with_changes(
    lyrics: object,
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> tuple[str, list[SunoSanitizeReplacement]]:
    """Sanitize lyrics and return replacements made."""
    return sanitize_text_for_suno_with_changes(
        lyrics,
        field="lyrics",
        blocked_terms=blocked_terms,
        replacements=replacements,
        runtime_config=runtime_config,
    )


def sanitize_lyrics_for_suno(
    lyrics: object,
    *,
    blocked_terms: Iterable[str] | None = None,
    replacements: dict[str, str] | None = None,
    runtime_config: SunoRuntimeBlocklist | None = None,
) -> str:
    """Replace Suno-blocked tokens with safe wording (case-insensitive; spaced/hyphen OK)."""
    return sanitize_text_for_suno(
        lyrics,
        blocked_terms=blocked_terms,
        replacements=replacements,
        runtime_config=runtime_config,
    )


def format_suno_replacements(replacements: Iterable[SunoSanitizeReplacement]) -> str:
    """Format replacements for user-facing status messages."""
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
    """Infer replacements already applied using learned terms and default mapping."""
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
        if re.search(blocked_term_pattern(term), combined, flags=re.IGNORECASE):
            continue
        if re.search(blocked_term_pattern(target), combined, flags=re.IGNORECASE):
            inferred.append(
                SunoSanitizeReplacement(
                    field="text",
                    source=term,
                    target=target,
                )
            )
    return inferred
