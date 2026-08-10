# Studio Spectrum — free drag, local palette, bar controls, preview fidelity

## Changes
- Spectrum preview drag stays enabled whenever spectrum is active (not only when the Spectrum node is selected), with free overscan (±2.0) instead of edge clamping.
- Spectrum Material card has its own **Palette** (inherits global when set to Inherit).
- Shape card adds **Bar count**, **Mirror** (shape default / full / half), **Peak caps**, and **Solid band**.
- Circle “zoom in/out” from Pulse/Breathing fixed: animation scale drives bar height/width only, not ring radius.
- Preview targets ~120 Hz (`CAMXORA_PREVIEW_HZ`) with `swapInterval(0)`. Optional 10-bit request via `CAMXORA_PREVIEW_DEEP_COLOR=1` (falls back to 8-bit; ~16.7M colors already).

## Notes
- True guaranteed 120 Hz + 10-bit HDR still depends on GPU, OS compositor, and display. Preview uses 8-bit RGBA by default (millions of colors). Existing HDR bloom remains opt-in via `CAMXORA_PREVIEW_HDR_BLOOM=1`.
