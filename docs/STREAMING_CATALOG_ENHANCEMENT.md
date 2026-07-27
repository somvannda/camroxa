# Music Streaming Catalog Enhancement

Feature spec for evolving `music.camxora.com` from a basic playback portal into a complete streaming experience — starting with **genre** and **Suno track cover art**, plus a roadmap for everything else still missing.

**Status:** PR1–PR4 largely complete (2026-07-17). Genre browse API + `music_web` pages live. Admin streaming catalog metadata UI + metadata sync live. **Music prompt genres** (migration `062`) fixes admin genre column showing full Suno production prompt text.
**Related:** `docs/MUSIC_STREAMING.md`, migration `043_streaming_catalog.py`, `060_ai_structure_and_streaming_metadata.py`, `062_music_description_genres.py`, `platform_api/services/streaming_upload_service.py`
**Product scope:** [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — **`platform_api`** (upload pipeline, public API), **`music_web`** (player/browse UI), **`admin_portal`** (catalog admin). Desktop client **`camxora_python`** is not required for streaming playback; Electron/`python_app` excluded.

---

## 1. Current state (baseline)

### What works today

| Layer | Capability |
|-------|------------|
| **Upload pipeline** | Suno callback → MP3 download → Backblaze B2 → `stream_tracks` / `stream_albums` |
| **Cover** | Album cover from Camxora image jobs, Suno clip art fallback, or profile logo |
| **Public API** | Home, album detail, search, genre browse, play URL (signed MP3) |
| **music_web** | Home + album page + search + genre browse + bottom player |
| **Admin** | Publish/hide/delete tracks & albums, retry failed upload jobs, metadata sync, catalog columns (genre, duration, cover) |
| **Prompt catalog** | Admin-managed `music_descriptions.genres` — short browse genres separate from production content |

### What is stored on `stream_tracks` today

- `title`, `lyrics`, `variant` (ok/alt), `storage_key`, `size_bytes`, `mime_type`
- `genre` (primary browse label), `genres` JSONB (full list from prompt catalog)
- `duration_seconds`, `track_number`, `cover_storage_key`, `suno_image_url`, `tags` (Suno clip tags)

### What is stored on `stream_albums` today

- `album_name`, `album_slug`, `channel_role`, `cover_storage_key`, `publish_status`
- `genre`, `genres` JSONB (primary + full list propagated from linked songs)

### Upstream data we already have (but do not propagate as genre display)

| Source | Field | Example use |
|--------|-------|-------------|
| `music_descriptions` | `genres` JSONB | **Primary genre source** for streaming catalog |
| `music_descriptions` | `content` | Production / mood notes — **not** used as browse genre |
| `suno_tasks` | `style` | Full Suno production prompt — **not** used as browse genre |
| Suno clip metadata | `tags` | Fallback browse tags when prompt genres empty |
| `songs` | `description_id`, `structure_id` | Link back to prompt catalog |

---

## 2. Goal

Make the public music portal feel like a real streaming product:

1. **Browse by genre** (minimum viable discovery)
2. **Show cover art reliably** — including when Camxora image jobs are off or failed
3. **Display duration** and basic track metadata in the player and lists
4. Lay groundwork for artist pages, lyrics, playlists, and admin metadata editing

---

## 3. Recommendation: metadata model

### Phase A — Ship with genre + Suno cover (delivered)

#### Album-level fields

| Column | Type | Source |
|--------|------|--------|
| `genre` | `VARCHAR(120)` | First entry from `music_descriptions.genres` via song link; fallback: Suno clip `tags` |
| `genres` | `JSONB` | Full list from prompt catalog genres |
| `description` | `TEXT` nullable | Optional admin edit; default from music description |
| `release_year` | `SMALLINT` nullable | Default: `EXTRACT(YEAR FROM published_at)` |

#### Track-level fields

| Column | Type | Source |
|--------|------|--------|
| `genre` | `VARCHAR(120)` nullable | Primary from prompt genres or Suno clip tags |
| `genres` | `JSONB` | Full prompt genre list |
| `duration_seconds` | `FLOAT` | Suno clip `duration` from record-info |
| `track_number` | `SMALLINT` nullable | `songs.batch_index + 1` at upload time |
| `cover_storage_key` | `VARCHAR(1024)` nullable | Per-track art when Suno provides distinct images |
| `suno_image_url` | `VARCHAR(1000)` nullable | Original Suno URL (audit/debug; 14-day TTL) |
| `tags` | `JSONB` | Suno clip `tags` only (not prompt genres) |

> **Design choice:** Genre lives on **both** album and track. Album genre is the browse key; track genre allows OK/ALT variants to differ later.

### Phase B — Discovery & UX (follow-up)

- Genre landing pages: `/genres/edm`, `/genres/lo-fi` — **done**
- Artist list + detail (`/artists`, `/artists/{id}`) — API exists, UI is stub
- Album browse page — API exists, UI is stub
- **Lyrics panel** on track/album page — show full lyrics (**Phase A decision: yes**)
- **Karaoke-style synchronized highlight** (line/word) while track plays — planned UX in `music_web` player (Phase B)
- Player: seek bar, duration display, queue, next/previous

### Phase C — Product features (later)

- User accounts, favorites, listening history → see [`MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`](./MUSIC_STREAMING_PORTAL_ENHANCEMENT.md) (shared Camxora auth; Phase 2+)
- Playlists (user + editorial)
- Explicit/content rating, ISRC, copyright line
- Analytics (plays, top tracks)
- HLS/adaptive streaming (see `docs/PRODUCTION_INFRASTRUCTURE_PLAN.md`)

---

## 4. Suno track cover art

### Problem

Today, cover art depends on **Camxora Auto-Gen Image**. When that is off or fails (common on sandbox), albums show placeholders even though Suno generates artwork.

The Suno API returns cover URLs per generated clip ([callback docs](https://docs.sunoapi.org/suno-api/generate-music-callbacks)):

```json
{
  "audio_url": "https://…/track.mp3",
  "source_audio_url": "https://…/track.mp3",
  "image_url": "https://…/cover.jpeg",
  "source_image_url": "https://…/cover.jpeg",
  "duration": 198.44,
  "tags": "electrifying, rock"
}
```

We parse audio URLs in `suno_audio_resolver.py` and now also persist image URLs, duration, and tags.

### Recommended cover priority

When a streaming upload runs (callback or reconcile):

```
1. Existing album cover from Camxora image job (keep current behavior)
2. Suno clip image_url / source_image_url → download → B2 cover.jpg
3. Channel profile logo (existing fallback)
4. Platform default placeholder
```

Per-track cover (optional in Phase A):

- Store `stream_tracks.cover_storage_key` when OK and ALT clips have different Suno images
- Album cover = thumbnail track’s art or first successful clip

### Image download notes

- Suno files are retained ~14 days — download and store on B2 promptly (same lesson as MP3 URLs)
- Re-use download helper pattern from `suno_audio_resolver.download_suno_mp3_bytes()` with image content-type validation
- Resize to JPEG max 1200px server-side before B2 upload (optional, saves CDN bandwidth)
- **License:** Confirmed OK — subscription-generated content is Camxora property; re-host covers on CDN same as MP3

---

## 5. Genre: where it comes from

### Resolved priority (upload + metadata sync)

```
1. music_descriptions.genres (via songs.description_id) — primary
   → stream_albums.genre / stream_tracks.genre = first genre
   → stream_albums.genres / stream_tracks.genres = full JSON array
2. Suno clip tags (comma-split) — fallback only
3. Do NOT use suno_tasks.style / full production prompt as genre
```

Normalize for browse URLs:

- Slug: `slugify(primary_genre)` → `eurodance`, `hands-up`
- Display: keep original casing from prompt catalog

### Batch → streaming propagation

At batch creation, description is already on each `songs.description_id`. When `StreamingUploadService._upload_mp3_variant()` runs:

1. Load `music_descriptions.genres` in `get_suno_stream_context()`
2. Write primary + full list to `stream_albums` and `stream_tracks`
3. Write `duration_seconds`, Suno clip `tags`, and cover art separately

### OK vs ALT tracks

**Intentional:** OK and ALT are separate published tracks (same song, different music variants). Each variant can belong to its own album. Genre browse does **not** dedupe by song.

---

## 6. Music prompt genres (admin catalog)

### Problem

The admin streaming catalog **Genre** column previously showed the full Suno `style` / production prompt (e.g. *"Eurodance and Hands Up track featuring…"*). Browse and admin need short, human-curated genre labels.

### Solution

Add `music_descriptions.genres` — a JSON array of short strings (e.g. `["Eurodance", "Hands Up"]`):

| Layer | Change |
|-------|--------|
| **DB** | Migration `062`: `music_descriptions.genres JSONB NOT NULL DEFAULT '[]'`; `stream_albums.genres`, `stream_tracks.genres` |
| **API** | `GET/POST/PUT /api/v1/prompts/descriptions` include `genres: string[]` |
| **Validation** | 1–60 chars each, max 10 genres, trim, case-insensitive dedupe |
| **Admin portal** | Multi-genre chip input on description form; genres column in prompts table |
| **Streaming** | Upload + metadata sync read prompt genres first; never style prompt |

**Follow-up:** Backfill genres on existing descriptions manually in admin (empty `genres` → Suno clip tags fallback until filled).

---

## 7. API & UI changes

### Public API (`streaming_public.py`)

Extend responses:

```typescript
// Album
{
  genre: string | null
  genres: string[]
  genre_slug: string | null
  description: string | null
  cover_url: string | null
  track_count: number
  total_duration_seconds: number | null
}

// Track
{
  genre: string | null
  genres: string[]
  genre_slug: string | null
  duration_seconds: number | null
  track_number: number | null
  cover_url: string | null   // track or album fallback
}
```

Endpoints (Phase A):

- `GET /public/streaming/genres` — list genres with album/track counts (unnest `genres` JSONB)
- `GET /public/streaming/genres/{slug}` — albums + recent tracks in genre

### music_web

| Page | Enhancement |
|------|-------------|
| Home | Genre chips row; show duration on track rows |
| Album detail | Genre badge, total duration, release year, full lyrics |
| Search | Filter by genre |
| Player bar | Duration + seek (Phase B); karaoke lyric highlight (Phase B) |
| `/genres/[slug]` | Genre browse page — **done** |

### Admin portal

| Enhancement | Priority | Status |
|-------------|----------|--------|
| Cover thumbnail column | A | Done |
| Genre column + metadata sync | A | Done (uses prompt genres after backfill) |
| Duration column | A | Done |
| Prompt description genres editor | A | Done |
| Bulk genre assign | B | Planned |
| Manual cover upload/replace | B | Planned |

---

## 8. Phased delivery plan

### PR1 — Suno metadata extraction (backend only) — **Done**

- Parse `image_url`, `duration`, `tags` from record-info + callbacks
- Persist on `suno_tasks`
- Unit tests in `test_suno_audio_resolver.py`

### PR2 — Streaming schema + upload pipeline — **Done**

- Migration: genre, duration, track_number, cover fields
- Upload Suno cover when no Camxora cover exists
- Populate genre from prompt genres / clip tags (not style prompt)

### PR3 — Public API + music_web genre browse — **Done**

- Genre list/detail endpoints
- Home genre chips + track duration display
- Album genre badge

### PR4 — Admin metadata editing — **Done**

- Catalog table columns, metadata sync, cover preview

### PR5 — Music prompt genres — **Done**

- Migration `062`, prompt CRUD, admin chip input, streaming genre priority fix

---

## 9. Complete streaming website checklist

| Category | Item | Status |
|----------|------|--------|
| **Metadata** | Genre (prompt catalog) | **Done** |
| | Duration | **Done** (new uploads + sync) |
| | Track number / disc order | **Done** |
| | Release date / year | Planned |
| | Description / credits | Partial (lyrics in DB) |
| **Artwork** | Suno cover fallback | **Done** |
| | Per-track art | Optional Phase A |
| | Admin cover upload | Phase B |
| **Discovery** | Search | Done |
| | Genre browse | **Done** |
| | Artist pages | API done, UI stub |
| | Album browse | API done, UI stub |
| | Playlists | Not started |
| | Related / recommended | Not started |
| **Playback** | Signed MP3 URL | Done |
| | Full lyrics display | Planned (Phase B UI) |
| | Karaoke lyric highlight | Planned (Phase B) |
| | Duration + seek | Not started |
| | Queue / autoplay | Not started |
| | Volume / repeat | Not started |
| **Social** | User accounts on portal | Not started |
| | Favorites / library | Not started |
| | Share links | Not started |
| **Admin** | Publish/hide/delete | Done |
| | Metadata edit + sync | **Done** |
| | Prompt genre curation | **Done** |
| | Analytics | Not started |
| **Legal** | DMCA / takedown workflow | Not started |
| | Explicit labeling | Not started |

---

## 10. Resolved decisions

1. **OK vs ALT as separate tracks** — Intentional. Same song, different music variants; each variant is its own published track and can belong to its own album. Genre browse does **not** dedupe by song.
2. **Genre taxonomy** — Free-text + slug for browse URLs. Admin curation enum later. **Not** using full Suno style/production prompt as genre display; use `music_descriptions.genres` instead.
3. **Lyrics on public site** — Show **full lyrics**. Phase B: karaoke-style synchronized highlight (line/word) while track plays in `music_web` player.
4. **Suno image license** — Confirmed OK. Subscription content is Camxora property; re-host covers on CDN same as MP3.

---

## 11. SLAI text models (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`)

Registered in `platform_api/ai/registry.py` under `SLAI_TEXT_MODELS` only (not image or music). Verified for all `TEXT_OPERATIONS` in `platform_api/ai/types.py`: `channel_name`, `channel_description`, `channel_keywords`, `channel_tags`, `lyric`, `title`, `album`.

Sandbox SLAI health probes may still return 401 if the API key is missing or invalid in that environment — an env configuration issue, not a routing/registry gap.

---

## 12. Key files to touch

| Area | Path |
|------|------|
| Music prompt genres | `platform_api/migrations/versions/062_music_description_genres.py`, `platform_api/repositories/prompt_repo.py`, `platform_api/routers/prompts.py`, `admin_portal/src/pages/prompts/` |
| Genre resolution | `platform_api/services/music_genre_utils.py`, `platform_api/services/streaming_upload_service.py`, `platform_api/services/streaming_metadata_sync_service.py` |
| Suno clip parsing | `platform_api/clients/suno_client.py`, `platform_api/services/suno_audio_resolver.py` |
| Callback | `platform_api/routers/callbacks.py` |
| Upload | `platform_api/services/streaming_upload_service.py` |
| Catalog DB | `platform_api/repositories/streaming_repo.py` |
| Public API | `platform_api/services/streaming_catalog_service.py`, `platform_api/routers/streaming_public.py` |
| Admin UI | `admin_portal/src/pages/streaming/catalog.tsx`, `admin_portal/src/pages/prompts/` |
| Public UI | `music_web/src/app/**`, `music_web/src/components/**` |
| Schema | `060_ai_structure_and_streaming_metadata.py`, `062_music_description_genres.py` |

---

## 13. Success criteria (Phase A)

- [x] Every new Suno batch with streaming enabled gets genre on album + tracks (from prompt genres or clip tags)
- [x] Albums without Camxora image jobs still get cover from Suno when available
- [x] `duration_seconds` populated for new uploads
- [x] music_web shows genre on album page and supports `/genres/{slug}` browse
- [x] Admin catalog shows genre, duration, and cover thumbnail
- [x] Admin prompt descriptions support short browse genres separate from production content
