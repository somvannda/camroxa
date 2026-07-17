# Debug Session: flying-glow-blur

Status: [OPEN]
Debug Server: http://127.0.0.1:7777/event
Log File: .dbg/trae-debug-log-flying-glow-blur.ndjson

## Symptom
- `Flying Glow` still looks blurry in the live preview after prior shader, pass, bloom, and DPR tuning.

## Expected
- `Flying Glow` should read as a sharp, solid surface in preview.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | Shared post-fx or blur compositor path is still active for `flying-glow` at runtime | High | Low | Rejected: runtime `postFxPlan` and mapped `postFx` are both `null` during reproduction |
| B | Live runtime layer data differs from the tightened source values | High | Low | Rejected: reproduction shows `glow: 0`, `blur: 0`, `blendMode: normal`, `solidBand: true` |
| C | Effective preview DPR is too low on the actual preview surface | Medium | Low | Weak support only: runtime `dpr` is `1`, but this matches the actual window/device state rather than a hidden blur path |
| D | Alternate or fallback renderer path is active | Medium | Medium | Pending |
| E | Final presentation uses a filtering path that softens the output texture | Medium | Medium | Not supported by current evidence; no post-fx path is active during reproduction |

## Plan
- Add runtime instrumentation only.
- Reproduce and capture evidence.
- Confirm or reject hypotheses from logs.
- Apply the minimal fix only after evidence is clear.

## Instrumentation Points
- `previewFrameRunner.ts`: live `flying-glow` frame state, layer data, DPR, quality tier
- `previewGpuDomainPreparation.ts`: post-fx plan and mapped WebGPU settings
- `webgpuSpectrumRenderer.ts`: actual presentation path, pixel size, post-fx state, sampler metadata

## Evidence Summary
- Reproduced with the live preview still visibly blurry at the wing edges.
- Runtime logs show:
  - `style: "flying-glow"`
  - `hasPostFx: false`
  - `postFxPlan: null`
  - `postFx: null`
  - layer state: `glow: 0`, `blur: 0`, `blendMode: "normal"`, `solidBand: true`
  - `webgpuReady: true`
  - `dpr: 1`
- Conclusion: the remaining blur is coming from the base `Flying Glow` wing shape itself, not from bloom, stale template data, or shared compositor post-fx.
