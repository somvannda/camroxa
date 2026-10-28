# Feature / API parity — Create + Library

Date: 2026-10-28

## 1. Link audit

42 unique links found on `/create` + `/library` (shell, rows, menus). All page links return
**200**. Only authenticated media URLs (`/api/v3/web-music/generations/…/download`) return
401 to an unauthenticated probe — they work in the browser because the session cookie is
sent.

No dead page links were found.

## 2. Button audit

Working:

- Tabs (Songs/Speech/Sounds), Simple/Advanced, credits menu, model menu (except the
  intentionally disabled "Create Custom Model"), attach pills, prompt `+` menu and all its
  submenus, Songs-to-generate, Styles tools (saved/shuffle/enhance), Lyrics tools
  (write/prompt/auto), More Options, Song Title, Save-to, new/rename workspace, Create.
- Workspace selector, plus/select/share, search, filters, sort, list, pager, row
  play/like/dislike/share/remix, downloads (MP3/WAV/LRC/SRT), More menu, publish, Studio.
- Rail: play, playlist add/create, like, downloads, remix/edit, delete.
- Library: all 9 tabs, search, filters, sort, quick pills, trash mode, pagination,
  playlist create/open/delete, workspace create, projects, covers, liked hooks, history.

Honest "not enabled" panels (no backend wiring in the web app):

| Feature | UI today | Backend status |
|---|---|---|
| Attach audio (upload/record) | **Implemented**: file picker, mic recording, then Extend / Cover | `POST /api/v3/web-music/studio/uploads` + `/studio/uploads/{id}/extend|cover` |
| Voice reference | **Implemented + verified**: pick a saved persona or create one from a song; attaches `persona_id` as a voice persona | `/studio/personas` + `persona_id`/`voice_persona`; source song must belong to a Voice-entitled account |
| Image attach | **Implemented**: upload to B2, stored as `reference_image_urls`, forwarded as `imageUrls` | `POST /api/v3/web-music/studio/images` |
| Video attach | **Implemented**: pick a finished song, render a cover-art MP4, download | `POST /api/v3/web-music/studio/videos` → internal `/internal/studio/video` |
| Playlist reference | **Implemented**: picker merges playlist track styles into Styles | Platform playlists + items APIs |

## 3. musicapi.camxora.com

Live and Suno-backed:

- `GET /` → “Camxora Music API” docs/dashboard (Next.js).
- `GET /health` → `{"ok":true,"accounts":10,"jobs":72}`.
- `GET /v1/credits`, `/v1/task/…`, `/v1/upload/status/…` → `401 {"error":"Unauthorized."}`
  without an API key, so the REST surface is live at **`/v1/*`**.

Documented endpoint families (`/docs`): music generation, extend, cover, mashup,
replace-section, remaster, add-vocals/instrumental, cover-image, upload-extend/cover,
lyrics, stems, WAV, MIDI, recovery, MP4 video, upload init/register/status, Suno voice,
credits, task, Studio projects.

**Do not call it from the browser.** It uses an API key (secret) and lives on a different
origin; the web app must go through `platform_api` (`/api/v3/web-music/*`) as it does now.

## 4. Remaining gaps

The "+" menu is now backed end-to-end except for full Suno-native voice enrolment:

1. `POST /v1/voice/record|validate|phrase` and the raw recording upload flow
   (the platform uses persona creation from a finished song instead).
2. `POST /v1/upload/init|register|status` for native reference-audio uploads
   (Studio audio now uses platform uploads + Extend/Cover).

Already proxied today: generation (`/generate`), studio projects, extends/covers/stems,
personas, Studio audio/image uploads, video rendering, generations/streams/downloads,
lyrics drafts, playlist style import, plans.

## 5. Recommended next steps

1. **Audio attach — done** (upload, record, Extend, Cover; upload API returns 201).
2. **Image attach — done** (B2 upload → `image_urls` → `imageUrls`).
3. **Video — done** (cover-art MP4 render + download).
4. **Playlist reference — done** (style import).
5. **Voice — verified** (saved persona attach + generation); create-from-song
   needs a Voice-entitled account that owns the source song.
