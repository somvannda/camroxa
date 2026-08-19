# Web music LRC/SRT Pro gate

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`

## Summary

LRC and SRT timed-lyrics downloads now require a paid subscription, matching MP3/WAV download rules.

## Notes

- LRC is fetched live from Suno `get-timestamped-lyrics` (word alignments → line-level LRC).
- SRT is converted from that LRC for video editors.
- Instrumental tracks remain excluded; alignments may take ~1 minute after generation completes.
