# Preview P4.1 — HDR bloom design spike

**Date:** 2026-08-04  
**Status:** design only  
**Branch:** `docs/preview-p4-hdr-bloom-design`  
**Design:** [`docs/PREVIEW_HDR_BLOOM_DESIGN.md`](../PREVIEW_HDR_BLOOM_DESIGN.md)

## Summary

Documents the intended CapCut-class glow pipeline: draw into `RGBA16F`,
threshold/blur bloom, tonemap to SDR, then blit into the Qt preview FBO with
**alpha forced opaque** so frameless translucency does not see through.

No renderer code in this change. P4.2/P4.3 implement behind a flag later.
