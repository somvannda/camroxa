# Spectrum Motion Zoom (Video)

## Summary

Spectrum inspector now has a **Motion** control (None / Zoom) plus Zoom Strength
and Reaction Speed, matching the Logo motion idea. When Zoom is on, the spectrum
ring radius and bar height pulse with bass/kick.

Closed circle/ring gradients now use **spatial melt** (same as Studio) so the
first and last palette stops blend at the join instead of showing a hard seam.

## Surfaces

- Video Spectrum inspector (`spectrum_inspector.py`)
- Draft / save (`audioSettings.spectrumMotionMode`, `spectrumMotionZoomStrength`,
  `spectrumMotionSpeed`)
- Preview + export (`visualizer_video`)
- Color helpers (`spectrum_color_engine.py` spatial melt)

## Notes

- Defaults to Motion None (no behavior change for existing templates).
- Reaction Speed default is `3` (higher = snappier). Do not use Motion Smoothing
  for zoom lag — that dial only affects FFT bar smoothing.
- Studio engine is unchanged for motion; it already had spatial melt.
