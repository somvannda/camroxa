# Studio Spectrum — layers, sections, size, draw order, preview drag

## Changes
- Multi-ring `composition.spectrum.layers` with Add/Dup/Delete/reorder in Inspector.
- Separate Shape / Material / Animation cards with contextual knobs.
- Overall `sizeScale` (Size slider + mouse wheel in preview when Spectrum is selected).
- Full-preview drag for spectrum/logo position (Video-style edit modes).
- Preview paint order: particles → atmosphere → **spectrum** → logo → text (spectrum above fog/particles).

## Notes
- Export GPU path still draws particles after spectrum in this pass; preview order is the Studio-facing source of truth for now.
