# Suno Studio API coverage map

Status: discovery / design. No Suno credentials or raw tokens are stored here.

## 1. What Suno Studio exposes in the UI

Observed in the authenticated Studio 2.0 interface:

- Project create/load
- Audio track, MIDI track, file upload
- Record / play / loop / metronome
- BPM and time signature
- Timeline, clips, take lanes
- Clip editor
- Automation lanes
- Volume, pan, mute, solo
- Plugins and plugin presets
- Playable keyboard / built-in synths
- Stem separation
- Extend, cover/remix, add vocals, replace section
- Ask Studio chat / agent
- Library
- Export full project, stems, or ranges

Public Studio 2.0 page also lists:

- MIDI controller support
- Musical typing, arpeggiator, chord mode
- Custom effects/plugins
- Sidechain compression, convolution reverb
- Audio/stem import
- BPM, pitch, volume editing
- Automation curves
- Advanced stem separation
- Export songs, stems, selected ranges

## 2. Observed Suno web API families

These are internal Suno web endpoints observed while loading Studio. They are not a documented or stable public API.

```text
POST /a/api/studio/create-project?title=...&major_version=2
GET  /a/api/plugins/catalog?include_archived=true
GET  /a/api/plugins/{id}/presets
POST /a/api/realtime/token
GET  /a/api/agent/conversation/{id}
POST /a/api/user/user_config/
GET  /a/api/prompts/v2
GET  /a/api/lyrics-projects
GET  /a/api/custom-model/shared
GET  /a/api/billing/info/
```

Additional project, track, clip, upload, export, plugin, and agent calls are expected as the UI is exercised.

## 3. What our `musicapi` wrapper already contains

Low-level Suno client methods:

```text
extendMusic
coverMusic
stems
addVocals
replaceSection
uploadExtendMusic
uploadCoverMusic
createPersona
generateCoverImage
stemsDetail
```

Existing HTTP routes include:

```text
POST /me/stems
POST /me/replace-section
POST /me/persona-create
POST /me/voice-generate
POST /me/voice-validate
POST /me/voice-phrase
POST /me/voice-record
POST /me/music/replace-section
```

Known operation costs in `musicapi`:

```text
extend: 10
cover: 10
stems: 8
stems_split: 20
stems_advanced: 12
upload_extend: 10
upload_cover: 10
```

## 3b. Implemented in this branch

### Studio project persistence

```text
GET    /v1/studio/projects
POST   /v1/studio/projects
GET    /v1/studio/projects/{id}
PATCH  /v1/studio/projects/{id}
DELETE /v1/studio/projects/{id}
POST   /v1/studio/projects/{id}/fork
```

Auth: existing `Authorization: Bearer <musicapi API key>`.
Storage: `studio_projects` table in the `sunoapi` database, migration
`0041_studio_projects.sql`. The project arrangement is versioned JSON under
`data` until track/clip tables are added.

### Existing Suno-backed clip operations

Already available through API-key routes:

```text
POST /v1/music/extend
POST /v1/music/cover
POST /v1/music/stems
POST /v1/music/remaster
POST /v1/music/add-vocals
POST /v1/music/add-instrumental
POST /v1/music/replace-section
POST /v1/music/mashup
POST /v1/music/cover-image
POST /v1/persona/create
POST /v1/upload/init
POST /v1/upload/register
```

### Web cloud save (platform_api)

The logged-in Studio editor now uses the platform API for cloud project state:

```text
GET    /api/v3/web-music/studio/projects
POST   /api/v3/web-music/studio/projects
GET    /api/v3/web-music/studio/projects/{id}
PATCH  /api/v3/web-music/studio/projects/{id}
DELETE /api/v3/web-music/studio/projects/{id}
POST   /api/v3/web-music/studio/projects/{id}/fork
```

The Studio editor autosaves lanes, loop region, zoom and master volume after 650 ms
and reloads the newest project on open. Local storage remains the offline fallback.

### Internal Studio stems endpoint

`musicapi` now has a service-to-service endpoint for the first Suno-backed
Studio operation:

```text
POST /internal/studio/stems
GET  /internal/studio/jobs/{id}
```

Authentication: `x-internal-token` matching `STUDIO_INTERNAL_TOKEN`.
It is not exposed to browsers. It resolves the clip's owning Suno account from
`asset_owners`/`jobs`, pins the job to that account, and returns a job id for
polling. This is the safe bridge for `platform_api` to call after it has
authenticated the Camxora user and charged credits.

The same internal service now covers:

```text
POST /internal/studio/stems
POST /internal/studio/extend
POST /internal/studio/cover
POST /internal/studio/add-vocals
POST /internal/studio/add-instrumental
POST /internal/studio/replace-section
GET  /internal/studio/jobs/{id}
```

`platform_api` exposes the matching Studio routes and verifies Camxora
ownership before calling them. Studio project ids and clip ids stay linked to
the caller's account.

### Studio Stems API (implemented)

```text
POST /api/v3/web-music/studio/generations/{task_id}/stems
GET  /api/v3/web-music/studio/operations/{operation_id}
```

- `variant`: `ok` or `alt`
- `mode`: `vocal`, `stems`, or `advanced`
- Verifies the Camxora user owns the generation
- Stores a `studio_operations` row
- Calls `musicapi /internal/studio/stems`
- Polls the internal job
- Returns the stem clips

Configuration:

```text
platform_api: PLATFORM_STUDIO_INTERNAL_TOKEN
musicapi:     STUDIO_INTERNAL_TOKEN
```

The token must match in both services. It is never sent to the browser.

The Studio inspector now has:

```text
Separate stems
  Vocals + instrumental
  Full stems
AI edits
  Extend
  Cover
  Add vocals
  Add instrumental
  Replace section
```

Stems results contain two takes per stem. The editor loads one take per stem
name so a 12-track operation adds 12 lanes instead of 24.

Studio prices are read from `credit_pricing` through:

```text
GET /api/v3/web-music/studio/pricing
```

The Inspector displays the configured costs next to the Stems and AI edit
actions, so admin pricing changes are reflected without hardcoding amounts in
the frontend.

Local mixdown export supports:

```text
Full mix
Loop range
Stems ZIP (one rendered file per unmuted track)
```

Range and stem exports use the same Web Audio graph, fades, EQ, sends and
master limiter as playback. Stem files are packaged into one ZIP archive so a
12-track export is a single browser download.

Each track has a **Dynamics** section with compression and drive/saturation,
plus delay, reverb and chorus sends. All are saved with the project and applied
to playback and export. Drive uses a normalized soft-clip waveshaper before the
compressor; chorus uses an LFO-modulated delay.

The Studio editor runs in a standalone full-screen shell rather than the
Camxora site chrome. Its compact top bar shows project status, playhead,
bar/beat, BPM and time signature, with collapsible Library and Inspector
panels. A Studio AI prompt bar accepts basic stems/extend/cover/vocal commands
for the selected clip.

Right-clicking a clip opens an edit menu with split, duplicate, mute,
copy/paste mix settings, reset mix, rename-track and remove actions.
Double-clicking a track header also renames it.

The Library supports **All / Instrumental / Vocals / Ready** filters in
addition to search, and hides tracks that do not match the active filter.

The Studio supports **4/4, 3/4 and 6/8** time signatures. The setting updates
the bar/beat readout and metronome accents, and is saved with the project.

The snap grid supports **Off / Bar / Beat / 1/8 / 1/16**. Clip drag, trim and
loop-region edits snap to the selected grid division using the current BPM and
time signature. The grid choice is saved with the project.

The timeline supports named **section markers**. Click the flag button to add a
section at the playhead, click a marker to seek, double-click to rename, and
right-click to remove. Markers are saved with the project.

The project menu includes **Open project**, which lists saved cloud projects
with their update time and loads the selected project into Studio. Project rows
also support rename and delete, with deletion clearing the active session when
the current project is removed.

The Inspector is contextual and split into **Clip / Mix / AI** tabs. Clip shows
timing, volume, pan and MIDI piano roll; Mix shows automation, EQ, sends and
dynamics; AI shows stem separation and AI edits. The AI tab is only available
for original generated clips.

Studio keyboard shortcuts:

```text
Space       play/pause
S           split at playhead
D           duplicate selected clip
M           mute selected clip
L           toggle loop
R           start/stop recording
← / →       seek 1 second (Shift = 5 seconds)
Home / End  seek to start/end
Esc         deselect
Ctrl/Cmd+Z  undo (Shift = redo)
```

Studio supports durable audio import:

```text
POST /api/v3/web-music/studio/uploads
GET  /api/v3/web-music/studio/uploads/{upload_id}
```

Uploads are limited to 50 MB audio files, stored in the platform streaming
bucket, and referenced by `uploadId` in the project. The editor re-signs the
URL when loading, so imported tracks survive reloads and URL expiry.

Studio also supports microphone recording. A finished recording is uploaded
through the same durable upload endpoint and added as a normal track, so it can
be edited and exported like any imported or generated clip.

A lightweight MIDI instrument track provides a 12×16 piano-roll grid with
triangle, sine and saw synths. Click an empty cell to add a note; click an
existing note to select it and edit its length, velocity or delete it. Notes
are rendered through the same Web Audio buffer path, so MIDI tracks support
fades, EQ, FX, dynamics, automation and export like audio tracks.

The transport includes a BPM-driven metronome with accented downbeats. Click
scheduling follows the loop range and is monitoring-only; it is not included
in exports.

Studio project version history is available from the **Versions** dialog:

```text
GET  /api/v3/web-music/studio/projects/{id}/versions
POST /api/v3/web-music/studio/projects/{id}/versions
POST /api/v3/web-music/studio/projects/{id}/versions/{version_id}/restore
```

Snapshots include lanes, loop, zoom and master settings; the newest 50 are
retained per project.

Read-only Studio sharing is available from the **Share** dialog:

```text
POST /api/v3/web-music/studio/projects/{id}/shares
GET  /api/v3/web-music/studio/shares/{token}
```

Share links expire after 7 days and open `/studio/shared/{token}`, a public
read-only view of the project title, BPM, tracks and arrangement.

Share viewers can leave feedback without an account:

```text
GET  /api/v3/web-music/studio/shares/{token}/comments
POST /api/v3/web-music/studio/shares/{token}/comments

GET  /api/v3/web-music/studio/projects/{project_id}/comments
```

Comments are stored against the project and appear on the shared page. The
project owner can also read them from the Studio **Share** dialog.

Share links can be **View only** or **Can edit**.

Editable links load into Studio through:

```text
/studio/editor?share={token}
```

and save through:

```text
PATCH /api/v3/web-music/studio/shares/{token}
```

A signed-in viewer can also fork the shared project into their own Studio:

```text
POST /api/v3/web-music/studio/shares/{token}/fork
```

The fork is a full editable copy with a “(shared copy)” title.

Editable share sessions report collaborator presence:

```text
POST /api/v3/web-music/studio/shares/{token}/presence
```

Active collaborators appear as avatars in the Studio top bar; presence expires
after 90 seconds.

Editable sessions poll for remote changes every 5 seconds. When another
collaborator saves, a “Collaborator changes are available” banner offers a safe
reload. This is near-real-time refresh, not conflict-free real-time editing.

Shared saves use optimistic concurrency: the editor sends the project
`updated_at` it loaded. A stale save is rejected with HTTP 409 and triggers the
reload banner instead of overwriting a collaborator’s work. The first autosave
after loading a shared project is suppressed to avoid overwriting newer remote
state.

The Inspector supports per-clip **volume and pan automation** points. Points
are saved with the project and applied to both playback and export; volume
automation overrides the clip fades when points are present. Pan automation
uses the same point editor and schedules the stereo panner.

When storage is configured, musicapi adds `durable_url` to finished clips.
Studio prefers `durable_url` over Suno `audio_url` and `media_urls`, so playback
uses the stored copy instead of an expiring upstream CDN link.

Verified locally with a storage-backed Extend run: the returned `durable_url`
pointed at the stored MP3, returned HTTP 200, and served `audio/mpeg`.

Matching platform routes:

```text
POST /api/v3/web-music/studio/generations/{task_id}/extend
POST /api/v3/web-music/studio/generations/{task_id}/cover
POST /api/v3/web-music/studio/generations/{task_id}/add-vocals
POST /api/v3/web-music/studio/generations/{task_id}/add-instrumental
POST /api/v3/web-music/studio/generations/{task_id}/replace-section
GET  /api/v3/web-music/studio/operations/{operation_id}
```

Studio operations now charge through the existing credit/ownership gateway:

```text
Normal Studio edit          12 credits
Stems — 2 track             12 credits
Stems — 12 track            60 credits
```

Normal edits and 2-track stems are two credits above the measured Suno charge.
The 12-track stems price is 60 credits, ten above Suno's measured 50-credit
charge. Charge and refund paths were verified against a mocked internal service.

Measured Suno-side charges are recorded in
[suno-studio-operations-charge-report.md](suno-studio-operations-charge-report.md).

## 4. Architecture decision

```text
web-camxora Studio
        |
        v
platform_api  -> auth, ownership, credits, plan gates, audit, API keys
        |
        v
musicapi.camxora.com -> Suno key pool, assets, jobs, upstream operations
        |
        v
Suno web/internal APIs
```

- `musicapi.camxora.com` owns Suno/audio operations.
- `platform_api` owns user identity, credit pricing, entitlements, and public API keys.
- Studio must never call Suno directly or receive raw Suno cookies/tokens.
- Do not expose a raw 1:1 clone of Suno's internal API. Expose a Camxora domain API.

### Scope boundary

In scope:

```text
Studio projects / tracks / clips / takes
Studio assets and uploads
Suno-backed Studio edit operations
Plugins and presets
Automation
Ask Studio agent
Export jobs
Realtime collaboration tokens
```

Out of scope:

```text
New checkout / pricing pages
New plans / subscriptions
Invoices / receipts / top-up flows
New billing APIs
```

Billing and access are not new Studio features. They already live in `platform_api`.
Studio API routes still require the existing service authentication, user ownership,
credit reservation, rate limits, and audit trail. That is authorization, not a new
billing product.

## 5. Proposed Camxora Studio API

### Projects

```text
POST   /v1/studio/projects
GET    /v1/studio/projects
GET    /v1/studio/projects/{project_id}
PATCH  /v1/studio/projects/{project_id}
DELETE /v1/studio/projects/{project_id}
POST   /v1/studio/projects/{project_id}/fork
```

### Tracks, clips, takes

```text
POST   /v1/studio/projects/{project_id}/tracks
PATCH  /v1/studio/projects/{project_id}/tracks/{track_id}
DELETE /v1/studio/projects/{project_id}/tracks/{track_id}

POST   /v1/studio/projects/{project_id}/clips
PATCH  /v1/studio/projects/{project_id}/clips/{clip_id}
DELETE /v1/studio/projects/{project_id}/clips/{clip_id}

POST   /v1/studio/projects/{project_id}/clips/{clip_id}/takes
PATCH  /v1/studio/projects/{project_id}/takes/{take_id}
```

### Assets and uploads

```text
POST /v1/studio/uploads/init
POST /v1/studio/uploads/{upload_id}/complete
GET  /v1/studio/assets/{asset_id}/signed-url
```

### Suno-backed edit operations

```text
POST /v1/studio/clips/{clip_id}/stems
POST /v1/studio/clips/{clip_id}/extend
POST /v1/studio/clips/{clip_id}/cover
POST /v1/studio/clips/{clip_id}/add-vocals
POST /v1/studio/clips/{clip_id}/replace-section
GET  /v1/studio/operations/{operation_id}
GET  /v1/studio/operations/{operation_id}/result
```

All operations must be queued, idempotent, ownership-checked, credit-priced, and refundable on failure.

### Ask Studio / agent

```text
POST /v1/studio/agent/conversations
GET  /v1/studio/agent/conversations/{conversation_id}
POST /v1/studio/agent/conversations/{conversation_id}/messages
```

### Plugins, presets, automation

```text
GET  /v1/studio/plugins
GET  /v1/studio/plugins/{plugin_id}/presets
POST /v1/studio/plugins
PUT  /v1/studio/plugins/{plugin_id}/presets
PUT  /v1/studio/clips/{clip_id}/automation
```

### Export

```text
POST /v1/studio/projects/{project_id}/exports
GET  /v1/studio/exports/{export_id}
GET  /v1/studio/exports/{export_id}/download
```

Export scopes:

```text
full | stems | range
formats: wav | mp3
```

### Realtime / collaboration

```text
POST /v1/studio/projects/{project_id}/realtime-token
```

## 6. What should stay client-side

These do not need a Suno operation:

- Waveform rendering
- Timeline zoom and playhead
- Local clip drag/trim/split
- Local mixing, fades, EQ, delay, reverb
- WAV/MP3 mixdown for the current local arrangement
- Keyboard/MIDI audition
- Local undo/redo

If cloud projects are required, their **project state** still needs the project/track/clip API.

## 7. Delivery phases

### Phase 1: Project foundation

- Studio project persistence
- Track/clip/take CRUD
- Asset upload and signed URLs
- Save/load/fork
- Local Studio switches from localStorage to API-backed projects

### Phase 2: Suno edit operations

- Stems
- Extend
- Cover
- Add vocals
- Replace section
- Job polling and result clips
- Credit pricing, refunds, ownership checks

### Phase 3: Studio production

- Plugin catalog/presets
- Automation persistence
- Ask Studio conversations
- Export jobs (full/stems/range)
- Realtime tokens/collaboration

### Phase 4: Hardening

- Rate limits
- Idempotency keys
- Audit logs
- Usage caps
- Failure/refund tests
- ToS/compliance review

## 8. Legal and security constraints

- Suno Studio’s private web API is undocumented and unstable.
- Do not expose raw Suno cookies, tokens, or internal 1:1 endpoints.
- Do not scrape other users’ content.
- Use only a controlled key pool and test accounts.
- Do not present cloned Suno endpoints as an official Suno API.
- Get legal/compliance review before public launch of AI edit operations.

## 9. Immediate next step

Build Phase 1 and Phase 2a (stems) first:

```text
Studio project save/load
  -> clip selected
  -> POST /v1/studio/clips/{id}/stems
  -> musicapi /me/stems
  -> poll operation
  -> add vocals/instrumental stems as new Studio lanes
```

This gives a real Suno-backed Studio workflow without trying to clone the entire DAW at once.
