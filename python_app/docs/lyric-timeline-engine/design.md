## Lyric Timeline Engine — Design

### Product Goal
Build a scalable timed text/media foundation for the video system instead of stretching the current `textOverlays` feature beyond its intended role.

V1 should provide:
- English-only automatic lyric overlay
- audio-grounded sync
- consistent preview/export behavior
- clean future support for karaoke highlighting and lipsync-driven video systems

### Why the current system is not enough
Verified current constraints:
- `textOverlays` is a small overlay list in the template model and is currently capped during normalization.
- Qt preview and GPU renderer each contain their own overlay playback logic.
- `textOverlays` is suitable for intros/outros/labels, not full-song lyric timelines.

### UX Principles
- Keep profile-level feature enablement separate from template-level visual styling.
- Keep song-specific timing data separate from reusable templates.
- Make failure non-destructive: if lyric alignment fails, video export should still work normally.
- Ensure preview and export show the same active lyric behavior.

### Ownership Model
#### Profile owns feature toggles
Examples:
- `Enable English Lyric`
- future `Enable Other Language Lyric`
- future `Enable LipSync Video`

Reason:
Different channels/profiles may want different publishing behavior.

#### Template owns presentation only
Template should define:
- lyric anchor/position
- font size
- text color
- stroke color/width
- shadow
- safe area
- line spacing
- optional karaoke highlight style
- optional max lines / wrapping behavior

Template should NOT permanently store song-specific timed lyric content.

#### Song / Render artifact owns timing data
The timed lyric artifact should belong to the generated song/render pipeline because it changes per song/audio output.

### Core Experience
#### When English lyric is enabled
1. A profile with `Enable English Lyric` generates or selects a song.
2. The system uses song lyrics (`lyricsPolished` fallback `lyricsRaw`) plus produced song audio.
3. Alignment service generates timed English lyric data.
4. Video preview shows the active lyric line while scrubbing/playing.
5. Exported video renders the same lyric line timing.

#### When alignment fails
- Show a clear status/error in UI.
- Do not break normal export.
- Allow export without lyrics.

### Timeline Model Direction
Use a dedicated timeline root instead of forcing everything into `textOverlays`.

Example conceptual structure:
```json
{
  "timeline": {
    "tracks": [
      {"id": "intro-title", "type": "static_text", "enabled": true},
      {"id": "lyrics-en-lines", "type": "lyric_lines", "enabled": true},
      {"id": "lyrics-en-words", "type": "lyric_words", "enabled": true},
      {"id": "phonemes-en", "type": "phoneme_track", "enabled": false}
    ]
  }
}
```

### V1 Rendering Scope
V1 should render:
- active lyric line
- optional next line hook later

V1 should prepare for but not fully implement:
- per-word highlighting
- phoneme visualization
- viseme-driven animation

### Future Lipsync Readiness
The system should be designed so that future pipelines can consume:
- line timing
- word timing
- phoneme timing
- viseme timing

This avoids rebuilding the system later when moving from lyric overlay to lipsync video.

### UI Areas Affected
#### Profile screen
Add feature toggle:
- `Enable English Lyric`

#### Video workspace
Add lyric style controls under template/video settings, such as:
- position
- font size
- primary color
- stroke/shadow
- safe area
- karaoke style options later

#### Status / workflow
Show lyric alignment state:
- not requested
- pending
- ready
- failed

### Non-Goals for V1
- multilingual alignment
- final phoneme-to-viseme engine
- full karaoke word highlight editor
- manual subtitle authoring UI
- avatar/lipsync video generation itself

### Success Criteria
- English lyric enablement is profile-specific
- lyric timing data is not hardwired into template reuse logic
- preview/export remain visually consistent
- architecture remains extendable for future lipsync and multilingual expansion
