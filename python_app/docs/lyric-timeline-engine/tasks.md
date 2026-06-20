## Lyric Timeline Engine

### Goal
- Replace the current narrow `textOverlays` limitation with a scalable timeline-based text/media system.
- Deliver V1 English auto-lyric overlay with audio-grounded sync using Whisper alignment.
- Preserve a clean path toward future word highlighting, phoneme timing, viseme tracks, and AI lipsync video.

### Phase 1 — Foundation
- [ ] Add profile-level feature toggle for `Enable English Lyric`
- [ ] Add profile model support for future lyric/lipsync toggles without polluting global settings
- [ ] Introduce a new timeline domain model separate from `textOverlays`
- [ ] Keep backward compatibility for existing `textOverlays`-based templates
- [ ] Add migration-safe normalization for new template/timeline fields

### Phase 2 — Data Model
- [ ] Define `timeline.tracks[]` root structure in template/runtime payloads
- [ ] Add track types for:
  - [ ] `static_text`
  - [ ] `lyric_lines`
  - [ ] `lyric_words`
  - [ ] `phoneme_track`
  - [ ] `marker_track`
- [ ] Define English lyric artifact structure with:
  - [ ] line-level timing
  - [ ] word-level timing
  - [ ] optional phoneme/viseme placeholders
- [ ] Decide persistence location for generated lyric timeline data (DB + export artifact)

### Phase 3 — Alignment Engine
- [ ] Add Whisper-based alignment service for English songs
- [ ] Accept source lyrics from `lyricsPolished` fallback `lyricsRaw`
- [ ] Align lyric text to produced song audio and emit line/word timestamps
- [ ] Add failure handling for:
  - [ ] missing lyrics
  - [ ] missing audio
  - [ ] alignment timeout/failure
  - [ ] poor confidence / unusable output
- [ ] Cache alignment results to avoid rerunning on unchanged song/audio pairs

### Phase 4 — Renderer Integration
- [ ] Create shared timeline evaluation helpers used by:
  - [ ] Qt preview (`components.py`)
  - [ ] GPU export renderer (`gpu_render.py`)
  - [ ] live preview (`run_live_preview`)
- [ ] Render active lyric line from the timeline at current playback/export time
- [ ] Add optional word-level highlight hook for future karaoke mode
- [ ] Keep visual styling configurable via template, not embedded in song data

### Phase 5 — UI / UX
- [ ] Add profile checkbox: `Enable English Lyric`
- [ ] Add template-side lyric style controls (position, font size, colors, stroke, shadow, safe area)
- [ ] Add preview visibility in Video workspace
- [ ] Show alignment status / errors in UI
- [ ] Clarify that V1 is English only

### Phase 6 — Persistence / Pipeline
- [ ] Persist lyric timeline artifact in a durable place linked to song/audio/template usage
- [ ] Pass runtime timeline payload into export renderer safely
- [ ] Ensure export and preview use the same timeline evaluation rules
- [ ] Plan versioning for future phoneme/viseme expansion

### Phase 7 — Future Expansion
- [ ] Add phoneme extraction / G2P for English
- [ ] Add viseme mapping layer for avatar or lipsync video engines
- [ ] Add multilingual strategy later (`Enable Other Language Lyric`)
- [ ] Add advanced karaoke styles and per-word highlighting

### Validation
- [ ] Existing templates with `textOverlays` still work unchanged
- [ ] English lyric profile can enable lyrics without affecting other profiles
- [ ] Preview and export show the same active lyric line at the same time
- [ ] Alignment result is reused when inputs have not changed
- [ ] Failure states degrade gracefully without breaking normal video export
