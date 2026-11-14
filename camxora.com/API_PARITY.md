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
| Video attach | **Implemented**: `+ → Video` opens a picker (MP4/MOV/WebM), uploads one reference clip, shows a removable chip, and sends `video_urls` with the generation | `POST /api/v3/web-music/studio/video-uploads` → `videoUrls` (max 1) via `/internal/...` |
| Video render | **Implemented**: pick a finished song on the song rail (`Video`), render a cover-art MP4, download | `POST /api/v3/web-music/studio/videos` → internal `/internal/studio/video` |
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
lyrics drafts, playlist style import, credit packs.

## 5. Recommended next steps

1. **Audio attach — done** (upload, record, Extend, Cover; upload API returns 201).
2. **Image attach — done** (B2 upload → `image_urls` → `imageUrls`).
3. **Video — done** (cover-art MP4 render + download).
4. **Playlist reference — done** (style import).
5. **Voice — done for saved personas and library songs**; raw sample
   Record → Trim → Phrase → Verify → Persona is implemented end-to-end through
   platform_api → musicapi but still needs a live microphone test.

## 6. Pre-deploy retest queue

- [ ] **Raw voice sample verification**
  - Source sample extraction is verified (internal route returned 200 for a real
    vocal MP3).
  - Test the full UI flow with a real microphone: Record → Trim → Use Voice →
    read the phrase → Verify → name → appears in My Voices.
  - Trim now selects a real start/end range and re-encodes the sample to WAV
    before upload; still needs a live mic test.
  - Verification/persona creation still depends on the Premier voice entitlement
    and available credits.
- [ ] **Voice persona creation after the Premier credit refresh**
  - On 2026-10-28 the Premier account `iamduke1987@gmail.com` had **0 credits**
    (plan renews around **2026-11-07**), so it could not generate new source songs.
  - Before production: confirm credits in `/admin/accounts`, generate a source song
    on Premier, create a persona from it, attach it in `+ → Voice`, and generate
    with `persona_id`. Confirm the result is `SUCCESS`.
  - If the pool still prefers `acct-2` for new generations, adjust routing so songs
    intended as voice sources are generated on the Premier account.
- [ ] **Demo persona cleanup**
  - `Wink Voice` (`provider_persona_id 735f11c4-df0c-44ed-ab55-b38113285c06`) was
    inserted manually to verify the pipeline. Remove or replace it with a
    UI-created persona before deploy.

## 4. Remaining feature gaps (2026-11-14)

Production is on hold: `camxora.com/` is built and verified locally only, and
`music.camxora.com` must stay unchanged. Every control that looked finished but
did nothing is tracked here; a gap is either implemented or removed — never left
as a stub.

| Surface | Control | Today | Next step |
|---|---|---|---|
| Studio | **YouTube Tutorials** | disabled | External channel does not exist; keep the honest disabled row. |
| Studio | Plugin **unverified** badge | shown | Verify the remaining plugin parameter maps against the reference, then drop the badge. |

Closed in this pass (2026-11-14):

- Learn → **Learning Center** now opens a real in-app tour (five steps) instead
  of a disabled row; the settings dialog no longer ships empty "Window
  management"/"Content" stubs.
- Library → **Audio + → Upload/Record** deep-links into the working Create
  uploader/recorder (`/create?attach=upload|record`) instead of a "not enabled"
  panel.
- Song menu → **Open in Editor / Open in Studio / Replace Section / Crop Song**
  now deep-link `?clip=<generation>&variant=&intent=`. The editor materialises
  that version as a one-track project (`lib/studio-from-clip.ts`) and shows the
  relevant hint, instead of opening an unrelated project or staying disabled.
- Create → **Sounds** is wired end to end: `POST /api/v3/web-music/sounds`
  charges through the music price, queues a `kind='sounds'` task on the shared
  queue, submits `POST /v1/sounds` in musicapi, and the existing poll/library
  surface renders the result. Migration `200_suno_task_kind` adds the discriminator.
  The price is intentionally the music price until the pricing table gets a
  dedicated `sounds` row (a product/pricing decision, not code).
- Song menu → **Use as Inspiration** now opens Create in advanced mode with the
  song's style filled in and empty lyrics, so the user writes their own song in
  that style (`/create?inspire=<id>`).
- **Speech** tab and **Hooks / Liked Hooks** library tabs were removed: no
  provider or backend exists for either, and leaving "coming soon"/"not enabled"
  surfaces in the app is the stub D-034 forbids. Re-add them when a provider is
  wired; the Library now lists Songs, Playlists, Albums, Workspaces, Studio
  Projects, Cover Art, Uploads, History and Trash.
- The Create model menu no longer offers the disabled "Create Custom Model"
  (Beta, 100 credits) row: there is no custom-model backend, so the menu lists
  only usable models. The Studio prompt bar's model menu drops the same row.
  "Sample this song" keeps its disabled row but now states the real blocker
  (clip-reference provider) instead of "coming soon".
- The Studio **master chain** no longer suggests Reverb: Suno's
  `masterSignalChain` carries only limiter/EQ/compressor, so a master reverb
  would be a local-only effect (D-034). The dock offers EQ and Compressor, both
  rendered by the master bus.
- Song menu → **Sample this song** is wired end to end: it opens Create with the
  source clip attached (`/create?sample=<id>&variant=`), the form shows a
  removable “Sampling …” chip, and submitting sends `sample_task_id` +
  `sample_variant`. The server resolves the owned clip's durable audio URL,
  stores it on the task (migration `201`), and forwards it as `audio_urls` to
  musicapi's agentic audio-reference path. No raw provider URL comes from the
  browser.
