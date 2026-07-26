# Follow-up (held) — Desktop GPU export / Analyzing audio

**Status:** **HELD** — do not prioritize until after production platform cutover  
**Date opened:** 2026-07-25  
**Related changelogs:**

- [`docs/changelog/2026-07-25-export-failure-diagnostics.md`](./changelog/2026-07-25-export-failure-diagnostics.md) (v0.4.2 logging)
- [`docs/changelog/2026-07-25-export-analyzing-audio-hang.md`](./changelog/2026-07-25-export-analyzing-audio-hang.md) (v0.4.3 analysis fix — built, validation paused)
- [`docs/changelog/2026-07-25-desktop-v0.4.3-sandbox-release.md`](./changelog/2026-07-25-desktop-v0.4.3-sandbox-release.md)

---

## Problem (1050 Ti + dual Xeon E5)

Progress export reaches **Creating OpenGL context**, then stalls on **Analyzing audio** (GPU ~idle). RTX 3060 machines are fine.

This step is **CPU `librosa` analysis**, not GPU render/NVENC. Dual-socket OpenBLAS oversubscription + full-rate analysis made the step appear hung forever. Parallel export workers (≥2) made it worse on 4 GB VRAM.

## What was already implemented (v0.4.3 installer exists)

| Change | Intent |
|--------|--------|
| Cap OpenBLAS/MKL/OMP threads during analysis | Avoid Xeon livelock |
| Analyze at 22.05 kHz | Faster STFT/onset/beat |
| Beat track from onset envelope | Skip second heavy pass |
| Progress: Loading → Spectrum → Onset → Beats | Visible movement in UI/logs |
| Force workers=1 on `low` GPU tier | No dual GL exporters on 1050 Ti |
| Richer exit-code logging (0.4.2) | Crash tails in Send diagnostics |

Installer path (already built):  
`camxora_python/dist/installer/CamxoraSetup-0.4.3.exe`

**Important:** This does **not** move rendering to CPU. GPU OpenGL + NVENC paths are unchanged; only the pre-encode audio analysis path was optimized.

## Still to validate later

1. Install 0.4.3 on the 1050 Ti PC; confirm Analyzing audio completes and encode starts.  
2. If still stuck: Send diagnostics and note last sub-step (Loading / Spectrum / Onset / Beats).  
3. Optional follow-ups if needed:
   - Run analysis **before** creating the OpenGL context  
   - Soft-timeout / skip beats on very long tracks  
   - Stop auto-video rapid retry on hard `exit code 1`  
   - Filter pygame banner from cancel error noise (partially done)

## Explicitly out of scope while prod cutover is active

- New desktop builds unless required for prod publish  
- Further audio-analysis refactors  
- Changing default export quality / NVENC settings for this issue  

When resuming, start from this doc + the 0.4.3 changelog, then re-test on the 1050 Ti hardware.
