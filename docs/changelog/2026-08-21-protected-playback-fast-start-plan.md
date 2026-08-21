# Protected playback fast-start plan (doc only)

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** docs

## Summary

Plan for Play to start after the first decrypted chunk on every device (Chrome/Edge MSE stays; Safari/iOS/Firefox use progressive Web Audio). No implementation in this change. Ciphertext-only on the wire; no MP3 blob URL.

See [`docs/PROTECTED_PLAYBACK_FAST_START.md`](../PROTECTED_PLAYBACK_FAST_START.md).
