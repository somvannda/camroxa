# Debug Session: manual-export-black-video [OPEN]

## Symptom
- Manual WebGPU export produces an MP4 with audio, but the video frames are black.

## Expected
- Manual WebGPU export should produce visible video frames matching the live preview.

## Hypotheses
- `H1`: The export host captures before the WebGPU scene actually draws, so ffmpeg receives all-black buffers.
- `H2`: The GPU readback contains real image data, but the pixel format/channel order passed to ffmpeg is incorrect.
- `H3`: Export reads only the WebGPU layer while visible content depends on composition layers not included in the captured frame.
- `H4`: The readback source stays stale or empty during manual export mode even though timestamps advance.
- `H5`: Exported frames are effectively transparent/zero-alpha, which encodes as black while audio remains valid.

## Evidence Plan
- Instrument the hidden export host around manual render, readback, and capture submission.
- Instrument the main-process frame stream to inspect whether frame buffers vary or are near-zero.
- Capture lightweight pixel statistics from a few sampled frames to distinguish empty, stale, and channel-mismatch cases.

## Status
- Open
- No business-logic fix applied yet.
- Next step: instrumentation only.
