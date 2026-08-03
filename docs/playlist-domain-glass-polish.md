# Playlist domain + glass/glossy polish (design)

**Date:** 2026-07-30  
**Status:** design only — agree before implementation  
**Surface:** Desktop `camxora_python` video workspace  
**References:** Pulse Rail / Lyric Studio long-play screenshots (Glass Aurora, Retro Vinyl, Noir Press, Neon Spectrum, Synth Grid / Split Stage)

---

## 1. Goal

Ship a **Playlist** right-rail domain that matches the expensive long-play look from the reference images:

- Art + tracklist compositions (split / stacked / vinyl / glass cards)
- Now-playing highlight + durations
- Style presets with matching fonts
- **Glass / glossy** materials on Playlist panels **and** Spectrum (premium frost, specular edge, soft bloom — not muddy glow)

Keep Album as a sibling domain. Spectrum / Background / Logo / Particles / Lightning stay on the left rail.

---

## 2. Product decisions (proposed)

| Decision | Proposal | Notes |
|----------|----------|--------|
| Tab label | Rename right-rail **Title → Playlist** | Same slot; no third tab unless we later need both |
| Schema key | Keep `titleText` for v1 (alias UI as Playlist) | Avoids migration risk; optional rename to `playlistText` in Phase 2.5 |
| Content source | Pipeline tracks + manual titles (existing Title behavior) | |
| Spectrum glass | **After Playlist Phase 1** (deferred) | Shared glass language, but Playlist ships first |
| Timeline / gaps / hardcover | Phase 2 under export / arrangement | Not Playlist chrome |

---

## 3. Reference analysis → CAMXORA mapping

### 3.1 Layout patterns seen in screenshots

| Reference look | On-canvas structure | CAMXORA home |
|----------------|---------------------|--------------|
| Split Stage | Art left + playlist panel right | Playlist layout `split` |
| Glass Now-Playing card | Frosted card: art + title + thin wave + list | Playlist layout `glass_card` + glass materials |
| Synth Grid floor | Neon perspective floor + floating UI | **Background** grid/floor + Playlist overlay |
| Neon Spectrum list | Art badge + neon list + bottom bar spectrum | Playlist `neon_list` + Spectrum bars |
| Retro Vinyl | Circular art / vinyl badge + bordered tracklist | Playlist `vinyl` |
| Noir Press | Big track count + high-contrast list + accent | Playlist `noir_press` |
| Gold Lacquer | Thin gold edges, dark lacquer panels | Playlist `gold_lacquer` |

### 3.2 What is *not* Playlist

| Reference control | Belongs to |
|-------------------|------------|
| Floor / horizon / cell size / reflection % | Background (3D/floor grade) |
| Spectrum bar raise / scroll / width | Spectrum (already has Raise Scroll, Row Width, etc.) |
| Arrangement colored song blocks | Pipeline / long-play export |
| Lyric cues / Whisper / Gemini | Out of video Playlist scope |
| Hardcover / gap between songs / opening shot | Phase 2 timing (export) |

---

## 4. Styles (presets)

### 4.1 Phase 1 — Playlist style presets (ship first)

| Key | Label | Visual intent |
|-----|-------|---------------|
| `split_stage` | Split Stage | Art left, list right, clean glass or solid panel |
| `glass_aurora` | Glass Aurora | Frosted panels, cyan/purple wash, soft edge light |
| `neon_spectrum` | Neon Spectrum | Cyan↔magenta neon list + active glow |
| `retro_vinyl` | Retro Vinyl | Circular art treatment, magenta rim, badge |
| `noir_press` | Noir Press | B/W + one accent, large track-count numeral |
| `gold_lacquer` | Gold Lacquer | Black lacquer + thin gold strokes |

Each preset sets: layout, panel glass params, fonts, colors, list style, now-playing chrome, art frame.

### 4.2 Phase 2 — more Playlist styles

| Key | Label | Visual intent |
|-----|-------|---------------|
| `synth_grid` | Synth Grid | Assumes neon floor BG; floating glass now-playing + list |
| `stacked_hero` | Stacked Hero | Centered art → title → list |
| `cold_type` | Cold Type | Typographic column, minimal chrome |
| `slow_shutter` | Slow Shutter | Soft trails / ghosted art plate (light motion on art/panel) |
| `youtube_collection` | YT Collection | “Tracklist” header + big count + transport chrome |

---

## 5. Fonts

### 5.1 Principle

- Prefer **OFL / Apache / SIL** fonts bundled under `camxora_python/assets/fonts/`
- Register in `system_fonts.BUILTIN_FONT_*` so Playlist + Spectrum text can pick them
- Fall back to OS fonts if bundle missing

### 5.2 Phase 1 font pack (download + bundle)

| Font | License | Use with |
|------|---------|----------|
| **Inter** (or **Outfit**) | OFL | Glass / Split / Neon body + UI list |
| **Montserrat** | OFL | Neon titles, modern geometric |
| **Orbitron** or **Rajdhani** | OFL | Synth / Neon display headers |
| **Playfair Display** | OFL | Gold Lacquer titles |
| **Bebas Neue** | OFL | Noir Press big numerals / headers |
| **Source Serif 4** | OFL | Noir editorial body (optional) |

### 5.3 Phase 2 font pack

| Font | Use with |
|------|----------|
| **Cormorant Garamond** | Luxury Gold / Vinyl body |
| **IBM Plex Sans** | Cold Type / technical lists |
| **Space Grotesk** | Modern stacked hero |

### 5.4 Preset → font mapping (defaults)

| Preset | Title font | List font |
|--------|------------|-----------|
| Split Stage | Inter SemiBold | Inter Regular |
| Glass Aurora | Outfit SemiBold | Outfit Regular |
| Neon Spectrum | Montserrat Bold | Rajdhani Medium |
| Retro Vinyl | Montserrat SemiBold | Inter Regular |
| Noir Press | Bebas Neue | Source Serif / Inter |
| Gold Lacquer | Playfair Display | Inter Light |

---

## 6. UI controls — Playlist inspector

### 6.1 Phase 1 (agree + implement after doc sign-off)

**Section: Style**
- Preset Look combo (Phase 1 styles)
- Restore original (session / factory — same pattern as Title)

**Section: Layout**
- Layout: `split` | `stacked` | `vinyl` | `glass_card` | `column` (legacy list)
- Panel side: left | right (for split)
- Art: show/hide, size %, corner radius
- Track count badge: show/hide (“10” / “LONG PLAY”)

**Section: List**
- Content: pipeline | manual
- List style: number / padded / bullet / dash / plain
- Show durations: on/off
- Max visible rows + scroll behavior (clip vs fade)
- Inactive color / active color
- Active index: auto (current pipeline track) | manual

**Section: Now Playing**
- Highlight on/off
- “NOW PLAYING” pill on/off
- Accent color
- Highlight opacity / border glow

**Section: Glass panel** (expensive feel)
- Panel opacity
- Frost / blur strength
- Border width + border color (gold / neon / white)
- Specular edge (top-left highlight) 0–100
- Inner fill color (tint)
- Shadow softness

**Section: Typography**
- Title font / size / weight
- List font / size
- Letter spacing (header)
- Align

**Section: Position** (existing drag)
- Enable Playlist drag on preview when Playlist tab active
- X / Y (template units)

### 6.2 Phase 2 Playlist controls

**Chrome**
- Transport bar (cosmetic play/prev/next/shuffle/repeat) — non-interactive export decoration
- Progress bar under title
- “Track N of M” label
- Vinyl badge style (ring thickness, label text)

**Motion**
- Panel entrance (fade / slide)
- Active-row pulse on beat (light)
- Art react (subtle scale — optional hook to logo audio)

**Glass advanced**
- Dual-layer glass (back plate + front plate)
- Noise / grain on frost
- Chromatic edge (thin RGB fringe)
- Background blur sample radius (true frosted look in preview/export)

**Long-play timing** (if we expose in Playlist later — prefer Export tab)
- Gap between songs
- Opening shot duration
- Hardcover hold

---

## 7. Glass / glossy Spectrum (same expensive language)

Reference UIs feel expensive because of **frosted glass + thin specular edges + controlled bloom**, not because of more blur mush.

### 7.1 Phase 1 — Spectrum glass material

Add under Spectrum layer (or instance) materials:

| Control | Intent |
|---------|--------|
| **Glass Fill** | Semi-transparent fill behind bars / under solid band |
| **Frost** | Soft backdrop blur amount for fill plate |
| **Specular Edge** | Thin bright rim along bar tops or band outline |
| **Gloss** | Directional highlight along bar length (not full additive wash) |
| **Edge Color** | Gold / cyan / white rim independent of fill gradient |
| **Glass Opacity** | Plate vs bars balance |

Preset chips (optional Phase 1):
- `glass_clear` — light frost, white specular
- `glass_neon` — cyan rim, tinted frost
- `glass_gold` — warm rim, dark lacquer fill
- `glass_noir` — thin white edge, near-black fill

### 7.2 Phase 2 — Spectrum glass polish

- Per-bar bevel (fake SSAO / contact shadow under bars)
- Animated specular sweep on beat (subtle)
- Mirrored floor reflection already exists — tune with glass plate so reflection reads as polished floor
- Shared “Material Engine” catalog used by Playlist panels + Spectrum glass + Lightning bolt edge (optional unify)

### 7.3 What we will *not* do for “glass”

- Crushing everything with high blur + white glow (muddy)
- Replacing vivid bar gradients with grey glass
- Forcing glass on every style preset (opt-in material)

---

## 8. Technical architecture (implementation guide)

### 8.1 Playlist domain plug-in points

| Area | Path |
|------|------|
| Right rail tabs | `features/video/widgets/right_rail.py` — label `Title` → `Playlist` |
| Inspector | `text_domain_inspectors.py` (`TitleInspector` → present as Playlist) |
| Registry / presets | `text_domain_registry.py` — new layout keys + style patches |
| Runtime draw | `text_domain_runtime.py` — panel glass, now-playing, art plate |
| Draft / save | `template_draft_domains.py`, `video_template_save.py` |
| Preview drag | `video_view.py` text drag overlay sync |

### 8.2 Schema (Phase 1 additions on `titleText`)

```text
titleText.layout: split | stacked | vinyl | glass_card | column | grid…
titleText.panel: { opacity, frost, borderWidth, borderColor, specular, fill, shadow }
titleText.art: { enabled, size, radius }
titleText.nowPlaying: { enabled, pill, accent, opacity }
titleText.showDurations: bool
titleText.trackCountBadge: bool
titleText.style.fontFamily / listFontFamily / …
```

Legacy `column` / grids keep working.

### 8.3 Spectrum glass schema

```text
layers[].materialMode: none | glass
layers[].glassFill, glassFrost, glassSpecular, glassGloss, glassEdgeColor, glassOpacity
```

Render: preview + `gpu_render` after bar geometry; glass plate under bars; specular as thin bright strip (additive, capped).

### 8.4 Fonts

- Download OFL packages into `camxora_python/assets/fonts/<Family>/`
- Extend `system_fonts.BUILTIN_FONT_FILES` / `BUILTIN_FONT_OPTIONS`
- GPU/PIL path resolution already uses builtin map — verify Khmer fallback still works

---

## 9. Phased delivery

### Phase 1 — Playlist first (“Looks expensive, usable”)

**Scope: Playlist only.** Spectrum glass is deferred to a follow-up after Playlist Phase 1 ships.

1. Rename UI **Title → Playlist**
2. Layouts: Split, Glass Card, Vinyl (basic), Column legacy
3. Now Playing highlight + durations + track count badge
4. Phase 1 style presets (6)
5. Bundle Phase 1 fonts
6. Playlist glass panel controls
7. ~~Spectrum glass material~~ → **Phase 1b / after Playlist** (see §7)
8. Tests + changelog

**Exit criteria:** User can pick Glass Aurora / Neon / Vinyl / Noir / Gold / Split, see frosted playlist panel, export matches preview.

### Phase 1b — Spectrum glass (after Playlist)

1. Spectrum glass material (Fill / Frost / Specular / Gloss / Edge) + 4 material chips
2. Preview + export parity
3. Tests + changelog

**Exit criteria:** Optional glass spectrum reads premium without muddy glow; can pair with Playlist glass styles.

### Phase 2 — “Reference parity”

1. Styles: Synth Grid, Stacked Hero, Cold Type, Slow Shutter, YT Collection
2. Phase 2 fonts
3. Transport / progress chrome (decorative)
4. Advanced glass (dual plate, grain, chromatic edge, true backdrop blur)
5. Spectrum glass Phase 2 (bevel, beat specular, shared material catalog)
6. Optional long-play timing controls (or Export tab)
7. Optional `titleText` → `playlistText` rename with migrate

**Exit criteria:** Side-by-side with Pulse Rail refs feels in the same premium family without copying their IP/assets.

---

## 10. Out of scope

- Cloning Pulse Rail branding, assets, or lyric-studio transcription
- Music portal / YouTube playlist upload features
- Replacing Spectrum Raise Scroll / Row Width (already shipped)
- Full 3D floor engine inside Playlist (Background owns floor)

---

## 11. Decisions (locked 2026-07-30)

1. **Rename Title → Playlist** (same tab; keep `titleText` schema for v1).
2. **All 6 Phase 1 styles** ship: Split Stage, Glass Aurora, Neon Spectrum, Retro Vinyl, Noir Press, Gold Lacquer.
3. **Bundle OFL fonts** from §5.2 into `camxora_python/assets/fonts/`.
4. **Playlist Phase 1 first**; Spectrum glass = Phase 1b after.
5. **Long-play timing** (gap / hardcover / opening) stays **plan-only** in this doc — do **not** implement yet (Phase 2 / Export later).
6. **Chrome fidelity (same day):** glass panel is a real rounded plate (PIL frost veil); NOW PLAYING is a pill overlay; Layout `split` / `split_left` snap side positions (labels match behavior).
7. **Purple Neon Glowing** = **list card only** (`layout: list_card`): frosted glass panel, PLAYLIST header, numbered rows with title + artist subtitle + duration, neon outlined active row. Not a full left/right/bottom stage.

---

## 12. Approval checklist

**Decided**
- [x] Playlist Phase 1 first; Spectrum glass deferred (Phase 1b)
- [x] Rename Title → Playlist
- [x] Keep all 6 Phase 1 styles
- [x] Bundle OFL fonts
- [x] Timing controls: plan only (no implementation yet)

**Build contract**
- [x] This doc is the build contract for Playlist Phase 1

Implement **Playlist Phase 1 only** next. Spectrum glass (1b) and Phase 2 after. Timing stays documented, not coded.
