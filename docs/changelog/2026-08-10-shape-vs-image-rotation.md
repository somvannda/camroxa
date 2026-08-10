# Separate shape vs image rotation

## Summary
Spectrum **Shape rotation** spins the path + crop mask. Center image adds
**Image rotation** to spin the picture inside the crop without turning the path.

## Surfaces
- Desktop Studio Spectrum → Shape dial + Center image dial
- Logo shader: `logo_rot_rad` (content) vs `logo_mask_rot_rad` (mask)
