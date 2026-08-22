# License session 500 on packaged play

**Date:** 2026-08-20  
**Branch:** `bugfix/license-session-play-source`

## Summary

Packaged play opens a license session that writes `play_source`, `search_query`, `country`, and `session_bind`. Migration `107` never added those columns, so `POST /web-music/licenses/sessions` returned 500 and the player showed License session failed.

## Product impact

Packaged catalog and Create tracks can start a license session and play.

## Files touched

- `platform_api/migrations/versions/108_license_session_audit.py`
