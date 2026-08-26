# API v3 cutover — emit and serve v3 only

## Summary

Cutover means clients and the API use `/api/v3` only. Stream, download, HLS, avatar, desktop-release, Suno callback, and YouTube OAuth URLs are now built on `/api/v3`. Nginx streaming and WebSocket locations are `/api/v3` only (no leftover `/api/v1` accept).

`camxora` (Electron) and `python_app` were left on v1 as requested.

`/api/v1` routers stay dual-mounted so in-flight Suno jobs and an already-registered Google OAuth redirect do not 404 until those dashboards are updated. We do not send new traffic there.

## Ops

- Add Google OAuth redirect `https://api.sandbox.camxora.com/api/v3/youtube/oauth/callback` (and production when shipping).
- New Suno tasks callback to `/api/v3/callbacks/suno`.
