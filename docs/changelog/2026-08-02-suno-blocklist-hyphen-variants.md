# Suno blocklist: catch spaced/hyphenated producer-tag variants

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/suno-blocklist-hyphen-variants`

## Root cause (Bass Reactor song overcharge)

Suno rejected producer tag **`lowlight`**. The submitted lyrics contained the hyphenated form **`low-light`** (`…the low-light endless bassline…`). The blocklist already had `lowlight → afterglow`, but matching used whole-word `\blowlight\b`, which does not match `low-light` or `low light`. Submit passed sanitize, Suno failed, auto-retry stacked song charges.

## Fix

`blocked_term_pattern()` allows optional space/hyphen/underscore between letters for block terms of length ≥ 3. Sanitize + risk scan use it on API and desktop mirrors.

## Files

- `platform_api/services/suno_lyrics_sanitize.py`
- `camxora_python/shared/lib/suno_lyrics_sanitize.py`
- `platform_api/tests/test_suno_lyrics_sanitize.py`
