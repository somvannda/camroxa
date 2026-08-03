"""System font discovery for Album/Playlist typography.

Uses Qt's font database for the UI list, and resolves a file path for PIL
rasterization (GPU text textures). Prefers bundled OFL fonts under
``camxora_python/assets/fonts/`` when registered as Camxora builtin ids.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Repo assets root: .../camxora_python/assets/fonts
_ASSETS_FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

# Built-in Camxora ids → Windows TTF filenames OR relative paths under assets/fonts.
BUILTIN_FONT_FILES: dict[str, str] = {
    "arial": "arial.ttf",
    "arialbd": "arialbd.ttf",
    "segoeui": "segoeui.ttf",
    "segoeuib": "segoeuib.ttf",
    "impact": "impact.ttf",
    "georgia": "georgia.ttf",
    "georgiab": "georgiab.ttf",
    "consola": "consola.ttf",
    "comic": "comic.ttf",
    # Playlist Phase 1 OFL pack (bundled)
    "inter": "Inter/Inter-Variable.ttf",
    "montserrat": "Montserrat/Montserrat-Variable.ttf",
    "rajdhani": "Rajdhani/Rajdhani-Medium.ttf",
    "rajdhanib": "Rajdhani/Rajdhani-Bold.ttf",
    "playfair": "PlayfairDisplay/PlayfairDisplay-Variable.ttf",
    "bebasneue": "BebasNeue/BebasNeue-Regular.ttf",
    "sourceserif": "SourceSerif4/SourceSerif4-Variable.ttf",
}

BUILTIN_FONT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inter", "Inter"),
    ("montserrat", "Montserrat"),
    ("rajdhani", "Rajdhani"),
    ("rajdhanib", "Rajdhani Bold"),
    ("playfair", "Playfair Display"),
    ("bebasneue", "Bebas Neue"),
    ("sourceserif", "Source Serif 4"),
    ("arial", "Arial"),
    ("arialbd", "Arial Bold"),
    ("segoeui", "Segoe UI"),
    ("segoeuib", "Segoe UI Bold"),
    ("impact", "Impact"),
    ("georgia", "Georgia"),
    ("georgiab", "Georgia Bold"),
    ("consola", "Consolas"),
    ("comic", "Comic Sans"),
)

_BUNDLED_BOLD_ALIASES: dict[str, str] = {
    "rajdhani": "rajdhanib",
    "inter": "inter",
    "montserrat": "montserrat",
    "playfair": "playfair",
    "sourceserif": "sourceserif",
    "bebasneue": "bebasneue",
}

# Allowed filename suffixes after the family stem (not script names like Cham/Khmer).
_STYLE_SUFFIXES = frozenset(
    {
        "regular",
        "bold",
        "italic",
        "bolditalic",
        "light",
        "medium",
        "semibold",
        "demibold",
        "black",
        "thin",
        "extralight",
        "ultralight",
        "extrabold",
        "ultrabold",
        "heavy",
        "book",
        "roman",
        "oblique",
        "variable",
        "vf",
        "ui",
        "mt",
    }
)

# Weight preference when Bold is checked (lower score = better).
_BOLD_WEIGHT_RANK: tuple[str, ...] = (
    "bold",
    "semibold",
    "demibold",
    "extrabold",
    "ultrabold",
    "black",
    "heavy",
    "medium",
)
_REGULAR_WEIGHT_RANK: tuple[str, ...] = (
    "regular",
    "roman",
    "book",
    "medium",
    "light",
    "thin",
)


def _windows_fonts_dirs() -> list[Path]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    dirs = [windir / "Fonts"]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
    if local.is_dir():
        dirs.append(local)
    return dirs


def _arial_fallback(*, bold: bool = False, italic: bool = False) -> str:
    names: list[str] = []
    if bold and italic:
        names.extend(["arialbi.ttf", "arialbd.ttf", "ariali.ttf", "arial.ttf"])
    elif bold:
        names.extend(["arialbd.ttf", "arial.ttf"])
    elif italic:
        names.extend(["ariali.ttf", "arial.ttf"])
    else:
        names.append("arial.ttf")
    for folder in _windows_fonts_dirs():
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
    return "arial.ttf"


# Preferred faces when the selected font cannot cover Unicode / Khmer text.
_UNICODE_FALLBACK_FAMILIES: tuple[str, ...] = (
    "Noto Sans Khmer",
    "Noto Sans Khmer UI",
    "Khmer UI",
    "Khmer OS",
    "Khmer OS Content",
    "Khmer OS Battambang",
    "Khmer Mondulkiri",
    "DaunPenh",
    "Khmer",
    "Segoe UI",
    "Arial Unicode MS",
    "Arial",
)


def text_script_hints(text: str) -> set[str]:
    """Return coarse script tags present in ``text`` (for font fallback)."""
    hints: set[str] = set()
    for ch in str(text or ""):
        cp = ord(ch)
        if 0x1780 <= cp <= 0x17FF or 0x19E0 <= cp <= 0x19FF:
            hints.add("khmer")
        elif 0x0E00 <= cp <= 0x0E7F:
            hints.add("thai")
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:
            hints.add("arabic")
        elif 0x0900 <= cp <= 0x097F:
            hints.add("devanagari")
        elif 0x1000 <= cp <= 0x109F:
            hints.add("myanmar")
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            hints.add("cjk")
        elif 0x0400 <= cp <= 0x04FF:
            hints.add("cyrillic")
        elif cp > 0x024F and ch.isalpha():
            hints.add("other")
    return hints


def text_needs_complex_shaping(text: str) -> bool:
    """True when per-character layout would break OpenType shaping (Khmer, etc.)."""
    hints = text_script_hints(text)
    return bool(hints & {"khmer", "thai", "arabic", "devanagari", "myanmar"})


def _font_has_codepoint(path: str, codepoint: int) -> bool:
    """Return True if ``path`` appears to provide a glyph for ``codepoint``."""
    try:
        from PySide6.QtGui import QRawFont
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is not None:
            raw = QRawFont(path, 24.0)
            if raw.isValid():
                glyphs = raw.glyphIndexesForString(chr(codepoint))
                return bool(glyphs) and any(int(g) != 0 for g in glyphs)
    except Exception:
        pass

    # Headless / no-Qt fallback: compare advance to the .notdef / PUA box.
    try:
        import unicodedata

        from PIL import ImageFont

        font = ImageFont.truetype(path, 48)
        ch = chr(codepoint)
        adv = float(font.getlength(ch))
        notdef = float(font.getlength("\ue000"))
        cat = unicodedata.category(ch)
        if cat.startswith("M"):
            # Real combining marks are often zero-width; .notdef tofu is not.
            if notdef > 0.5 and abs(adv - notdef) < 0.01:
                return False
            return True
        if abs(adv - notdef) < 0.01:
            return False
        return True
    except Exception:
        return False


@lru_cache(maxsize=1024)
def font_covers_text(path: str, text: str) -> bool:
    """Best-effort: selected face must provide glyphs for non-Latin sample chars."""
    sample_cps: list[int] = []
    for ch in str(text or ""):
        cp = ord(ch)
        if cp < 128:
            continue
        if ch.isspace():
            continue
        sample_cps.append(cp)
        if len(sample_cps) >= 8:
            break
    if not sample_cps:
        return True
    if not path or not Path(path).is_file():
        return False
    hits = sum(1 for cp in sample_cps if _font_has_codepoint(path, cp))
    return hits >= max(1, (len(sample_cps) + 1) // 2)


@lru_cache(maxsize=512)
def resolve_font_for_text(
    family: str,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
) -> str:
    """Resolve a face that can render ``text``, falling back for Khmer/Unicode."""
    preferred = resolve_font_file(family, bold=bold, italic=italic)
    if font_covers_text(preferred, text):
        return preferred
    hints = text_script_hints(text)
    ordered: list[str] = []
    if "khmer" in hints:
        ordered.extend(_UNICODE_FALLBACK_FAMILIES)
    else:
        ordered.extend(("Segoe UI", "Arial Unicode MS", "Noto Sans", "Arial"))
        ordered.extend(_UNICODE_FALLBACK_FAMILIES)
    seen = {preferred.lower()}
    for name in ordered:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        path = resolve_font_file(name, bold=bold, italic=italic)
        if path.lower() in seen:
            continue
        seen.add(path.lower())
        if font_covers_text(path, text):
            return path
    return preferred


def _compact(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def _stem_matches_family(stem: str, family: str) -> bool:
    """True only for the same family — not NotoSansCham for NotoSans."""
    stem_c = _compact(stem)
    fam = _compact(family)
    if not fam or not stem_c:
        return False
    if stem_c == fam:
        return True
    if not stem_c.startswith(fam):
        return False
    rest = stem_c[len(fam) :]
    # Allow NotoSansRegular / NotoSans-Bold, reject NotoSansCham / NotoSansKhmer.
    return rest in _STYLE_SUFFIXES


def _style_tokens(path: str) -> set[str]:
    stem = Path(path).stem.lower().replace("_", "-")
    parts = [p for p in stem.split("-") if p]
    # Also split CamelCase tails: PoppinsBold → bold
    tokens: set[str] = set()
    for part in parts[1:] if len(parts) > 1 else parts:
        tokens.add(part)
    compact = _compact(Path(path).stem)
    for token in _STYLE_SUFFIXES:
        if compact.endswith(token) and len(compact) > len(token):
            tokens.add(token)
    return tokens


def _pick_face(candidates: tuple[str, ...] | list[str], *, bold: bool, italic: bool) -> str | None:
    """Choose the best Regular/Bold/Italic face from a family file list."""
    paths = [str(p) for p in candidates if p]
    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]

    scored: list[tuple[int, int, str]] = []
    for path in paths:
        tokens = _style_tokens(path)
        is_italic = bool(tokens & {"italic", "oblique", "bolditalic"})
        # Weight token
        weight = "regular"
        for token in (
            "thin",
            "extralight",
            "ultralight",
            "light",
            "medium",
            "semibold",
            "demibold",
            "bold",
            "extrabold",
            "ultrabold",
            "black",
            "heavy",
            "book",
            "roman",
            "regular",
        ):
            if token in tokens:
                weight = token
                break
        if "bolditalic" in tokens:
            weight = "bold"
            is_italic = True

        italic_penalty = 0 if (is_italic == italic) else 40
        if bold:
            try:
                weight_score = _BOLD_WEIGHT_RANK.index(weight)
            except ValueError:
                weight_score = 20 + (0 if weight == "regular" else 5)
        else:
            try:
                weight_score = _REGULAR_WEIGHT_RANK.index(weight)
            except ValueError:
                # Prefer not to pick bold faces when Bold is off.
                weight_score = 10 if weight in {"bold", "semibold", "extrabold", "black", "heavy"} else 15

        # Prefer shorter / Regular-named files on ties.
        name_bias = 0 if "regular" in Path(path).stem.lower() else 1
        scored.append((italic_penalty + weight_score, name_bias, path))

    scored.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    return scored[0][2]


@lru_cache(maxsize=1)
def list_system_font_families() -> tuple[str, ...]:
    """Return sorted unique font family names from the OS (via Qt)."""
    try:
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            return ()
        families = [str(name).strip() for name in QFontDatabase.families() if str(name).strip()]
    except Exception:
        return ()
    cleaned: list[str] = []
    for name in families:
        if name.startswith("."):
            continue
        if len(name) > 48:
            continue
        # Skip placeholder / test junk families (repeated identical glyphs).
        compact = "".join(ch for ch in name if ch.isalnum())
        if compact and len(set(compact.casefold())) <= 2 and len(compact) >= 8:
            continue
        if name.upper().startswith("ABC-TEXT") or name.upper().startswith("ABCTEXT"):
            continue
        cleaned.append(name)
    return tuple(sorted(set(cleaned), key=lambda s: s.casefold()))


@lru_cache(maxsize=512)
def _scan_font_candidates(needle: str) -> tuple[str, ...]:
    """Return candidate font files for a family, exact/style matches only."""
    fam = _compact(needle)
    if not fam:
        return ()
    exact: list[str] = []
    styled: list[str] = []
    # Also accept filenames that keep spaces (\"Khmer OS Content.ttf\").
    needle_l = str(needle or "").strip().lower()
    for folder in _windows_fonts_dirs():
        if not folder.is_dir():
            continue
        for ext in ("*.ttf", "*.otf", "*.ttc"):
            try:
                matches = list(folder.glob(ext))
            except Exception:
                continue
            for file in matches:
                stem = file.stem
                stem_c = _compact(stem)
                stem_l = stem.lower()
                if stem_c == fam or stem_l == needle_l:
                    exact.append(str(file))
                elif _stem_matches_family(stem, needle):
                    styled.append(str(file))
                elif needle_l and stem_l.replace(" ", "") == needle_l.replace(" ", ""):
                    exact.append(str(file))
    styled.sort(key=lambda p: (0 if "regular" in Path(p).stem.lower() else 1, Path(p).name.lower()))
    # De-dupe while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for path in exact + styled:
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return tuple(out)


@lru_cache(maxsize=1)
def list_font_options() -> tuple[tuple[str, str], ...]:
    """Builtin Camxora fonts first, then every installed family with a real file.

    Qt sometimes registers a generic family (e.g. \"Noto Sans\") from a script
    face (NotoSansCham). Those ghosts have no exact file match and are skipped
    so picking them cannot blank Latin titles.
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for key, label in BUILTIN_FONT_OPTIONS:
        seen.add(key.casefold())
        seen.add(label.casefold())
        out.append((key, label))
    for family in list_system_font_families():
        key = family.casefold()
        if key in seen:
            continue
        if not _scan_font_candidates(family):
            continue
        seen.add(key)
        out.append((family, family))
    return tuple(out)


def _bundled_font_path(relative: str) -> Path | None:
    rel = str(relative or "").replace("\\", "/").strip().lstrip("/")
    if not rel:
        return None
    # Bundled assets use Family/File.ttf; bare Windows names are not under assets.
    if "/" not in rel:
        return None
    candidate = _ASSETS_FONTS_DIR / rel
    if candidate.is_file():
        return candidate
    return None


def _builtin_path(family_key: str, *, bold: bool, italic: bool) -> str | None:
    key = str(family_key or "").strip().lower()
    # Bundled OFL pack first (Playlist Phase 1).
    bundled_key = key
    if bold and key in _BUNDLED_BOLD_ALIASES:
        bundled_key = _BUNDLED_BOLD_ALIASES[key]
    bundled_rel = BUILTIN_FONT_FILES.get(bundled_key) or BUILTIN_FONT_FILES.get(key)
    if bundled_rel and ("/" in bundled_rel or "\\" in bundled_rel):
        found = _bundled_font_path(bundled_rel)
        if found is not None:
            return str(found)

    # Map common builtin ids / labels to a concrete Windows file.
    if key in {"arial", "arialbd", "arialbi", "ariali"}:
        return _arial_fallback(bold=bold or key.endswith("bd") or key.endswith("bi"), italic=italic or key.endswith("i"))
    mapping = {
        ("segoeui", False, False): "segoeui.ttf",
        ("segoeui", True, False): "segoeuib.ttf",
        ("segoeui", False, True): "segoeuii.ttf",
        ("segoeui", True, True): "segoeuiz.ttf",
        ("segoeuib", True, False): "segoeuib.ttf",
        ("segoeuib", False, False): "segoeuib.ttf",
        ("impact", False, False): "impact.ttf",
        ("georgia", False, False): "georgia.ttf",
        ("georgia", True, False): "georgiab.ttf",
        ("georgia", False, True): "georgiai.ttf",
        ("georgia", True, True): "georgiaz.ttf",
        ("georgiab", True, False): "georgiab.ttf",
        ("georgiab", False, False): "georgiab.ttf",
        ("consola", False, False): "consola.ttf",
        ("consola", True, False): "consolab.ttf",
        ("consola", False, True): "consolai.ttf",
        ("consola", True, True): "consolaz.ttf",
        ("comic", False, False): "comic.ttf",
        ("comic", True, False): "comicbd.ttf",
    }
    # Normalize segoeuib / georgiab keys into family base.
    base = key
    if key in {"segoeuib", "segoeuii", "segoeuiz"}:
        base = "segoeui"
    if key in {"georgiab", "georgiai", "georgiaz"}:
        base = "georgia"
    filename = mapping.get((base, bool(bold), bool(italic)))
    if filename is None and base in {"segoeui", "georgia", "consola", "comic", "impact"}:
        filename = mapping.get((base, False, False))
    if not filename:
        mapped = BUILTIN_FONT_FILES.get(key)
        if mapped:
            filename = mapped
    if not filename:
        return None
    for folder in _windows_fonts_dirs():
        candidate = folder / filename
        if candidate.is_file():
            return str(candidate)
    return filename


@lru_cache(maxsize=512)
def resolve_font_file(family: str, *, bold: bool = False, italic: bool = False) -> str:
    """Resolve a font family / Camxora id to a TTF/OTF path for PIL.

    When ``bold`` / ``italic`` are set, prefers matching faces
    (e.g. Poppins-Bold.ttf) instead of always returning Regular.
    """
    raw = str(family or "arial").strip()
    key = raw.lower()

    builtin = _builtin_path(key, bold=bool(bold), italic=bool(italic))
    if builtin and Path(builtin).is_file():
        return builtin
    if builtin and BUILTIN_FONT_FILES.get(key):
        # Allow bare filename for PIL search as last builtin attempt.
        pass

    candidates = _scan_font_candidates(key) or _scan_font_candidates(raw)
    picked = _pick_face(candidates, bold=bool(bold), italic=bool(italic))
    if picked:
        return picked

    if builtin:
        return builtin
    return _arial_fallback(bold=bool(bold), italic=bool(italic))


def clear_font_caches() -> None:
    list_system_font_families.cache_clear()
    list_font_options.cache_clear()
    resolve_font_file.cache_clear()
    resolve_font_for_text.cache_clear()
    font_covers_text.cache_clear()
    _scan_font_candidates.cache_clear()
