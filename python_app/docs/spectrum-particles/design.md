## Spectrum Particles v2 — Design

### Product Goals
- Give Boss more cinematic particles without overwhelming settings.
- Keep preview (editor) and export (MP4) visually consistent.
- Preserve current defaults so existing templates don’t change unexpectedly.

---

## User Experience

### Where It Lives
- Spectrum editor → Particles section (same place as current particle settings UI).

### New Controls (Minimal Set)
1) Spawn
- Spawn mode: Always / Audio-reactive only
- Trigger: Kick / Bass / Kick or Bass
- Threshold: 0.00 → 1.00

2) Color
- Base color (existing)
- React color (new)
- React strength: 0.00 → 1.00

3) Style
- Style dropdown:
  - Dot (existing)
  - Soft Glow
  - Ring
  - Spark (cross sparkle)
  - Bokeh

### Behavior Rules
- When Spawn mode = Audio-reactive only:
  - No new particles spawn until the selected trigger crosses threshold.
  - Existing particles continue to animate and fade out normally.
- Color blending:
  - Particles blend from Base → React color based on trigger intensity.
  - Strength controls maximum blend amount.
- Style:
  - Style changes only the sprite shape (not physics), so it’s safe and predictable.

---

## States
- Disabled: no particles rendered (preview + export).
- Enabled + Always: current behavior (baseline).
- Enabled + Audio-reactive: births gated by threshold.

---

## Accessibility / Clarity
- All values show reasonable ranges and avoid “mystery numbers”.
- Keep labels consistent between preview and export behavior:
  - Trigger uses the same audio metric in both environments.

---

## Non-Goals (for this iteration)
- Per-particle texture/image selection.
- Per-particle rotation/directional streak simulation.
- Complex randomness groups (seed, phase, etc.).
