# CAMXORA Studio — functional end-to-end audit (Agent A)

**Date:** 2026-11-16
**Auditor:** Agent A (QA team), branch `qa/studio-functional-audit` (base `origin/main` @ `46f68025`)
**Scope:** real UI, end-to-end, against the local sandbox stack. No product code changed.
**Account:** sandbox `somvannda@gmail.com` (shared sandbox DB `camxora_pfm_sandbox` / `sunoapi`).
**Browser:** headless Chromium 156 (Playwright), viewport 1689×1277 (the captured reference size).

## Verdict summary

| Verdict | Count |
| --- | --- |
| PASS | 47 |
| FAIL | 3 |
| BLOCKED | 1 |
| **Total areas** | **51** |

Three failures: one data-loss defect (D1), one autosave/versioning defect right after a rename (D2),
and one cosmetic take-naming defect (D3). Everything else in the requested matrix worked in the
real UI, including mocked prompt-bar generation, mocked stem separation, WAV/MP3/JSON export,
logged-out share view, offline replay, draft recovery, comments, presence, recording and bounce
(bounce and recording really uploaded into the moto bucket).

## Stack used (and how to reproduce it)

```powershell
# storage stand-in + bucket
python -m moto.server -p 9000
python -c "import boto3; boto3.client('s3', endpoint_url='http://127.0.0.1:9000', aws_access_key_id='minioadmin', aws_secret_access_key='minioadmin', region_name='us-east-1').create_bucket(Bucket='camxora-studio')"

# platform API against the sandbox DB, Studio token from musicapi/.env, provider pointed at local musicapi
$env:PLATFORM_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox"
$env:PLATFORM_STUDIO_INTERNAL_TOKEN="<STUDIO_INTERNAL_TOKEN from musicapi/.env>"
$env:PLATFORM_SUNO_API_BASE_URL="http://127.0.0.1:4003"
$env:PLATFORM_STREAMING_B2_KEY_ID="minioadmin"; $env:PLATFORM_STREAMING_B2_APPLICATION_KEY="minioadmin"
$env:PLATFORM_STREAMING_B2_BUCKET="camxora-studio"; $env:PLATFORM_STREAMING_B2_REGION="us-east-1"
$env:PLATFORM_STREAMING_B2_ENDPOINT="http://127.0.0.1:9000"
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100 --env-file platform_api/.env

cd musicapi; npm run serve                        # :4003
python scripts/dev/run-platform-worker.py         # job queue
cd camxora.com; npm run dev                       # :3103 (Next 16.3.4, Turbopack)
```

Readiness before every batch: `GET :8100/health` = 200, `GET :3103/studio` = 200, `GET :4003/health` = 200.
The host kills long-lived children between tool calls, so the stack was started and torn down once per
batch (11 batches). Each batch drove the real UI with throwaway Playwright scripts
(`tmp-qa/*.mjs`, deleted before committing; evidence kept).

**Provider safety:** `/api/v3/web-music/generate`, `/api/v3/web-music/generations/<id>` and
`/api/v3/web-music/studio/generations/<id>/stems` were mocked with `page.route` for every generation
and stem test. No real provider call and no credit spend happened in this audit. The one paid surface
that cannot be mocked from the client (the prompt-bar **plugin designer**, which posts a credit-charged
design job) was **not run** — see “Blocked”.

---

## Results by area

### 1–2. Home, project lifecycle

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Create blank project from home | PASS | Home → “New project” → editor opens with chip “Untitled project”, 0 clips, first-run onboarding overlay | `01-home-blank-project.png` |
| 2 | Rename project (chip menu) | PASS | Chip → Rename → new title → chip and `GET /projects/<id>` both show the new title | `02-home-lifecycle.console.log` |
| 3 | Arrangement edit + save **right after a rename** | **FAIL** | After renaming via the chip menu, adding a track PATCHes with the stale version → **409**, pill “Save failed · Retry”, alertdialog “This project changed in another tab”. “Keep mine” re-saves correctly | `02-home-error.png`, `01-verify-rename-conflict.png`, `02-verify-keep-mine.png` — see **D2** |
| 4 | Reload → persistence | PASS | Title, BPM, tracks and clip positions come back after `page.reload()` | `02-home-lifecycle.console.log` |
| 5 | Open existing project from the home card menu | PASS | Search → card “…” → Open → same project id | `05-home-card-menu.png` |
| 6 | Open from the editor chip → My Projects | PASS | Chip → Open Project → “My Projects” dialog lists cards, search narrows, card opens | `06-home-my-projects-dialog.png` |
| 7 | Delete → Recently Deleted → restore | PASS | Home card → Delete → confirm (“moves the project to Recently Deleted”); `GET` = 404; chip → Open Project → Recently Deleted → Restore → `GET` = 200 and card back on home | `07-home-delete-confirm.png`, `08-home-recently-deleted.png`, `09-home-after-restore.png` |

### 3. Library rail

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 8 | Rail tabs | PASS | Root tiles All Songs / Liked / Stems / Uploads all present; “In Project” and “Liked only” chips live in the Songs toolbar | `02-lib2-root.png`, `03-lib2-all-songs.png` |
| 9 | Search + filters | PASS | 9 songs → search “zzz-no-such-song” → 0 → clear → 9; Filter songs menu has 3 radios; “Liked” sets `aria-pressed=true` | `05-lib2-search-filters.png` |
| 10 | Add a clip to the lane | PASS | Row → Add → clip count +1, persisted `lanes` +1 | `07-lib2-add-clip.png` |
| 11 | Song detail rail + Back | PASS | Double-click row → “Song details” rail, Info selected, Stems tab, More menu (3 items: Add to project / Download WAV / Move to trash), Back returns to the list | `07-lib-song-detail.png` |
| 12 | Uploads | PASS | Uploads tile → Choose audio file (`public/seed/demo-loop.wav`) → list 50 → 51 rows (storage configured, no refusal alert) | `08-lib2-upload.png` |
| 13 | In Project | PASS | Chip pressed → lists the project’s own songs only | `09-lib2-in-project.png` |

### 4. Arrangement

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 14 | Add track | PASS | Add new track → Audio → DOM and persisted tracks 1 → 2 | `02-arrange-add-track.png` |
| 15 | Move clip | PASS | Drag one bar → `lanes[0].start` 0 → 2 s | `03-arrange-move.png` |
| 16 | Trim clip | PASS | Right grip +96 px → duration 4 → 6 s, start unchanged | `04-arrange-trim.png` |
| 17 | Split | PASS | Playhead inside the clip → clip menu → “Split Ctrl E” (enabled) → clips 2 → 3, persisted | `02-editors-split-retest.png` |
| 18 | Duplicate | PASS | Select clip → `Ctrl+D` → +1 clip, persisted | `05-arrange-duplicate.png` |
| 19 | Zoom presets | PASS | Zoom in 288→432 px, Zoom out back to 288, Fit to content 576 | `06-arrange-zoom.png` |
| 20 | Undo / redo | PASS | Delete → 3→2 clips, Undo → 3, Redo → 2 (and re-undo to restore) | `07-arrange-undo-redo.png` |
| 21 | Autosave status | PASS | Pill observed as “Saving…” then “Saved” on every edit | `08-arrange-autosave-race.png` |
| 22 | Second edit during a save | PASS | PATCH delayed 1.5 s; mute Track 1 then Track 2 while the first write was in flight → both persisted, no conflict, final pill “Saved” (write queue serialises) | `08-arrange-autosave-race.png` |

### 5. Editors

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 23 | MIDI editor | PASS | Add MIDI track → grid click ×2 = 2 notes; velocity drag 100 → 46; Quantize 16 puts every note on the 1/16 grid; reopen from the clip = 2 notes; reload = 2 notes | `03-editors-midi.png`, `04-editors-midi-reload.png` |
| 24 | Automation lane | PASS | Automation → click Volume lane → 1 point (“Volume 50 at 120.00s”); Pan lane → 1 point; after reload the volume point is still there | `05-editors-automation.png` |
| 25 | Warp markers | PASS | Double-click clip → Clip settings → Stretch off→on, “On Beat” → 9 heads, `warp.mode="beat"` with markers 0…4 s persisted; drag + `Shift+Q` kept them | `02-plugins-clip-settings-warp.png` |
| 26 | Clip settings | PASS | Volume −6 dB + Reverse → persisted `audio:{gainDb:-6, reverse:true}`, loop/pitch/speed controls present | same |
| 27 | Take lanes | PASS | Clip → Take lanes → band with the empty copy “Create a clip to see alternate takes here”; toggling closes it | `07-editors-take-lanes.png` |
| 28 | Section markers | PASS | Right-click clip → Create Section → ruler marker “Section Audio A at 00:00.000”; survives reload | `08-editors-section-marker.png` |

### 6. Plugin dock

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 29 | Add EQ + bypass | PASS | Add effect → EQ → article “EQ slot 1”, Gain −4.5 persisted in `chains[track][0].params`; Bypass toggles `aria-pressed` true/false | `02-fx-eq.png` |
| 30 | Preset stepper + custom preset + sidechain | PASS | Default → “Clear all settings” → label “Custom”; Save preset “QA Glue” → listed in the menu and the slot label; stepper Vocal → Default; Sidechain menu lists None / Track 1 / Track 2 × Pre-fx/Post-fader, chosen route persisted `{trackId, tap:"pre"}` | `01-lib-compressor.png` |
| 31 | Convolution IR load + designer | PASS | Built-in load “Halls › Large Hall” → `assetId:"large-hall"`; with Settings ▸ Content ▸ “Advanced content features” on, the picker offers **Design response.**, the designer saves “QA Custom Hall”, it appears under Custom and persists as `assetId:"custom-…"` | `03-fx-convolution-no-designer.png` (designer hidden with the default off), `02-lib-ir-designer.png`, `03-lib-ir-custom.png` |
| 32 | Stereo Utility + persistence | PASS | Add Stereo Utility (4 knobs); reload → the full chain (3 slots) is rebuilt | `05-fx-stereo-reload.png` |
| 33 | Remove plugin | PASS | “Remove …” on the first slot → 4 → 3 slots | `06-fx-remove.png` |
| 34 | Designed/custom plugin from the prompt bar | **BLOCKED** | The prompt bar’s design mode says “Asks the plugin agent to build it (uses credits)” — a paid provider operation, so it was not submitted | — (see “Blocked”) |

### 7. Master dock, sends, groups

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 35 | Limiter + presets + master spectrum | PASS | Main → Master chain → Add effect → Limiter (5 knobs); presets Default/Clean/Warm/Loud apply; Add EQ + Compressor → 4 master entries persisted in `data.masterChain`; `canvas.se-spectrum[aria-label="Master spectrum"]` present | `07-fx-master-dock.png`, `04-lib-master-spectrum.png` |
| 36 | Sends + groups A–D | PASS | Delay 42 / Reverb 17 persisted `{delay:42,reverb:17}`; Group A assigned (`groupId:"A"`, `groups{"A":60}`); both survive reload | `08-fx-sends-groups.png` |

### 8. Prompt bar (mocked provider)

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 37 | Generate a part → new clip | PASS | Mock `POST /generate` + `GET /generations/<id>`; assistant shows a take, Commit inserts at the playhead → clips 1 → 2 at 11 s, toast “Take added to the track at the playhead.” | `02-gen-assistant.png`, `01-gen2-insert.png` |
| 38 | Generate over an existing clip → take stack | PASS | Second commit over the same spot keeps 1 clip but persists 2 takes, opens Take lanes with both rows, toast “Take added to the clip.” | `02-gen2-take-stack.png` |
| 39 | Stems | PASS | Add a library song (has a source generation) → Get Stems → “Separate” → mocked operation polls once and adds 2 tracks/clips (“QA Vocals”, “QA Drums”), persisted | `04-gen-stems-dialog.png`, `05-gen-stems-result.png` |

### 9. Export, share, offline, comments, presence

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 40 | WAV export + toast | PASS | Export → Full Song → download `QA A export ….wav`, RIFF/WAVE header, 705,644 B (4 s stereo 44.1k/16-bit + header); toast “Full Song download started!” | `02-exp-wav-toast.png` |
| 41 | MP3 export | PASS | MP3 radio `aria-checked=true` → `.mp3` download, MPEG frame sync `0xFF Ex`, no RIFF header | `03-exp-mp3.png` |
| 42 | JSON export → import round-trip | PASS | Project (JSON) download parses to the same title/lanes/tracks; importing it opens “<title> (imported)” with 1 clip and a new id | `04-exp-json-import.png` |
| 43 | Share link + logged-out view | PASS | Share Project → link `/studio/shared/<token>`; anonymous context: HTTP 200, title and arrangement rendered, “READ-ONLY STUDIO SHARE”, comment box, no login wall | `02-share-dialog.png`, `99-shared-anon.png` |
| 44 | Offline edit replay | PASS | Go offline → `a` → pill “Offline · changes not saved”, edit visible locally → back online → “Saved” and the track is on the server | `03-share-offline.png` |
| 45 | Draft recovery after a failed write | PASS | Abort PATCH → pill “Save failed” → reload → alert “Recovered draft” → Restore draft → “Saved” and persisted | `04-share-draft.png` |
| 46 | Comments | PASS | Clip menu → Clip Info → “Write a comment” → Post → note visible; survives reload | `05-share-comment.png` |
| 47 | Presence | PASS | Second context joins the same project → first tab shows 1 presence avatar and 1 remote cursor | `07-exp-presence.png` |

### 10. Record and bounce

| # | Area | Verdict | What I did | Evidence |
| --- | --- | --- | --- | --- |
| 48 | Record → take | PASS | Arm Track 1 → Record → 3.5 s → Stop → new lane “Take 2”, 3.6 s, uploaded to the moto bucket (`…/studio/uploads/….webm`) and persisted | `03-verify-record.png` |
| 49 | Bounce track | PASS | Track options → Bounce track → new track “Track 1 (bounced)” with its own lane rendered to `…/studio/uploads/….wav` in the bucket, source muted | `04-verify-bounce.png` |
| 50 | Risk probe: edit while the project is loading | **FAIL** | Pressing `a` while “Loading project…” is visible replaced the server document with `{tracks:[…]}` — the two clips were gone after reload | `02-load-probe.png`, `03-load-probe-reload.png` — see **D1** |
| 51 | Defect repro: rename then edit | **FAIL** | Same as #3, isolated with a fresh project: server `{lanes:1, tracks:[Track 1]}` → rename → add track (DOM 2 tracks) → PATCH **409**, conflict dialog, server unchanged, “Keep mine” then saves 2 tracks | `01-verify-rename-conflict.png`, `02-verify-keep-mine.png` — see **D2** |

---

## Defects, ranked by user impact

### D1 — Editing during “Loading project…” destroys every clip in the project (High)

**Impact:** irreversible data loss of the whole arrangement (lanes). It is not a race between two
users — a single user pressing a shortcut (or clicking a track control) in the first second after
opening a project loses all clips. The window is one `GET /studio/projects/<id>` round-trip, so it
grows on slow networks.

**Repro (deterministic, 3/3 in the control-vs-probe run):**
1. Create a project with 2 clips (server `data.lanes.length = 2`, `data.tracks.length = 1`).
2. Open `/studio/editor?project=<id>`.
3. While the “Loading project…” indicator is still on screen (the project chip paints first), press
   `a` (add audio track) — no other action.
4. Read the project back: `data` is now `{"tracks":[<1 track>]}` — the `lanes` key is **gone**.
   Reload the editor: 0 clips.

**Evidence:** `evidence-a/02-load-probe.png`, `evidence-a/03-load-probe-reload.png`,
`evidence-a/11-loading-data-loss.console.log` (server shape before / @0.6 s / @3.6 s / @7.6 s / after
reload). Control run that waits for the load keeps both lanes (`01-load-control.png`).

**Where it comes from (for the fix):** `writeProjectData` starts from `projectRef.current?.data || {}`
and persist() runs with `expectedUpdatedAt = null` while the document is still loading, so the write
replaces `data` with the empty document plus the new track. Nothing gates edits on `loading`, and the
toolbar/track panel are fully interactive under the loading overlay.

**Suggested fix direction:** block edits (and the global shortcuts) until `loading === false`; or make
persist a no-op until the first `getStudioProject` resolves; or always merge a full document
(`lanes` + `tracks`) rather than the partial object being edited.

### D2 — Renaming a project makes the next edit fail with a false “changed in another tab” conflict (Medium)

**Impact:** after every rename, the next save (any edit) returns 409 and the editor shows
“Save failed · Retry” plus a modal “This project changed in another tab. Reload before saving.”
The work is not lost — “Keep mine” re-saves it correctly — but the user is told a collaborator
changed the project when nobody did, and the edit appears unsaved until they answer the modal.

**Repro:**
1. Open a project, chip → Rename → save a new title.
2. Immediately add a track (or move a clip).
3. PATCH `/api/v3/web-music/studio/projects/<id>` → **409**; pill “Save failed · Retry”; dialog
   “This project changed in another tab.” Server still has the old track list.
4. “Keep mine” → PATCH 200, pill “Saved”, the edit is persisted.

**Evidence:** `evidence-a/02-home-error.png`, `evidence-a/01-verify-rename-conflict.png`,
`evidence-a/02-verify-keep-mine.png`; logs `02-home-lifecycle.console.log`,
`12-final-verify.console.log` (`patchStatuses [409]` → `[409,200]` after Keep mine).

**Where it comes from:** the rename PATCH bumps `updated_at`, and the editor’s `onRenamed` handler only
copies the new title into local state (`setProject({...current, title: next})`), leaving the cached
version used as `expected_updated_at` stale.

### D3 — The first recorded take is titled “Take 2” when the track already has a clip (Low, cosmetic)

**Impact:** confusing take naming; the first recording on a track with one existing clip is labelled
“Take 2” (the clip is otherwise correct and persists).

**Repro:** project with one clip on Track 1 → arm → Record 3 s → Stop → new lane titled **“Take 2”**.

**Evidence:** `evidence-a/12-final-verify.console.log` (`recorded: {title:"Take 2", duration:3.6, …}`),
`evidence-a/03-verify-record.png`.

**Where it comes from:** `const take = (owner?.clipIds.length ?? 0) + 1;` — the number counts clips on
the track, not existing takes.

## Observations (behaviour notes, not filed as defects)

- **O1 — success toast can expire before a long render finishes.** Bounce renders for ~15 s; by the
  time it lands, the status toast read empty in two runs (`08-generate-record.console.log`,
  `12-final-verify.console.log`), so the only success signal is the new “(bounced)” track. The WAV/MP3
  exports (1–3 s) always showed their toast.
- **O2 — the assistant panel takes over the left column.** While it is open the track headers
  (arm, mute, options) are not reachable; you must press “Close assistant”. Intended or not, it is
  worth a design decision because generating then recording/bouncing is a common sequence.
- **O3 — the Songs list paints empty before it fills.** “All Songs” showed 0 rows for ~1.5 s with no
  skeleton, then 9 rows (first measurement 0, retest 9). Cosmetic timing; no error.
- **O4 — first-run onboarding blocks the editor on an empty project** (“How do you want to start?”,
  needs “Start empty”). It is keyed per project in `localStorage`, so it reappears in every fresh
  browser profile; that is why automation must dismiss it after creating a blank project.

## Not covered / blocked

- **Designed/custom plugin from the prompt bar (BLOCKED).** The prompt-bar design mode posts a
  credit-charged design job (“Asks the plugin agent to build it (uses credits)”). Running it would be a
  paid provider operation, which the audit must not do. The free custom-content path was covered
  instead: Impulse Response Designer → custom IR → persisted `assetId`.
- **Real provider generation / stem separation.** Both were mocked by design (no credits). Queue
  latency, credit charging and separation quality were not exercised.
- **Suno Sync push.** Not run (needs a live provider session); the rest of the project menu was covered.
- **Conflict resolution “Reload theirs” and version-history restore.** “Keep mine” was exercised
  (D2); the other branches were not.
- **Export scopes “Multitrack” and “Selected Time Range”.** The task asked for WAV and MP3 scopes,
  which passed; the other two menu items were not run.
- **Responsive/narrow layout, keyboard-only navigation beyond the shortcuts used, a11y and
  performance.** Out of scope for this functional pass (single viewport 1689×1277).

## Data-dependence and retries (honesty notes)

- The rename→save failure (D2) was hit twice, on two different projects, both times immediately after
  a rename; it is not data-dependent.
- The loading data-loss probe (D1) ran twice (once inside the share batch, once isolated with a
  control run) with the same result.
- Early library/share/offline “failures” in my first pass were harness mistakes, all retried and
  passed: (a) clicking library filters while the rail had switched from the root tiles to the songs
  view, (b) counting dialog cards before the list rendered, (c) clicking the project chip before the
  document load finished — (c) is what exposed D1.
- No uncaught page exceptions were seen in any run. The only failed requests were deliberate
  (offline simulation, aborted PATCH for the draft test) plus the 409 in D2.
- 20 QA projects were created in the shared sandbox and soft-deleted at the end (204) — they now sit
  in the sandbox account’s “Recently Deleted”. Titles start with `QA ` (`QA A …, QA load …,
  QA rename …, QA record …, QA bounce …, QA probe …`) if anyone wants to purge them permanently.

## Evidence index

`docs/studio/reports/evidence-a/`

- `*.console.log` — full per-batch run logs with verdicts, HTTP statuses and console errors
  (`02-home-lifecycle`, `03-arrangement`, `04-editors`, `05b-plugins-master`, `06b-library`,
  `07-generate-record`, `08-generate-record`, `09-export-share`, `10-share-offline`,
  `11-loading-data-loss`, `12-final-verify`).
- `NN-*.png` — numbered screenshots per step (home, arrangement, editors, library, plugin/master dock,
  generation/record, export/share/offline, and the two defect captures).
- `downloads/v4rcv-project.json` — the JSON export used for the import round-trip (the WAV/MP3
  downloads were deleted after their headers/sizes were recorded in the logs).
