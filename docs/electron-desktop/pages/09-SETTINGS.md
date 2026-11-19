# 9. Settings

> **Feature prefix:** `ST-`
> **Route:** `/app/settings`
> **Phase:** P2 (Profiles/Preferences/Publication) + P8 (prompts, pools, Suno, diagnostics)
> **Sources of truth:**
> - `camxora_python/features/settings/views/settings_view.py`
> - `camxora_python/features/settings/widgets/*`
> - `camxora_python/shared/workers/data_workers.py` (settings workers)
> - `platform_api/routers/{profiles,profile_video_templates,settings_router,prompts,content_pools,youtube,image_sample_packs,client_logs}.py`

---

## 1. Purpose

The control room for channel profiles, YouTube publication, local paths and workers, image
rendering, prompt libraries, content pools and Suno defaults.

Eight tabs: **Profiles, Publication, Preferences, Descriptions, Structures, Moods, Pools,
Suno**.

Not a place for per-run actions (those live on Music/Image/Progress).

---

## 2. Layout

```
[ header: Settings ]
┌────────────────────┬──────────────────────────────────────────────┐
│ Profiles           │ selected tab content (scrolls)              │
│ Publication        │                                              │
│ Preferences        │                                              │
│ Descriptions       │                                              │
│ Structures         │                                              │
│ Moods              │                                              │
│ Pools              │                                              │
│ Suno               │                                              │
├────────────────────┴──────────────────────────────────────────────┤
│ dirty summary · [Save all changes]  [Discard]                      │
└───────────────────────────────────────────────────────────────────┘
```

The footer is sticky. It shows how many tabs are dirty and the last save result. Tabs that
have immediate actions (YouTube connect) are marked as such.

---

## 3. Profiles tab

### 3.1 List / selection

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-01 | Profile list | All profiles with name, folder, run prefix; sorted by name | P0 |
| ST-02 | Search | Matches name, folder and run prefix; case-insensitive | P0 |
| ST-03 | Select | Selecting a profile loads it into the editor; unsaved draft warns | P0 |
| ST-04 | New profile | Creates a draft; only name is required | P0 |
| ST-05 | Profile limit | Shows `{used} / {allowance}`; New disabled at the cap with an explanation | P0 |
| ST-06 | Delete | Confirmation; deletes via API; selects the next profile | P0 |
| ST-07 | Empty | "No profiles yet." + New profile | P0 |

### 3.2 Editor

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-08 | Identity card | Initials/logo preview, name, folder, run prefix | P0 |
| ST-09 | Name | Required; max length; trims | P0 |
| ST-10 | Folder name | Auto-generated from name until manually edited | P0 |
| ST-11 | Run prefix | Optional; validation for safe filename characters | P0 |
| ST-12 | Logo upload | File picker, preview, upload/cache; replaces on save | P0 |
| ST-13 | Cover upload | File picker, preview, upload/cache | P0 |
| ST-14 | Video template | Select a **Vizzy** pipeline template; validation blocks a missing/incompatible template; old Camxora templates are not listed | P0 |
| ST-15 | Reel template | Select a reel-kind **Vizzy** pipeline template; validation enforces the vertical output | P0 |
| ST-16 | Output resolution | 1920×1080, 1080×1920, 1080×1080, 1280×720 | P0 |
| ST-17 | Image mode | BG + TH / BG Only / TH Only | P0 |
| ST-18 | YouTube card | Connected channel name; Connect / Disconnect / Refresh | P0 |
| ST-19 | Save | Validates, saves, updates the list and identity card | P0 |
| ST-20 | Cancel | Reverts the draft to the last saved values | P0 |
| ST-21 | Dirty guard | Switching profile/tab with unsaved changes prompts | P0 |
| ST-22 | Media cache | Remote logo/cover is cached locally and survives restart | P1 |
| ST-23 | Delete guard | Cannot delete a profile referenced by an active run without confirmation | P1 |
| ST-24 | Folder collision | Explains when the folder name is already used | P1 |

---

## 4. Publication tab

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-25 | Profile selector | Loads publication defaults for the selected profile | P0 |
| ST-26 | YouTube status | Connected/Not connected; locked note when no channel | P0 |
| ST-27 | Visibility | Public / Unlisted / Private / Scheduled | P0 |
| ST-28 | Schedule | Hour/minute pickers + Clear; only enabled for Scheduled | P0 |
| ST-29 | Schedule summary | Human summary of the scheduled time/timezone | P0 |
| ST-30 | Audience | Made for kids checkbox | P0 |
| ST-31 | AI use | Yes/No disclosure | P0 |
| ST-32 | Category | YouTube categories list | P0 |
| ST-33 | Playlist | Select from channel playlists | P0 |
| ST-34 | Create playlist | Creates a playlist via the API and selects it | P0 |
| ST-35 | Channel description | Multiline | P0 |
| ST-36 | Keywords | Comma-separated, max length | P0 |
| ST-37 | Tags | Comma-separated, max count | P0 |
| ST-38 | Title template | Supports the documented tokens; live preview | P0 |
| ST-39 | Description template | Supports tokens; live preview | P0 |
| ST-40 | Validation | Shows field-level errors before save | P0 |
| ST-41 | Save publication | Saves only the publication fields; keeps the user on the tab | P0 |
| ST-42 | Dirty state | Save disabled until a change | P0 |
| ST-43 | Playlist load failure | Playlist select degrades; the rest of the tab still works | P1 |
| ST-44 | Schedule timezone | Shows the account timezone and converts correctly | P1 |

---

## 5. Preferences tab

### 5.1 Local paths

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-45 | FFmpeg path | Field + Browse + Open + Download FFmpeg | P0 |
| ST-46 | FFmpeg validation | Probe on save; shows the version or a readable error | P0 |
| ST-47 | FFmpeg download | Downloads to the managed tools folder with progress | P1 |
| ST-48 | Suno output dir | Field + Browse + Open; persists across updates | P0 |
| ST-49 | Path warnings | Warns when the drive is missing or not writable | P0 |
| ST-50 | Folder layout note | Explains `{channel}/{date_album}` and shared subfolders | P0 |

### 5.2 Workers

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-51 | Music workers | 1–5 | P0 |
| ST-52 | Image workers | 1–8 | P0 |
| ST-53 | Export workers | 1–10 | P0 |
| ST-54 | Merge workers | 1–2 | P0 |
| ST-55 | YouTube workers | 1–5 | P0 |
| ST-56 | Chunk size | 128/256/512 MB | P0 |
| ST-57 | Guardrail | Warns when the total exceeds a safe CPU/memory budget | P1 |
| ST-58 | Restart note | Explains which changes apply immediately vs after restart | P1 |

### 5.3 Image and rendering

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-59 | Output resolution | Same list as profiles | P0 |
| ST-60 | Style strength | 0–100 slider with a numeric label | P0 |
| ST-61 | Image source mode | AI Generated / User Provided | P0 |
| ST-62 | Background source | Prompt only / Category / Admin library | P0 |
| ST-63 | Thumbnail source | Prompt only / Category / Admin library | P0 |
| ST-64 | Thumbnail generation | AI text on background / Composite (legacy) | P0 |
| ST-65 | Mode coupling | AI mode shows reference controls; User mode hides them | P0 |
| ST-66 | Explanation | One note explaining style strength and source semantics | P0 |
| ST-67 | Server-managed packs | When the server manages samples, hide local pack/library controls and explain | P0 |

### 5.4 Sample packs and library (only when local packs are enabled)

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-68 | Pack list | Background/thumbnail packs with version/size | P1 |
| ST-69 | Install | Downloads and installs with progress | P1 |
| ST-70 | Reload | Refreshes the pack list | P1 |
| ST-71 | Curation | Pin up to 5 background and 5 thumbnail samples | P1 |
| ST-72 | Random toggle | Random background/thumbnail sample | P1 |
| ST-73 | Hover preview | Hovering a sample previews it | P2 |
| ST-74 | Least-used note | Explains the least-used rotation | P2 |

### 5.5 Storage and diagnostics

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-75 | Cache size | Shows the audio-analysis cache size | P0 |
| ST-76 | Clear cache | Confirms and deletes only the cache; does not touch user files | P0 |
| ST-77 | Cache policy | Shows the 2 GB / 30-day policy | P0 |
| ST-78 | Diagnostics status | "Logs stay on this computer until you send them." | P0 |
| ST-79 | Send diagnostics | Packages redacted logs + app/OS info; shows upload id | P0 |
| ST-80 | Redaction | Tokens, emails, cookies and sensitive paths are absent | P0 |
| ST-81 | Raw console | Hidden unless `CAMXORA_SHOW_DIAGNOSTICS=1` | P1 |

---

## 6. Descriptions / Structures / Moods tabs

These three tabs share one component with a different `kind`.

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-82 | Workspace default | Select the default for the Music page | P0 |
| ST-83 | Default structure | Description tab only; selects the structure paired with a description | P0 |
| ST-84 | Selected name | Shows the selected catalog entry | P0 |
| ST-85 | User catalog | Paginated list of user-owned entries | P0 |
| ST-86 | Prompt editor | Create/edit name + body; validation; character count | P0 |
| ST-87 | Save | Creates/updates the user entry and refreshes the list | P0 |
| ST-88 | Delete | Confirmation; deletes the selected user entry | P0 |
| ST-89 | Save all | Workspace defaults apply only after "Save all changes" | P0 |
| ST-90 | Admin entries | Read-only; a label distinguishes admin vs user entries | P0 |
| ST-91 | Search | Filters the user catalog | P1 |
| ST-92 | Empty | "No user prompts yet." + Create | P0 |
| ST-93 | Error | Inline error; the editor keeps the typed value | P0 |

**Status (P8, `desktop/settings-p8`):**

- [x] ST-82–ST-93 implemented for Descriptions, Structures and Moods (`prompt-catalog-tab.tsx`)
- [x] Workspace defaults read/patch `defaultDescriptionId`, `defaultStructureId`, `defaultMoodId` and apply on Save all
- [x] User CRUD against `/prompts/me/{kind}`; admin entries are labelled read-only
- [x] Covered by `tests/unit/settings-prompts.test.ts` and `tests/e2e/settings.mjs`

---

## 7. Pools tab

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-94 | Stats | Openings, titles, albums, ownership counts | P0 |
| ST-95 | Table | Paginated pool contents (page size 50) | P0 |
| ST-96 | Pager | Previous/Next, page label, disabled at bounds | P0 |
| ST-97 | Current pool note | Summary for the selected pool kind | P0 |
| ST-98 | Read-only | No edit controls; explains editing is in the Admin Portal | P0 |
| ST-99 | Error | "Pool counts are unavailable right now." | P0 |
| ST-100 | Refresh | Manual refresh of counts/table | P1 |

**Status (P8, `desktop/settings-p8`):**

- [x] ST-94–ST-100 implemented in `pools-tab.tsx`
- [x] Page size 50 with `Previous`/`Next`, range + page labels and bounds disabled
- [x] Read-only: no form controls; the tab explains that editing is in the Admin Portal
- [x] The stats endpoint has no per-user ownership counts, so the summary says “Account-wide”

---

## 8. Suno tab

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-101 | Default version | Supported versions only | P0 |
| ST-102 | Auto merge | Toggle | P0 |
| ST-103 | Merge group size | Numeric with bounds | P0 |
| ST-104 | Timeout | Milliseconds, bounded | P0 |
| ST-105 | Retry count | Bounded | P0 |
| ST-106 | Validation | Invalid values block save with a field error | P0 |
| ST-107 | Supported note | Explains only supported defaults are shown | P0 |

**Status (P8, `desktop/settings-p8`):**

- [x] ST-101–ST-107 implemented in `suno-tab.tsx`
- [x] Bounds: timeout 1000–600000 ms, retries 0–20, merge group 0–20; out-of-range values block the save
- [x] Patches only changed `suno*` keys and leaves unknown settings keys untouched
- [x] An unsupported stored version is shown as “not supported” and must be changed before saving

---

## 9. Global behaviour

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| ST-108 | Dirty tracking | Footer lists dirty tabs; Save enabled only when dirty | P0 |
| ST-109 | Save all | Saves every dirty tab in a deterministic order; reports partial failure | P0 |
| ST-110 | Discard | Reverts all dirty tabs after confirmation | P0 |
| ST-111 | Per-tab save | Publication and Profiles have their own save action | P0 |
| ST-112 | Optimistic cache | Settings are cached for first paint; revalidated in the background | P0 |
| ST-113 | Account switch | Settings reset for the new account; no cross-account leakage | P0 |
| ST-114 | YouTube OAuth | Connect starts the browser flow; polling updates the card; disconnect confirms | P0 |
| ST-115 | YouTube mismatch | Connecting a channel that does not match the profile warns | P1 |
| ST-116 | Token expiry | YouTube auth errors give a "Reconnect from the YouTube tab" action | P0 |
| ST-117 | Unsaved navigation | Leaving Settings with dirty tabs prompts | P0 |
| ST-118 | Keyboard | Tab list arrow navigation; Save shortcut `Ctrl/Cmd+S` | P1 |
| ST-119 | Loading | Per-tab skeleton, not a full-page spinner | P0 |
| ST-120 | Error | One error banner per tab; fields keep values | P0 |

---

## 10. Tests

| ID | Scenario | Assert |
|---|---|---|
| ST-T1 | Profile create | Name-only profile appears in the list and API |
| ST-T2 | Folder auto-slug | "Beattok Remixes" → `beattok-remixes` until edited |
| ST-T3 | Profile save | Resolution/image mode/templates round-trip |
| ST-T4 | Publication save | Visibility/schedule/category persist |
| ST-T5 | Schedule validation | Schedule only when visibility = Scheduled |
| ST-T6 | Paths | FFmpeg probe and Suno dir persist |
| ST-T7 | Workers | Values save and apply per the restart note |
| ST-T8 | Image mode | AI/manual toggles the reference controls |
| ST-T9 | Prompts | Create/edit/delete a user description |
| ST-T10 | Pools | Pagination and read-only state |
| ST-T11 | Suno | Bounds validation |
| ST-T12 | Dirty save | Save all writes only dirty tabs |
| ST-T13 | Account switch | No previous account values remain |
| ST-T14 | YouTube | Connect/disconnect/poll states |
| ST-T15 | Diagnostics | Redaction verified with a seeded secret |

---

## 11. Dependencies

- Profiles, YouTube, prompts, content pools, sample packs, Suno settings endpoints.
- Template store (Video/Reel template pickers).
- FFmpeg service and managed paths.
- Diagnostics/logger service.

---

## 12. Definition of Done

- [ ] ST-01 … ST-120 implemented; all `P0` verified against sandbox.
- [x] ST-82 … ST-107 (Descriptions, Structures, Moods, Pools, Suno) implemented and verified with the fixture API.
- [x] All eight tabs have loading/error/empty/dirty states.
- [ ] Video/Reel template pickers only offer compatible pipeline templates.
- [ ] Profile CRUD and publication round-trip verified.
- [x] Prompt CRUD round-trip verified (Descriptions/Structures/Moods, fixture API).
- [ ] YouTube OAuth verified end-to-end.
- [ ] Diagnostics redaction verified.
- [ ] ST-T1 … ST-T15 pass.
- [ ] Visual baseline approved.
