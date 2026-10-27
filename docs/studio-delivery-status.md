# Camxora Studio delivery status

Last updated: 2026-10-27
Branch: `feat/camxora-apex`

## Goal

Ship Camxora Studio v1 as a reliable Suno-backed creation workspace. Users can
create or import audio, arrange and mix it, use MIDI, save and reopen projects,
collaborate safely, and export — with correct billing, durable storage and no
data loss.

This is not a promise to clone every Suno Studio feature.

## Implementation backlog — complete

### Shell and editing

- [x] Standalone full-screen Studio shell
- [x] Multi-track timeline
- [x] Clip drag, trim, split, duplicate, reorder and delete
- [x] Undo / redo and keyboard shortcuts
- [x] Context menu, rename and track colors
- [x] Section markers
- [x] Loop range, snap grid and zoom
- [x] BPM, time signature, tap tempo and metronome
- [x] Master transport and meters

### Audio

- [x] Audio import and durable uploads
- [x] Microphone recording with count-in
- [x] Waveform rendering
- [x] Reverse audio
- [x] Varispeed 50–200%
- [x] Alternate take lanes
- [x] Linear / exponential fades
- [x] 3-band EQ and low-pass filter
- [x] Delay, convolution reverb and chorus
- [x] Compression, drive and rhythmic ducking
- [x] Volume/pan automation with per-point curves
- [x] Track groups A–D with names, colors, volume, mute, solo and collapse
- [x] Master compression, drive, EQ, limiter, presets and meter/spectrum
- [x] Mixer view with channel strips, levels, pan, mute/solo and master strip

### MIDI

- [x] Piano roll with triangle, sine and saw synths
- [x] Note add, edit, delete, length and velocity
- [x] Major/minor chord mode
- [x] Arpeggiator up/down
- [x] Playable one-octave keyboard
- [x] Web MIDI controller input
- [x] MIDI note recording at the playhead
- [x] Quantize, transpose and octave navigation
- [x] Standard MIDI import and export

### Suno-backed operations

- [x] Stems — 2-track
- [x] Stems — 12-track
- [x] Extend
- [x] Cover
- [x] Add vocals
- [x] Add instrumental
- [x] Replace section
- [x] Remaster
- [x] Mashup
- [x] Cover image
- [x] Uploaded-audio Extend
- [x] Uploaded-audio Cover
- [x] Personas
- [x] Persona-backed Replace section
- [x] Word-level aligned lyrics

### Projects

- [x] Cloud autosave and load
- [x] Local fallback
- [x] Project browser
- [x] Search and sort
- [x] Pinned projects
- [x] Project tags and tag filtering
- [x] Archive and restore
- [x] Rename and duplicate
- [x] Version history and restore
- [x] `.camxora.json` export/import

### Collaboration and sharing

- [x] View-only and editable share links
- [x] 1/7/30-day expiry
- [x] Share-link list, copy, open and revoke
- [x] Public read-only share page
- [x] Comments and nested replies
- [x] Owner comment counts and unread state
- [x] Presence avatars
- [x] Collaborator playhead cursors
- [x] Collaborator track-selection badges
- [x] Click-to-follow collaborator playhead
- [x] Optimistic conflict protection
- [x] Long-poll shared updates
- [x] Optional auto-apply of remote changes
- [x] Fork shared project

### Export

- [x] WAV full mix
- [x] MP3 full mix
- [x] WAV/MP3 loop range
- [x] Stem ZIP
- [x] MIDI export
- [x] Effects, automation, groups and master bus in exports

### Backend and operations

- [x] Pinned Suno-account routing for derivatives
- [x] Ownership checks and credit charging
- [x] Refunds on failed Studio operations
- [x] Studio internal token bridge
- [x] Platform pricing from `credit_pricing`
- [x] Studio readiness endpoint
- [x] Durable storage URL support
- [x] Migrations through `163_studio_presence_playhead`

## Verified in this branch

- [x] `web-camxora` TypeScript checks pass
- [x] `musicapi` TypeScript checks pass
- [x] Platform API Python compilation passes
- [x] Real Stems end-to-end test passed
- [x] MIDI export/import round trip passed
- [x] MIDI note recording passed
- [x] Track group volume/mute persistence passed
- [x] Group names/colors passed
- [x] Group collapse/expand passed
- [x] Mixer strips and master meter rendered
- [x] Project search, sort, duplicate, pin, tags and archive passed
- [x] Share-link creation/revocation/list passed
- [x] Comment reply and nested rendering passed
- [x] Comment count/unread badge passed
- [x] Long-poll updates endpoint passed
- [x] Presence API accepted playhead and selected lane
- [x] Readiness endpoint verified locally: tables, pricing, storage, internal
      token and musicapi reachability all pass; Suno account count is `0`
- [x] Automated non-Suno release checks: 17/17 passed, including project
      CRUD/pin/tags/archive, shares, comments, presence, long-poll and revoke

## Release gates — still open

These require production credentials, live Suno sessions or a second test user,
so they are **not** marked complete yet.

- [ ] Production `STUDIO_INTERNAL_TOKEN` matches platform and musicapi
- [ ] Production durable B2/S3 storage configured
- [ ] Migrations `158`–`163` applied in sandbox and production
- [ ] Readiness endpoint returns `ready: true`
- [ ] At least one active Suno account is available in the musicapi pool
- [ ] Live Stems 2/12 acceptance re-run in target environment
- [ ] Live Extend acceptance
- [ ] Live Cover acceptance
- [ ] Live Add vocals / Add instrumental acceptance
- [ ] Live Replace section acceptance
- [ ] Live Remaster acceptance
- [ ] Live Mashup acceptance
- [ ] Live Cover image acceptance
- [ ] Live Uploaded Extend/Cover acceptance
- [ ] Live Persona creation and persona-backed Replace acceptance
- [ ] Live aligned lyrics acceptance
- [ ] Failed-operation refund verification in target environment
- [ ] Two-user editable share session verified
- [ ] Presence cursors/follow verified with two users
- [ ] Revoked/expired links fail immediately in target environment
- [ ] Production WAV/MP3/stems/MIDI export smoke test
- [ ] Mobile and desktop regression pass
- [ ] Browser console clean on main Studio paths
- [ ] Sandbox deploy and smoke test
- [ ] Production deploy approval and rollback plan

## Deferred after v1

- [ ] True CRDT real-time co-editing
- [ ] Track-triggered sidechain compression
- [ ] Pitch-preserving audio warp/time-stretch
- [ ] Advanced automatic take comping
- [ ] Custom Suno models
- [ ] Native plugin hosting
- [ ] Comment email/Telegram notifications

## Next action

Do not add more feature scope. Configure the target environment until the
readiness endpoint is green, then run the live Suno acceptance suite and the
two-user collaboration test.

Use [studio-release-runbook.md](studio-release-runbook.md) for the exact
migration, readiness, acceptance, sandbox, production and rollback steps.
