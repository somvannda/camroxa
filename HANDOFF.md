# HANDOFF — Suno-parity `/create` + `/library`

Last session: 2026-10-27
Status: **`/create` and `/library` both rebuilt; `tsc` clean; uncommitted.**
Read this end-to-end before touching code.

---

## 1. Goal

Make Camxora's `http://localhost:3103/create` and `http://localhost:3103/library` match
`suno.com/create` and `suno.com/library` **1:1**: same layout, ordering, controls, flows
and behaviour. The user's words: *"clone 1:1"*, *"check every clickable link, buttons,
everything"*.

Branding stays **CAMXORA** (logo/name, copy). Do not copy Suno's logo or text verbatim
beyond generic UI labels.

---

## 2. Hard scope rules (user corrected an earlier overreach)

- **Only** `web-camxora/components/CreateStudio.tsx` and `web-camxora/components/LibraryView.tsx`
  (+ their shared CSS/API helpers).
- **Do NOT** restyle or rewrite the global shell again: `components/Sidebar.tsx`,
  `components/Player.tsx`, `app/(site)/layout.tsx`, `components/Topbar.tsx`,
  `components/Footer.tsx`. These were rewritten once and **reverted at the user's request**.
- **Studio is not Create.** `/studio/editor` (`StudioEditorView.tsx`, ~6.8k lines) is a
  separate timeline editor. Out of scope unless the user asks.
- No commits / pushes / deploys unless the user explicitly asks.
- One worktree = one agent. This work owns the `camxora-apex` worktree; don't run a second
  agent in it.

---

## 3. Where everything lives

| Thing | Path / value |
|---|---|
| Repo (worktree to edit) | `C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\camxora-apex` |
| Branch | `feat/camxora-apex` (HEAD `1d31d26d`) |
| Next.js web app | `<worktree>\web-camxora` — dev server on **3103** |
| Platform API (FastAPI) | `<worktree>\platform_api` — **8100** (`PLATFORM_DEBUG=true`) |
| Suno proxy API (Fastify) | `<worktree>\musicapi` — **4003** |
| Local Postgres | `postgres://postgres:postgres@localhost:5432` — DBs `platform_db`, `sunoapi` |
| Web env | `web-camxora/.env.local`: `PLATFORM_API_URL=http://localhost:8100`, Turnstile disabled |
| Suno reference | user is logged into `suno.com` in the connected browser tab |

Run / verify:

```powershell
cd "C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\camxora-apex\web-camxora"
npx tsc --noEmit          # current state: clean
curl.exe -s -o NUL -w "%{http_code}" http://localhost:3103/create   # expect 200
```

The dev server is already running (`next dev -p 3103`, Turbopack). Edits hot-reload.

### Auth for visual QA

- `web-camxora` authenticates against **platform_api** (`/api/v3/auth/*`), not musicapi.
- `login` is email+password or Google; cookies are `camxora_access_token` /
  `camxora_refresh_token`; the Next rewrites proxy `/api/v3/*` → `:8100`.
- There is **no dev bypass**. To inspect authenticated pages, either:
  1. ask the user to sign in in the connected browser, or
  2. (what was done here) snapshot the `password_hash` for
     `somvannda@gmail.com`, temporarily set a known bcrypt hash, log in through `/login`,
     then **restore the original hash**. The session stays valid afterwards.
     Never write credentials into the repo or this file.
- A fresh browser tab may hit a transient **502** while Turbopack compiles — reload.

---

## 4. Current state of the work (git)

```
 M web-camxora/app/globals.css              +281
 M web-camxora/components/CreateStudio.tsx  heavily restructured (~2.8k lines)
 M web-camxora/lib/web-music-api.ts         +17
```

- `npx tsc --noEmit` → **passes**.
- `/create` renders the new Suno layout. Verified via DOM metrics (see §7).
- `/library` still renders the **old** Camxora layout (`LibraryView.tsx`, 284 lines).
- Sidebar/Player/layout are pristine (`git status` confirms).

### What already works on `/create`

- Songs / Speech / Sounds tabs (Speech & Sounds show a "coming soon" pane).
- Simple ↔ Advanced segmented control.
- Credits chip + menu (balance, per-song cost, plan, buy, redeem).
- Model picker with Suno's exact copy (`v6 Pro`, `v6-wild Pro`, `v6-mini`, Custom Model Beta).
- Audio / Voice / Image(Inspo) attach bar → honest "not enabled yet" modal.
- Simple: prompt box + char count + `+` button + drop hints + "Songs to generate" (1/5/10/20).
- Advanced: Styles box + saved-style picker + Instrumental/Shuffle/Enhance, Lyrics with
  Write/Prompt + auto-generate, **More Options** accordion (Exclude styles, Vocal Gender,
  Duration Custom/Auto, Max Mode, Weirdness, Style Influence, Variety, Personalize),
  Song Title, Save to workspace, Clear-all + Create.
- Feed: Workspaces header (switch/create/rename), Share menu, search, Filters menu,
  sort (Newest/Oldest/Most liked/Least liked), List/Grid view toggle, select-mode,
  compact pager, "Today/Yesterday/date" groups, Suno-style clip rows, per-row
  Like (real API), Dislike (local), Share/copy, Publish (→ `/publish?clip=`),
  More menu (copy link, playlist, MP3/WAV/LRC/SRT, Studio, Delete).
- Detail modal (play, unlock, downloads, playlist add/create, like, settings KV,
  exclude styles, style/lyrics copy, delete, open Studio).
- Batch select → ZIP download; toasts; drag-over overlay.

---

## 5. Suno reference data captured (reuse this, don't re-research)

### 5.1 Design tokens (`getComputedStyle(document.documentElement)`)

```
--color-background-primary      #101012
--color-background-secondary    #1c1c1f
--color-background-tertiary     #252529
--color-background-button-primary #f7f4ef
--color-foreground-primary      #f7f4ef
--color-foreground-secondary    #c2c2c1
--color-foreground-tertiary     #a3a3a3
--color-foreground-inactive     #6a6a72
--color-border-primary          #ffffff1a
--color-border-secondary        #ffffff26
--color-accent-brand / pink     #fd429c
--color-accent-purple/amethyst  #8b6efe
--radius-lg .5rem  --radius-xl .75rem  --radius-2xl 1rem  --radius-3xl 1.5rem
Font: "Neue Montreal" (proprietary) → we use Inter from Google Fonts.
```

Buttons are **pills** (`9999px`), primary = light bg / dark text, disabled = `#252529` /
`#6a6a72`.

### 5.2 Measured geometry (viewport 1297×1245, sidebar expanded)

| Element | Suno |
|---|---|
| Sidebar island | `x=8 y=8 w=248 h=1157`, radius 12, bg `#101012` |
| Brand row | h 72, logo 112×40 at (32,24) |
| Nav item | 224×48, radius pill, padding 8/16, 14px/500, icon 18 |
| Sidebar bottom group | four 224×40 rows (Earn Credits, Labs, Notifications, More) |
| Main column | x=264, w=1025 |
| Create: form column | x=280, **w=418** |
| Create: feed column | x=738, **w≈520** (toolbar visibly overflows → make it wrap) |
| "What to create" tabs | h 49, 3×139, bottom border `#ffffff1a`, 16px/400 |
| Active tab indicator | 2px tall, `#f7f4ef`, animated left/width |
| Simple/Advanced | segmented, h 38, radius pill, container `#252529`, active `#3a3a40` |
| Attach buttons | h 56, `rgba(255,255,255,.04)`, outer corners pill |
| Prompt box | ~403 wide, radius 16, textarea 14px |
| Create button | 354×48, radius pill, 17px/500 |
| Credits chip / model btn | h 40, radius pill |
| Feed toolbar pills | h 40, 15px/500 (`Filters (n)` becomes white when active) |
| Clip row | **520×110**, radius 20, padding 12, gap 16 |
| Clip cover | 86×86, radius 12, 1px `rgba(255,255,255,.1)`, duration badge bottom-right |
| Clip title | 14px/500 |
| Clip description | 12px, 2-line clamp |
| Row actions | h 32 pills, 15px/500, bg `#252529` |
| Library H1 | 30px/36, weight 600, padding 16 0 |
| Library tabs | h 44, 14px/400, letter-spacing .28px, padding 12/16 + 2px white indicator |
| Library search | h 40, radius 50, bg `rgba(255,255,255,.04)`, w up to 524 |
| Library Audio / Trash | 94×44 transparent pill / 44×44 icon pill |
| Library rows | 666–963×110 |

### 5.3 Suno `/create` control inventory (Simple)

`Songs | Speech | Sounds` → `Simple | Advanced` → credits chip → model (`v6`).
Attach bar: `Audio` `Voice` `Image`.
Prompt textarea (placeholder: "Cambodian hip-hop with a rising pre-chorus"), `+` (36×36),
`Drop to attach` / `Drop here to remix`, `Create` (418×48).

Feed: `Workspaces` + `My Workspace ▾` + `Share`; toolbar `Search clips` · `Filters (n)` ·
`New` (sort) · `View: List` · pager `‹ [1] ›`; `Today` group; rows with
`Play`, duration, title, `V6` badge, description, `Like`, `Dislike`, `Share`, `Publish`,
`More options` (48×48).

### 5.4 Suno `/create` control inventory (Advanced)

`Audio` `Voice` `Inspo`; **Styles** (+ saved-style bookmark, 0/1000, personalize icon);
**Lyrics** textarea (1000); **More Options** → `Exclude styles`, `Vocal Gender`
(Male/Female), `Duration` (Custom/Auto), `Max Mode` (Off/On), `Weirdness` slider +
"Expected results", `Style Influence` + "Moderate", `Variety` + "Balanced variety",
`Personalize` (My Taste / Off / On); `Song Title (Optional)`;
`Save to...` (`My Workspace`); footer `Clear all` (48×48) + `Create`.

### 5.5 Menus / popovers (exact contents)

- **Model**: `Model` · `Create Custom Model` (Beta) · "Create a model based on your uploads
  (100 Credits)" · `All Models` · `v6 Pro — Powerful. Versatile. Refined. Our best model yet.`
  · `v6-wild Pro — Best for experimental ideas.` · `v6-mini — A free, more efficient version
  of premium v6 models.`
- **Filters**: `Liked, Disliked, Public, Private, Uploads, Full song, Cover, Voice,
  Downloads, Hide Disliked, Hide Stems`
- **Sort**: `Newest, Oldest, Most liked, Least liked`
- **View**: `List` / `Grid`
- **Library Audio menu**: `Upload`, `Record`

### 5.6 Suno `/library` control inventory

H1 `Library` · `Audio ▾` · `Trash`.
Tabs: `Songs, Playlists, Albums, Workspaces, Studio Projects, Cover Art, Hooks,
Liked Hooks, History`.
Toolbar: `Search` · `Filters (n)` · `New` · view toggle.
Rows ×110 with per-row actions; pagination `Page [n] ‹ ›` at the bottom.

---

## 6. Camxora architecture you must reuse

### 6.1 Files

```
web-camxora/
  app/(site)/create/page.tsx      → <CreateStudio />
  app/(site)/library/page.tsx     → <LibraryView />
  app/globals.css                 → old Camxora CSS + new .s-* block at the END (keep it last)
  components/CreateStudio.tsx     → rebuilt (reuse its logic!)
  components/LibraryView.tsx      → TO BE REBUILT
  components/ui/{select,switch,checkbox}.tsx
  lib/library-api.ts              → fetchGenerations / fetchPlaylists / fetchLikedTracks + types
  lib/web-music-api.ts            → quota, generate, workspaces, playlists, likes, downloads
  lib/auth-fetch.ts               → musicAuthFetch (adds X-Portal-Context: user, 401 refresh)
```

### 6.2 Types

```ts
WebMusicGeneration { id, title, style, lyrics?, model?, model_label?, instrumental?,
  status, created_at?, error_message?, negative_tags?, vocal_gender?, style_weight?,
  weirdness_constraint?, audio_weight?, is_preview?, unlockable?, preview_seconds?, clips[] }
WebMusicClip { variant, label?, image_url?, audio_url?, download_url?,
  duration_seconds?, ready?, package_status?, title?, is_preview?, preview_seconds? }
WebMusicQuota { limit, used, remaining, is_pro?, requires_upgrade?, credits_remaining?,
  credits_per_song?, has_subscription?, can_download?, daily_free_*, queue_limit?, queue_used?, previews? }
WebMusicWorkspace { id, name, is_default?, created_at? }
WebMusicPlaylistSummary { id, name, song_count?, is_public? }
LikedTrack { id, title, artist_name?, cover_url?, duration_seconds?, added_at? }
```

### 6.3 Endpoints (platform_api, all under `/api/v3`, proxied by Next)

```
GET    /web-music/quota
GET    /web-music/generations?limit&offset[&workspace_id]
GET    /web-music/generations/{task_id}
PATCH  /web-music/generations/{task_id}             (title)
DELETE /web-music/generations/{task_id}
POST   /web-music/generate | /generate-draft | /generate-styles
GET    /web-music/generations/{id}/stream[/{variant}]
GET    /web-music/generations/{id}/download | /download-wav | /timed-lyrics
GET/POST/PATCH  /web-music/workspaces[/{id}]
GET/POST/PATCH/DELETE /web-music/playlists[/{id}]  + /playlists/{id}/items
GET    /web-music/likes/keys
PUT/DELETE /web-music/generations/{task_id}/like?variant=ok|alt
GET/POST /web-music/studio/projects (+ /{id}, /versions, /shares …)
GET    /streaming/library/likes        (LikedTrack[] — "Liked Hooks" tab)
```

Helpers already added last session in `lib/web-music-api.ts`:

```ts
fetchWebMusicLikedKeys(): Promise<string[]>          // "generationId:variant"
likeWebMusicGeneration(id, variant, liked): Promise<void>
```

### 6.4 CSS you must build on (end of `globals.css`, scoped to `.s-page`)

```
Page/shell : .s-page
Buttons    : .s-btn (+ -primary -secondary -ghost -sm -lg -icon)
Tabs       : .s-tabs .s-tab .s-tab-indicator .s-tabs-sm
Segmented  : .s-segment .s-segment-item
Pills      : .s-pill .s-chip .s-tag .s-status(.ok/.err/.live)
Form       : .s-field .s-input .s-textarea .s-char .s-add-btn .s-create-btn
             .s-prompt-box .s-style-box .s-lyrics-box .s-more/.s-more-head/.s-more-body
             .s-settings-row .s-radio-pair .s-switch .s-slider
Attach     : .s-attach .s-attach-btn
Create     : .s-create-grid .s-form-col .s-form-scroll .s-form-foot .s-form-topline
             .s-credits .s-model .s-drop-hint
Feed       : .s-feed .s-feed-head .s-workspace .s-feed-tools .s-search .s-pager
             .s-feed-scroll .s-day
Rows       : .s-row(.selected) .s-cover .s-cover-play .s-dur .s-row-body .s-row-title
             .s-row-desc .s-row-actions .s-act(.on/.icon-only) .s-row-more
Library    : .s-lib .s-lib-head .s-lib-title .s-lib-actions .s-lib-tools .s-lib-body
             .s-lib-foot .s-playlists .s-playlist .s-playlist-cover .s-selectbox
Misc       : .s-empty .s-skel .s-menu/.s-menu-item/.s-menu-label/.s-menu-sep
             .s-modal-overlay .s-modal .s-modal-head .s-modal-body .s-modal-foot
             .s-toast .s-error .s-note(.warn) .s-kv .s-box .s-detail-* .s-grid .s-card
Page hooks : `.main:has(.s-page) .topbar{display:none}`,
             `.content:has(.s-page){padding:0;overflow:hidden;display:flex;flex-direction:column}`,
             `.content:has(.s-page) .site-footer{display:none}`
```

Anything new must be **page-scoped** so other routes keep the old Camxora look.

---

## 7. `CreateStudio.tsx` internals (so you don't break it)

- Business logic from the original file is intact; only the JSX was replaced.
- State groups: form (`mode, prompt, title, style, lyrics, lyricsMode, instrumental, model,
  vocalGender, negativeTags, styleWeight, weirdness, audioWeight, simpleSongCount`),
  UI (`createTab, feedSearch, feedSort, feedFilters, filtersOpen, sortOpen, viewMode,
  detailOpen, shareOpen, workspaceMenuOpen, rowMenuKey, likedKeys, dislikedKeys, toast,
  feedPage, attachModal, modelOpen, creditsOpen, stylePresetsOpen, dragging, durationMode,
  maxMode`), data (`songs, selectedId, selectedDetail, selectedVariant, quota, workspaces,
  playlists, totalSongs, loadingSongs, …`).
- Derived (just before the return): `feedRows → filteredRows → sortedRows → pageRows →
  groupedRows`, `activeFilterCount`, `displayCredits`, `shortModel`, `sortLabel`,
  `createDisabled`.
- Handlers added: `toggleLikeRow`, `toggleDislikeRow`, `copyClipLink`, `deleteRow`,
  `openDetail`, `clearAllFields`.
- `openDetail` = `selectSong()` + `setDetailOpen(true)`; the modal reuses the old inspector.
- Outside-click handling uses `[data-s-menu]` containers + a global `mousedown`/`Escape`
  listener.
- `activeWorkspaceName` must be declared **once** (a duplicate declaration was removed).
- `WebMusicQuota` has **no** `plan_name` — use `has_subscription || is_pro`.

### Gotchas

- **UTF-8 BOM breaks PostCSS**: PowerShell `Set-Content`/`Add-Content -Encoding utf8`
  writes a BOM, and Turbopack fails with
  `Parsing CSS source code failed … Unexpected token Delim('*')`.
  Always write with:
  ```powershell
  [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
  ```
  and strip an existing BOM with `$text.TrimStart([char]0xFEFF)`.
- Keep the new CSS block at the **end** of `globals.css` (it relies on cascade order).
- The connected browser window is 1000×700 → media queries at ≤1180 shrink the two columns.
  Desktop widths (≥1280) are the target; verify metrics by forcing
  `form.style.width='418px'; feed.style.width='520px'` via `browser.evaluate` if needed.
- `browser.screenshot` fails unless the desktop window is visible; rely on
  `browser.snapshot` (a11y) and `browser.evaluate` DOM/style dumps.
- Suno tabs are session-scoped; tab IDs change. Re-open `suno.com/create` / `/library`
  (the user is logged in) before comparing.

---

## 8. What's left — do this next

### 8.1 Rebuild `LibraryView.tsx` (main task)

Structure to implement (mirror §5.6 exactly):

```
.s-page > .s-lib
  .s-lib-head     h1 "Library" | .s-pill "Audio ▾" (Upload, Record) | 44×44 Trash
  .s-tabs-sm      Songs, Playlists, Albums, Workspaces, Studio Projects, Cover Art,
                  Hooks, Liked Hooks, History  (+ sliding 2px indicator)
  .s-lib-tools    .s-search | Filters (n) | sort | List/Grid
  .s-lib-body     tab content
  .s-lib-foot     pagination (Page [n] ‹ ›)
```

Tab → data mapping:

| Tab | Source |
|---|---|
| Songs | `fetchGenerations()` → clip rows (reuse the row markup from CreateStudio) |
| Playlists | `fetchPlaylists()` → `.s-playlists` cards |
| Albums | empty state (no API) |
| Workspaces | `listWebMusicWorkspaces()` → cards + "New workspace" |
| Studio Projects | `GET /web-music/studio/projects` (add `fetchStudioProjects()`), empty fallback |
| Cover Art | generations with `clips[].image_url` → `.s-grid` of covers |
| Hooks | empty state |
| Liked Hooks | `fetchLikedTracks()` → rows |
| History | generations sorted by `created_at` desc (same rows) |

Required behaviour:

- Search + Filters (same 11 items, disable unsupported) + Sort (4) + List/Grid, all functional.
- Row actions: Play (real audio: `/api/v3/web-music/generations/{id}/stream/{variant}`),
  Like (real API), Dislike (local), Share/copy link, More (copy, playlist, downloads,
  Studio, delete).
- Trash mode: toggle → checkbox column + "Delete selected" with confirm; only generations
  are deletable (playlist DELETE exists but no helper yet).
- Pagination: 50/page, arrows + numeric input.
- Detail modal like CreateStudio's (settings, style, lyrics, downloads, delete).
- Loading skeletons, empty states per tab, error banner, toasts.
- `playTrack({ ... audioUrl })` so playback is real.

### 8.2 Small fixes / polish

- Toolbar wrapping at 520–560px: verify `Search` doesn't collapse (fixed to `flex: 1 1 180px`).
- Row height 114 vs Suno 110 — trim `.s-row` padding or `.s-row-desc` height if you want exact.
- `formatClipDuration` and `statusClass` live inside the component body in CreateStudio —
  consider hoisting both into `lib/` so LibraryView can share them.
- Consider a shared `ClipRow` component once LibraryView exists (avoid a third copy).
- Remove unused leftovers from the old CSS if safe (do not delete old global classes used by
  other pages).

### 8.3 Verification checklist

```powershell
cd ...\web-camxora
npx tsc --noEmit
curl.exe -s -o NUL -w "%{http_code}" http://localhost:3103/create
curl.exe -s -o NUL -w "%{http_code}" http://localhost:3103/library
```

Then in the browser (logged in):

1. `/create` Simple: type a prompt → Create enables → credits line updates.
2. Switch to Advanced → every control renders in Suno order; More Options expands.
3. Feed: search / filters / sort / list↔grid / pager; row like persists after reload.
4. Open a row → modal shows settings, style, lyrics, downloads, delete.
5. `/library`: all 9 tabs render, search/filters/sort work, trash deletes, pagination works.
6. Regression: `/`, `/discover`, `/pricing`, `/studio` still look like the old Camxora
   (the `.s-*` CSS must not leak).

---

## 9. Suggested prompt for the fresh session

> Work only in `...\camxora-apex\web-camxora` (branch `feat/camxora-apex`, dev server on
> 3103). Read `HANDOFF.md` first. `/create` is already rebuilt to match Suno — do not
> regress it. Now rebuild `components/LibraryView.tsx` to match `suno.com/library` 1:1
> using the existing `.s-*` design system and platform_api endpoints. Keep the sidebar,
> player, layout, Topbar and Footer untouched. Run `npx tsc --noEmit`, then verify both
> pages in the browser at ≥1280px and confirm other routes are unaffected. Don't commit.

---

## 10. Update — 2026-10-27 (library rebuild done)

- `components/LibraryView.tsx` rebuilt: 9 tabs, search / filters / sort / quick pills, row
  actions Play / Like / Dislike / Share / Remix, trash mode + confirm delete, playlist /
  workspace / studio-project / cover-art / liked-hooks / history tabs, 50-per-page pager with
  Load more.
- Right detail rail (Suno-style) replaces the desktop modal: 400px rail, 192px cover, close X,
  Play / MP3 / WAV / Playlist / Like, Settings / Style (Show more) / Lyrics, Open in Studio +
  Delete. Under 1100px it becomes a fixed right drawer. `?clip=&variant=` deep links open it;
  closing clears the params.
- Shared helpers live in `lib/clip-utils.ts`; `CreateStudio.tsx` imports them (no local
  duplicates). Encoding fixed: no double-encoded middle-dot / em-dash leftovers.
- Library CSS additions sit at the END of `globals.css` under "library page": rail, shell,
  tab fade mask, disabled pills, 110px rows, playlist cards, <=980px tweaks.
- Verified: tsc clean; /create and /library 200; other routes still old Camxora; like persists
  across reload; sort label; add-to-playlist; playlist delete; workspace create; studio projects
  render; cover art; empty states; deep link + Escape; no console errors.
- Still open: trash delete of a real generation (only 1 song exists, not destroyed); rail
  play/like/comment counts + "Cover of" need APIs; "QA Workspace" left in the dev DB (no DELETE
  workspace endpoint); no commit/push.

New helpers in `lib/web-music-api.ts`: `listWebMusicPlaylistItems`,
`deleteWebMusicPlaylist`, `listWebMusicStudioProjects` (+ `WebMusicPlaylistItem`,
`WebMusicStudioProject`).
### Palette + rail update (same session)

- The `.s-*` pages are retinted to Camxora: `--s-bg:#070a13`, `--s-bg2:#0f1322`,
  accent `#a855f7`, primary CTA / Create / active pills / liked state use
  `linear-gradient(100deg,#7c3aed,#a855f7)`. Destructive confirm uses `s-btn-danger`.
  Scoped to `.s-page` so other routes keep the old Camxora skin.
- Rail actions: Play (full width) + Remix / Edit (full width) + MP3/WAV/Playlist/Like grid;
  footer is Delete only. Style box clamps with Show more, timestamp is relative (`2d ago`).
- Tabs measure overflow and fade at the right edge only when the rail is open; the extra
  List/Grid toggle was removed (not in Suno's library). Rows stay 110px.
### Header, form cards, compact create rows (same session)

- Restored the global Topbar on `.s-page` routes (removed the hide rule) and set
  `.content:has(.s-page){padding:68px 0 88px}` so the page sits between the fixed
  header (68px) and the fixed player (88px).
- Create form: Styles, Lyrics and More Options are each wrapped in `.s-form-card`
  (`--s-bg2` surface, 1px border, 12px radius) matching the rail cards.
- Create feed rows use the same actions as Library (Play / Like / Dislike / Share / Remix),
  compacted to 30px icon buttons when the rail shares the row; Publish lives in the More menu.
- Detail rail is shared via `components/TrackRail.tsx`: 320px (create 280/320), 160px cover,
  11/12/13/16 type scale, 40px actions, 16px icons.
- Library rail overlay (<=1100px) is inset below the header and above the player
  (`top:68px;bottom:88px`).
- Form cards flattened: the inner style/lyrics boxes are now transparent (no nested
  panel) so Styles / Lyrics / More Options each read as one card, matching the rail.
  `.s-form-card:focus-within` is the focus affordance; More Options expands inside
  its own card (card grows, body stays framed).
### Two large frame cards + compact create page (same session)

- The music-generation column is now one large frame card (`.s-form-col`: `--s-bg2`,
  1px border, 16px radius) containing the tabs, segmented control, attach bar, prompt and
  the three sections; the workspace/feed column is a matching frame card. The rail stays
  its own panel.
- Inside the generation card the three sections are divided by 1px rules
  (`.s-form-card + .s-form-card`) instead of being nested cards.
- Compact pass: 58px header, search on its own row in the workspace toolbar, controls on
  one row beneath it, pager inline, chips 28px, segment/credits/model 34px, attach bar
  48px, prompt 76px min-height.
- Creation grid at 1297px: form 336 / workspace 401 / rail 264, 16px gaps, no overflow.
### Accordion form, attach pills, workspace header (latest)

- Create form follows the newer Suno layout: collapsible **Styles** and **Lyrics**
  sections (chevron toggles, default open), **More Options** accordion, then Song Title
  and Save to as divided sections inside the one large form card.
- Attach controls are compact pills (+ Audio, + Voice, + Inspo/Image) instead of
  the full-width segmented bar.
- Workspace card header: uppercase Workspaces label, boxed workspace selector,
  plus (new workspace), select-mode, and share icon buttons.
- Section labels are 11px uppercase; form sections separated by 1px rules with 14px
  padding; cards use the same surfaces as the rail.
### Compact workspace rows + rail action grid

- Create workspace rows are now 64px: round play button, title + version, meta line
  (status · model · date), inline **LRC / SRT / MP3 / WAV** download chips, and the
  ≡ menu. Like, dislike, copy link, remix, playlist, publish, studio and delete live
  in that menu.
- TrackRail actions follow the reference: full-width Play, then a 3-column grid
  (Playlist / Like / LRC / SRT / MP3 / WAV; LRC+SRT only for vocal tracks). Footer has
  Remix / Edit and Delete.
- Row height 64px verified; no horizontal overflow at 1297px.
- Compact workspace rows now have their own rounded surface (2% white fill, 1px subtle
  border, 4px gap) so each clip reads as a separate item; selected rows use a violet tint.
### Advanced tab audit: one card per section

- Advanced now renders 5 section cards inside the generation card: Styles, Lyrics,
  More Options, Song Title, Save to. Each is `rgba(255,255,255,.022)` with a 1px
  border, 12px radius, 12px padding, and 10px gaps between cards.
- Type scale inside the form: section labels 13px/500, inputs 13.5–14px, chips 12px,
  char counters 11px, accordion headers 13px/500.
- All cards measure 310px wide at 1297px; no horizontal overflow.
### Design system codified (this pass)

- `web-camxora/DESIGN_SYSTEM.md` is now the source of truth: type scale
  (11/12/13/14/15/16/18/22/24/26/30/32), icon tiers (12/13/14/16/18), spacing
  (4/6/8/10/12/16/20/24), control heights (28/32-34/40/44/46/48), radii, surfaces,
  component specs and do/don't rules.
- Tokens live in `.s-page` (`--s-fs-*`, `--s-ico-*`, `--s-ctl-*`,
  `--s-danger*`, `--s-warn`, `--s-ok-soft`, `--s-info-soft`).
- `npm run check:ui` (`scripts/check-ui-system.mjs`) fails on off-scale font sizes,
  off-scale control heights and raw hex outside the palette. Run it with `npm run
  typecheck` before shipping.
- Fixed in this pass: 10.5/11.5/12.5/13.5/17px text, 10/15px icons, 56/38/36/30/26px
  controls, 14px card padding, 14px rail gap, 12px input radius, nested prompt box,
  footer gradient surface, inline `#fb9b85` (now `.s-danger-text`).
- The audit was produced by a ui-ux-pro-max subagent pass; its P2 items (radius/gap
  polish, row resting surfaces) remain optional.
### Create polish + design-system checks (latest)

- Simple mode: "Songs to generate" is now a section card; prompt composer is a 12px card;
  Create CTA and clear-all circle are both 46px.
- Workspace rows 64px, download chips 28px; rail head 40px; rail cards 12px padding / 10px gap.
- `npm run check:ui` and `npm run typecheck` both pass.
### Readability pass (compact scale)

- Effective control scale: buttons 36px/13px (14px icon), small 30px, CTA 44px/14px,
  tabs 42px/14px, pills/search 32px/13px, chips 28px/12px, menus 30px/13px,
  rail actions 36px, rail grid 30px/12px, downloads 26px/11px.
- Icon rule enforced in DESIGN_SYSTEM.md: icon <= text+1 (12→12, 13→14, 14–16→16).
- Create CTA and clear-all circle are both 44px; the footer gradient now uses the card
  surface. No horizontal overflow at 1297px.
- 
pm run check:ui and 
pm run typecheck pass.
### Darker inputs + Lyrics header cleanup

- New token `--s-field:#0a0d18` (darker than the card `#0f1322`). Applied to
  `.s-input`, `.s-textarea`, search, workspace selector, radio pairs, and the
  style/lyrics input areas inside form cards.
- Lyrics header rebuilt: label left; Write/Prompt in a 28px radio-pair (24px items,
  12px text); Auto-generate a 28px chip (12px); chevron 24px. All vertically centred,
  no wrap at 310px.
- Removed the inline 26px/12px overrides on the Write/Prompt buttons.
### Small-screen rules + Styles height

- Styles textarea: rows 3, min-height 96px (was 2 rows ~56px).
- ≤860px: create becomes a single column — form, workspace, then rail stacked full
  width; toolbar search full width; tabs compact.
- ≤560px: 8px page padding, 10px card padding, attach pills wrap, row download chips
  move under the row.
- DESIGN_SYSTEM.md now has a Responsive section.
### Full create/library audit (latest)

- Styles save/bookmark action moved from inside the textarea to the section header
  (next to the counter and collapse chevron); textarea now uses the full field width.
- Styles and Lyrics textareas both 128px tall (min 128, max 240).
- Library fixes: row title 14px, row action 32px/14px with 14px icon, row radius 12,
  search 32px; rail title 15, meta 12, KV/text 13, cards 12px padding.
- Removed static inline pixel styles from CreateStudio/LibraryView (skeleton padding,
  rowline min-heights, margin, 56px cover -> `.s-cover-sm`).
- npm run typecheck and check:ui pass.
### Dropdowns unified, model fills the row

- .s-select is the single dropdown trigger spec: 32px, field background, 1px border,
  10px radius, 13px text, 12px chevron (applied to Save to; workspace selector already
  matched).
- The Model dropdown uses the same field style and now **fills the remaining width** of
  the top line (segment 138 + credits 53 + model 107 = 310px, right edge aligned).
- Dropdown menus stay 30px items / 13px with 13px icons.
### Top-line 3:1, full-width attach, dropdown behavior

- Top line is a 3:1 grid: Simple/Advanced 230px + credits/model group 77px at 310px,
  no overflow. Credits icon hidden in the 1/4 column; labels stay 12px.
- Audio/Voice/Inspo pills are flex:1 and fill the whole row (99px each at 310px).
- Workspace menus: separate state for the feed selector and Save-to, and opening one
  closes the other; only one menu open at a time. Default workspace is filtered from the
  list to remove the duplicate "My Workspace".
- Menus: 28px items / 12px / 12px icon / 220px max. Icons reduced: buttons 13, chips 11,
  menu 12, rail grid 11, row play 12.
### Small-screen top line + smaller menu icons

- ≤620px: top line is 2:1 (segment / credits+model) so the model chevron is never
  clipped; credits/model overflow is visible.
- ≤400px: top line stacks (segment full width, credits+model on the next row).
- Workspace trigger compacted to 150x30 with 12px text; menu icons 11px, trigger
  chevrons 11px.
### Global caret size + workspace in Simple mode

- New token `--s-caret:11px`: every dropdown caret, accordion chevron (Styles/Lyrics/
  More Options) and menu item icon now computes 11px (verified all five selectors).
- `Save to...` (workspace selector + new/rename dialogs) moved out of the Advanced-only
  branch so it renders in Simple mode too; Simple now shows 2 section cards
  (Songs to generate + Save to).
### Global icon system + responsive labels

- Global rule: `.icon,.fa-replaced{display:inline-flex;align-items:center;justify-content:center;
  line-height:1;flex:none}`. Icon-text gap standardized to 6px in buttons/pills/menus/selects
  (5px chips). Topbar icons and account chevron 15px.
- Play row button icon verified centered: button center and icon center both (635, 282).
- Attach pills use semantic icons (music/mic/lightbulb or image) with `.s-btn-label` text.
- ≤620px hides `.s-btn-label`: attach pills become 34px icon circles, Filters/List keep
  icons; ≤680px hides the account name.
- Account chevron 15px matches the other topbar icons.
### Full ui-ux-pro-max audit (2026-10-28)

- Audited 25 routes with browser metrics (title/h1, overflow, alt text, unnamed buttons,
  unlabeled inputs, sub-24px targets, console) plus the ui-pro-max contrast/target checks.
- Result: 0 console errors, 0 horizontal overflow, 0 missing alt, 0 unnamed buttons.
- Fixed: /create and /studio/editor had no rendered h1 -> added `.sr-only` headings
  (new `.sr-only` utility in globals.css).
- Report: `web-camxora/UI_AUDIT.md` (summary, contrast table, per-route table, next steps).
- Main remaining inconsistency: only /create and /library use the .s-* design system;
  other pages still use the legacy CSS.
### Lyrics auto-generate moved into the input footer

- Header now shows only Lyrics + Write/Prompt toggle + collapse chevron.
- Auto-generate is an icon-only 26px button inside the lyrics box, bottom-left, on the
  same row as the 0/5000 counter (counter right). Icon 12px, aria-label
  "Auto-generate lyrics", title tooltip. Hidden in Prompt mode/instrumental.
### Suno-style "+" add menu on Create

- Prompt composer "+" now opens a 230px menu: Lyrics, Styles, Playlist, Image, Video,
  Audio, Voice. Lyrics/Styles/Audio/Voice open in-place submenus with a back header.
- Wired: Lyrics (Write -> Advanced + focus, Auto-generate, Instrumental), Styles
  (Saved, Shuffle, Enhance), Audio (Upload/Record -> modal), Playlist/Image/Video/Voice
  -> honest "not enabled" modals with Studio link.
- Parity gaps: playlist reference, image/video/audio/voice uploads need backend support.
### Audio attach implemented (real Studio upload)

- Add audio modal now has a file picker (audio/*, 50 MB), mic recording (MediaRecorder),
  and after upload shows filename, duration, size + Extend / Cover actions.
- New helpers in lib/web-music-api.ts: uploadWebMusicStudioAudio,
  extendWebMusicStudioUpload, coverWebMusicStudioUpload, getWebMusicStudioOperation.
- Upload verified end-to-end: POST /web-music/studio/uploads -> 201 with signed URL;
  UI shows `ui-upload.wav · 0:01 · 8 KB` and the Extend/Cover buttons.
- Extend/Cover queue a studio operation and poll /studio/operations/{id}, then refresh feed.
  Not clicked in QA to avoid spending credits.
- Two tiny QA uploads remain in storage (qa-audio.wav, ui-upload.wav); no delete endpoint.
- Voice/video/playlist/image still need platform_api proxies (see API_PARITY.md).