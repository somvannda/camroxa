# Diamond spectrum path matches diamond mask

## Summary
Spectrum Shape **Diamond** used a 45° polygon rotation, which drew an
axis-aligned **square** path while Mask Diamond cropped a point-up ◇. Path
rotation is now 0 so bars and center-image crop share the same diamond.

## Surfaces
- Desktop Studio Spectrum Shape / Mask
- `visualizer/_spectrum_fast.py` diamond geometry
- Logo mask SDF size aligned to the frame
