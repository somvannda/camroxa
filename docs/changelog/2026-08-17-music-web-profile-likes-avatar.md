# Music web profile polish, likes, avatar

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`

## Summary

- Profile page redesign: avatar upload, Free plan badge, Download App link, removed studio onboarding copy.
- Fix false "Starter subscription" for free users (pending/inactive subs no longer treated as active).
- Heart button works for created tracks via `web_music_likes` API.
- User profile photo upload (`POST /users/me/avatar`).

## Migration

- `099_user_avatar_web_music_likes`: `users.avatar_url`, `web_music_likes` table
