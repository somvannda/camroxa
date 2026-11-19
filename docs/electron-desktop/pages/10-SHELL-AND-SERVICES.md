# 10. Shell and Shared Services

> **Feature prefix:** `SH-`
> **Scope:** global — window, navigation, session, updates, notifications, background
> coordinators, files, diagnostics, command palette
> **Phase:** P0/P1
> **Sources of truth:**
> - `camxora_python/app/root_window.py`, `app/application.py`, `app/router.py`
> - `camxora_python/shared/services/*`
> - `camxora_python/shared/widgets/*`
> - `camxora_python/shared/workers/*`

---

## 1. Window and app lifecycle

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-01 | Single instance | A second launch focuses the existing window and exits | P0 |
| SH-02 | Frameless window | Custom title bar, drag region, minimise/maximise/close, double-click to maximise | P0 |
| SH-03 | Window state | Remembers size, position and maximised state; restores on screen | P0 |
| SH-04 | Minimum size | 1280×800; layout never clips at that size | P0 |
| SH-05 | App icon | Taskbar/Start menu icon; stable AppUserModelID on Windows | P0 |
| SH-06 | Deep links | `camxora://auth/callback` and `camxora://project/...` route correctly | P1 |
| SH-07 | Quit guard | Running exports/downloads prompt before quit; cancel/stop is offered | P0 |
| SH-08 | Crash recovery | Renderer crash shows a reload screen; main crash writes a dump and restarts cleanly | P0 |
| SH-09 | Env selection | Sandbox/production baked into the build; no user-facing switch | P0 |
| SH-10 | Global error boundary | An unexpected renderer error shows a recoverable panel, not a blank window | P0 |

---

## 2. Shell chrome

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-11 | Sidebar | Account card, workspace routes, utility routes, logout | P0 |
| SH-12 | Active route | 2 px accent rail + surface step; exactly one active row | P0 |
| SH-13 | Route badges | Progress shows active/failed count; Music shows pending downloads | P1 |
| SH-14 | Page header | Eyebrow/title/description + page actions; hidden for Vizzy | P0 |
| SH-15 | Footer | Status message, live dot, environment, version, credits/profiles | P0 |
| SH-16 | Flash messages | Success/error toasts with one action; 4 s auto-dismiss | P0 |
| SH-17 | Command palette | `Ctrl/Cmd+K`; every route and primary action; fuzzy search | P1 |
| SH-18 | Keyboard shortcuts | Global map documented in Help; `Ctrl+1…9` routes, `Ctrl+,` settings | P1 |
| SH-19 | Notification centre | In-app list of recent notifications with read state | P1 |
| SH-20 | Offline indicator | Sidebar/footer dot when offline; pages show cached data | P0 |
| SH-21 | Theme | Dark theme only in 2.0.0; tokens centralised; no light-theme half-state | P0 |
| SH-22 | Vizzy mode | Sidebar collapses to 64 px; shell header reduces to a project strip | P0 |
| SH-23 | Window controls | Native-like controls respect the OS; no fake macOS dots on Windows | P1 |

---

## 3. Session and security

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-24 | Token storage | `safeStorage` encrypted; never in `localStorage`/logs | P0 |
| SH-25 | Refresh single-flight | Concurrent 401s share one refresh | P0 |
| SH-26 | Rotation | Rotated refresh tokens are persisted atomically | P0 |
| SH-27 | Session expiry | Emits one `session:expired`; returns to login; no request storm | P0 |
| SH-28 | Saved accounts | List summaries only; no tokens in the list | P0 |
| SH-29 | Logout | Clears tokens, query cache, per-user caches | P0 |
| SH-30 | Sensitive redaction | Logger redacts tokens, emails, cookies, absolute paths | P0 |
| SH-31 | IPC validation | Every channel validates input and output with Zod | P0 |
| SH-32 | Navigation lock | External navigation is blocked/opened in the browser | P0 |
| SH-33 | Permission handler | Camera/mic/geolocation denied by default; notifications allowed | P0 |
| SH-34 | CSP | Strict policy; no remote scripts; no `unsafe-eval` | P0 |

---

## 4. API client

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-35 | Base URL | Environment-specific; renderer never sees it | P0 |
| SH-36 | Auth injection | Bearer attached in main; renderer never handles access tokens | P0 |
| SH-37 | Error envelope | `{ code, message, detail, requestId }` from platform errors | P0 |
| SH-38 | Retry policy | GET retries network/5xx; mutations do not auto-retry | P0 |
| SH-39 | Timeouts | Read 30 s, generation 120 s, export 600 s | P0 |
| SH-40 | Upload | Multipart with progress; cancel where supported | P0 |
| SH-41 | Schema drift | OpenAPI type check fails CI on drift | P1 |
| SH-42 | Offline queue | Mutations are not queued; the UI explains and allows retry | P0 |

---

## 5. Background coordinators

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-43 | Music downloads | 4 s/12 s, download + sync, single-flight | P0 |
| SH-44 | Pipeline recovery | 60 s, missing local files, re-fetch, run state | P0 |
| SH-45 | Image output sync | 30 s, path/status reconciliation | P0 |
| SH-46 | Progress local sync | 60 s, reconcile local run state | P0 |
| SH-47 | Video pipeline | Event-driven render/merge/reel/upload jobs on the Vizzy renderer | P0 |
| SH-48 | Workspace prefs | Debounced push to `/settings` | P1 |
| SH-49 | Update check | Start + 6 h; respects channel and mandatory gate | P0 |
| SH-50 | Notifications | Persistent connection; OS + in-app; dedupe | P0 |
| SH-51 | Coordinator status | Diagnostics shows last run, next run, last error | P1 |
| SH-52 | Kill switch | Each coordinator can be paused in Settings (support-only) | P1 |
| SH-53 | Offline pause | All coordinators pause offline and resume with backoff | P0 |

---

## 6. Files, media and FFmpeg

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-54 | File picker | Native dialogs; filters; multi-select | P0 |
| SH-55 | Open/reveal | Opens the OS viewer / reveals in folder; missing path explained | P0 |
| SH-56 | Ensure directory | Creates nested dirs; surfaces permission errors | P0 |
| SH-57 | Media protocol | `camxora-media://` streams allowlisted files with range support | P0 |
| SH-58 | Image preview | Reads image bytes off the UI thread; no flicker | P0 |
| SH-59 | FFmpeg probe | Version/codecs; graceful when missing | P0 |
| SH-60 | FFmpeg job queue | Concurrency 2, progress, cancel, cleanup | P0 |
| SH-61 | Output validation | Probe duration/streams before reporting success | P0 |
| SH-62 | Path safety | Symlink/`..` checks; no writes outside managed roots without user choice | P0 |
| SH-63 | Disk space check | Warns before a large export when free space is low | P1 |
| SH-64 | Temp cleanup | Removes partial outputs and temp frames on failure/quit | P0 |

---

## 7. Updates and packaging

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-65 | Release check | Version manifest; channel-aware | P0 |
| SH-66 | Mandatory gate | Blocks the app until installed or explicitly quit | P0 |
| SH-67 | Background download | Progress; resumable where supported | P1 |
| SH-68 | Install/relaunch | Closes children, writes marker, relaunches | P0 |
| SH-69 | Failure recovery | Restores the previous version and shows the persisted error | P0 |
| SH-70 | Signature | Installer and update payload verified | P0 |
| SH-71 | Uninstall | Removes app files; keeps user projects/settings unless selected | P0 |
| SH-72 | First run | Creates managed dirs, seeds settings, shows a short setup check | P1 |

---

## 8. Diagnostics and support

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| SH-73 | Structured logs | JSONL, rotated, 7-day retention | P0 |
| SH-74 | Log viewer | Hidden route; filter by level/category; copy | P1 |
| SH-75 | Send diagnostics | Bundles logs + app/OS + note; preview size; upload id | P0 |
| SH-76 | Redaction check | Seeded token/email/path absent from the bundle | P0 |
| SH-77 | Crash report | Last crash summary included on request | P1 |
| SH-78 | System info | App version, Electron/Chromium/Node, OS, GPU, locale | P1 |
| SH-79 | Support IDs | Batch id, request id and job id are copyable from errors | P1 |

---

## 9. Tests

| ID | Scenario | Assert |
|---|---|---|
| SH-T1 | Second launch | Focuses existing window |
| SH-T2 | Session expiry | One refresh, then login |
| SH-T3 | Token leakage | No token/email in logs or diagnostics |
| SH-T4 | IPC fuzz | Invalid payloads rejected without crash |
| SH-T5 | Coordinator offline | Pauses and resumes |
| SH-T6 | FFmpeg cancel | Process stops, partial output removed |
| SH-T7 | Media protocol | Outside-root path rejected |
| SH-T8 | Update failure | Previous version restored |
| SH-T9 | Crash boundary | Renderer crash recoverable |
| SH-T10 | Window restore | Size/position restored on screen |

---

## 10. Definition of Done

- [ ] SH-01 … SH-79 implemented; all `P0` verified.
- [ ] Security review signed off (CSP, IPC, tokens, navigation).
- [ ] Diagnostics redaction verified with seeded secrets.
- [ ] Coordinators survive route changes and app sleep/resume.
- [ ] Installer/update/uninstall verified on a clean Windows VM.
- [ ] SH-T1 … SH-T10 pass.
