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
| Voice reference | “Add voice reference” modal | **Partial**: personas exist (`/studio/personas`), but voice clone/generate/apply endpoints are not proxied |
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

## 4. What is missing in the web stack

To make the "+" menu behave like Suno end-to-end, `platform_api` needs new proxy routes for:

1. `POST /v1/upload/init` → `POST /v1/upload/register` → `GET /v1/upload/status/:id`
   (reference audio / images).
2. `POST /v1/voice/generate|record|validate|apply|extend|phrase`, `GET /v1/voice/…`
   (voice library + cloning).
3. `POST /v1/mp4/generate` (video generation) + status.
4. A playlist-reference contract (no obvious musicapi endpoint; would need product
   mapping, e.g. playlist → style tags).

Already proxied today: generation (`/generate`), studio projects, extends/covers/stems,
personas, Studio audio uploads, generations/streams/downloads, lyrics drafts, plans.

## 5. Recommended next steps

1. **Audio attach — done** (upload, record, Extend, Cover; upload API returns 201).
2. **Voice** — expose `/v1/voice/*` through platform_api, then build the voice picker.
3. **Video** — expose `/v1/mp4/generate`, show progress via `/v1/task/:id`.
4. **Playlist reference** — decide the product mapping before building UI.
