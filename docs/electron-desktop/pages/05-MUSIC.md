# 5. Music

> **Feature prefix:** `MU-`
> **Route:** `/app/music`
> **Phase:** P4
> **Sources of truth:**
> - `camxora_python/features/music/views/music_view.py`
> - `camxora_python/features/music/widgets/*`
> - `camxora_python/.docs/pages/07_MUSIC_REQUIREMENTS.md`
> - `camxora_python/shared/services/music_download_coordinator.py`
> - `platform_api/routers/{profiles,settings_router,prompts,music_history,credits,generation,batch,content_pools,music_downloads}.py`

---

## 1. Purpose

The batch composer and song editor: configure generation defaults, draft/polish lyrics,
select channel pairs, set automation flags, and generate one batch per planned day × channel
pair.

Not the operational recovery table (Progress), not the image editor, not the video editor.

---

## 2. Data

### 2.1 Workspace bootstrap (parallel)

| # | Method | Path | Purpose |
|---|---|---|---|
| 1 | GET | `/users/me` | Account context |
| 2 | GET | `/profiles` | Primary/secondary channels |
| 3 | GET | `/settings` | Music defaults, image mode, output dirs |
| 4 | GET | `/prompts/descriptions/public` | Description options |
| 5 | GET | `/prompts/structures/public` | Structure options |
| 6 | GET | `/music/history?limit=8` | History batches/songs |
| 7 | GET | `/credits/operation-costs` | Draft/Polish/Suno/Image labels |

Operation costs may fail gracefully → empty list.

### 2.2 Mutations

| # | Method | Path | Trigger |
|---|---|---|---|
| M-1 | PATCH | `/settings` | Debounced music settings autosave |
| M-2 | POST | `/content-pools/{kind}/claim` | Draft |
| M-3 | POST | `/content-pools/{kind}/finalize` | Draft success |
| M-4 | POST | `/content-pools/{kind}/release` | Draft failure |
| M-5 | POST | `/generation/draft` | Draft |
| M-6 | POST | `/generation/polish-lyrics` | Polish |
| M-7 | POST | `/batches` | Generate (one per day × pair) |
| M-8 | GET | `/batches/{id}` | Status poll after Generate |

### 2.3 Background coordinator

| # | Method | Path | Purpose |
|---|---|---|---|
| B-1 | GET | `/music/downloads/pending?limit=24` | Pending Suno MP3s |
| B-2 | POST | `/music/downloads/sync` | Report downloaded files |

Poll: 4 s while pending, 12 s idle.

---

## 3. Layout

```
[ error banner ]
[ loading card "Loading music workspace..." ]

[ top strip: From | To | Language | Creativity | Unique opening | Strict | History | Count | planned-days ]

[ Song card ] [ Primary channels ] [ Secondary channels ] [ Automation card ]

[ History card: filters | summary | table ]
```

Column ratio on wide screens: Song 1.5, Primary 0.75, Secondary 0.75, Automation 0.95.
Stack below 1280 px.

---

## 4. Features

### 4.1 Workspace load and state

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-01 | Parallel bootstrap | One worker/query for the seven calls; partial failures degrade gracefully | P0 |
| MU-02 | Loading | "Loading music workspace..." card until first success | P0 |
| MU-03 | Load error | Error banner with "Unable to load the music workspace from the current backend contracts." | P0 |
| MU-04 | Settings init | Apply API settings once; set the persisted snapshot to prevent a re-save loop | P0 |
| MU-05 | Prompt defaults | Auto-select the first description/structure when none is selected | P0 |
| MU-06 | Profile sanitisation | Fallback to the first/second profile when selections disappear | P0 |
| MU-07 | Refresh on return | Re-fetch on page activation; no stale composer reset | P1 |
| MU-08 | Dirty guard | Navigating away with unsaved composer text warns before discarding | P1 |

### 4.2 Top settings strip

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-09 | From/To | Date pickers bound to the batch range; default today | P0 |
| MU-10 | Language | English, Khmer, German, Spanish, French | P0 |
| MU-11 | Creativity | 0–100 slider with a live numeric label | P0 |
| MU-12 | Unique opening | Checkbox | P0 |
| MU-13 | Strict | 1–5 select | P0 |
| MU-14 | History window | 50/100/200/500/1500 | P0 |
| MU-15 | Count | 1–50 songs per batch | P0 |
| MU-16 | Planned days chip | "{n} planned day(s)" or an invalid-range message | P0 |
| MU-17 | Invalid range | To < From shows an error tone and disables Generate | P0 |
| MU-18 | Autosave | 400 ms debounce PATCH; status idle → saving → saved (1.8 s) → idle | P0 |
| MU-19 | Autosave guard | No autosave until initial settings are applied | P0 |
| MU-20 | Autosave error | Shows "Unable to save settings" and retries on the next change | P0 |

### 4.3 Song editor

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-21 | Draft button | Disabled when description is empty or a draft is pending | P0 |
| MU-22 | Polish button | Disabled when lyrics are empty or polish is pending | P0 |
| MU-23 | Draft credit label | From the `lyric` operation cost | P0 |
| MU-24 | Effect preview | Valence, danceability, instrumentalness bars from creativity | P0 |
| MU-25 | Polish strength | Slider 0–100 in the effect row | P0 |
| MU-26 | Title | Editable text field | P0 |
| MU-27 | Album | Editable text field | P0 |
| MU-28 | Lyrics | Multiline editor; preserves line breaks; no autocorrect | P0 |
| MU-29 | Seed notice | Shows claimed pool seeds after a successful draft | P0 |
| MU-30 | Copy title | Clipboard + toast | P0 |
| MU-31 | Copy lyrics | Clipboard + toast | P0 |
| MU-32 | Copy both | Clipboard + toast | P0 |
| MU-33 | Revisions | Disabled placeholder with "0 credits" | P0 |
| MU-34 | Duplicate Polish | Second Polish action in the action row (reference parity) | P0 |
| MU-35 | Character count | Shows lyric length; warns above the backend limit | P1 |
| MU-36 | Clear composer | Confirms before clearing title/album/lyrics | P1 |

### 4.4 Draft flow

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-37 | Avoid lists | Build from history using the selected window | P0 |
| MU-38 | Claim pool | Claims title, album and (when unique opening) opening seeds | P0 |
| MU-39 | Description suffix | Adds the inspiration suffix from claimed seeds | P0 |
| MU-40 | Draft request | POST `/generation/draft` with the full payload | P0 |
| MU-41 | Success | Finalize all claims; populate title/album/lyrics; store seeds | P0 |
| MU-42 | Failure | Release all claims; show the error; no partial composer overwrite | P0 |
| MU-43 | Reservation token | UUID, fallback `pool-{timestamp}-{random}` | P0 |
| MU-44 | Double submit | Blocked while pending; the button reflects the wait | P0 |
| MU-45 | Timeout | A slow draft stays cancellable and does not lock the page | P1 |

### 4.5 Polish flow

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-46 | Request | POST `/generation/polish-lyrics` with lyrics, strength and primary profile id | P0 |
| MU-47 | Success | Replaces the composer lyrics; undo is available | P0 |
| MU-48 | Failure | Error banner; original lyrics unchanged | P0 |
| MU-49 | Empty guard | No request when lyrics are blank | P0 |

### 4.6 Channel pairs

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-50 | Lists | Every profile appears in both Primary and Secondary | P0 |
| MU-51 | Toggle | Click selects/deselects; selected rows show a 1-based order index | P0 |
| MU-52 | Empty | "No profiles available yet." | P0 |
| MU-53 | Order preserved | Pairing uses list order by index | P0 |
| MU-54 | Overlap warning | Same profile on both sides shows an inline warning; Generate disabled | P0 |
| MU-55 | Count mismatch | Different primary/secondary counts show a warning; Generate disabled | P0 |
| MU-56 | Search | Filter profiles by name in each list | P1 |
| MU-57 | Select all/none | Bulk actions with the same validation | P2 |

### 4.7 Automation card

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-58 | Description select | Syncs the description text/id used by Generate | P0 |
| MU-59 | Structure select | Syncs the structure text/id | P0 |
| MU-60 | Auto image | Toggle `autoGenImage` | P0 |
| MU-61 | Auto GSuno | Toggle `autoGSuno` | P0 |
| MU-62 | Auto video | Toggle `autoVideoAfterSuno`; starts the Vizzy pipeline render for the run | P0 |
| MU-63 | Auto merge | Toggle `autoMergeAfterVideo`; merges validated long-form outputs | P0 |
| MU-64 | Auto reel | Toggle `autoReelAfterVideo`; renders the vertical reel branch | P0 |
| MU-65 | Auto upload | Visible but **disabled**, exactly as 1.7.1; upload uses the existing publication/manual flow | P0 |
| MU-66 | Info text | Explains the render → merge → reel stages and that upload remains manual/unchanged | P0 |
| MU-67 | Save status | "Saving…" / "Saved" / "Unable to save" | P0 |
| MU-68 | Batch status | Latest summary + polled batch status | P0 |
| MU-69 | Operation costs | Draft, Polish, Revisions (0), Suno, Image, Video, Merge, Upload labels | P0 |
| MU-70 | Plan line | `{days} day x {pairs} pair x {songs} songs = {n} song jobs` | P0 |
| MU-71 | Cost lines | Draft/Suno/Image/Video/Merge/Upload/Batch totals | P0 |
| MU-72 | Generate label | `Generate ({n} Credits)` or `Generate` | P0 |
| MU-73 | Generate disabled | Pending, no profiles, mismatch, overlap, invalid dates | P0 |
| MU-74 | Warnings | Pair count mismatch and same-profile overlap | P0 |
| MU-75 | Cost parity | Default 12; Auto image 92; Auto GSuno 40; 3-day + GSuno 120; manual image excludes image cost | P0 |
| MU-76 | Pipeline hand-off | Generate starts the selected render/merge/reel stages; status flows to Progress/Vizzy; a missing/incompatible saved **Vizzy** template blocks with a specific reason; Auto-Upload stays disabled; old Camxora templates are not selectable; no toggle silently no-ops | P0 |

### 4.8 Generate flow

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-77 | Fan-out | One POST `/batches` per planned day × primary pair | P0 |
| MU-78 | Payload | OK/ALT ids, description/structure ids, flags, count, language, creativity, `pairing_mode=match_key`, from=to=run date | P0 |
| MU-79 | Manual dirs | Plan OK/ALT run directories and pass `ok_run_dir`/`alt_run_dir`; create folders after the response | P0 |
| MU-80 | Manual base | `sunoOutputDir` or `downloadsDir` fallback | P0 |
| MU-81 | Success | Set latest batch id, summary, refresh workspace/history | P0 |
| MU-82 | Failure | Error banner; no batch id set; completed batches are reported | P0 |
| MU-83 | Summary | "Created 3 batch runs across 3 planned days and 1 channel pair." | P0 |
| MU-84 | Partial failure | If batch 2 of 3 fails, keep batch 1, report exactly what was created | P1 |
| MU-85 | Generate confirmation | For > 1 day or > 2 pairs, confirm the cost and count | P1 |

### 4.9 Batch status

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-86 | Poll | GET `/batches/{id}` every 2.5 s while active | P0 |
| MU-87 | Display | Status line in the automation card | P0 |
| MU-88 | Stop | Stop on page deactivate or cleared id | P0 |
| MU-89 | Failure | A poll error does not erase the last status | P1 |

### 4.10 History

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-90 | Flatten | Batches → songs with row numbers | P0 |
| MU-91 | Filters | From/To + "Last batch only" | P0 |
| MU-92 | Columns | No, Album, Title (+ batch index/id), Description, Structure, Primary (+ folder), Secondary (+ folder), Suno, Generated | P0 |
| MU-93 | Row click | Loads title/album/lyrics and description/structure ids into the composer | P0 |
| MU-94 | Seed reset | Row click clears draft pool seeds | P0 |
| MU-95 | Folder buttons | Ensure directory + open path; missing path shows an error | P0 |
| MU-96 | Empty | "No history rows match the current filters." | P0 |
| MU-97 | Summary | History summary + updated timestamp | P0 |
| MU-98 | Refresh | A new batch appears without a full app reload | P1 |
| MU-99 | Export | Copy/export the filtered history as CSV | P2 |

### 4.11 Shell download coordinator

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MU-100 | Start | Starts with an authenticated shell; survives route changes | P0 |
| MU-101 | Poll | Pending limit 24; 4 s/12 s cadence | P0 |
| MU-102 | Download | Writes the MP3 to `target_path`, verifies non-zero size | P0 |
| MU-103 | Sync | POST primary/secondary downloaded flags | P0 |
| MU-104 | Invalidate | Refreshes Progress and Music data after sync | P0 |
| MU-105 | Single-flight | No overlapping download runs | P0 |
| MU-106 | Retry/backoff | Failed downloads retry with a cap and surface in Diagnostics | P0 |
| MU-107 | Pause offline | Pauses when offline; resumes when online | P1 |

---

## 5. States

| State | Composer | Channels | Automation | History |
|---|---|---|---|---|
| Loading | placeholders | placeholders | placeholders | skeleton |
| Error | disabled or last values | last values | last values | last values |
| Invalid range | editable | editable | Generate disabled + warning | visible |
| Drafting | fields locked | editable | Generate disabled | visible |
| Generating | fields locked | locked | progress/status | visible |
| Success | refreshed | refreshed | new batch status | refreshed |
| Pipeline running | locked | locked | status/progress per stage | visible |

---

## 6. Tests

| ID | Scenario | Assert |
|---|---|---|
| MU-T1 | Inverted dates | Generate disabled + invalid range |
| MU-T2 | History headers | All nine columns + sample row |
| MU-T3 | Cost labels | Draft 3, Polish 3, Revisions 0, Suno 7, Image 5 |
| MU-T4 | Plan line | `1 day x 1 pair x 4 songs = 4 song jobs` |
| MU-T5 | Default total | 12 credits |
| MU-T6 | Auto image | 92 credits, image total 80 |
| MU-T7 | Auto GSuno | 40 credits, suno total 28 |
| MU-T8 | 3 days + GSuno | 120 credits, 3 batch calls with correct dates |
| MU-T9 | Draft | Pool inspiration in description + seed notice |
| MU-T10 | Automation hand-off | Auto video/merge/reel start the pipeline; Auto-Upload stays disabled; a missing template blocks with a reason |
| MU-T11 | Manual dirs | OK/ALT directories created with the correct names |
| MU-T12 | Autosave | 400 ms debounce, no loop, saved status |
| MU-T13 | Download sync | Pending → downloaded → synced; Progress refreshes |
| MU-T14 | Pipeline cost | Auto-Video/Merge/Reel/Upload costs appear in the preflight and are not double-charged on retry |

---

## 7. Dependencies

- Settings (music defaults, output dirs, profiles).
- Progress (download sync invalidation).
- Vizzy automation pipeline (Auto-Video/Merge/Reel/Upload) — **2.0.0**, see
  [`../09-PIPELINE-AUTOMATION.md`](../09-PIPELINE-AUTOMATION.md).
- Shell coordinator runtime.

---

## 8. Definition of Done

- [ ] MU-01 … MU-107 implemented; all `P0` verified against sandbox.
- [ ] Cost parity scenarios MU-T3 … MU-T8 pass exactly.
- [ ] Draft claim/finalize/release verified with a mocked pool and a real sandbox.
- [ ] Generate fan-out verified for 1/3 days and 1/2 pairs.
- [ ] Download coordinator runs in main and survives route changes.
- [ ] History row click round-trips a real song.
- [ ] Auto-Video/Merge/Reel start the pipeline and report status.
- [ ] Auto-Upload remains disabled exactly as 1.7.1.
- [ ] The cost label includes render/merge for the selected automation.
- [ ] Visual baseline approved.
