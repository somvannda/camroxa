"""Admin-only content-pool management routes."""

from __future__ import annotations

import json
import random
import re
import unicodedata
import asyncpg
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, require_admin

router = APIRouter(prefix="/admin/content-pools", tags=["admin-content-pools"])

PoolKind = Literal["titles", "albums", "openings"]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class ContentPoolStat(BaseModel):
    total: int
    unused: int
    reserved: int
    stale_reserved: int
    available: int


class ContentPoolStatsResponse(BaseModel):
    titles: ContentPoolStat
    albums: ContentPoolStat
    openings: ContentPoolStat


class ContentPoolRow(BaseModel):
    id: int
    text: str
    secondary_text: str | None = None
    used_count: int
    reservation_state: Literal["available", "reserved", "stale"]
    reserved_by: str | None = None
    reserved_at: str | None = None
    created_at: str | None = None


class ContentPoolListResponse(BaseModel):
    kind: PoolKind
    total: int
    limit: int
    offset: int
    items: list[ContentPoolRow]


class ContentPoolPresetConfig(BaseModel):
    include_defaults: bool = True
    adjectives: list[str] = Field(default_factory=list)
    nouns: list[str] = Field(default_factory=list)
    verbs: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    feelings: list[str] = Field(default_factory=list)
    whos: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    times: list[str] = Field(default_factory=list)


class ContentPoolPresetPack(BaseModel):
    id: str
    kind: PoolKind
    name: str
    description: str
    is_active: bool
    config: ContentPoolPresetConfig
    created_at: str | None = None
    updated_at: str | None = None


class ContentPoolPresetPackListResponse(BaseModel):
    kind: PoolKind
    items: list[ContentPoolPresetPack]


class CreateContentPoolPresetPackRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    is_active: bool = True
    config: ContentPoolPresetConfig = Field(default_factory=ContentPoolPresetConfig)


class UpdateContentPoolPresetPackRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    config: ContentPoolPresetConfig | None = None


class GeneratePresetPackBanksRequest(BaseModel):
    target_count: int = Field(default=10000, ge=100, le=10000)


class GeneratedPresetPackBanks(BaseModel):
    adjectives: list[str] = Field(default_factory=list)
    nouns: list[str] = Field(default_factory=list)
    verbs: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    feelings: list[str] = Field(default_factory=list)
    whos: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    times: list[str] = Field(default_factory=list)


class GeneratePresetPackBanksResponse(BaseModel):
    kind: PoolKind
    target_count: int
    banks: GeneratedPresetPackBanks


class GenerateContentPoolRequest(BaseModel):
    count: int = Field(ge=1, le=200000)
    preset_pack_id: str | None = None


class GenerateContentPoolResponse(BaseModel):
    requested: int
    attempted: int
    inserted: int
    duplicates_skipped: int


class ImportContentPoolRequest(BaseModel):
    text: str = Field(min_length=1)


class ImportContentPoolResponse(BaseModel):
    inserted: int


class UpdateContentPoolItemRequest(BaseModel):
    text: str | None = None
    secondary_text: str | None = None


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
    "after-hours", "airborne", "all-night", "amber-haze", "aurora", "backseat", "barefoot", "blackout", "blue-hour",
    "citywide", "coastal", "cold-fire", "daybreak", "daydream", "deep-blue", "desert", "downtown", "dreamwave",
    "drizzle-lit", "dusty", "festival", "first-light", "flickering", "floodlit", "ghostlight", "gold-dust", "hazy",
    "headlight", "heartwired", "high-rise", "holographic", "horizon-bound", "infrared", "jet-black", "late-summer",
    "low-lit", "luminous", "marble", "mercury", "moonrise", "nightdrive", "northbound", "opal", "overcast",
    "paper-thin", "pearl", "pulsing", "rose-gold", "runaway", "shadowed", "shoreline", "signal-blue", "slow-burn",
    "soft-glow", "southbound", "starbound", "storm-lit", "summer-rain", "sunrise-lit", "televised", "ultraviolet",
    "velour", "vinyl", "warm-blooded", "wave-lit", "westbound", "wireless",
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
    "drift", "loop", "strobe", "laser", "fog", "constellation", "satellite", "nightdrive", "afterparty", "airwave",
    "alley", "anthem", "backbeat", "backseat", "balcony", "beatdrop", "billboard", "boardwalk", "broadcast",
    "cathedral", "coastline", "crossfade", "daybreak", "daylight", "dialtone", "downtown", "drive", "freefall",
    "freeway", "glowline", "hallway", "headlights", "heartline", "hinterland", "horizonline", "interlude", "jetstream",
    "lifeline", "lookout", "motif", "nightfall", "outline", "overdrive", "overpass", "paradise", "passage",
    "postcard", "pulsewave", "runway", "shoreline", "sidewalk", "signalfire", "skyline", "soundcheck", "spotlight",
    "stairwell", "storyline", "streetlight", "sunrise", "switchblade", "tide", "undertow", "underpass", "vapor",
    "vault", "viewfinder", "vinyl", "voiceprint", "weekend", "wildfire", "windowpane",
]
_VERBS = [
    "chase", "follow", "forget", "remember", "hold", "leave", "find", "lose", "burn", "freeze", "drift", "run",
    "hide", "show", "turn", "fade", "glow", "fall", "rise", "wait", "breathe", "call", "answer", "promise",
    "break", "build", "dance", "move", "stay", "go", "arrive", "believe", "bleed", "collide", "count", "crash",
    "cross", "disappear", "drive", "drop", "escape", "float", "fly", "gather", "ignite", "keep", "lean", "lift",
    "linger", "listen", "melt", "pull", "race", "reach", "return", "rush", "shake", "shine", "slip", "spin",
    "stumble", "survive", "swim", "touch", "trace", "travel", "tremble", "vanish", "wander", "whisper", "write",
]
_PLACES = [
    "on the rooftop", "in the hallway", "by the river", "under streetlights", "in the backseat", "at the station",
    "in the club", "on the coastline", "beneath the neon", "under the moon", "in the quiet room", "inside the static",
    "between the lines", "in the dark", "in the blue hour", "across the boardwalk", "along the boulevard",
    "at the harbor", "at the lookout", "behind the hotel", "beneath the skyline", "between the headlights",
    "by the arcade", "by the shoreline", "down the freeway", "inside the afterglow", "inside the backroom",
    "inside the broadcast", "inside the daydream", "inside the downtown rush", "inside the night train", "near the balcony",
    "near the corner booth", "next to the speaker stack", "on the bridge", "on the dance floor", "on the empty avenue",
    "on the fire escape", "on the last train", "on the overpass", "on the pier", "on the side street",
    "past the tunnel lights", "through the underpass", "under the billboard", "under the headlights", "under the overcast sky",
    "within the coastline haze", "within the hotel glow", "within the stairwell echo", "within the subway rush",
    "within the window light",
]
_FEELINGS = [
    "like home", "for the first time", "like we never left", "until the morning", "without a warning",
    "in perfect sync", "on repeat", "in slow motion", "in the afterglow", "in the silence", "in the noise",
    "under my skin", "all at once", "as if the room stopped", "as if the world bent", "before the goodbye",
    "caught in the current", "closer than thunder", "for one more chorus", "in the blue hour", "in the deep end",
    "in the late-night glow", "in the middle of forever", "like a clean escape", "like a loaded memory",
    "like a midnight promise", "like a runaway spark", "like borrowed daylight", "like city lights on rain",
    "like static in my veins", "more than enough", "right on the edge", "safe in the dark", "shaking but alive",
    "somewhere between fear and fire", "too close to midnight", "wide awake again", "with nowhere to hide",
    "without looking back", "without losing the rhythm",
]
_OPENING_WHOS = [
    "I", "We", "You", "Tonight", "Somewhere", "In my head", "In your eyes", "Under the neon", "After midnight",
    "This city", "That heartbeat", "The last believer", "The radio", "The skyline", "My shadow", "Your echo",
    "Our silence", "The afterglow", "The backseat", "The chorus", "A restless soul", "An honest liar", "Every runaway",
    "Somebody's dream", "The midnight driver", "The silver screen", "The downtown ghost", "A borrowed light",
]
_OPENING_MOODS = [
    "love", "heartbreak", "longing", "regret", "hope", "jealousy", "desire", "nostalgia", "loneliness", "euphoria",
    "afterglow", "ache", "belief", "confession", "doubt", "envy", "fever", "forgiveness", "gravity", "heat",
    "hunger", "mercy", "panic", "patience", "relief", "static", "tenderness", "thrill", "wonder", "yearning",
]
_OPENING_TIMES = [
    "tonight", "right now", "in the morning", "after midnight", "before dawn", "all summer", "all winter",
    "for one more hour", "at blue hour", "at closing time", "at daybreak", "at first light", "at golden hour",
    "before sunrise", "during the comedown", "during the chorus", "just past midnight", "long after dark",
    "long before daylight", "on the weekend", "through the sunrise", "until the last call", "when the lights go low",
]

_PRESET_FIELDS_BY_KIND: dict[PoolKind, tuple[str, ...]] = {
    "titles": ("adjectives", "nouns", "verbs", "places", "feelings"),
    "albums": ("adjectives", "nouns"),
    "openings": ("adjectives", "nouns", "verbs", "places", "whos", "moods", "times"),
}
_RESERVATION_STALE_SECONDS = 900
_MAX_PRESET_FIELD_ITEMS = 10000
_MAX_RESOLVED_BANK_ITEMS = 10240
_ADJECTIVE_PREFIXES = [
    "after-hours", "analog", "arcade", "aurora", "backseat", "blue-hour", "cathedral", "celestial", "chrome",
    "cinematic", "cloudline", "coastal", "desert", "downtown", "dreamwave", "dusty", "ember", "festival",
    "glass", "golden-hour", "hologram", "horizon", "infrared", "late-night", "low-light", "luminous", "magnetic",
    "marble", "mercury", "moonrise", "night-drive", "northbound", "opal", "outlaw", "overcast", "paper-thin",
    "paradise", "retro-future", "riverlight", "rose-gold", "shadowline", "silver-screen", "slow-burn", "soft-glow",
    "southbound", "starline", "summer-rain", "sundown", "sunrise", "ultraviolet",
]
_ADJECTIVE_SUFFIXES = [
    "coded", "colored", "drenched", "faded", "facing", "framed", "glazed", "heavy", "laced", "leaning", "lit",
    "locked", "loved", "marked", "mixed", "painted", "pulled", "ready", "ridden", "scarred", "set", "shaped",
    "signed", "sleeved", "softened", "soaked", "stained", "struck", "swept", "tuned", "washed", "worn",
]
_NOUN_PREFIXES = [
    "afterglow", "arcade", "backbeat", "blueprint", "boulevard", "broadcast", "cathedral", "chorus", "citylight",
    "coastline", "daydream", "downtown", "driver", "echo", "electric", "festival", "firelight", "freeway", "glimmer",
    "harbor", "heartbeat", "highrise", "hinterland", "hotel", "hush", "interlude", "jetstream", "kiss", "lifeline",
    "moonlight", "nightfall", "outline", "overdrive", "paradise", "postcard", "radio", "refrain", "river", "runway",
    "satellite", "shoreline", "signal", "skyline", "spotlight", "station", "storyline", "sunline", "tempo", "wildfire",
]
_NOUN_SUFFIXES = [
    "archive", "avenue", "boulevard", "broadcast", "chapter", "code", "collection", "diary", "district", "drive",
    "engine", "field", "forecast", "garden", "glow", "guide", "hotel", "house", "journal", "letter", "line", "map",
    "mirror", "parade", "parlor", "passage", "record", "ritual", "room", "season", "signal", "story", "theory",
    "thread", "ticket", "vault", "view", "wave", "window", "wire",
]
_VERB_PARTICLES = [
    "again", "alone", "awake", "back", "beyond", "by heart", "clean", "close", "deeper", "down slow", "forever",
    "for real", "forward", "in color", "in circles", "in time", "loud", "low", "on cue", "on repeat", "out loud",
    "past midnight", "soft", "too fast", "too late", "toward daylight", "under pressure", "until dawn", "without warning",
]
_VERB_OBJECTS = [
    "the afterglow", "the avenue lights", "the backseat", "the bassline", "the blue hour", "the broken signal",
    "the coastline", "the echo", "the freefall", "the highway", "the horizon", "the last chorus", "the late train",
    "the moonlight", "the nightdrive", "the northbound lane", "the outline", "the radio static", "the shoreline",
    "the skyline", "the spotlight", "the station", "the story", "the summer rain", "the tidal pull", "the tunnel light",
    "the velvet noise", "the weekend", "the window glow", "your shadow",
]
_PLACE_OPENERS = [
    "above", "across", "along", "around", "behind", "beneath", "between", "beyond", "by", "inside", "near", "past",
    "through", "under", "within",
]
_PLACE_DESCRIPTORS = [
    "amber", "arcade", "backstreet", "blue", "broken", "burning", "cathedral", "city", "coastal", "desert", "dim",
    "distant", "downtown", "electric", "empty", "festival", "floodlit", "glass", "golden", "late-night", "low-lit",
    "midnight", "moonlit", "neon", "northbound", "ocean", "open", "quiet", "radio", "rain-soaked", "river", "rooftop",
    "shadow", "silver", "slow", "soft", "southbound", "star", "sunrise", "velvet",
]
_PLACE_LOCATIONS = [
    "alley", "arcade", "avenue", "backseat", "balcony", "boardwalk", "boulevard", "bridge", "club floor", "coastline",
    "corner booth", "dancehall", "downtown station", "express lane", "freeway", "hallway", "harbor", "highway", "hotel",
    "lookout", "parking lot", "pier", "railway", "riverbank", "rooftop", "shoreline", "side street", "signal tower",
    "skywalk", "stairwell", "station", "streetlight", "subway platform", "summer motel", "tunnel", "underpass", "window seat",
]
_FEELING_OPENERS = [
    "like", "as if", "with", "without", "still", "almost", "somehow", "suddenly", "forever", "for once", "all at once",
    "right now", "by daylight", "after the chorus", "under pressure", "in motion", "off guard", "in secret",
]
_FEELING_STATES = [
    "a borrowed sunrise", "a clean escape", "a cut wire", "a falling star", "a late confession", "a live current",
    "a locked memory", "a long goodbye", "a nightdrive promise", "a perfect echo", "a runaway spark", "a shared silence",
    "a slow collision", "a soft landing", "a sudden glow", "an open wound", "home again", "just enough", "light as static",
    "love on repeat", "more than thunder", "new skin", "nothing but afterglow", "only the chorus", "our last secret",
    "pure voltage", "restless summer", "safe in the dark", "too close to midnight", "wide awake",
]
_FEELING_CLOSERS = [
    "after midnight", "all over again", "at the red light", "beneath the skyline", "for one more verse", "in the blue hour",
    "in the afterglow", "in the backseat", "in the quiet", "on the coastline", "on the dance floor", "on the freeway",
    "on the last train", "through the static", "until morning", "without a warning",
]
_WHO_PREFIXES = [
    "I", "We", "You", "Tonight's", "The last", "A restless", "That midnight", "This city", "Somebody's", "Every",
]
_WHO_SUFFIXES = [
    "believer", "burner", "caller", "chorus", "dreamer", "driver", "heartbeat", "liar", "lover", "outsider", "pilot",
    "runner", "saint", "signal", "speaker", "stranger", "survivor", "thief", "traveler", "witness",
]
_MOOD_PREFIXES = [
    "afterglow", "barely-hidden", "beautiful", "borrowed", "cinematic", "electric", "fading", "fever", "golden",
    "half-healed", "heavy", "hollow", "honest", "late-night", "loud", "low-key", "magnetic", "midnight", "open",
    "reckless", "restless", "sleepless", "soft", "sudden", "summer", "tender", "unguarded", "velvet", "wild",
]
_MOOD_SUFFIXES = [
    "ache", "belief", "craving", "desire", "doubt", "euphoria", "faith", "fever", "gravity", "heat", "hunger", "longing",
    "memory", "mercy", "nostalgia", "panic", "patience", "regret", "relief", "static",
]
_TIME_PREFIXES = [
    "after", "before", "during", "just past", "right before", "somewhere around", "through", "until", "well after", "well before",
]
_TIME_WINDOWS = [
    "blue hour", "closing time", "daybreak", "dawn", "first light", "golden hour", "last call", "last light", "midnight",
    "moonrise", "rush hour", "sunrise", "sunset", "the chorus", "the comedown", "the bridge", "the weekend",
]


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip()


def _raise_preset_pack_migration_needed() -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "Preset-pack storage is not available yet because the database migration has not been applied. "
            "Run `python -m alembic -c platform_api/alembic.ini upgrade head` from the project root."
        ),
    )


def _handle_preset_pack_storage_error(exc: Exception) -> None:
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        _raise_preset_pack_migration_needed()
    if "content_pool_preset_packs" in str(exc).lower() and "does not exist" in str(exc).lower():
        _raise_preset_pack_migration_needed()


def _coerce_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _clean_phrase_list(
    raw_value: Any,
    *,
    max_items: int = _MAX_PRESET_FIELD_ITEMS,
    max_length: int = 160,
) -> list[str]:
    if isinstance(raw_value, str):
        raw_items = raw_value.splitlines()
    elif isinstance(raw_value, list):
        raw_items = raw_value
    else:
        raw_items = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        if not text:
            continue
        if len(text) > max_length:
            text = text[:max_length].strip()
        norm = _normalize_text(text)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _merge_bank(default_values: list[str], custom_values: list[str], include_defaults: bool) -> list[str]:
    source = list(default_values)
    if custom_values:
        source = list(default_values) + list(custom_values) if include_defaults else list(custom_values)
    elif not include_defaults:
        source = list(default_values)
    return _clean_phrase_list(source, max_items=_MAX_RESOLVED_BANK_ITEMS, max_length=160)


def _sanitize_preset_config(kind: PoolKind, raw_config: Any) -> ContentPoolPresetConfig:
    if isinstance(raw_config, ContentPoolPresetConfig):
        raw = raw_config.model_dump()
    else:
        raw = _coerce_json_object(raw_config)

    include_defaults = bool(raw.get("include_defaults", True))
    data: dict[str, Any] = {"include_defaults": include_defaults}
    for field_name in _PRESET_FIELDS_BY_KIND[kind]:
        data[field_name] = _clean_phrase_list(
            raw.get(field_name),
            max_items=_MAX_PRESET_FIELD_ITEMS,
            max_length=160,
        )
    return ContentPoolPresetConfig.model_validate(data)


def _append_unique(out: list[str], seen: set[str], text: str, target_count: int) -> bool:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    norm = _normalize_text(cleaned)
    if not cleaned or not norm or norm in seen:
        return False
    seen.add(norm)
    out.append(cleaned)
    return len(out) >= target_count


def _pick_many(values: list[str], count: int) -> list[str]:
    source = [str(item or "").strip() for item in values if str(item or "").strip()]
    if not source:
        return [""] * count
    if len(source) >= count:
        return random.sample(source, count)
    return [random.choice(source) for _ in range(count)]


def _compose_text(*parts: str) -> str:
    text = " ".join(str(part or "").strip() for part in parts if str(part or "").strip())
    text = re.sub(r"\s+([,?.!])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_candidate_rows(rows: list[tuple[str, ...]], seen_norms: set[str]) -> list[tuple[str, ...]]:
    unique_rows: list[tuple[str, ...]] = []
    for row in rows:
        norm = str(row[-1] or "").strip()
        if not norm or norm in seen_norms:
            continue
        seen_norms.add(norm)
        unique_rows.append(row)
    return unique_rows


def _generate_massive_adjectives(target_count: int) -> list[str]:
    out = _clean_phrase_list(_ADJECTIVES, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for prefix in _ADJECTIVE_PREFIXES:
        for base in _ADJECTIVES:
            if _append_unique(out, seen, f"{prefix} {base}", target_count):
                return out
    for base in _ADJECTIVES:
        for suffix in _ADJECTIVE_SUFFIXES:
            if _append_unique(out, seen, f"{base} {suffix}", target_count):
                return out
    for prefix in _ADJECTIVE_PREFIXES:
        for suffix in _ADJECTIVE_SUFFIXES:
            if _append_unique(out, seen, f"{prefix} {suffix}", target_count):
                return out
    for base in _ADJECTIVES:
        for prefix in _ADJECTIVE_PREFIXES:
            if _append_unique(out, seen, f"{base} {prefix}", target_count):
                return out
    return out[:target_count]


def _generate_massive_nouns(target_count: int) -> list[str]:
    out = _clean_phrase_list(_NOUNS, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for prefix in _NOUN_PREFIXES:
        for noun in _NOUNS:
            if _append_unique(out, seen, f"{prefix} {noun}", target_count):
                return out
    for noun in _NOUNS:
        for suffix in _NOUN_SUFFIXES:
            if _append_unique(out, seen, f"{noun} {suffix}", target_count):
                return out
    for noun in _NOUNS:
        for noun2 in _NOUNS:
            if noun == noun2:
                continue
            if _append_unique(out, seen, f"{noun} {noun2}", target_count):
                return out
    return out[:target_count]


def _generate_massive_verbs(target_count: int) -> list[str]:
    out = _clean_phrase_list(_VERBS, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for verb in _VERBS:
        for particle in _VERB_PARTICLES:
            if _append_unique(out, seen, f"{verb} {particle}", target_count):
                return out
    for verb in _VERBS:
        for obj in _VERB_OBJECTS:
            if _append_unique(out, seen, f"{verb} {obj}", target_count):
                return out
    for verb in _VERBS:
        for obj in _VERB_OBJECTS:
            for particle in _VERB_PARTICLES:
                if _append_unique(out, seen, f"{verb} {obj} {particle}", target_count):
                    return out
    return out[:target_count]


def _generate_massive_places(target_count: int) -> list[str]:
    out = _clean_phrase_list(_PLACES, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for opener in _PLACE_OPENERS:
        for descriptor in _PLACE_DESCRIPTORS:
            for location in _PLACE_LOCATIONS:
                if _append_unique(out, seen, f"{opener} the {descriptor} {location}", target_count):
                    return out
    return out[:target_count]


def _generate_massive_feelings(target_count: int) -> list[str]:
    out = _clean_phrase_list(_FEELINGS, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for opener in _FEELING_OPENERS:
        for state in _FEELING_STATES:
            if _append_unique(out, seen, f"{opener} {state}", target_count):
                return out
    for opener in _FEELING_OPENERS:
        for state in _FEELING_STATES:
            for closer in _FEELING_CLOSERS:
                if _append_unique(out, seen, f"{opener} {state} {closer}", target_count):
                    return out
    for opener in _FEELING_OPENERS:
        for state in _FEELING_STATES:
            for descriptor in _PLACE_DESCRIPTORS:
                if _append_unique(out, seen, f"{opener} {state} beneath the {descriptor} glow", target_count):
                    return out
    return out[:target_count]


def _generate_massive_whos(target_count: int) -> list[str]:
    out = _clean_phrase_list(_OPENING_WHOS, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for prefix in _WHO_PREFIXES:
        for suffix in _WHO_SUFFIXES:
            text = f"{prefix} {suffix}"
            if _append_unique(out, seen, text, target_count):
                return out
    for prefix in _WHO_PREFIXES:
        for adjective in _ADJECTIVES:
            for suffix in _WHO_SUFFIXES:
                if _append_unique(out, seen, f"{prefix} {adjective} {suffix}", target_count):
                    return out
    for prefix in _WHO_PREFIXES:
        for noun in _NOUNS:
            for suffix in _WHO_SUFFIXES:
                if _append_unique(out, seen, f"{prefix} {noun} {suffix}", target_count):
                    return out
    return out[:target_count]


def _generate_massive_moods(target_count: int) -> list[str]:
    out = _clean_phrase_list(_OPENING_MOODS, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for prefix in _MOOD_PREFIXES:
        for suffix in _MOOD_SUFFIXES:
            if _append_unique(out, seen, f"{prefix} {suffix}", target_count):
                return out
    for prefix in _MOOD_PREFIXES:
        for suffix in _MOOD_SUFFIXES:
            for closer in _FEELING_CLOSERS:
                if _append_unique(out, seen, f"{prefix} {suffix} {closer}", target_count):
                    return out
    return out[:target_count]


def _generate_massive_times(target_count: int) -> list[str]:
    out = _clean_phrase_list(_OPENING_TIMES, max_items=target_count, max_length=160)
    seen = {_normalize_text(item) for item in out}
    for prefix in _TIME_PREFIXES:
        for window in _TIME_WINDOWS:
            if _append_unique(out, seen, f"{prefix} {window}", target_count):
                return out
    for window in _TIME_WINDOWS:
        for prefix in _TIME_PREFIXES:
            if _append_unique(out, seen, f"{window} {prefix} the bridge", target_count):
                return out
    for prefix in _TIME_PREFIXES:
        for descriptor in _PLACE_DESCRIPTORS:
            for window in _TIME_WINDOWS:
                if _append_unique(out, seen, f"{prefix} the {descriptor} {window}", target_count):
                    return out
    return out[:target_count]


def _generate_massive_preset_banks(kind: PoolKind, target_count: int) -> GeneratedPresetPackBanks:
    data: dict[str, Any] = {}
    for field_name in _PRESET_FIELDS_BY_KIND[kind]:
        if field_name == "adjectives":
            data[field_name] = _generate_massive_adjectives(target_count)[:target_count]
        elif field_name == "nouns":
            data[field_name] = _generate_massive_nouns(target_count)[:target_count]
        elif field_name == "verbs":
            data[field_name] = _generate_massive_verbs(target_count)[:target_count]
        elif field_name == "places":
            data[field_name] = _generate_massive_places(target_count)[:target_count]
        elif field_name == "feelings":
            data[field_name] = _generate_massive_feelings(target_count)[:target_count]
        elif field_name == "whos":
            data[field_name] = _generate_massive_whos(target_count)[:target_count]
        elif field_name == "moods":
            data[field_name] = _generate_massive_moods(target_count)[:target_count]
        elif field_name == "times":
            data[field_name] = _generate_massive_times(target_count)[:target_count]
    return GeneratedPresetPackBanks.model_validate(data)


def _resolve_preset_banks(kind: PoolKind, config: ContentPoolPresetConfig | None) -> dict[str, list[str]]:
    include_defaults = True if config is None else bool(config.include_defaults)
    resolved: dict[str, list[str]] = {}
    if kind in {"titles", "albums", "openings"}:
        resolved["adjectives"] = _merge_bank(_ADJECTIVES, list(config.adjectives) if config else [], include_defaults)
        resolved["nouns"] = _merge_bank(_NOUNS, list(config.nouns) if config else [], include_defaults)
    if kind in {"titles", "openings"}:
        resolved["verbs"] = _merge_bank(_VERBS, list(config.verbs) if config else [], include_defaults)
        resolved["places"] = _merge_bank(_PLACES, list(config.places) if config else [], include_defaults)
    if kind == "titles":
        resolved["feelings"] = _merge_bank(_FEELINGS, list(config.feelings) if config else [], include_defaults)
    if kind == "openings":
        resolved["whos"] = _merge_bank(_OPENING_WHOS, list(config.whos) if config else [], include_defaults)
        resolved["moods"] = _merge_bank(_OPENING_MOODS, list(config.moods) if config else [], include_defaults)
        resolved["times"] = _merge_bank(_OPENING_TIMES, list(config.times) if config else [], include_defaults)
    return resolved


def _parse_openings_text(raw_text: str) -> list[tuple[str, str]]:
    lines = [line.rstrip("\r") for line in str(raw_text or "").splitlines()]
    non_empty = [line.strip() for line in lines if line.strip()]
    out: list[tuple[str, str]] = []
    tab_pairs = [line for line in non_empty if "\t" in line]
    if tab_pairs and len(tab_pairs) >= max(1, len(non_empty) // 2):
        for line in non_empty:
            parts = [part.strip() for part in line.split("\t", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                out.append((parts[0], parts[1]))
        return out
    for idx in range(0, len(non_empty), 2):
        if idx + 1 >= len(non_empty):
            break
        out.append((non_empty[idx], non_empty[idx + 1]))
    return out


def _generate_title_candidates(count: int, config: ContentPoolPresetConfig | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    attempts = 0
    banks = _resolve_preset_banks("titles", config)
    while len(out) < count and attempts < count * 60:
        attempts += 1
        adjective, adjective2 = _pick_many(banks["adjectives"], 2)
        noun, noun2 = _pick_many(banks["nouns"], 2)
        verb, verb2 = _pick_many(banks["verbs"], 2)
        place, place2 = _pick_many(banks["places"], 2)
        feel = random.choice(banks["feelings"])
        text = random.choice(
            [
                _compose_text(adjective, noun),
                _compose_text("Echoes of the", adjective, noun),
                _compose_text("After the", adjective, noun),
                _compose_text("Under the", adjective, noun),
                _compose_text("When the", adjective, noun, "calls"),
                _compose_text("Between the", adjective, noun, "and the", adjective2, noun2),
                _compose_text("Where the", adjective, noun, "meets the", adjective2, noun2),
                _compose_text("The", adjective, noun, "feels", feel),
                _compose_text("Nothing but", adjective, noun, place),
                _compose_text(verb.capitalize(), "through the", adjective, noun),
                _compose_text("We", verb, "through the", adjective, noun, place),
                _compose_text("Don't let the", adjective, noun, verb2),
                _compose_text("I", verb, place, "and stay", feel),
                _compose_text("This", noun, "still feels", feel),
                _compose_text("The", noun, "returns", place2),
                _compose_text(adjective, noun, "before we", verb2),
            ]
        )
        norm = _normalize_text(text)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(text)
    return out


def _generate_album_candidates(count: int, config: ContentPoolPresetConfig | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    attempts = 0
    banks = _resolve_preset_banks("albums", config)
    while len(out) < count and attempts < count * 60:
        attempts += 1
        adjective, adjective2 = _pick_many(banks["adjectives"], 2)
        noun, noun2 = _pick_many(banks["nouns"], 2)
        text = random.choice(
            [
                _compose_text(adjective, noun),
                _compose_text("Stories from the", adjective, noun),
                _compose_text("Letters in the", adjective, noun),
                _compose_text("Inside the", adjective, noun),
                _compose_text("The", adjective, noun, "Collection"),
                _compose_text(adjective, noun, "and", noun2),
                _compose_text("Between the", adjective, noun, "and the", adjective2, noun2),
                _compose_text("Songs for the", adjective, noun),
                _compose_text("The", noun, "in", adjective, "light"),
                _compose_text(adjective.capitalize(), noun, "Archives"),
                _compose_text("Notes from the", adjective, noun),
                _compose_text("Dreams of the", adjective, noun2),
            ]
        )
        norm = _normalize_text(text)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(text)
    return out


def _generate_opening_pairs(
    count: int,
    config: ContentPoolPresetConfig | None = None,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    attempts = 0
    banks = _resolve_preset_banks("openings", config)
    while len(out) < count and attempts < count * 80:
        attempts += 1
        adjective, adjective2 = _pick_many(banks["adjectives"], 2)
        noun, noun2 = _pick_many(banks["nouns"], 2)
        verb, verb2 = _pick_many(banks["verbs"], 2)
        place, place2 = _pick_many(banks["places"], 2)
        who = random.choice(banks["whos"])
        mood = random.choice(banks["moods"])
        time_label = random.choice(banks["times"])
        if who in {"I", "We", "You"}:
            line1 = random.choice(
                [
                    _compose_text(who, verb, "the", adjective, noun, place) + ".",
                    _compose_text(who, verb, "through the", adjective, noun, time_label) + ".",
                    _compose_text(who, verb, place, "like the", adjective, noun, "never left") + ".",
                    _compose_text(who, verb, "and the", adjective, noun, "follows", place2) + ".",
                    _compose_text(who, "still", verb, "the", noun, "under the", adjective, noun2) + ".",
                ]
            )
        else:
            line1 = random.choice(
                [
                    _compose_text(who + ",", "the", adjective, noun, "feels too close", time_label) + ".",
                    _compose_text(who, "meets the", adjective, noun, place) + ".",
                    _compose_text(who, "keeps the", adjective, noun, "alive", time_label) + ".",
                    _compose_text(who, "turns the", adjective2, noun2, "into a warning", place2) + ".",
                    _compose_text(who, "leans into the", adjective, noun, "before daylight", time_label) + ".",
                ]
            )
        line2 = random.choice(
            [
                _compose_text("My", mood, "is louder than the kick drum", time_label) + ".",
                _compose_text("The", adjective2, noun2, "keeps circling back", time_label) + ".",
                _compose_text("I hide the truth in the", noun2 + ",", "but it still shines", time_label) + ".",
                _compose_text("We wear that", mood, "like neon under broken weather", time_label) + ".",
                _compose_text("Even the", adjective2, noun2, "can't drown this", mood, time_label) + ".",
                _compose_text("I let the", noun2, "decide who we are", time_label) + ".",
                _compose_text("Your name lands like", mood, "under my skin", time_label) + ".",
                _compose_text("The room goes quiet, but the", noun, "still", verb2, time_label) + ".",
                _compose_text("We trade our", mood, "for a little more daylight", time_label) + ".",
                _compose_text("Every", noun2, "in the dark sounds like mercy", time_label) + ".",
                _compose_text("I keep the", adjective2, noun2, "close in case we", verb2, "again") + ".",
                _compose_text("Hold me like the", noun, "will vanish", time_label) + ".",
            ]
        )
        norm = _normalize_text(f"{line1} {line2}")
        if norm and norm not in seen:
            seen.add(norm)
            out.append((line1, line2))
    return out


def _build_row(kind: PoolKind, row: Any) -> ContentPoolRow:
    reserved_at = row["reserved_at"] if "reserved_at" in row else None
    reservation_token = str(row["reservation_token"] or "").strip() if "reservation_token" in row else ""
    reserved_by = str(row["reserved_by"] or "").strip() if "reserved_by" in row else ""
    reservation_state: Literal["available", "reserved", "stale"] = "available"
    if reservation_token:
        if "is_stale_reservation" in row and bool(row["is_stale_reservation"]):
            reservation_state = "stale"
        else:
            reservation_state = "reserved"
    if kind == "openings":
        return ContentPoolRow(
            id=int(row["id"]),
            text=str(row["line1"] or ""),
            secondary_text=str(row["line2"] or "") or None,
            used_count=int(row["used_count"] or 0),
            reservation_state=reservation_state,
            reserved_by=reserved_by or None,
            reserved_at=reserved_at.isoformat() if reserved_at else None,
            created_at=row["created_at"].isoformat() if row["created_at"] else None,
        )
    return ContentPoolRow(
        id=int(row["id"]),
        text=str(row["text"] or ""),
        used_count=int(row["used_count"] or 0),
        reservation_state=reservation_state,
        reserved_by=reserved_by or None,
        reserved_at=reserved_at.isoformat() if reserved_at else None,
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
    )


def _build_preset_pack(row: Any) -> ContentPoolPresetPack:
    kind = str(row["kind"])
    config = _sanitize_preset_config(kind, row["config"])
    return ContentPoolPresetPack(
        id=str(row["id"]),
        kind=kind,
        name=str(row["name"] or ""),
        description=str(row["description"] or ""),
        is_active=bool(row["is_active"]),
        config=config,
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


async def _fetch_stats() -> ContentPoolStatsResponse:
    pool = get_db_pool()

    async def fetch_stat(table_name: str) -> ContentPoolStat:
        row = await pool.fetchrow(
            f"""
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE COALESCE(used_count, 0) = 0)::int AS unused,
                COUNT(*) FILTER (
                    WHERE COALESCE(reservation_token, '') <> ''
                      AND reserved_at IS NOT NULL
                      AND reserved_at >= (NOW() - ({_RESERVATION_STALE_SECONDS} * interval '1 second'))
                )::int AS reserved,
                COUNT(*) FILTER (
                    WHERE COALESCE(reservation_token, '') <> ''
                      AND (
                        reserved_at IS NULL
                        OR reserved_at < (NOW() - ({_RESERVATION_STALE_SECONDS} * interval '1 second'))
                      )
                )::int AS stale_reserved,
                COUNT(*) FILTER (
                    WHERE COALESCE(reservation_token, '') = ''
                       OR reserved_at IS NULL
                       OR reserved_at < (NOW() - ({_RESERVATION_STALE_SECONDS} * interval '1 second'))
                )::int AS available
            FROM {table_name}
            """
        )
        return ContentPoolStat(
            total=int(row["total"] or 0),
            unused=int(row["unused"] or 0),
            reserved=int(row["reserved"] or 0),
            stale_reserved=int(row["stale_reserved"] or 0),
            available=int(row["available"] or 0),
        )

    return ContentPoolStatsResponse(
        titles=await fetch_stat("title_pool"),
        albums=await fetch_stat("album_pool"),
        openings=await fetch_stat("opening_pairs"),
    )


async def _fetch_list(kind: PoolKind, limit: int, offset: int) -> ContentPoolListResponse:
    pool = get_db_pool()
    table_name = {"titles": "title_pool", "albums": "album_pool", "openings": "opening_pairs"}[kind]
    total = int(await pool.fetchval(f"SELECT COUNT(*) FROM {table_name}") or 0)
    if kind == "openings":
        rows = await pool.fetch(
            """
            SELECT
                id,
                line1,
                line2,
                COALESCE(used_count, 0) AS used_count,
                reservation_token,
                reserved_by,
                reserved_at,
                CASE
                    WHEN COALESCE(reservation_token, '') <> ''
                     AND (
                        reserved_at IS NULL
                        OR reserved_at < (NOW() - ($3 * interval '1 second'))
                     )
                    THEN TRUE
                    ELSE FALSE
                END AS is_stale_reservation,
                created_at
            FROM opening_pairs
            ORDER BY id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
            _RESERVATION_STALE_SECONDS,
        )
    else:
        column_name = "title" if kind == "titles" else "album"
        rows = await pool.fetch(
            f"""
            SELECT
                id,
                {column_name} AS text,
                COALESCE(used_count, 0) AS used_count,
                reservation_token,
                reserved_by,
                reserved_at,
                CASE
                    WHEN COALESCE(reservation_token, '') <> ''
                     AND (
                        reserved_at IS NULL
                        OR reserved_at < (NOW() - ($3 * interval '1 second'))
                     )
                    THEN TRUE
                    ELSE FALSE
                END AS is_stale_reservation,
                created_at
            FROM {table_name}
            ORDER BY id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
            _RESERVATION_STALE_SECONDS,
        )
    return ContentPoolListResponse(
        kind=kind,
        total=total,
        limit=limit,
        offset=offset,
        items=[_build_row(kind, row) for row in rows],
    )


async def _fetch_preset_packs(kind: PoolKind) -> ContentPoolPresetPackListResponse:
    pool = get_db_pool()
    try:
        rows = await pool.fetch(
            """
            SELECT id, kind, name, description, config, is_active, created_at, updated_at
            FROM content_pool_preset_packs
            WHERE kind = $1
            ORDER BY is_active DESC, updated_at DESC, name ASC
            """,
            kind,
        )
    except Exception as exc:
        _handle_preset_pack_storage_error(exc)
        raise
    return ContentPoolPresetPackListResponse(
        kind=kind,
        items=[_build_preset_pack(row) for row in rows],
    )


async def _get_preset_pack(kind: PoolKind, preset_pack_id: str) -> ContentPoolPresetPack:
    try:
        preset_uuid = UUID(str(preset_pack_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Preset pack id is invalid.") from exc

    pool = get_db_pool()
    try:
        row = await pool.fetchrow(
            """
            SELECT id, kind, name, description, config, is_active, created_at, updated_at
            FROM content_pool_preset_packs
            WHERE kind = $1 AND id = $2
            """,
            kind,
            preset_uuid,
        )
    except Exception as exc:
        _handle_preset_pack_storage_error(exc)
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="Preset pack not found.")
    return _build_preset_pack(row)


async def _bulk_insert_rows(kind: PoolKind, rows: list[tuple[str, ...]]) -> int:
    if not rows:
        return 0
    pool = get_db_pool()
    inserted = 0
    chunk_size = 1000
    if kind == "titles":
        prefix = "INSERT INTO title_pool(title, norm) VALUES "
    elif kind == "albums":
        prefix = "INSERT INTO album_pool(album, norm) VALUES "
    else:
        prefix = "INSERT INTO opening_pairs(line1, line2, norm) VALUES "
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        placeholders: list[str] = []
        params: list[str] = []
        param_index = 1
        for row in chunk:
            placeholders.append("(" + ", ".join(f"${param_index + idx}" for idx in range(len(row))) + ")")
            params.extend(row)
            param_index += len(row)
        query = prefix + ", ".join(placeholders) + " ON CONFLICT (norm) DO NOTHING RETURNING id"
        inserted += len(await pool.fetch(query, *params))
    return inserted


async def _import_kind(kind: PoolKind, raw_text: str) -> int:
    if kind == "openings":
        rows = []
        for line1, line2 in _parse_openings_text(raw_text):
            norm = _normalize_text(f"{line1} {line2}")
            if line1 and line2 and norm:
                rows.append((line1, line2, norm))
        return await _bulk_insert_rows(kind, rows)
    rows = []
    for line in str(raw_text or "").splitlines():
        text = str(line or "").strip()
        norm = _normalize_text(text)
        if text and norm:
            rows.append((text, norm))
    return await _bulk_insert_rows(kind, rows)


async def _generate_kind(
    kind: PoolKind,
    count: int,
    preset_pack_id: str | None = None,
) -> GenerateContentPoolResponse:
    preset_pack = await _get_preset_pack(kind, preset_pack_id) if preset_pack_id else None
    if preset_pack is not None and not preset_pack.is_active:
        raise HTTPException(status_code=400, detail="Only active preset packs can be used for generation.")

    target = max(1, min(200000, int(count or 1)))
    inserted = 0
    attempted = 0
    rounds = 0
    stalled_rounds = 0
    seen_norms: set[str] = set()
    while inserted < target and rounds < 40:
        rounds += 1
        remaining = target - inserted
        overgenerate_multiplier = 4 if rounds >= 8 else 3 if rounds >= 4 else 2
        batch = min(5000, remaining)
        candidate_target = min(20000, max(batch * overgenerate_multiplier, remaining))
        if kind == "titles":
            rows = [
                (text, _normalize_text(text))
                for text in _generate_title_candidates(candidate_target, preset_pack.config if preset_pack else None)
            ]
        elif kind == "albums":
            rows = [
                (text, _normalize_text(text))
                for text in _generate_album_candidates(candidate_target, preset_pack.config if preset_pack else None)
            ]
        else:
            rows = [
                (line1, line2, _normalize_text(f"{line1} {line2}"))
                for line1, line2 in _generate_opening_pairs(candidate_target, preset_pack.config if preset_pack else None)
            ]
        rows = _dedupe_candidate_rows(rows, seen_norms)
        if not rows:
            stalled_rounds += 1
            if stalled_rounds >= 3:
                break
            continue
        attempted += len(rows)
        inserted_now = await _bulk_insert_rows(kind, rows)
        inserted += inserted_now
        if inserted_now == 0:
            stalled_rounds += 1
        else:
            stalled_rounds = 0
        if rounds >= 6 and inserted == 0:
            break
        if stalled_rounds >= 4:
            break
    return GenerateContentPoolResponse(
        requested=target,
        attempted=attempted,
        inserted=inserted,
        duplicates_skipped=max(0, attempted - inserted),
    )


@router.get("/stats", response_model=ContentPoolStatsResponse)
async def get_admin_content_pool_stats(_ctx: AdminDep) -> ContentPoolStatsResponse:
    return await _fetch_stats()


@router.get("/preset-packs/{kind}", response_model=ContentPoolPresetPackListResponse)
async def list_content_pool_preset_packs(
    kind: PoolKind,
    _ctx: AdminDep,
) -> ContentPoolPresetPackListResponse:
    return await _fetch_preset_packs(kind)


@router.post("/preset-packs/{kind}/generate-banks", response_model=GeneratePresetPackBanksResponse)
async def generate_content_pool_preset_pack_banks(
    kind: PoolKind,
    request: GeneratePresetPackBanksRequest,
    _ctx: AdminDep,
) -> GeneratePresetPackBanksResponse:
    target_count = max(100, min(_MAX_PRESET_FIELD_ITEMS, int(request.target_count or _MAX_PRESET_FIELD_ITEMS)))
    return GeneratePresetPackBanksResponse(
        kind=kind,
        target_count=target_count,
        banks=_generate_massive_preset_banks(kind, target_count),
    )


@router.post("/preset-packs/{kind}", response_model=ContentPoolPresetPack, status_code=201)
async def create_content_pool_preset_pack(
    kind: PoolKind,
    request: CreateContentPoolPresetPackRequest,
    _ctx: AdminDep,
) -> ContentPoolPresetPack:
    pool = get_db_pool()
    name = str(request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset pack name is required.")
    description = str(request.description or "").strip()
    config = _sanitize_preset_config(kind, request.config)
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO content_pool_preset_packs(kind, name, name_norm, description, config, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, NOW(), NOW())
            RETURNING id, kind, name, description, config, is_active, created_at, updated_at
            """,
            kind,
            name,
            _normalize_text(name),
            description,
            json.dumps(config.model_dump()),
            request.is_active,
        )
    except Exception as exc:
        _handle_preset_pack_storage_error(exc)
        if "duplicate key value" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A preset pack with this name already exists.") from exc
        raise
    return _build_preset_pack(row)


@router.patch("/preset-packs/{kind}/{preset_pack_id}", response_model=ContentPoolPresetPack)
async def update_content_pool_preset_pack(
    kind: PoolKind,
    preset_pack_id: str,
    request: UpdateContentPoolPresetPackRequest,
    _ctx: AdminDep,
) -> ContentPoolPresetPack:
    current = await _get_preset_pack(kind, preset_pack_id)
    pool = get_db_pool()

    name = str(request.name if request.name is not None else current.name).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset pack name is required.")
    description = str(request.description if request.description is not None else current.description).strip()
    is_active = current.is_active if request.is_active is None else bool(request.is_active)
    config = _sanitize_preset_config(kind, request.config if request.config is not None else current.config)

    try:
        row = await pool.fetchrow(
            """
            UPDATE content_pool_preset_packs
            SET name = $3,
                name_norm = $4,
                description = $5,
                config = $6::jsonb,
                is_active = $7,
                updated_at = NOW()
            WHERE kind = $1 AND id = $2
            RETURNING id, kind, name, description, config, is_active, created_at, updated_at
            """,
            kind,
            UUID(str(preset_pack_id)),
            name,
            _normalize_text(name),
            description,
            json.dumps(config.model_dump()),
            is_active,
        )
    except Exception as exc:
        _handle_preset_pack_storage_error(exc)
        if "duplicate key value" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A preset pack with this name already exists.") from exc
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="Preset pack not found.")
    return _build_preset_pack(row)


@router.delete("/preset-packs/{kind}/{preset_pack_id}", status_code=204)
async def delete_content_pool_preset_pack(
    kind: PoolKind,
    preset_pack_id: str,
    _ctx: AdminDep,
) -> Response:
    try:
        preset_uuid = UUID(str(preset_pack_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Preset pack id is invalid.") from exc

    pool = get_db_pool()
    try:
        result = await pool.execute(
            "DELETE FROM content_pool_preset_packs WHERE kind = $1 AND id = $2",
            kind,
            preset_uuid,
        )
    except Exception as exc:
        _handle_preset_pack_storage_error(exc)
        raise
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Preset pack not found.")
    return Response(status_code=204)


@router.get("/{kind}", response_model=ContentPoolListResponse)
async def list_admin_content_pool_items(
    kind: PoolKind,
    _ctx: AdminDep,
    limit: int = Query(default=100, ge=10, le=500),
    offset: int = Query(default=0, ge=0),
) -> ContentPoolListResponse:
    return await _fetch_list(kind, limit, offset)


@router.post("/{kind}/generate", response_model=GenerateContentPoolResponse)
async def generate_content_pool_items(
    kind: PoolKind,
    request: GenerateContentPoolRequest,
    _ctx: AdminDep,
) -> GenerateContentPoolResponse:
    return await _generate_kind(kind, request.count, request.preset_pack_id)


@router.post("/{kind}/import", response_model=ImportContentPoolResponse)
async def import_content_pool_items(
    kind: PoolKind,
    request: ImportContentPoolRequest,
    _ctx: AdminDep,
) -> ImportContentPoolResponse:
    return ImportContentPoolResponse(inserted=await _import_kind(kind, request.text))


@router.patch("/{kind}/{item_id}", response_model=ContentPoolRow)
async def update_content_pool_item(
    kind: PoolKind,
    item_id: int,
    request: UpdateContentPoolItemRequest,
    _ctx: AdminDep,
) -> ContentPoolRow:
    pool = get_db_pool()
    try:
        if kind == "openings":
            line1 = str(request.text or "").strip()
            line2 = str(request.secondary_text or "").strip()
            if not line1 or not line2:
                raise HTTPException(status_code=400, detail="Both opening lines are required.")
            row = await pool.fetchrow(
                """
                UPDATE opening_pairs
                SET line1 = $2, line2 = $3, norm = $4
                WHERE id = $1
                RETURNING id, line1, line2, COALESCE(used_count, 0) AS used_count, created_at
                """,
                item_id,
                line1,
                line2,
                _normalize_text(f"{line1} {line2}"),
            )
        elif kind == "titles":
            text = str(request.text or "").strip()
            if not text:
                raise HTTPException(status_code=400, detail="Title text is required.")
            row = await pool.fetchrow(
                """
                UPDATE title_pool
                SET title = $2, norm = $3
                WHERE id = $1
                RETURNING id, title AS text, COALESCE(used_count, 0) AS used_count, created_at
                """,
                item_id,
                text,
                _normalize_text(text),
            )
        else:
            text = str(request.text or "").strip()
            if not text:
                raise HTTPException(status_code=400, detail="Album text is required.")
            row = await pool.fetchrow(
                """
                UPDATE album_pool
                SET album = $2, norm = $3
                WHERE id = $1
                RETURNING id, album AS text, COALESCE(used_count, 0) AS used_count, created_at
                """,
                item_id,
                text,
                _normalize_text(text),
            )
    except HTTPException:
        raise
    except Exception as exc:
        if "duplicate key value" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A duplicate pool entry already exists.") from exc
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="Pool item not found.")
    return _build_row(kind, row)


@router.delete("/{kind}/{item_id}", status_code=204)
async def delete_content_pool_item(
    kind: PoolKind,
    item_id: int,
    _ctx: AdminDep,
) -> Response:
    pool = get_db_pool()
    table_name = {"titles": "title_pool", "albums": "album_pool", "openings": "opening_pairs"}[kind]
    result = await pool.execute(f"DELETE FROM {table_name} WHERE id = $1", item_id)
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Pool item not found.")
    return Response(status_code=204)


@router.post("/{kind}/clear", status_code=200)
async def clear_content_pool(
    kind: PoolKind,
    _ctx: AdminDep,
) -> dict[str, bool]:
    pool = get_db_pool()
    table_name = {"titles": "title_pool", "albums": "album_pool", "openings": "opening_pairs"}[kind]
    await pool.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY")
    return {"ok": True}
