"""Structured vocal language profiles for song descriptions and batch generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

LANGUAGE_LABELS: dict[str, str] = {
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "km": "Khmer",
}

LANGUAGE_ALIASES: dict[str, str] = {
    "english": "en",
    "german": "de",
    "spanish": "es",
    "french": "fr",
    "khmer": "km",
}

CHORUS_SECTION_KEYS = frozenset({"chorus", "hook", "drop", "final drop", "final-drop"})
VERSE_SECTION_KEYS = frozenset(
    {
        "intro",
        "verse",
        "build-up",
        "build up",
        "break",
        "bridge",
        "outro",
        "pre-chorus",
        "pre chorus",
    }
)

DEFAULT_BILINGUAL_SECTION_MAP: dict[str, str] = {
    "intro": "secondary",
    "verse": "secondary",
    "build-up": "secondary",
    "build up": "secondary",
    "break": "secondary",
    "bridge": "secondary",
    "outro": "secondary",
    "pre-chorus": "secondary",
    "pre chorus": "secondary",
    "chorus": "primary",
    "hook": "primary",
    "drop": "primary",
    "final drop": "primary",
    "final-drop": "primary",
}

SUNO_STYLE_MAX_LENGTH = 255


@dataclass(frozen=True, slots=True)
class VocalProfile:
    mode: str = "monolingual"
    primary_language: str = "en"
    secondary_language: str | None = None
    verse_role: str = "secondary"
    chorus_role: str = "primary"
    section_language_map: dict[str, str] = field(default_factory=dict)

    @property
    def is_bilingual(self) -> bool:
        return self.mode == "bilingual" and bool(self.secondary_language)


def language_label(code: str) -> str:
    normalized = str(code or "").strip().lower()
    resolved = LANGUAGE_ALIASES.get(normalized, normalized)
    return LANGUAGE_LABELS.get(resolved, normalized.title() if normalized else "English")


def normalize_section_key(header: str) -> str:
    text = str(header or "").strip().lower()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    return re.sub(r"\s+", " ", text)


def parse_vocal_profile(raw: Any) -> VocalProfile | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None

    mode = str(raw.get("mode") or "monolingual").strip().lower()
    if mode not in {"monolingual", "bilingual"}:
        mode = "monolingual"

    primary = str(raw.get("primary_language") or "en").strip().lower()
    secondary_raw = raw.get("secondary_language")
    secondary = (
        str(secondary_raw).strip().lower()
        if secondary_raw is not None and str(secondary_raw).strip()
        else None
    )

    verse_role = str(raw.get("verse_role") or "secondary").strip().lower()
    chorus_role = str(raw.get("chorus_role") or "primary").strip().lower()
    if verse_role not in {"primary", "secondary"}:
        verse_role = "secondary"
    if chorus_role not in {"primary", "secondary"}:
        chorus_role = "primary"

    section_map_raw = raw.get("section_language_map") or {}
    section_map: dict[str, str] = {}
    if isinstance(section_map_raw, dict):
        for key, value in section_map_raw.items():
            normalized_key = normalize_section_key(str(key))
            role = str(value or "").strip().lower()
            if normalized_key and role in {"primary", "secondary"}:
                section_map[normalized_key] = role

    if mode == "bilingual" and not secondary:
        return None

    profile = VocalProfile(
        mode=mode,
        primary_language=primary,
        secondary_language=secondary,
        verse_role=verse_role,
        chorus_role=chorus_role,
        section_language_map=section_map,
    )
    if profile.is_bilingual:
        return profile
    return VocalProfile(mode="monolingual", primary_language=primary)


def build_section_language_map_from_roles(
    *,
    verse_role: str = "secondary",
    chorus_role: str = "primary",
) -> dict[str, str]:
    """Build a section-name language map from verse/chorus role defaults."""
    normalized_verse = str(verse_role or "secondary").strip().lower()
    normalized_chorus = str(chorus_role or "primary").strip().lower()
    if normalized_verse not in {"primary", "secondary"}:
        normalized_verse = "secondary"
    if normalized_chorus not in {"primary", "secondary"}:
        normalized_chorus = "primary"

    section_map: dict[str, str] = {}
    for key in sorted(VERSE_SECTION_KEYS):
        section_map[key] = normalized_verse
    for key in sorted(CHORUS_SECTION_KEYS):
        section_map[key] = normalized_chorus
    return section_map


def vocal_profile_to_dict(profile: VocalProfile | None) -> dict[str, Any] | None:
    if profile is None or not profile.is_bilingual:
        return None
    payload: dict[str, Any] = {
        "mode": profile.mode,
        "primary_language": profile.primary_language,
        "secondary_language": profile.secondary_language,
        "verse_role": profile.verse_role,
        "chorus_role": profile.chorus_role,
    }
    if profile.section_language_map:
        payload["section_language_map"] = dict(profile.section_language_map)
    return payload


def validate_vocal_profile_payload(raw: Any) -> dict[str, Any] | None:
    profile = parse_vocal_profile(raw)
    if raw is None:
        return None
    if raw == {}:
        return None
    if profile is None:
        raise ValueError("Invalid vocal profile. Bilingual mode requires secondary_language.")
    return vocal_profile_to_dict(profile)


def resolve_workspace_batch_languages(
    *,
    language: str,
    secondary_language: str | None,
) -> tuple[str, str | None]:
    """Resolve lyric languages from workspace primary/secondary picks.

  When secondary is missing or matches primary, lyrics are monolingual.
    """
    primary = str(language or "en").strip().lower()
    secondary = str(secondary_language or "").strip().lower()
    if not secondary or secondary == primary:
        return primary, None
    return primary, secondary


def lyric_vocal_profile_for_batch(
    *,
    description_profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
) -> VocalProfile | None:
    """Build a vocal profile for lyric generation from workspace language picks."""
    resolved_primary, resolved_secondary = resolve_workspace_batch_languages(
        language=primary,
        secondary_language=secondary,
    )
    if resolved_secondary is None:
        return None

    if description_profile is not None and description_profile.is_bilingual:
        return VocalProfile(
            mode="bilingual",
            primary_language=resolved_primary,
            secondary_language=resolved_secondary,
            verse_role=description_profile.verse_role,
            chorus_role=description_profile.chorus_role,
            section_language_map=dict(description_profile.section_language_map),
        )

    return VocalProfile(
        mode="bilingual",
        primary_language=resolved_primary,
        secondary_language=resolved_secondary,
        verse_role="secondary",
        chorus_role="primary",
    )


def resolve_batch_languages(
    *,
    batch_language: str,
    secondary_language: str | None,
    profile: VocalProfile | None,
) -> tuple[str, str | None]:
    primary = str(batch_language or "en").strip().lower()
    if profile is None or not profile.is_bilingual:
        return primary, None

    secondary = str(secondary_language or profile.secondary_language or "").strip().lower()
    if not secondary:
        raise ValueError("secondary_language is required for bilingual descriptions.")
    if secondary == primary:
        raise ValueError("primary and secondary languages must differ.")
    return primary, secondary


def _role_for_section(section_key: str, profile: VocalProfile) -> str:
    if section_key in profile.section_language_map:
        return profile.section_language_map[section_key]
    if section_key in CHORUS_SECTION_KEYS:
        return profile.chorus_role
    if section_key in VERSE_SECTION_KEYS:
        return profile.verse_role
    return profile.verse_role


def language_for_role(role: str, *, primary: str, secondary: str) -> str:
    if role == "secondary":
        return secondary
    return primary


def resolve_header_language(
    header: str,
    *,
    profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
) -> str:
    if profile is None or not profile.is_bilingual or not secondary:
        return primary
    section_key = normalize_section_key(header)
    role = _role_for_section(section_key, profile)
    return language_for_role(role, primary=primary, secondary=secondary)


def build_section_language_plan(
    structure_headers: list[str],
    *,
    profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
) -> list[tuple[str, str, str]]:
    plan: list[tuple[str, str, str]] = []
    for header in structure_headers or []:
        code = resolve_header_language(
            header,
            profile=profile,
            primary=primary,
            secondary=secondary,
        )
        plan.append((header, code, language_label(code)))
    return plan


def sanitize_production_description(content: str) -> str:
    text = re.sub(r"\s+", " ", str(content or "").strip())
    if not text:
        return ""

    clause_drop_patterns: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bblend of\b.*\bvocals?\b", re.IGNORECASE),
        re.compile(r"\b(?:english|german|french|spanish|khmer)\s+vocals?\b", re.IGNORECASE),
        re.compile(r"\bvocals?\s+in\s+(?:english|german|french|spanish|khmer)\b", re.IGNORECASE),
        re.compile(
            r"\b(?:melodic\s+)?verses?\s+in\s+(?:english|german|french|spanish|khmer)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bchorus\s+features?\b.*\b(?:english|german|french|spanish|khmer)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:male\s+and\s+female|female\s+and\s+male)\s+vocals?\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bbilingual\b", re.IGNORECASE),
        re.compile(r"\bdual[\s-]?language\b", re.IGNORECASE),
    )

    kept: list[str] = []
    for clause in re.split(r",\s*", text):
        cleaned_clause = clause.strip(" .")
        if not cleaned_clause:
            continue
        if any(pattern.search(cleaned_clause) for pattern in clause_drop_patterns):
            continue
        kept.append(cleaned_clause)
    return ", ".join(kept).strip(" ,.")


def build_suno_vocal_style_line(
    *,
    profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
    structure_headers: list[str] | None = None,
) -> str:
    if profile is None or not profile.is_bilingual or not secondary:
        return f"Vocals in {language_label(primary)} throughout."

    primary_label = language_label(primary)
    secondary_label = language_label(secondary)
    if structure_headers:
        primary_headers = [
            normalize_section_key(header)
            for header in structure_headers
            if resolve_header_language(
                header,
                profile=profile,
                primary=primary,
                secondary=secondary,
            )
            == primary
        ]
        secondary_headers = [
            normalize_section_key(header)
            for header in structure_headers
            if resolve_header_language(
                header,
                profile=profile,
                primary=primary,
                secondary=secondary,
            )
            == secondary
        ]
        parts: list[str] = []
        if secondary_headers:
            parts.append(
                f"{secondary_label} vocals in {', '.join(dict.fromkeys(secondary_headers))}"
            )
        if primary_headers:
            parts.append(
                f"{primary_label} vocals in {', '.join(dict.fromkeys(primary_headers))}"
            )
        if parts:
            return ". ".join(parts) + "."

    return (
        f"{secondary_label} verses and {primary_label} chorus hooks. "
        f"Male and female vocals with pitch correction and light reverb."
    )


def resolve_suno_style_from_description(description_content: str) -> str:
    """Use the stored music description prompt as Suno style (trim + length cap only)."""
    text = re.sub(r"\s+", " ", str(description_content or "").strip())
    if not text:
        return "Contemporary pop"
    return truncate_suno_style(text)


def build_suno_style_prompt(
    *,
    production_description: str,
    profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
    structure_headers: list[str] | None = None,
) -> str:
    production = sanitize_production_description(production_description)
    vocal_line = build_suno_vocal_style_line(
        profile=profile,
        primary=primary,
        secondary=secondary,
        structure_headers=structure_headers,
    )
    if production and vocal_line:
        separator = " "
        max_production_len = SUNO_STYLE_MAX_LENGTH - len(vocal_line) - len(separator)
        if max_production_len < 48:
            return truncate_suno_style(f"{production}{separator}{vocal_line}".strip())
        if len(production) > max_production_len:
            production = production[:max_production_len].rstrip(" ,.;")
        style = f"{production}{separator}{vocal_line}".strip()
    else:
        style = production or vocal_line
    return truncate_suno_style(style)


def truncate_suno_style(text: str, *, max_length: int = SUNO_STYLE_MAX_LENGTH) -> str:
    """Fit Suno style text into DB/API varchar(255) limits."""
    compact = re.sub(r"\s+", " ", str(text or "").strip())
    if len(compact) <= max_length:
        return compact
    return compact[:max_length].rstrip(" ,.;")


def build_monolingual_language_instruction(language_code: str) -> str:
    return (
        f"Language: {language_label(language_code)}. "
        "Ignore any other language mentioned in the description."
    )


def build_metadata_language_instruction(
    *,
    language: str,
    secondary_language: str | None = None,
    profile: VocalProfile | None = None,
    slot: str,
) -> str:
    """Language instruction for title/album LLM slots (primary language only)."""
    _ = (secondary_language, profile, slot)
    return build_monolingual_language_instruction(language)


def build_bilingual_language_instruction(
    *,
    primary: str,
    secondary: str,
    profile: VocalProfile,
    structure_headers: list[str],
) -> str:
    plan = build_section_language_plan(
        structure_headers or [],
        profile=profile,
        primary=primary,
        secondary=secondary,
    )
    if not plan:
        return (
            f"- Bilingual song: primary={language_label(primary)}, "
            f"secondary={language_label(secondary)}.\n"
            "- Choose section headers and assign each section's lyric language "
            "according to the vocal profile.\n"
        )
    lines = [
        f"Bilingual song: primary={language_label(primary)}, secondary={language_label(secondary)}.",
        "Section language plan:",
    ]
    lines.extend(f"- {header} → {label}" for header, _code, label in plan)
    lines.append("Follow the section language plan exactly.")
    return "\n".join(lines)


def format_section_language_plan_text(
    structure_headers: list[str],
    *,
    profile: VocalProfile | None,
    primary: str,
    secondary: str | None,
) -> str:
    plan = build_section_language_plan(
        structure_headers,
        profile=profile,
        primary=primary,
        secondary=secondary,
    )
    return "\n".join(f"{header} → {label}" for header, _code, label in plan)
