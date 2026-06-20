## Lyric Timeline Engine — Technical Plan

### Current verified architecture

#### 1) Template overlay model is too narrow for lyrics
- Template default currently stores `textOverlays: []` in [spectrum_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/spectrum_model.py#L9-L101).
- Normalization currently reads `textOverlays` and clamps the working set during normalization in [spectrum_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/spectrum_model.py#L247-L275).
- This is appropriate for a handful of static overlays, not full-song lyric or phoneme timelines.

#### 2) Overlay playback logic is duplicated
- GPU/export/live overlay drawing is centralized in [_draw_text_overlays](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L430-L531) and called from export/live render paths in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L1546-L1554) and [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L3142-L3143).
- Qt preview contains a separate implementation in [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py#L1130-L1194).
- This duplication is a risk for preview/export timing drift if lyric logic is layered in without refactoring.

#### 3) Time source is already available
- Qt preview uses `self.current_time` and playback clock sync in [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py#L233-L260).
- GPU export uses frame time `float(i)/fps` in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L1546-L1554).
- Live preview uses `c_time` in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L3142-L3143).
- These hooks are enough to drive a timeline evaluator.

#### 4) Lyrics data already exists, but not timed
- Song records already contain `lyricsRaw` and `lyricsPolished` in [music_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L173-L176).
- DB schema includes `lyrics_raw` and `lyrics_polished` in [music_migrate.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_migrate.py#L10-L41).
- The app already loads and uses lyrics in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L7815-L7818).
- There is currently no timed lyric, word, subtitle, or phoneme schema in the project.

#### 5) Profile is the right place for feature toggles
- Profiles already own output/publishing behavior like `videoTemplateId`, `outputResolution`, and YouTube settings in [music_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L244-L253).
- Therefore `Enable English Lyric` belongs in the profile model, not global settings.

---

## Recommended target architecture

### A. Keep `textOverlays` backward compatible
Do not remove or mutate existing `textOverlays` semantics for current templates.

Use cases that should remain on `textOverlays`:
- intro titles
- outro cards
- short labels
- non-lyric decorative text

### B. Introduce a new timeline root
Add a new root concept to the normalized template/runtime state:

```json
{
  "timeline": {
    "version": 1,
    "tracks": []
  }
}
```

This timeline root should be normalization-safe and optional.

### C. Separate template styling from song timing artifacts
Recommended split:
- **Profile**: feature enablement (`enableEnglishLyric`)
- **Template**: lyric display style
- **Song/render artifact**: timed content (`lines`, `words`, later `phonemes`)

This prevents template reuse from being polluted by song-specific alignment data.

---

## Proposed data model

### 1) Profile additions
Extend normalized profile with fields similar to:
- `enableEnglishLyric: bool`
- future `enableOtherLanguageLyric: bool`
- future `enableLipSyncVideo: bool`

### 2) Template additions
Template should gain lyric presentation config, for example:

```json
{
  "lyricSettings": {
    "enabled": true,
    "anchor": "bottom-center",
    "x": 0,
    "y": 120,
    "sizePx": 54,
    "color": "#ffffff",
    "strokeColor": "#000000",
    "strokeWidth": 3,
    "shadow": 0.45,
    "maxLines": 2,
    "lineGap": 10,
    "safeMarginPx": 64,
    "highlightCurrentWord": false
  }
}
```

This belongs in template normalization, not inside song rows.

### 3) Song / artifact timeline payload
Recommended persisted artifact shape:

```json
{
  "version": 1,
  "language": "en",
  "source": "whisper-align",
  "audioHash": "...",
  "lyricsHash": "...",
  "lines": [
    {
      "id": "l1",
      "text": "I was driving through the midnight rain",
      "startSec": 12.14,
      "endSec": 15.82,
      "words": [
        {"text": "I", "startSec": 12.14, "endSec": 12.32},
        {"text": "was", "startSec": 12.32, "endSec": 12.61}
      ]
    }
  ],
  "phonemes": []
}
```

### 4) Timeline track descriptors
Suggested template/runtime track descriptors:
- `static_text`
- `lyric_lines`
- `lyric_words`
- `phoneme_track`
- `marker_track`

The track descriptor should point to the data source, not inline the whole song payload unless necessary.

---

## Alignment engine direction

### Recommendation
Use Whisper-based alignment for English only in V1.

### Why
- Audio-grounded timing is much better than LLM-estimated timing.
- Word timing becomes available for future karaoke mode.
- Word timing is a better base for future phoneme/viseme extraction.
- Future lipsync video benefits directly from audio-grounded timing.

### Service responsibilities
Create a dedicated alignment service, for example under `services/`:
- normalize source lyrics
- read produced song audio
- run alignment
- emit line + word timestamps
- score/validate output
- cache results

### Inputs
- song audio path
- `lyricsPolished` fallback `lyricsRaw`
- language = English only

### Outputs
- line timing list
- word timing list
- optional confidence/diagnostic metadata

### Failure handling
The service must return controlled failures for:
- no lyrics text
- no audio path
- alignment exception
- empty timestamps
- unusable confidence

---

## Renderer integration plan

### Problem to solve
Qt preview and GPU renderer currently each implement timed text drawing separately.

### Recommended refactor
Create shared timeline evaluation helpers in a common module, for example:
- `timeline_active_line(timeline, time_sec)`
- `timeline_active_words(timeline, time_sec)`
- `timeline_window_state(...)`

These helpers should be pure and reused by:
- Qt preview in `components.py`
- export path in `gpu_render.py`
- live preview in `gpu_render.py`

### Rendering V1
V1 should render only the active lyric line using `lyricSettings` style.

### Rendering V2+
Later add:
- per-word highlight
- previous/next line context
- karaoke fill animation
- phoneme/viseme debug preview

---

## Persistence options

### Option A — add columns to songs table
Pros:
- easy lookup by song
- direct persistence

Cons:
- potentially large JSON in primary table
- may mix song metadata and render artifacts too tightly

### Option B — dedicated lyric timeline table (recommended)
Suggested shape:
- `song_uid`
- `audio_hash`
- `lyrics_hash`
- `language`
- `timeline_json`
- `source`
- `status`
- `error`
- timestamps

Pros:
- cleaner separation
- easier caching/versioning
- safer for future phoneme/viseme growth

### Option C — filesystem artifact only
Pros:
- simple

Cons:
- weaker lifecycle management
- harder DB-driven workflow visibility

### Recommendation
Use a dedicated DB table plus optional exported JSON artifact file for debugging/reuse.

---

## File impact plan

### Likely model changes
- [music_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py)
  - add profile toggle normalization
- [spectrum_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/spectrum_model.py)
  - add `timeline` and `lyricSettings` normalization

### Likely DB changes
- [music_migrate.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_migrate.py)
  - add lyric timeline table or columns
- [music_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_db.py)
  - CRUD for timeline artifact

### Likely service changes
- new lyric alignment service in `python_app/services/`
- optional hash/cache helper utilities

### Likely UI changes
- [music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py)
  - profile checkbox
- [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py)
  - load/save toggle + workflow status
- [settings_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/settings_view.py) or [video_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/video_view.py)
  - lyric style controls

### Likely renderer changes
- [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py)
- [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py)
- potentially [visualizer/main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/main.py) runtime payload handling if needed

---

## Risk assessment

### Performance risks
- Whisper alignment can be slow on long tracks.
- Word-level rendering must avoid per-frame text rerasterization.
- Large lyric payloads should be cached and reused.

### Architecture risks
- Shoving lyrics into `textOverlays` will create debt quickly.
- Storing song-specific timing in templates will corrupt reuse boundaries.
- Duplicated timing logic across preview/export can cause mismatches.

### UX risks
- Alignment failures must be visible but non-blocking.
- Users must understand that V1 is English only.

### Future-proofing risks
- If word timing is omitted now, lipsync migration becomes harder later.
- If no versioned timeline artifact exists, schema evolution becomes messy.

---

## Recommended next implementation slice

### Slice 1
- Add planning-approved schema for:
  - profile toggle
  - template lyric settings
  - dedicated timeline artifact table/model
- Add shared timeline evaluator skeleton
- Keep rendering disabled initially except for debug data flow

### Slice 2
- Integrate English Whisper alignment service
- Persist/reuse timeline artifact
- Render active line in preview/export

### Slice 3
- Add word highlight and future phoneme hooks
