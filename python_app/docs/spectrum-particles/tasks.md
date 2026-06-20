## Spectrum Particles v2 — Tasks

### Goal
Upgrade particles to support:
- Spawn gating (only spawn when audio reacts; trigger = kick/bass/both)
- Audio-reactive color blending (base → react color)
- Multiple particle sprite styles (Dot, Soft Glow, Ring, Spark, Bokeh)
While keeping the Web preview and MP4 export visually consistent.

### Scope
- Web spectrum editor preview (React canvas overlay)
- MP4 export renderer (Python ModernGL point sprite shader + particle config)
- Template schema + defaults + normalization (TS + Python)

### Milestones
- M1: Spec + UI wiring
- M2: Preview implementation
- M3: Export implementation
- M4: Verification + docs update

---

## M1 — Schema + UI Wiring
- [ ] Add new particle settings to template schema (TS store): trigger, threshold, react color, blend strength, style.
- [ ] Add defaults + normalization (TS) with backward compatibility.
- [ ] Add UI controls in spectrum editor panel (Particles section).

Acceptance
- UI shows new controls and updates template state without errors.
- Old templates (missing fields) still render as before.

---

## M2 — Web Preview (ParticlesCanvas)
- [ ] Implement spawn gating based on trigger + threshold.
- [ ] Implement audio-reactive color blend (base color → react color).
- [ ] Implement particle style rendering:
  - Dot
  - Soft Glow
  - Ring
  - Spark (cross sparkle)
  - Bokeh blob

Acceptance
- Toggling spawn gating visibly stops new particles until threshold reached.
- Color shifts on kick/bass as configured.
- Styles change shape in preview.

---

## M3 — Export Renderer (Python ModernGL)
- [ ] Extend `particlesSettings` parsing to read new fields (with safe defaults).
- [ ] Apply spawn gating to exported spawn rate (no births until audio threshold).
- [ ] Apply per-frame color blend for particles (`pt_col`).
- [ ] Extend point-sprite fragment shader to support styles via uniform `pt_style`.

Acceptance
- Export MP4 particles match preview behavior for gating, color blend, and styles.
- No performance regression for default settings.

---

## M4 — Verification + Documentation
- [ ] Manual test: preview settings update live.
- [ ] Manual test: export a short MP3 and visually confirm particle behavior.
- [ ] Regression test: export with particles disabled (no particles drawn).
- [ ] Update `DEVELOPMENT_LOG.md` with design decisions and impacted files.

---

## Risks / Notes
- Keeping preview and export identical requires shared math choices (threshold curve, blending curve).
- Shader changes must preserve existing default look (Dot) and not affect non-particle layers.
