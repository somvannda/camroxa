## UX

### Spectrum Toggle
- Location: Template settings → Spectrum tab.
- Control: `Enable Spectrum` toggle.
- Behavior: when OFF, spectrum ring/lines are not rendered (preview + export).

### Logo CD Spin
- Location: Template settings → Logo tab.
- Controls:
  - `Spin (CD)` toggle
  - `Direction`: Clockwise / Counter-clockwise
  - `Speed`: slider (slow → fast)
- Behavior: logo rotates smoothly around its center; export matches preview.

### Background Fit + Drag/Scale
- Location: Template settings → Background tab.
- Controls:
  - `Fit mode`: Cover / Contain / Original
  - `Scale`: slider (percentage)
  - `Reset transform` button
  - `Edit background in preview` toggle (drag mode)
- Behavior:
  - Background never stretches; fit mode preserves aspect ratio.
  - When edit mode is ON: dragging in preview moves background; wheel adjusts scale.
  - Export output matches the configured background transform.

