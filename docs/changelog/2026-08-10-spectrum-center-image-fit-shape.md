# Center image fits spectrum shape

## Summary
Square center images can be clipped with an explicit Mask (square / circle / triangle /
hexagon / diamond / heart) or Match spectrum. Show center image toggles visibility.
Spectrum yellow outlines are the bar path — separate from the image mask.

## Fixes
- Reliable triangle/hex/diamond SDF crop (GPU smoke test)
- Resolve logo paths via Downloads fallback; status shows `logo=MISSING:…` when unloadable
- Selecting a center image stores an absolute path and defaults Size to 280

## Surfaces
- Desktop Studio Spectrum → Center image (Mask + Show)
- Preview + GPU export logo shader (`logo_mask_mode`)
