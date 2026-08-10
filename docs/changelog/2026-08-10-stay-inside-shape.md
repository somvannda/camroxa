# Stay inside shape + fixed-frame crop

## Summary
Center image **Mask** always crops to the spectrum **shape frame**. **Image size**
may be larger than the frame (zoom inside the crop). Optional **Stay inside shape**
caps Image size so it cannot exceed the frame.

## Surfaces
- Desktop Studio Spectrum → Center image
- Preview + export logo shader (`logo_frame_size_px` vs `logo_size_px`)
