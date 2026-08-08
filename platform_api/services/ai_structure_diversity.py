"""Genre-aware viral structure seeds for AI Structure (ai_free) lyric mode.

Keeps production description content out of lyric prompts — only uses
``music_descriptions.genres`` (and optional soft layout seeds) to steer variety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


# Exact overused commercial-pop sequence observed on production.
DEFAULT_OVERUSED_STRUCTURE = (
    "[Verse 1] -> [Pre-Chorus] -> [Chorus] -> [Verse 2] -> [Pre-Chorus] -> "
    "[Chorus] -> [Bridge] -> [Final Chorus] -> [Outro]"
)

_BUCKET_ELECTRONIC = "electronic"
_BUCKET_POP = "pop"
_BUCKET_URBAN = "urban"
_BUCKET_DEFAULT = "default"

_ELECTRONIC_TOKENS = (
    "edm",
    "electronic",
    "electronica",
    "house",
    "techno",
    "trance",
    "dubstep",
    "drum and bass",
    "dnb",
    "dn b",
    "eurodance",
    "hands up",
    "hardstyle",
    "hard dance",
    "progressive house",
    "future bass",
    "electro",
    "dance",
    "dance music",
    "club",
    "big room",
    "festival",
    "melodic techno",
    "synthwave",
    "garage",
    "breaks",
    "trance",
    "psytrance",
    "drumstep",
)

_URBAN_TOKENS = (
    "hip hop",
    "hip-hop",
    "hiphop",
    "rap",
    "trap",
    "r&b",
    "rnb",
    "r and b",
    "soul",
    "afrobeats",
    "afrobeat",
    "drill",
)

_POP_TOKENS = (
    "pop",
    "dance pop",
    "synthpop",
    "synth-pop",
    "k-pop",
    "kpop",
    "indie pop",
    "teen pop",
    "electropop",
)


@dataclass(frozen=True, slots=True)
class StructureFamily:
    """Soft layout seed for AI Structure mode."""

    id: str
    label: str
    headers: tuple[str, ...]
    buckets: frozenset[str]

    @property
    def fingerprint(self) -> str:
        return " -> ".join(self.headers)

    @property
    def layout_block(self) -> str:
        return "\n".join(self.headers)


# Shared viral / hook-early families. Build/drop only for electronic buckets.
STRUCTURE_FAMILIES: tuple[StructureFamily, ...] = (
    StructureFamily(
        id="cold_open_chorus",
        label="Cold-open chorus (hook first)",
        headers=("[Chorus]", "[Verse]", "[Chorus]", "[Verse]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="short_intro_double_chorus",
        label="Short intro, double chorus",
        headers=("[Intro]", "[Verse]", "[Chorus]", "[Chorus]", "[Outro]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="verse_pre_chorus_chorus",
        label="Verse / pre-chorus / chorus",
        headers=("[Verse]", "[Pre-Chorus]", "[Chorus]", "[Verse]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="hook_bridge_hook",
        label="Hook / verse / hook / bridge / hook",
        headers=("[Chorus]", "[Verse]", "[Chorus]", "[Bridge]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="verse_chorus_bridge",
        label="Verse / chorus / bridge / chorus",
        headers=("[Verse]", "[Chorus]", "[Verse]", "[Chorus]", "[Bridge]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="chorus_heavy_no_pre",
        label="Chorus-heavy (no pre-chorus)",
        headers=("[Verse]", "[Chorus]", "[Verse]", "[Chorus]", "[Outro]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="radio_edit_short",
        label="Short radio edit",
        headers=("[Verse]", "[Chorus]", "[Verse]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="post_chorus_lift",
        label="Chorus + post-chorus lift",
        headers=("[Verse]", "[Chorus]", "[Post-Chorus]", "[Verse]", "[Chorus]", "[Post-Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="delayed_chorus",
        label="Delayed chorus (two verses first)",
        headers=("[Verse]", "[Verse]", "[Pre-Chorus]", "[Chorus]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="bridge_early",
        label="Early bridge turn",
        headers=("[Verse]", "[Chorus]", "[Bridge]", "[Verse]", "[Chorus]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="hook_tag_outro",
        label="Hook tag outro",
        headers=("[Intro]", "[Hook]", "[Verse]", "[Hook]", "[Outro]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="double_hook_open",
        label="Double hook open",
        headers=("[Chorus]", "[Chorus]", "[Verse]", "[Chorus]", "[Outro]"),
        buckets=frozenset({_BUCKET_POP, _BUCKET_URBAN, _BUCKET_DEFAULT, _BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="spoken_verse_hook",
        label="Sparse verse, hook-heavy",
        headers=("[Verse]", "[Hook]", "[Verse]", "[Hook]", "[Hook]"),
        buckets=frozenset({_BUCKET_URBAN, _BUCKET_DEFAULT}),
    ),
    StructureFamily(
        id="build_drop",
        label="Build / drop / break / drop",
        headers=("[Intro]", "[Build]", "[Drop]", "[Break]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="verse_build_drop",
        label="Verse / build / drop",
        headers=("[Verse]", "[Build]", "[Drop]", "[Verse]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="cold_drop",
        label="Cold drop (minimal intro)",
        headers=("[Drop]", "[Break]", "[Drop]", "[Break]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="build_drop_outro",
        label="Build / drop / outro",
        headers=("[Build]", "[Drop]", "[Build]", "[Drop]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="verse_drop_chorus_hybrid",
        label="Verse / drop / chorus hybrid",
        headers=("[Verse]", "[Drop]", "[Chorus]", "[Drop]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="festival_build_drop",
        label="Festival build / drop / breakdown",
        headers=("[Intro]", "[Build]", "[Drop]", "[Breakdown]", "[Build]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="anthem_chorus_drop",
        label="Anthem chorus into drop",
        headers=("[Verse]", "[Chorus]", "[Build]", "[Drop]", "[Chorus]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="hands_up_double_drop",
        label="Hands-up double drop",
        headers=("[Intro]", "[Verse]", "[Drop]", "[Verse]", "[Drop]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="club_hook_drop",
        label="Club hook / drop",
        headers=("[Hook]", "[Build]", "[Drop]", "[Hook]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="eurodance_verse_chorus_drop",
        label="Eurodance verse / chorus / drop",
        headers=("[Verse]", "[Chorus]", "[Drop]", "[Verse]", "[Chorus]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="trance_long_build",
        label="Trance long build",
        headers=("[Intro]", "[Verse]", "[Build]", "[Build]", "[Drop]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="bass_break_drop",
        label="Bass break / drop loop",
        headers=("[Intro]", "[Drop]", "[Break]", "[Build]", "[Drop]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="dance_radio_drop",
        label="Dance radio with late drop",
        headers=("[Verse]", "[Pre-Chorus]", "[Chorus]", "[Drop]", "[Chorus]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="vocal_chop_drop",
        label="Vocal chop into drop",
        headers=("[Intro]", "[Hook]", "[Build]", "[Drop]", "[Hook]", "[Outro]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
    StructureFamily(
        id="two_drop_no_verse",
        label="Two-drop instrumental push",
        headers=("[Build]", "[Drop]", "[Break]", "[Build]", "[Drop]"),
        buckets=frozenset({_BUCKET_ELECTRONIC}),
    ),
)


def normalize_structure_fingerprint(headers: Sequence[str] | str) -> str:
    """Normalize a header sequence into a comparable fingerprint string."""
    if isinstance(headers, str):
        text = headers.strip()
        if "->" in text:
            parts = [part.strip() for part in text.split("->") if part.strip()]
        else:
            parts = [
                line.strip()
                for line in text.splitlines()
                if line.strip().startswith("[") and line.strip().endswith("]")
            ]
        return " -> ".join(parts)
    return " -> ".join(str(item).strip() for item in headers if str(item).strip())


def structure_fingerprint_from_lyrics(lyrics: str) -> str | None:
    """Extract a section-header fingerprint from lyric text, or None."""
    from platform_api.services.generation_service import extract_lyric_section_headers

    headers = extract_lyric_section_headers(lyrics)
    if not headers:
        return None
    return normalize_structure_fingerprint(headers)


def _token_hits(blob: str, tokens: Iterable[str]) -> int:
    return sum(1 for token in tokens if token in blob)


def classify_structure_bucket(genres: Sequence[str] | None) -> str:
    """Map description genres to a structure bucket."""
    names = [str(item or "").strip() for item in (genres or []) if str(item or "").strip()]
    if not names:
        return _BUCKET_DEFAULT
    blob = " ".join(name.casefold() for name in names)
    electronic = _token_hits(blob, _ELECTRONIC_TOKENS)
    urban = _token_hits(blob, _URBAN_TOKENS)
    pop = _token_hits(blob, _POP_TOKENS)
    # Prefer electronic when clearly present (even alongside "dance pop").
    if electronic and electronic >= urban and electronic >= pop:
        return _BUCKET_ELECTRONIC
    if urban and urban >= pop:
        return _BUCKET_URBAN
    if pop:
        return _BUCKET_POP
    return _BUCKET_DEFAULT


def families_for_bucket(bucket: str) -> list[StructureFamily]:
    """Return viral families allowed for a genre bucket."""
    key = (bucket or _BUCKET_DEFAULT).strip().lower() or _BUCKET_DEFAULT
    matched = [family for family in STRUCTURE_FAMILIES if key in family.buckets]
    if matched:
        return matched
    return [family for family in STRUCTURE_FAMILIES if _BUCKET_DEFAULT in family.buckets]


def choose_ai_structure_seed(
    *,
    genres: Sequence[str] | None = None,
    batch_index: int = 0,
    avoid_fingerprints: Sequence[str] | None = None,
) -> StructureFamily:
    """Pick a soft layout seed, rotating by batch index and skipping avoids."""
    bucket = classify_structure_bucket(genres)
    pool = families_for_bucket(bucket)
    if not pool:
        pool = list(STRUCTURE_FAMILIES)

    avoid = {
        normalize_structure_fingerprint(item)
        for item in (avoid_fingerprints or [])
        if str(item or "").strip()
    }
    avoid.add(normalize_structure_fingerprint(DEFAULT_OVERUSED_STRUCTURE))

    start = abs(int(batch_index)) % len(pool)
    ordered = pool[start:] + pool[:start]
    for family in ordered:
        if family.fingerprint not in avoid:
            return family
    return ordered[0]


def build_ai_structure_diversity_system_rules() -> str:
    """Extra system-prompt rules for viral variety (AI Structure mode)."""
    return (
        "- Prefer hook-early, chorus-heavy, viral-friendly layouts for the song's genre.\n"
        "- Pre-Chorus and Final Chorus are optional — do not require them.\n"
        "- Do NOT default to this overused layout: "
        f"{DEFAULT_OVERUSED_STRUCTURE}.\n"
        "- Vary section choices across songs; keep labels as simple bracket headers.\n"
    )


def build_ai_structure_seed_user_block(
    *,
    preferred_layout: str | None,
    avoid_structures: Sequence[str] | None = None,
    genres: Sequence[str] | None = None,
) -> str:
    """User-prompt block with soft seed + avoid list (no production description)."""
    parts: list[str] = []
    genre_names = [str(item).strip() for item in (genres or []) if str(item).strip()]
    if genre_names:
        parts.append(
            "Genre cues for structure only (do not write production/mix notes into lyrics): "
            + ", ".join(genre_names[:6])
        )
    layout = str(preferred_layout or "").strip()
    if layout:
        parts.append(
            "Preferred section layout (soft guide — keep this overall shape, "
            "you may adapt labels slightly if needed):\n"
            f"{layout}"
        )
    avoids = [
        normalize_structure_fingerprint(item)
        for item in (avoid_structures or [])
        if str(item or "").strip()
    ]
    # Keep prompt bounded.
    avoids = [item for item in avoids if item][:8]
    if avoids:
        bullet = "\n".join(f"- {item}" for item in avoids)
        parts.append(
            "Avoid repeating these exact section sequences already used in this batch:\n"
            f"{bullet}"
        )
    return "\n\n".join(parts)
