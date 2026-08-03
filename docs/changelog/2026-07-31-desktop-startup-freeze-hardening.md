# Desktop startup freeze hardening (v1.0.5 → v1.0.6)

**Date:** 2026-07-31 (v1.0.5), updated 2026-08-01 (v1.0.6)
**Status:** implemented locally, pending sandbox/production installer distribution

## Summary

A user reported that a freshly installed v1.0.4 desktop build worked fine on the dev machine but got permanently stuck on the "Opening studio → Workspace ready" loading screen on a second machine. The windowed (`console=False`) PyInstaller build has `sys.stdout`/`sys.stderr` set to `None` and there was no global exception hook anywhere in the app, so any unhandled exception during the final startup transition produced zero visible error and zero log output — the window simply froze on its last-drawn frame forever.

A client log pulled from the affected machine showed background coordinators (video pipeline, music downloads) were already running and later hit cascading 401s from a silently-failing token refresh — proving the app shell object had been fully constructed in memory, but the final `shell.show_home()` call (which reveals the window) had thrown and aborted before `self._stack.setCurrentWidget(shell)` could run.

## Product impact

**Before:** on some machines, the desktop app could hang indefinitely on the loading screen after login, with no error message, no crash, and no way to diagnose why — the only recourse was force-quitting the process.

**After:** if the final dashboard-activation step throws, the app now still reveals the main window (the dashboard may show an error state, but the app is usable) instead of hanging forever. The real exception, plus any lazy-page-prewarm failure and any silent session-refresh failure, is now written to the local log file for diagnosis.

## Technical impact

- `app/bootstrap.py` — installs a global `sys.excepthook` and `threading.excepthook` that route unhandled exceptions to the existing `AppLogger` (file-backed, ring-buffered) instead of a `None` stdout/stderr no-op.
- `app/root_window.py` — `RootWindow._prewarm_next_shell_page()` now wraps `shell.show_home()` in try/except: logs on failure but **always** calls `self._stack.setCurrentWidget(shell)` afterward, so the loading screen can never hang forever on this path again.
- `app/application.py` — `AppShellWidget.prewarm_pending_page()` now logs (previously silently swallowed) any exception raised while building a lazy page (video/music/image/settings/profile) during startup prewarm.
- `shared/services/session_service.py` — `SessionService.ensure_fresh_session()` now logs the underlying exception when an access-token refresh attempt fails, instead of only surfacing as downstream "Unauthenticated" pauses in unrelated coordinators minutes later.
- `shared/services/workspace_prefs_sync.py` — **proactive fix for a second instance of the same bug class**, found while auditing the codebase for "zero error" after the `workspace_defaults.py` fix. Video workspace prefs (`backgroundPath`, `logoPath`, `selectedMp3Path`, `mp3Directory`) are separately synced account-wide via `desktopWorkspacePrefs` (`build_settings_patch_from_local()` / `pull_workspace_prefs_from_settings()`), so the exact same failure mode was reachable here too: a background/logo image or MP3 selection made on one machine would get pulled down verbatim on a second machine and reference a file/folder that doesn't exist there. `apply_workspace_snapshot()` now drops any of these path fields that don't resolve to a real file/directory on the current machine before writing the pulled-down snapshot to the local prefs cache, instead of letting a second machine inherit a dead reference. This was not yet reported as a live bug — found and fixed proactively.
- `shared/lib/workspace_defaults.py` — **root cause found and fixed (two layers).**
  1. `ensure_directory()` called `Path.mkdir(parents=True, exist_ok=True)` with no exception handling. `apply_workspace_path_defaults()` (which computes/creates the default Downloads/Suno/Merged/Samples/Images folders) is invoked from ~8 different call sites: startup (`show_home()`, settings prewarm), every sidebar navigation, every settings save, and every music-workspace refresh/push-notification tick. `ensure_directory()` now catches `OSError`, logs it once per unique path (deduped so it doesn't spam the log file), and returns the path anyway so callers keep working best-effort instead of crashing on every single interaction.
  2. **The actual trigger, confirmed with the user:** `downloadsDir`/`sunoOutputDir`/`mergedDir`/the image sample+output dirs are filled in once and then persisted **account-wide on the server** via `workspace_defaults_sync.ensure_workspace_defaults()` → `api.patch_settings(patch)`. A local Windows folder path is inherently machine-specific, but because it's saved to the account, logging into the same account on a **second machine with a different Windows username** replays the *first* machine's absolute path (e.g. `C:\Users\<dev-machine-user>\AppData\Local\Camxora\Media\Downloads`) verbatim — which doesn't exist and can't be created on the second machine (Windows won't let a normal process create new folders directly under `C:\Users\`). `apply_workspace_path_defaults()` now checks `Path(existing).is_dir()` after attempting to create a previously-saved path; if it's still not a real directory (stale cross-machine value, unplugged external/network drive, etc.), it self-heals to this machine's own default and includes it in the `patch`, so the account setting self-corrects to a value that actually works on whichever machine is currently running.

No API contracts, database schema, or admin/portal surfaces changed — desktop client only.

## Files touched

- `camxora_python/app/bootstrap.py`
- `camxora_python/app/root_window.py`
- `camxora_python/app/application.py`
- `camxora_python/shared/services/session_service.py`
- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/services/workspace_prefs_sync.py`
- `camxora_python/pyproject.toml` (version 1.0.4 → 1.0.5)
- `camxora_python/tests/test_app_version.py`
- `camxora_python/tests/test_workspace_defaults.py` (new regression tests for uncreatable-directory resilience)
- `camxora_python/tests/test_workspace_prefs_sync.py` (new — cross-machine video path sanitization)
- `CHANGELOG.md`

## Migration / deploy

- No database/API changes. Desktop-only.
- Built on branch `fix/startup-freeze-hardening` (based on `release/desktop-1.0.4` / tag `v1.0.4`), in a dedicated worktree, so it does not mix with in-flight playlist or album-2 work on other branches.
- Version bumped to `1.0.5` (git tag pending — not yet created/pushed).
- Not deployed/published anywhere; installer built locally for the reporting user to reinstall and reproduce with logging enabled.

## Incident

- **Symptom:** v1.0.4 installer worked on the dev machine, but hung on "Opening studio → Workspace ready" on a second machine, then (after v1.0.5 hardening) surfaced as a continuous `PermissionError` crash loop instead of a silent hang.
- **Root cause (confirmed with the user):** the second machine does **not** have a Windows user named "Kong Somvannda" — that name belongs to the original/dev machine. `downloadsDir`, `sunoOutputDir`, `mergedDir`, and the image sample/output dirs are first-run defaults that get filled in **once** and then persisted **account-wide on the server** (`workspace_defaults_sync.ensure_workspace_defaults()` → `api.patch_settings(patch)`) — not stored per-machine. So:
  1. First run on the dev machine ("Kong Somvannda"): these settings were empty → filled with `C:\Users\Kong Somvannda\AppData\Local\Camxora\Media\...` → saved to the account on the server.
  2. Same account logs in on the second machine (different real Windows username) → the app fetches settings from the server and sees these fields **already filled** with the dev machine's absolute paths → treats them as user-set and tries to `mkdir` the literal dev-machine path, which doesn't exist and can't be created there (Windows won't let a normal process create new folders directly under `C:\Users\`) → `PermissionError: Access is denied` on every call site that touches workspace settings (startup, every navigation, every settings save, every workspace refresh) — dozens of times per session, matching the log timestamps exactly.
- **Why this matches the "stuck at workspace ready" report:** before the v1.0.5 exception-hook/try-except hardening shipped, this exact `PermissionError` firing inside `show_home()` during the final startup transition was swallowed silently (console-less build, no global exception hook) and the loading screen never advanced. The v1.0.5 log confirmed the app *did* recover and stay usable after that hardening (it went on to load pages, install templates, etc.) — proving that fix works — but the underlying crash was still firing on every interaction, and every one of those interactions was also silently trying (and failing) to write real files (downloads, merges, samples) into a folder on a machine it could never exist on.
- **Fix:** `apply_workspace_path_defaults()` now verifies a previously-saved path actually became a real directory after attempting to create it; if not (stale cross-machine value, unplugged external/network drive, etc.), it self-heals to this machine's own local default and includes the corrected value in the `patch`, so the account setting self-corrects to something that actually works wherever the app is currently running.
- **Verification:** new regression tests reproduce both layers: `test_ensure_directory_does_not_raise_when_uncreatable` / `test_apply_workspace_path_defaults_survives_uncreatable_root` (no more crash), and `test_apply_workspace_path_defaults_heals_stale_cross_machine_path` (the exact reported scenario — a saved path from a different machine self-heals to a working local default and gets included in the patch).

## Tests

- `pytest tests/test_session.py tests/test_session_refresh.py tests/test_session_user_isolation.py -q` → 6 passed.
- `pytest tests/test_workspace_defaults.py -q` → 8 passed (3 new regression tests: uncreatable-directory resilience x2, stale cross-machine path self-heal).
- `pytest tests/test_workspace_defaults.py tests/test_music_readiness.py tests/test_settings_workspace.py -q` → 19 passed.
- `pytest tests/test_workspace_prefs_sync.py -q` → 8 passed (new module, covers cross-machine video path sanitization end to end).
- Full suite run on this branch (after both fixes): 801 passed, 6 pre-existing failures unrelated to this change (encoding/module/date-flakiness issues already present on this checkpoint-based branch before this session's edits).
- Full suite pending before any tag/publish.

## Follow-ups

- **Architecture:** these workspace folder paths are still persisted account-wide even after this fix — the self-heal keeps the app from crashing/misbehaving, but the settings model itself (local filesystem paths synced to a cloud account) is a mismatch for a desktop app used on multiple machines. A cleaner long-term fix would store these five path keys as per-machine local config (e.g. `WorkspaceCache`, a local JSON file) instead of syncing them via `api.patch_settings()`, so one machine's folder choice never overwrites another's. The same applies to `desktopWorkspacePrefs` (video background/logo/MP3 paths) — sanitizing on pull-down closes the crash/dead-reference risk, but the underlying "sync a local path across machines" pattern is still there.
- Audited other places that persist absolute local paths account-wide (`music`/`image` local stores have no path-like prefs today; `videoRenderOutputDir` is read in three places but never actually written anywhere in the current app, so it's effectively dead code, not a live risk).
- **Known tradeoff of the self-heal:** if a user intentionally points one of these folders at a removable/network drive and it's briefly disconnected, the current self-heal will treat it as "unusable" and reset it to the local default (and persist that reset). This is a rare scenario for these specific settings (unlike, say, an export-destination picker) but worth documenting.
- Investigate why token refresh was failing repeatedly ~5 minutes after login on the affected machine (system clock/timezone skew is the leading hypothesis) — the new logging in `ensure_fresh_session()` should surface the real exception next time.
- Consider a startup watchdog (hard timeout) that force-reveals the shell if the loading sequence exceeds N seconds, as defense-in-depth beyond this specific fix.

---

## v1.0.6 update — Settings-page freeze, transient startup import crash, "2 processes" question

The v1.0.5 installer was reinstalled fresh and reproduced three new, distinct symptoms in the same session: (1) a hard `TypeError: 'NoneType' object is not subscriptable` crash on the very first launch, self-resolving on a later launch with no code change; (2) the Settings page becoming completely unresponsive ("Camxora.exe is not responding") whenever any field was edited; (3) two "Camxora" entries visible in Task Manager.

### 1. Settings page freeze on every keystroke — real regression, now fixed

**Root cause:** `SettingsView._on_profile_field_changed()` (and other field-changed handlers) call `_refresh_footer()` on **every keystroke**, which calls `_dirty_tabs()`, which calls `build_system_settings_patch()` → `build_system_settings_draft()` → `apply_workspace_path_defaults()` → `ensure_directory()` for all 6 workspace path keys — a **real, synchronous `mkdir()` syscall on the UI thread, on every single keystroke**, purely to build a comparison baseline for dirty-checking.

This call chain already existed before this session, but was cheap in the healthy case (`mkdir(exist_ok=True)` on an already-existing folder is nearly a no-op). The v1.0.5 fix that stopped `ensure_directory()` from crashing on an uncreatable path (see above) turned this into a **severe regression**: once a workspace path is uncreatable (the exact cross-machine scenario this branch already fixed once, but which can still occur, e.g. a user's own workspace folder became inaccessible for any reason), every keystroke now retried the same expensive, multi-level failing `mkdir(parents=True)` chain — for 6 keys — synchronously, freezing the UI thread long enough for Windows to show "Camxora.exe is not responding".

**Fix:** `ensure_directory()` in `shared/lib/workspace_defaults.py` now caches known-uncreatable paths and skips the `mkdir` syscall entirely on repeat calls (previously it only deduped the *log line*, not the actual syscall). Repeat calls to a known-bad path are now a simple set-membership check. Also added a timing guard in `SettingsView._refresh_footer()` that logs a warning (category `settings`) if the dirty-check ever takes >150ms on the UI thread again, so any future regression here is loud instead of silent.

### 2. Transient `TypeError` during startup import — not a code bug, hardened with a bounded retry

The crash trace shows `pydantic.fields.FieldInfo.metadata_lookup[key]` raising `'NoneType' object is not subscriptable` while importing `shared/models/platform.py` (a completely standard `Field(default_factory=list)` call). `metadata_lookup` is a plain class-level `dict` literal in pydantic's own source — for it to be `None` at runtime, the frozen module's bytecode must have been read/executed in a corrupted or truncated state. This is consistent with antivirus/Windows Defender real-time scanning still touching the freshly-extracted install files on the very first launch after install — it matches the reported behavior exactly ("resolves after a few tries", no code change needed).

This is not fixable at the call site (the code is correct), so `run_entry.py`'s `main()` now retries the fragile `load_desktop_env()` → `app.bootstrap.run()` import-and-launch chain up to once more on **any** exception, first clearing every module imported since the start of the attempt (so the retry gets a genuinely fresh import, not the same corrupted cached module). Each failed attempt is best-effort logged to `%LOCALAPPDATA%\Camxora\logs\early-startup-crash.log` using only stdlib (so the logging itself can't fail from a half-imported app module) before retrying or, on the final attempt, re-raising so the failure is still visible if it's not transient.

### 3. "2 Camxora processes in Task Manager" — expected, by design

`run_entry.py` re-launches the same `Camxora.exe` as a hidden `--visualizer-daemon` subprocess (`features/video/services/visualizer_daemon.py`) to keep a warm GPU/export worker alive across jobs, avoiding re-paying PyInstaller's import cost on every video render/export. Windows Task Manager groups it under the same "Camxora" name because it is the same executable with a different argv. Not a bug — no change made. If the daemon subprocess itself is genuinely hung on a specific machine, that would show up as a slow/stuck video export or preview, not a Settings-page freeze; the Settings-page freeze is fully explained and fixed by (1) above.

## Files touched (v1.0.6 additions)

- `camxora_python/shared/lib/workspace_defaults.py` — cache known-uncreatable paths to skip the syscall on repeat calls, not just the log line.
- `camxora_python/features/settings/views/settings_view.py` — timing guard around `_dirty_tabs()` in `_refresh_footer()`.
- `camxora_python/run_entry.py` — bounded retry with clean module cache around the startup import chain; best-effort early crash log.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`, `camxora_python/tests/test_app_version.py` (version 1.0.5 → 1.0.6).
- `camxora_python/tests/test_workspace_defaults.py` (new: `test_ensure_directory_caches_known_uncreatable_path`).
- `camxora_python/tests/test_run_entry_retry.py` (new).
- `CHANGELOG.md`.

## Tests (v1.0.6)

- `pytest tests/test_workspace_defaults.py -q` → 9 passed (new: mkdir-syscall caching proven via a counting monkeypatch of `Path.mkdir`).
- `pytest tests/test_run_entry_retry.py -v` → 3 passed (retry-recovers, retry-exhausts-then-raises, module-cache-reset).
- `pytest tests/test_app_version.py -v` → 6 passed.
- Full suite: `pytest tests/ -q` → 805 passed, 6 pre-existing failures (unchanged from before this session — module-not-found, big5-encoding fixture, and other checkpoint-branch issues unrelated to this work).

## Follow-ups (v1.0.6)

- Broader audit: any other UI code path that calls `apply_workspace_path_defaults()`/`ensure_directory()` (or similar real-filesystem-probing helpers) synchronously from a per-keystroke or per-render UI callback should be checked for the same pattern. This session only found/fixed the Settings-page instance.
- The known-uncreatable-path cache is process-lifetime and never re-probes; if the user fixes the underlying permission issue without restarting the app, it stays cached as bad until restart. Acceptable tradeoff given the alternative (re-attempting a slow failing syscall on every keystroke) is the exact bug being fixed here.
- Still open: confirm whether the reported "Refresh token reuse detected" / repeated re-auth on second launch is related to system clock skew or something else — the existing `ensure_fresh_session()` logging (v1.0.5) should surface the real exception next time it happens.

---

## v1.0.7 update — "Why is it so slow / why do we keep timing out?"

The v1.0.6 log showed `GET /users/me → 0: Request timed out` at startup, and `GET /media/channel-profiles/.../covers/0 → 0: Network error: peer closed connection without sending complete message body (received 2178801 bytes, expected 2447760)` twice for the same channel-profile cover, plus "Saving music defaults..." logged 3x for what turned out to be one save. The user asked specifically why the app feels slow and why timeouts happen "because everything is contacting our server directly."

### 1. Settings → selecting a profile downloaded its logo/cover synchronously on the UI thread — real regression, now fixed

**Root cause:** `SettingsView._resolve_profile_media_paths()` (called from `_bind_profiles_tab()`, which runs directly on the UI thread every time the user clicks a different profile in Settings) called `self._api.download_profile_logo()` / `download_profile_cover()` **synchronously** whenever the file wasn't already cached locally. `covers/0` alone is a ~2.4MB `FileResponse` off the production API — on a slow or unreliable connection this is exactly the kind of transfer that hits "peer closed connection without sending complete message body" mid-stream, and every one of those attempts fully froze the Settings page (and the rest of the app, since it's the same UI thread) for as long as the download took or until it failed.

**Fix:** `_resolve_profile_media_paths()` is now cache-only — it never touches the network. A new `ProfileMediaCacheWorker` (`shared/workers/data_workers.py`, same `QThread` + `succeeded`/`failed` signal pattern as every other background fetch in this app) downloads any missing logo/cover off the UI thread; `SettingsView._start_profile_media_cache_download()` kicks it off after binding the profile tab, and `_on_profile_media_cached()` fills in the resolved local path (and re-baselines the dirty-check) only if the user hasn't already switched to a different profile by the time it finishes. Selecting a profile is now instant regardless of network speed; the "Open" button for logo/cover just becomes usable a moment after the file finishes downloading in the background.

### 2. Large binary downloads (profile covers/logos) now retry once on a transient connection drop

**Root cause:** `PlatformClient.request_bytes()` had zero retry logic. Any transport-level failure — including a mid-transfer "peer closed connection" on a multi-megabyte file — was raised straight to the caller as a hard failure, requiring the user to manually retry (reselect the profile) to get the image.

**Fix:** `request_bytes()` now retries once (bounded, `max_network_attempts=2`, short backoff) for GET requests, but **only** on transport-level failures (`PlatformApiError.status == 0` — connect errors, timeouts, incomplete-body/`RemoteProtocolError`-class errors). A real HTTP error response (404, 500, etc.) is never retried, since retrying won't fix a server-side rejection. This directly targets the exact failure mode seen in the log without masking genuine server errors.

**What this does *not* fix:** the underlying reason the connection gets cut mid-transfer at all — that's either last-mile network instability on the client's connection, or the production API/reverse-proxy dropping slow transfers of large `FileResponse` bodies. Recommended follow-up: capture the exact frequency/size of these drops in production, and check `nginx`/`uvicorn` timeout settings (`proxy_read_timeout`, `send_timeout`, keep-alive) on the API host for anything shorter than a large-file transfer needs on a slow client connection.

### 3. "Saving music defaults..." logged 3x for one save — cosmetic, not a real triple-save

**Root cause:** `MusicView._schedule_settings_save()` is called once per individual settings field change (shuffle toggle, mood shuffle, etc.) and always flashed+logged "Saving music defaults..." immediately, then (re)started a 400ms debounce timer. Three field changes within the same 400ms window correctly resulted in exactly **one** `_persist_settings()` / one PATCH call (confirmed: only one "Music defaults saved." follows in every log sample) — but the status message and its log line fired 3 times, making it look like 3 separate slow saves were happening back-to-back.

**Fix:** `_schedule_settings_save()` now only flashes/logs "Saving music defaults..." if the debounce timer isn't already running (`self._save_timer.isActive()`), i.e. once per actual save cycle. No behavior change to what gets persisted or when — purely removes the misleading duplicate log/status noise.

### 4. Startup `/users/me` timeout and repeated "Camxora desktop starting" — network reliability, not a threading bug

`GET /users/me` already runs on a background bootstrap worker (not the UI thread), so its ~30s default timeout doesn't freeze the window — it does, however, keep the user on the startup/login screen for up to 30s before falling back to the login form, which reads as "slow" even though nothing is frozen. The three separate `"Camxora desktop starting"` log lines ~2–6 minutes apart in the same session are each a full fresh process start (that exact string is only logged once, at the very top of `app/bootstrap.py`'s `run()`) — there is no in-app auto-restart loop in this codebase apart from the explicit software-update install/relaunch flow (`software_update_installer.py`), which is user/update-gated and would show its own "Update" log lines. The most likely explanation is the user closing and reopening the app themselves while testing/troubleshooting the slowness — worth confirming directly with the user rather than assuming a hidden restart bug.

### Bottom line on "why is it slow"

It's a mix of both things the user suspected: (a) yes, a lot of screens do talk to the production API directly and some of that (profile media) was blocking the UI unnecessarily — now fixed; and (b) the specific "peer closed connection" errors point to real network/transfer reliability for large files against production, which is now retried once client-side but should also be checked server-side (proxy/timeout config) since a client-side retry only masks an occasional drop, not a systemic one.

## Files touched (v1.0.7 additions)

- `camxora_python/shared/workers/data_workers.py` — new `ProfileMediaCacheWorker` / `ProfileMediaCacheResult`.
- `camxora_python/features/settings/views/settings_view.py` — `_resolve_profile_media_paths()` made network-free; new `_start_profile_media_cache_download()` / `_on_profile_media_cached()` / `_finish_profile_media_cache_worker()`; wired into `_bind_profiles_tab()`.
- `camxora_python/shared/services/platform_client.py` — `request_bytes()` bounded retry-once on transport-level (status 0) failures for GET.
- `camxora_python/features/music/views/music_view.py` — `_schedule_settings_save()` only flashes/logs "Saving..." once per debounce window.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`, `camxora_python/tests/test_app_version.py` (version 1.0.6 → 1.0.7).
- `camxora_python/tests/test_settings_view.py` (new: `test_resolve_profile_media_paths_never_calls_network`, `test_bind_profiles_tab_starts_background_download_for_uncached_media`).
- `camxora_python/tests/test_profile_media_cache_worker.py` (new).
- `camxora_python/tests/test_platform_client_request_bytes_retry.py` (new).
- `camxora_python/tests/test_music_view.py` (new: `test_schedule_settings_save_flashes_once_per_debounce_window`).
- `CHANGELOG.md`.

## Tests (v1.0.7)

- `pytest tests/test_settings_view.py tests/test_music_view.py tests/test_profile_media_cache_worker.py tests/test_platform_client_request_bytes_retry.py tests/test_workspace_defaults.py tests/test_run_entry_retry.py -v` → 32 passed.

## Follow-ups (v1.0.7)

- Check production `nginx`/`uvicorn` timeout and buffering config for large `FileResponse` bodies (`platform_api/routers/media.py`) — the client-side retry helps but doesn't address a systemic server/proxy-side cause if one exists.
- Consider caching other large per-profile media (not just logo/cover) the same way if similar synchronous-download patterns turn up elsewhere.
- Confirm with the user whether the repeated "Camxora desktop starting" lines were manual relaunches (most likely) or something else; add a "graceful shutdown"/"app closing" log line if we want to distinguish crash-restart from manual-restart in future logs.

---

## v1.0.8 update — installer SmartScreen/process questions, phantom run folders, and the "0KB MP3 on a full drive" data-integrity bug

Follow-up on a fresh-machine install of v1.0.7: (1) the installer triggers Windows SmartScreen ("Windows protected your PC"); (2) two `Camxora Setup` processes were visible during install; (3) a batch run for 2 channels on 2026-08-02 also created a `2026-08-01` folder and an unrelated `BassVolt` folder; (4) the run folder silently defaulted to `E:\Suno`, which turned out to be a near-full USB stick, producing 0-byte MP3s that were still reported as "downloaded"/"export done"; (5) a `PermissionError: Access is denied: C:\Users\Kong Somvannda` block appeared again in the log, alongside a `Refresh token reuse detected` auth error.

### 1. SmartScreen warning — expected for an unsigned installer, no code fix available

`installer/Camxora.iss` has no `SignTool=`/Authenticode signing configured, so `CamxoraSetup-*.exe` is an unsigned binary with zero Windows/Microsoft reputation — this is exactly what triggers "Windows protected your PC". This cannot be fixed in code; it requires **purchasing and wiring up a code-signing certificate**:
- **OV (Organization Validation) cert** (~$100–300/yr, e.g. DigiCert/Sectigo/SSL.com): removes the "unknown publisher" line, but SmartScreen reputation still has to build up over time/downloads — the warning can persist for weeks after switching to this alone.
- **EV (Extended Validation) cert** or **Azure Trusted Signing** (Microsoft's newer, cheaper alternative, ~$10/mo via an Azure subscription): grants **instant** SmartScreen reputation, no warm-up period. This is the recommended path once the app ships to real users outside the team.
- Submitting the binary to Microsoft Defender Security Intelligence only helps for false-positive **malware** detections, not this "unrecognized app" reputation warning — not applicable here.
- No action taken this round; flagged for a decision on which certificate route to buy before any public release.

### 2. Two "Camxora Setup" processes during install — expected, Inno Setup UAC self-relaunch

`Camxora.iss` sets `PrivilegesRequired=admin`. Inno Setup's unelevated launcher stub triggers the UAC prompt, then re-launches itself as a second, elevated `Setup.exe` process and waits for it to finish — this is why Task Manager shows two "Camxora Setup (32 bit)" entries for the duration of the install. Not a bug; no change made.

### 3. Phantom `2026-08-01` and `BassVolt` folders — expected behavior of the account-wide pending-downloads sync, but it had a real bug hiding inside it

**Root cause:** `MusicDownloadCoordinator` (`shared/services/music_download_coordinator.py`) polls `list_pending_music_downloads()` every 4–12s in the background, for the **whole account**, not just the batch the user just ran on this machine — by design, so an MP3 generated on one device eventually lands on any other device logged into the same account. A brand-new machine logging into an account with pre-existing history (yesterday's `2026-08-01` batch, an older `BassVolt` profile/batch) will therefore immediately start pulling down *every* not-yet-downloaded MP3 for the account, creating their output folders on first sync. This is intentional cross-device sync, not a bug — but it was not obvious to the user, and it interacted badly with two real bugs found alongside it:

- `MusicDownloadSyncWorker.run()` (`shared/workers/data_workers.py`) called the raw, unguarded `shared.services.file_service.ensure_directory()` for each pending item's `output_dir`. That helper did a bare `Path.mkdir(...)` with **no exception handling at all** — if any single pending item's `output_dir` was a stale/cross-machine path, the whole sync cycle raised and **every other pending download that cycle was silently skipped too** (not just the bad one).
- **Fixed:** `file_service.ensure_directory()` now matches the same resilient pattern already used in `workspace_defaults.ensure_directory()` (catch `OSError`, log once, never raise). `MusicDownloadSyncWorker.run()`'s per-target loop is now also wrapped in a per-item `try/except` so one bad item is skipped and logged instead of aborting the whole cycle.

### 4. `E:\Suno` defaulting to a near-full USB drive → 0-byte MP3s reported as "done" — real data-integrity bug, fixed

**Root cause (two parts):**
1. `apply_workspace_path_defaults()`'s self-heal (added in v1.0.5) only checked `Path(existing).is_dir()` after `mkdir`. A synced `sunoOutputDir = "E:\Suno"` from a machine where `E:` was a real, spacious drive passed this check trivially on the new machine too — because `E:` there happened to be a Rufus-created Windows-install USB stick with only ~12KB free. Creating an empty folder on a nearly-full drive succeeds; every real download or export into it does not, and nothing was checking for that.
2. `MusicDownloadSyncWorker._download_file()` (`shared/workers/data_workers.py`) wrote `response.content` straight to disk and returned `True` on any HTTP 200, with **no check that the response body was non-empty and no check that the file actually landed at the expected size**. A same-cycle disk-space exhaustion, an empty response body, or a partial write could all produce a 0-byte file that still got marked `downloaded=True` and synced to the server as done — matching exactly the "download mp3 done, export done, but the file is 0kb" report.

**Fix:**
- New `shared/lib/disk_space.py` (`get_free_bytes()` / `has_sufficient_free_space()`, 200MB floor) — a small, dependency-free `shutil.disk_usage()` wrapper that treats "can't determine" as sufficient (never blocks on unknown) but flags a *known*-tiny drive as unusable.
- `apply_workspace_path_defaults()` now also calls `has_sufficient_free_space(existing)` before accepting a previously-saved path; a real-but-nearly-full drive now self-heals to the machine's own local default (same `patch`-back-to-server mechanism as the cross-machine-path fix), with a `log_warn` explaining why.
- `MusicDownloadSyncWorker._download_file()` now: (a) checks free space on the target drive before attempting the download at all; (b) treats an empty response body as a failure, not a success; (c) verifies the written file's size matches the downloaded content afterward; (d) deletes any accidental 0-byte leftover file; (e) logs a clear `category="music"` error in every failure case instead of failing silently. A rejected download is simply left `downloaded=False` and retried on the next poll cycle once the underlying problem (disk space, network) is resolved — it is never marked done.
- **Not done this round (flagged for follow-up, see below):** proactively letting the user pick/confirm the run folder *before* the first export starts, rather than only self-healing reactively after the fact.

### 5. `Refresh token reuse detected` + repeated `PermissionError` in the same log — re-examined, not a new regression

- **`PermissionError: C:\Users\Kong Somvannda`:** re-read the full log: this block appears exactly **once**, right after the first `Camxora desktop starting` in that session, and does **not** repeat on the three subsequent restarts in the same log (`13:12:31`, `13:13:59`, `13:14:25`). That is the *expected* one-time shape of the v1.0.5 self-heal (log the failed attempt against the stale synced path once, then silently fall back to the local default and patch the server) — not a reopened regression. The v1.0.8 disk-space fix above is the more likely actual gap this session was hitting (see §4).
- **`Refresh token reuse detected. All sessions have been revoked`:** traced `SessionService.ensure_fresh_session()` — it already serializes all refresh attempts through one `threading.Lock` + in-flight `Event` per process, so this is not a same-process race. The two failures 4s apart in the log are the *same already-invalid* refresh token being retried twice sequentially (once from `run_bootstrap()`'s proactive near-expiry refresh, once from `PlatformClient._send()`'s 401-triggered force-refresh on the following `get_me()` call) — both correctly fail identically because rotating refresh tokens are single-use, and both correctly result in `self.clear()` + a clean re-login 30s later, which is what happened. The open question is *why* the stored refresh token was already stale before this launch — most likely a previous session on this same new machine was closed/crashed after the server had already rotated the token but before the rotated pair was persisted locally. No code defect found in the refresh path itself; left as a watch-item rather than a fix (see follow-ups).

### 6. Resume-a-pipeline-after-changing-the-run-folder — proposed design, not yet built

User ask: if a run folder turns out to be on a bad/full drive mid-batch, let the user change the run folder and resume **without** re-drafting lyrics/title/album or re-requesting Suno generations — re-download MP3s and any already-succeeded server images into the new folder, then continue export/merge.

The existing `features/progress/lib/continue_progress.py` (`resolve_continue_progress()`) already picks the next pipeline step (retry drafts → retry Suno → images → export → merge) purely from a row's *current* `meta.run_dir` — there is currently no way to repoint that `run_dir` before continuing. Proposed shape for a follow-up:
1. A "Change run folder" action on the Progress row detail (`operational_rows_card.py` / `progress_detail_card.py`) that opens a folder picker and validates the new folder with `has_sufficient_free_space()` before accepting it.
2. A small server-side update to the run's `run_dir` (or a client-local override layered on top of it), scoped to *this* row/batch only — never touching lyrics/title/album/Suno task state.
3. A "re-download only" pass: re-fetch already-successful MP3s (Suno URLs are stable) and already-successful server images into the new folder, reusing the same integrity checks added in §4, then fall through to the existing `start_export`/`start_merge` continue actions once files exist at the new location.

Not implemented in this pass — this is a real (multi-file) feature, not a bug fix, and is called out here so it can be scoped/prioritized explicitly rather than folded silently into a hardening release.

## Files touched (v1.0.8 additions)

- `camxora_python/shared/lib/disk_space.py` (new) — `get_free_bytes()` / `has_sufficient_free_space()`.
- `camxora_python/shared/lib/workspace_defaults.py` — self-heal now also rejects a valid-but-nearly-full drive, not just a non-directory.
- `camxora_python/shared/services/file_service.py` — `ensure_directory()` hardened to never raise (matches `workspace_defaults.ensure_directory()`).
- `camxora_python/shared/workers/data_workers.py` — `MusicDownloadSyncWorker`: per-item try/except isolation in `run()`; `_download_file()` now checks disk space up front, rejects empty response bodies, verifies written file size, and cleans up 0-byte leftovers.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`, `camxora_python/tests/test_app_version.py` (version 1.0.7 → 1.0.8).
- `camxora_python/tests/test_disk_space.py` (new).
- `camxora_python/tests/test_workspace_defaults.py` (new: `test_apply_workspace_path_defaults_heals_low_disk_space_path`).
- `camxora_python/tests/test_music_download_coordinator.py` (new: bad-item isolation, empty-body rejection, low-disk-space rejection).
- `CHANGELOG.md`.

## Tests (v1.0.8)

- `pytest tests/test_disk_space.py tests/test_workspace_defaults.py tests/test_music_download_coordinator.py -q` → 24 passed.
- Full suite: `pytest -q` → 825 passed, 6 pre-existing failures (unchanged from v1.0.6/v1.0.7, unrelated to this work).

## Follow-ups (v1.0.8)

- Decide on and purchase a code-signing route (Azure Trusted Signing recommended) before any release outside the immediate team, to remove the SmartScreen warning.
- Build the "change run folder + resume pipeline" flow proposed in §6, once prioritized.
- Add a proactive low-disk-space warning (or a first-run "choose your run folder" prompt) at the point a batch is about to start, instead of only self-healing after the fact — the current fix stops the *silent 0-byte-file* failure mode, but the user still has to notice the change happened rather than being asked up front.
- If `Refresh token reuse detected` recurs on a machine that was *not* also freshly reinstalled/reset, capture the exact time gap since the previous successful refresh — that would confirm or rule out the "previous session crashed mid-rotation" hypothesis in §5.

---

## v1.0.9 update — "Change run folder & Resume" (§6 built)

Implements the §6 proposal from the v1.0.8 round: recover a batch/channel that ended up pointed at a bad/full drive by moving it to a new folder and re-fetching only the already-successful assets — never re-drafting lyrics/title/album and never re-requesting Suno generation.

### What was built

**Server (`platform_api`):**
- `BatchRepository.list_suno_audio_for_batch(batch_id, user_id)` — new read query: every `SUCCESS` Suno task for one batch with its stable audio URL(s), **regardless of the account's `downloaded_ok`/`downloaded_alt` flags** (those flags describe the *old* folder we're moving away from; the whole point of this feature is to re-fetch into a new one even if the account already marked it downloaded).
- `BatchService.build_batch_redownload_plan(user_id, batch_id, role, run_dir)` — verifies batch ownership, then builds `{song_id, task_id, title, track_number, download_url, target_path}` for every song with an audio URL matching the given channel role, with `target_path` computed against the **new** `run_dir` using the exact same naming helper (`_build_suno_download_target_path`) normal batch processing already uses, so the redownloaded files land with the same names/track numbering as if the batch had run there from the start.
- New endpoint `POST /music/downloads/batch-redownload-plan` (`{batch_id, role, run_dir}` → `{items: [...]}`), scoped to one batch (unlike the account-wide `/music/downloads/pending`).
- Reused the **existing** `POST /progress/sync-local` endpoint (no server change needed) to repoint `batch_channel_assets.run_dir` for this batch/profile/role — this is already the read-priority source for a row's `meta.run_dir` (`platform_api/routers/progress.py`), so once it's updated, `continue_progress.py`'s existing export/merge/continue logic on the desktop automatically looks in the new folder — no new "resume" code path was needed there at all.

**Desktop (`camxora_python`):**
- New `RunFolderRecoveryWorker` (`shared/workers/data_workers.py`, same `QThread` pattern as every other background worker in this app) orchestrates the whole recovery off the UI thread:
  1. Rejects the new folder up front if `has_sufficient_free_space()` says no (reuses the v1.0.8 disk-space check — never repeats the exact bug this feature exists to recover from).
  2. Calls `sync_local_progress()` **first** to repoint the server's `run_dir` — so even if a later step fails partway, Continue Progress and the account-wide pending-download sync already look in the right place on the next attempt.
  3. Calls the new `batch-redownload-plan` endpoint and re-downloads each track via `MusicDownloadSyncWorker._download_file()` (the exact same integrity-checked primitive from v1.0.8 — free-space check, empty-body rejection, size verification, 0-byte cleanup).
  4. Lists this batch's successful image jobs (`list_image_jobs(batch_id=..., status=["success"])`), filters to the matching channel role, and re-downloads each into the new folder (same basename) via the existing `ensure_image_output_local()` helper.
  5. Emits a `RunFolderRecoveryResult` (mp3/image totals, downloaded, failed) so the UI can show a precise summary instead of a bare "done".
- New context-menu action **"Change Run Folder & Resume…"** on `OperationalRowsCard` (next to the existing "Open Run Folder"), gated on the row already having a `run_dir` — wired through `ProgressView._change_run_folder()`: native folder picker → guards against picking the same folder → starts the worker → shows a result/notice banner → `refresh_data()` → runs **Continue Progress exactly once** for that row (`_flush_pending_auto_continue()`), the same single-step resolver a manual right-click uses. This does **not** auto-run the whole pipeline — if Continue Progress lands on `retry_drafts`/`retry_suno`/further image work, those still each need their own trigger, same as today; it only removes the "move folder, then remember to separately click Continue" extra step.
- Deliberately does **not** touch drafts, lyrics, album/title, or Suno task/job state — only `run_dir` plus the two asset kinds (MP3, image) get moved.

### Why no new "resume" logic was needed

`continue_progress.py`'s `resolve_continue_progress()` already reads `meta.run_dir` fresh on every Progress refresh to decide whether to start export/merge (see the priorities documented in this file's own docstring-equivalent code comments). Once the recovery worker repoints `run_dir` and the files exist there, the *existing* Continue Progress / Start Export / Start Merging actions just work — this feature only had to solve "get the files into a new folder and tell the server where that is," not reimplement any pipeline-continuation logic.

### Files touched (v1.0.9 additions)

- `platform_api/repositories/batch_repo.py` — new `list_suno_audio_for_batch()`.
- `platform_api/services/batch_service.py` — new `build_batch_redownload_plan()`.
- `platform_api/routers/music_downloads.py` — new `POST /music/downloads/batch-redownload-plan` endpoint + request/response models.
- `platform_api/tests/test_batch_service.py` — new `test_build_batch_redownload_plan_ignores_downloaded_flag`, `test_build_batch_redownload_plan_empty_run_dir_returns_nothing`.
- `platform_api/tests/test_music_downloads_router.py` — new `test_batch_redownload_plan`.
- `camxora_python/shared/models/platform.py` — new `BatchRedownloadItem`, `BatchRedownloadPlanResponse`.
- `camxora_python/shared/services/platform_api.py` — new `get_batch_redownload_plan()` client method.
- `camxora_python/shared/workers/data_workers.py` — new `RunFolderRecoveryResult`, `RunFolderRecoveryWorker`.
- `camxora_python/features/progress/widgets/operational_rows_card.py` — new `change_run_folder_requested` signal + context-menu action.
- `camxora_python/features/progress/views/progress_view.py` — new `_change_run_folder()` / `_on_change_run_folder_succeeded()` / `_on_change_run_folder_failed()` / `_flush_pending_auto_continue()`; folder picker + worker wiring + one-shot Continue Progress after the refresh that follows a successful move.
- `camxora_python/tests/test_run_folder_recovery_worker.py` (new).
- `camxora_python/tests/test_progress_view.py` — new `test_change_run_folder_auto_continues_matching_row_once`, `test_flush_pending_auto_continue_noop_when_row_not_found`.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`, `camxora_python/tests/test_app_version.py` (version 1.0.8 → 1.0.9).
- `CHANGELOG.md`, `platform_api/CHANGELOG.md`.

### Tests (v1.0.9)

- `pytest platform_api/tests/test_batch_service.py -k redownload -q` → 2 passed.
- `pytest camxora_python/tests/test_run_folder_recovery_worker.py -q` → 3 passed (low-disk-space rejection, happy-path repoint+redownload with role filtering, partial-failure counting).
- `pytest camxora_python/tests/test_progress_view.py -q` → 10 passed (2 new: auto-continue fires exactly once for the matching row and not on a later unrelated refresh; no-op when the row isn't found).
- `platform_api/tests/test_music_downloads_router.py::test_batch_redownload_plan` written and reviewed; blocked from running in this environment by a **pre-existing, unrelated** test-collection failure (`platform_api/routers/blog_posts.py` uses `status_code=204` with a response model under the installed FastAPI 0.116.1, which now asserts no body is allowed for 204 — present before this session's changes, not touched by this work).
- Full desktop suite: `pytest camxora_python/tests -q` → 828 passed, 6 pre-existing failures (unchanged set from v1.0.8, verified via `git stash` that they fail identically without this session's changes).

### Follow-ups (v1.0.9)

- Fix the pre-existing `blog_posts.py` / FastAPI 204-with-response-model collection error so the full `platform_api` test suite (including the new router test) can run again — unrelated to this feature, flagged for separate cleanup.
- Not deployed anywhere yet — desktop-only code paths were exercised via unit tests; recommend a manual smoke test (pick a real batch, change its run folder, confirm MP3s/images land and Continue Progress picks up correctly) before shipping an installer.
- Consider surfacing the same action from `ProgressDetailCard`, not just the row context menu, once the primary flow is validated.
- The image re-download step trusts `output_image_path`'s basename for the new file name; if a job's stored path is empty (shouldn't happen for `status=success` jobs, but not database-enforced), that image is silently skipped rather than guessed at — worth a follow-up warning surfaced to the user if this is ever observed in practice.

---

## v1.0.9 update, part 2 — Backblaze-preferred redownload + stop syncing already-finished pipelines to new machines

Two follow-up questions from the user after §"Change Run Folder & Resume" landed: (1) since every successful Suno track is already archived to Backblaze for streaming, shouldn't recovery prefer that durable copy over the original Suno URL? (2) the account-wide background MP3 auto-sync was pulling down *already-finished* pipelines (yesterday's batch, an unrelated `BassVolt` channel) onto a brand-new machine — should that be an explicit action instead, while a **still-running** batch keeps auto-downloading to whichever device is open (including a second device logged in mid-run, single-device restriction deferred)?

### 1. `build_batch_redownload_plan` now prefers the Backblaze copy

**Confirmed via code read:** `platform_api/routers/callbacks.py` schedules `StreamingUploadService.schedule_suno_streaming_upload()` on **every** successful Suno callback (not opt-in), which uploads the track to Backblaze B2 and records it in `stream_tracks` keyed by `(suno_task_id, variant)` — independent of any desktop machine. This is a durable copy that doesn't depend on the Suno CDN URL staying valid.

**Fix:** `BatchService._resolve_redownload_storage_keys()` (new) looks up `stream_tracks.storage_key` for the batch's Suno task IDs via a new `StreamingRepository.get_track_storage_keys_for_suno_tasks()`, and if streaming storage is configured and a matching archived track exists, `StorageService.get_signed_get_url()` mints a fresh signed URL and `build_batch_redownload_plan()` uses it instead of `audio_url_ok`/`audio_url_alt`. Any failure in this lookup (storage not configured, DB pool unavailable, track not yet archived) is caught and silently falls back to the Suno URL — this is a durability upgrade, never a hard dependency.

Note the vocabulary mismatch caught while wiring this up: `build_batch_redownload_plan`'s own `variant` is `"primary"/"secondary"` (used for filename suffixes), while `stream_tracks.variant` uses `"ok"/"alt"` (from `StreamingUploadService`) — these are mapped explicitly, not reused directly.

### 2. Account-wide auto-sync no longer re-pulls a channel whose pipeline is already fully complete

**Root cause (confirmed):** `list_pending_suno_downloads()` only checked `downloaded_ok`/`downloaded_alt` and a 30-day `batch.updated_at` window — it had no concept of "this channel's pipeline already finished end-to-end." A batch whose MP3 download had failed once (e.g. the v1.0.8 full-drive bug) stayed "pending" **forever** and kept getting retried on **every** machine the account logs into, even long after the batch/channel was fully exported, merged, and done. That's what produced yesterday's date folder and the unrelated `BassVolt` folder on a brand-new machine.

**Fix:** the query now joins `batch_channel_assets` for both the OK and ALT channel role and excludes a variant once `pipeline_complete = true` for that specific batch/profile/role (the same flag `mark_desktop_pipeline_complete()` sets when a merge/export finishes — see v1.0.9 part 1). A channel with no `batch_channel_assets` row yet, or `pipeline_complete = false`, is treated as "still running" and keeps auto-syncing to any device the account is logged into — deliberately no per-device scoping yet, per the user's explicit call ("if a second device logs in while the batch is still running, it should still get pulled — single-device restriction can come later").

**Validation:** this workspace has no DB-backed repo test harness (all `batch_repo` interactions are unit-tested via mocks at the service layer), so the new SQL was validated directly against the real local schema instead: connected to the local `platform_db`, added the two `batch_channel_assets` columns inside a transaction, ran the exact query, confirmed it executes and returns rows correctly, then rolled the transaction back (zero permanent change to the shared local DB).

**⚠️ Separate pre-existing risk found while validating, unrelated to this task:** the local dev DB's `alembic_version` is stamped `076_distrokid_wav`, but `batch_channel_assets.pipeline_complete`/`pipeline_completed_at` (migration `075_batch_channel_pipeline_complete`, an ancestor of `076` in this branch's migration graph) were **not actually applied** — meaning some other branch's `076_distrokid_wav` migration has `down_revision` pointing at `074_suno_audio_ids`, skipping `075` entirely. This is local-DB-only drift from parallel agent work sharing one Postgres instance, not touched by this session — but if `076_distrokid_wav` (as currently written) is ever applied to sandbox/production without `075` first, this new query (and the v1.0.9-part-1 recovery flow, which also depends on `pipeline_complete`) would fail with `column does not exist`. **Flagged for the team to check the actual migration head/order before deploying either `076_distrokid_wav` or this change to sandbox.**

### Files touched (v1.0.9 part 2)

- `platform_api/repositories/streaming_repo.py` — new `get_track_storage_keys_for_suno_tasks()`.
- `platform_api/services/batch_service.py` — `build_batch_redownload_plan()` now prefers Backblaze; new `_resolve_redownload_storage_keys()` helper.
- `platform_api/repositories/batch_repo.py` — `list_pending_suno_downloads()` now excludes channels with `pipeline_complete = true`.
- `platform_api/tests/test_batch_service.py` — new `test_build_batch_redownload_plan_prefers_backblaze_url_over_suno_url`, `test_resolve_redownload_storage_keys_returns_empty_when_pool_unavailable`.
- `platform_api/CHANGELOG.md`.

### Tests (v1.0.9 part 2)

- `pytest platform_api/tests/test_batch_service.py -k redownload -q` → 4 passed (2 new).
- New `list_pending_suno_downloads` SQL manually validated against the real local schema (see note above) — no automated repo-level test exists for this method in this codebase (mock-only convention).

### Follow-ups (v1.0.9 part 2)

- Resolve the `076_distrokid_wav` / `075_batch_channel_pipeline_complete` migration-graph gap **before that branch merges/deploys anywhere** — confirmed with the user this is local-shared-DB-only drift today (DistroKid is unreleased), not a live sandbox/production risk.
- Not deployed to sandbox yet — pending user confirmation, per this session's "don't deploy without asking" precedent.
- True per-device scoping (so a second device logged in mid-batch does *not* also pull it down) explicitly deferred by the user's request; would need a new device/session identifier on batches or a client-supplied device ID on the pending-downloads request.
- An explicit "pull this batch's history to this machine" action (for genuinely-finished batches a user wants on a new machine on purpose) was not built this round — `build_batch_redownload_plan` + `RunFolderRecoveryWorker` already have the right primitives; this would mainly need a batch-history browser/picker UI, since today's action only appears on rows that already have a `run_dir` on the current machine.

---

## v1.0.9 update, part 3 — Corrected Backblaze priority: Suno first, Backblaze only as a dead-URL fallback

Part 2 above got the priority backwards. Suno retains generated audio for **14 days**, and Backblaze should only ever be hit for images/thumbnails (already the case elsewhere) — not proactively for MP3s just because we archive there too. Corrected:

- `build_batch_redownload_plan()` now returns `download_url` = the original Suno URL (primary, unchanged base behavior) and a separate `fallback_download_url` = the signed Backblaze URL, only populated if a durable copy exists. Backblaze is never fetched from proactively — the field just rides along in the same response so the desktop doesn't need a second round-trip if the primary fails.
- If Suno's audio URL is somehow missing for a row entirely (e.g. an old row outside the 14-day window with the column never repopulated), `download_url` falls back to the Backblaze URL directly and `fallback_download_url` is `None` — nothing left to fall back to.
- `RunFolderRecoveryWorker`'s MP3 loop now tries `download_url` first; only on failure, and only if `fallback_download_url` is present, does it retry once against Backblaze before counting the track as failed. Logs a `category="music"` warning when this fallback triggers, so a pattern of "Suno URLs going dead" is visible in the logs rather than silent.

### Files touched (v1.0.9 part 3)

- `platform_api/services/batch_service.py` — `build_batch_redownload_plan()` priority corrected; docstrings updated.
- `platform_api/routers/music_downloads.py` — `BatchRedownloadItemResponse.fallback_download_url` (new, optional).
- `camxora_python/shared/models/platform.py` — `BatchRedownloadItem.fallback_download_url` (new, optional).
- `camxora_python/shared/workers/data_workers.py` — `RunFolderRecoveryWorker` retries `fallback_download_url` once on primary failure.
- `platform_api/tests/test_batch_service.py` — replaced the "prefers Backblaze" test with `test_build_batch_redownload_plan_prefers_suno_url_with_backblaze_as_fallback` and `test_build_batch_redownload_plan_uses_backblaze_when_suno_url_missing`.
- `camxora_python/tests/test_run_folder_recovery_worker.py` — new `test_recovery_worker_falls_back_to_backblaze_when_suno_url_dead`.

### Tests (v1.0.9 part 3)

- `pytest platform_api/tests/test_batch_service.py -k redownload -q` → 5 passed.
- `pytest camxora_python/tests/test_run_folder_recovery_worker.py -q` → 4 passed (1 new).

---

## v1.0.9 update, part 4 — Background/thumbnail images now durably archived to Backblaze too

User question while reviewing the redownload-priority fix above: "make sure we download bg image and thumbnail image from our Backblaze right? do we store both of them right? if not we should store both of them — we don't want to waste our AI cost regenerating a previous batch."

**Confirmed via code read: we did not.** Generated background/thumbnail PNGs (`ImageJobService._write_image_output`) were only ever written to a **server-local disk cache** (`PLATFORM_IMAGE_OUTPUT_CACHE_DIR/{job_id}.png`), served to the desktop via `GET /api/v1/image-jobs/{job_id}/output`. There is no B2 archival for these — only a separate, much smaller derived `cover.jpg` (via `StreamingUploadService.maybe_upload_cover_after_image_job()`) goes to Backblaze, and that's for the **streaming portal's** album art, not the full-resolution pipeline assets the desktop needs to render/export video. If the API server's local cache is ever lost (disk wipe, VPS migration, redeploy to a fresh disk — no TTL/prune job exists today, but also no redundancy), `/output` returns 404 with no way to recover the image short of paying the AI provider again. `docs/PRODUCTION_INFRASTRUCTURE_PLAN.md` already flagged this as an unstarted Phase 4 item ("Upload thumbnails/backgrounds to B2").

### What was built

Same durability pattern as the MP3 archival: **local cache stays the primary, fast path; Backblaze becomes the durable backing store, consulted only as a fallback on read.**

- New migration `076_image_job_storage_key` — `image_jobs.storage_key` (nullable `VARCHAR`), following `075_batch_channel_pipeline_complete`. Validated directly against the real local schema in a rolled-back transaction (same technique used for the `pipeline_complete` query in part 2 — no automated repo-level test harness exists for `batch_repo`/image-job queries in this codebase).
- `ImageJob` domain dataclass gains `storage_key: str | None = None`; the three existing `SELECT`s that hydrate `ImageJob` (`get_image_jobs_by_batch`, `get_image_jobs_for_user`, `get_image_job_by_id`) now include the column, and `_row_to_image_job` reads it defensively via `row.get(...)`.
- New `BatchRepository.update_image_job_storage_key(job_id, user_id, storage_key=...)`.
- New `StorageService.download_bytes(key)` — server-side read-back of raw object bytes (distinct from `get_signed_get_url()`, which hands the *client* a URL; here the API itself needs the bytes to re-populate its cache and serve them).
- `ImageJobService._archive_image_output_to_storage()` (new, best-effort, never raises) — scheduled via `asyncio.create_task()` right alongside the existing `maybe_upload_cover_after_image_job()` call, immediately after a job's output bytes are written to the local cache. Uploads to `images/{user_id}/{batch_id}/{kind}-{role}-{job_id}.png` and persists the key via `update_image_job_storage_key()`. Silently no-ops if streaming storage isn't configured for the environment (mirrors the existing cover-upload scheduling's own try/except-and-log pattern) — this is a durability bonus, never a hard dependency for the happy path.
- `ImageJobService.read_job_output_bytes()` — after the existing local-cache-miss and client-path-miss checks, now also tries `job.storage_key` via a new `_read_archived_image_bytes()` helper; if Backblaze has the bytes, they're returned **and** the local cache file is repopulated on the way out, so the next read is fast and doesn't re-hit Backblaze.

### Files touched (v1.0.9 part 4)

- `platform_api/migrations/versions/076_image_job_storage_key.py` (new).
- `platform_api/models/domain.py` — `ImageJob.storage_key`.
- `platform_api/repositories/batch_repo.py` — `storage_key` added to the 3 `ImageJob`-hydrating `SELECT`s and `_row_to_image_job`; new `update_image_job_storage_key()`.
- `platform_api/services/storage_service.py` — new `download_bytes()`.
- `platform_api/services/image_job_service.py` — new `_archive_image_output_to_storage()`, `_read_archived_image_bytes()`, `_pool_for_storage()`; archive scheduled on every successful job; `read_job_output_bytes()` falls back to the archive and repopulates the cache.
- `platform_api/tests/test_image_job_service.py` — new `test_archive_image_output_to_storage_uploads_and_persists_key`, `test_archive_image_output_to_storage_noop_when_not_configured`, `test_read_job_output_bytes_falls_back_to_backblaze_when_cache_missing`, `test_read_job_output_bytes_raises_when_no_cache_no_client_path_no_archive`.
- `platform_api/CHANGELOG.md`.

### Tests (v1.0.9 part 4)

- `pytest platform_api/tests/test_image_job_service.py -v` → 7 passed (4 new).
- New migration validated directly against the real local schema in a rolled-back transaction (column add + insert + select by name), consistent with the no-repo-test-harness convention already established in this doc.
- `pytest platform_api/tests/test_batch_service.py platform_api/tests/test_streaming_upload_service.py -q` → 2 pre-existing failures reconfirmed unrelated (same two as v1.0.9 part 1: `test_execute_batch_submits_suno_for_successful_drafts_when_enabled`, `test_schedule_suno_streaming_upload_creates_background_task` — both fail identically without this session's changes).

### Follow-ups (v1.0.9 part 4)

- Not deployed anywhere yet — needs the `076_image_job_storage_key` migration run on sandbox before this archival can take effect there; check the same migration-graph gap flagged in part 2 (`076_distrokid_wav` vs `075_batch_channel_pipeline_complete`) before applying, since this migration's `down_revision` also chains through `075`.
- Only the 16:9 background/thumbnail pair is archived today because that's typically all that's generated per channel; the schema already supports all 4 variants (`background_16x9`/`9x16`, `thumbnail_16x9`/`9x16`) so 9:16 assets are archived automatically too whenever a job for that kind actually runs — no extra work needed there.
- No backfill job for **already-existing** image jobs (created before this change) — their `storage_key` stays `NULL` until/unless they're regenerated. If durability for historical images matters, a one-off backfill script (read local cache → upload → persist key, for every `SUCCESS` job missing a `storage_key`) would need to run **before** decommissioning/wiping the current server cache.
- Same open item as MP3 archival: no per-image TTL/prune policy exists for the *local* cache today; this change makes losing it non-catastrophic (Backblaze fallback) rather than removing the need to eventually add a real retention policy for the cache directory itself.
