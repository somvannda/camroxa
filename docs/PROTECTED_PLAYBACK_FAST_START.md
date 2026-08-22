# Protected playback — fast start on every device

**Status:** Code on `feature/protected-playback-fast-start` (phases 0–4). Sandbox deployed 2026-08-21. Not committed. Not production.  
**Date:** 2026-08-21  
**Branch:** `feature/protected-playback-fast-start`  
**Worktree:** `D:\Development\Projects\Electron\MusicGenerator-ios-safari-ship`  
**Surfaces:** `music_web`, `platform_api`  
**Related:** [`changelog/2026-08-20-protected-playback.md`](./changelog/2026-08-20-protected-playback.md), [`changelog/2026-08-21-ios-safari-playback.md`](./changelog/2026-08-21-ios-safari-playback.md), [`changelog/2026-08-21-protected-playback-fast-start.md`](./changelog/2026-08-21-protected-playback-fast-start.md)

This is the implementation plan so packaged Play feels fast on **desktop and phone**, without handing listeners a downloadable MP3.

---

## Status checklist

Code for phases 0–4 is in the worktree above. The `bugfix/ios-player-responsive` branch in the main `MusicGenerator` tree now includes client phases 2–4 (progressive Web Audio, parallel fetch, RAM replay, duration pin, Media Session).

Legend: **done** = in the worktree; **partial** = coded but narrower than the plan; **pending** = not started.

### Phases

- [x] **0 — Traces.** `play_path=mse|webaudio|webaudio_ram`. `play_ok` includes `first_audio_ms=`. Chunk 0 decode logs `play_decode chunk=0`.
- [x] **1 — Server package cache.** In-process CXA1 ciphertext cache keyed by `packaged_storage_key` (90s, 8 packages). Chunk 1 does not re-download the whole object in the same process.
- [x] **2 — Parallel fetch.** Concurrency 3 on MSE and Web Audio. Decrypt retries once. Previous Play still aborted.
- [x] **3 — Progressive Web Audio.** Safari / all iOS / Firefox decode chunk 0, start PCM, append later buffers. Chrome stays MSE. Firefox is on the same Web Audio path (not iOS-only).
- [x] **4 — RAM replay (Web Audio only).** Same track in the same tab replays from in-memory PCM (`webaudio_ram`). Wiped on a different track.
- [ ] **5 — Optional encrypted HTTP cache.** Stable package URL + `private, max-age` for ciphertext. Content key still memory-only. **Not started. Not required for “Play feels fast.”**

### Path A — MSE (Chrome / Edge / Android Chrome)

- [x] Keep MSE; start after chunk 0.
- [x] Server serves one chunk from cached package (no per-chunk B2 GET).
- [x] Prefetch chunks 1..N, cap 3, append in order.
- [ ] Keep MediaSource + object URL so Play again does not re-fetch. **Pending (optional).**
- [x] Never `createObjectURL` of `audio/mpeg` bytes.

### Path B — Progressive Web Audio (Safari, iOS, Firefox)

- [x] Do not wait for the full file.
- [x] Decrypt chunk 0, strip ID3/sync, decode available frames with mpg123 (decoder kept alive so leftover frames carry into chunk 1).
- [x] `AudioContext.resume` from the tap; start the first PCM buffer as soon as chunk 0 decodes.
- [x] Later chunks decode in the background and schedule at the previous buffer’s end.
- [x] Wipe MP3 bytes after each decode. PCM stays in the graph only.
- [x] Never assign concatenated MP3 to `audio.src`.
- [x] If context is not `running`, show “Tap play again” (existing `friendlyPlaybackError`). Do not treat suspended as success.

### Shared

- [x] Abort previous track fetches on a new Play.
- [x] Parallel chunk HTTP, concurrency 3.
- [x] RAM cache keyed by `subject_type:subject_id:variant` for the **current** Web Audio track.
- [ ] RAM cache for **MSE** replay. **Pending.**
- [ ] Drop RAM on page hide after TTL. **Pending** (tab close still drops it; changing tracks already clears it).
- [x] Do not persist plaintext audio (no IndexedDB / Cache Storage / disk).

### Server details

- [x] In-process ciphertext cache (`encrypted_package_cache.py`).
- [ ] Redis cache. **Skipped** — in-process is enough for now.
- [ ] Per-chunk storage objects or B2 range reads. **Skipped** — cache + slice covers this.
- [x] Session segment URL stays `Cache-Control: private, no-store`.

### Easy-to-miss Web Audio details

- [x] Incremental mpg123 across chunks (decoder instance, not a separate remainder byte buffer).
- [x] Schedule additional sources; do not replace the whole graph on every chunk.
- [x] Duration is the clip’s `duration_seconds` from the start. Do **not** grow the bar as chunks arrive.
- [x] iOS gesture: first `source.start` waits only on chunk 0, not the full file.
- [x] One track of PCM in RAM, not a decoded album queue.
- [ ] Seek / skip into audio that is not decoded yet: show buffering or decode up to that point. **Partial** — seek is clamped to already-decoded PCM; no buffering UI.

### Automated tests

- [x] Theft / leak tests still pass (no origin MP3, no `blob:`/`data:audio/mpeg` play src).
- [x] Cache unit test: loader runs once for two `get_packaged_blob` calls.
- [ ] Mock HTTP: chunk 1 after chunk 0 must not call storage `download_bytes` a second time. **Pending** (cache is tested; the router is not).

### Ship / QA (all pending)

- [ ] Commit / push `feature/protected-playback-fast-start`
- [x] Sandbox deploy: `platform_api` + file-scoped `music_web` hotfix (not a full music_web tarball from a mixed tree)
- [ ] Manual matrix below (Chrome, Firefox, iPhone Safari at minimum)
- [ ] Production — only after sandbox QA and an explicit request

---

## Goal

After tap/click Play, **audible audio within about 1–3 seconds** on every supported browser, then the rest of the track fills in. Same security model as today.

Replay of the **current** track in the same tab should be instant (RAM). A hard refresh or a new user may still download ciphertext; they must not get a saved `.mp3`.

---

## What stays forbidden

These rules do not change on any device:

- No Suno or signed B2 MP3 URLs in the player.
- No `blob:` or `data:` **`audio/mpeg`** as `audio.src` (Chrome MediaSource object URLs are not an MP3 file; those stay allowed **only** for MSE).
- Wire format stays CXA1 encrypted chunks + license `content_key`.
- Do not write decrypted MP3, WAV, or PCM to IndexedDB, Cache Storage, or disk.
- Owner download stays paid, watermarked, API-side — not the player path.

An attacker can still record the speaker or dump RAM while a song is playing. That is already true. They must not get a file they can “Save as”.

---

## Why some devices are already faster

There are two player engines today:

| Engine | When | First sound before this work | First sound in worktree |
|--------|------|------------------------------|-------------------------|
| **MPEG MediaSource (MSE)** | Chromium says `MediaSource.isTypeSupported('audio/mpeg')` **and** the browser is not Apple WebKit | After **chunk 0** (~256 KB). Already progressive. | Same, plus server cache + parallel prefetch. |
| **Web Audio + in-memory MP3 decode** | iOS, iPad, macOS Safari, iOS Chrome/Firefox/Edge (all WebKit), Firefox (no MPEG MSE) | After **every** chunk, then decode. 30–90s on a 3-minute track. | After **chunk 0**, then append. |

Apple WebKit must **not** use MPEG MSE (`isSafariMpegMseBroken`). Safari reports support, then fails with “The operation failed for an operation-specific reason.”

Firefox desktop/Android typically **cannot** use MPEG MSE. They must use the Web Audio path, made progressive.

---

## Device matrix (do not skip)

Use this as the QA checklist. “Fast start” means sound after the first decrypted media unit, not after the whole file.

### Desktop

| Browser | Engine today | Fast-start method | Notes |
|---------|----------------|-------------------|--------|
| **Chrome** (Windows / macOS / Linux) | MSE `audio/mpeg` | Keep MSE. Speed up chunk 0 with server slice + parallel prefetch of later chunks. | Do **not** switch Chrome to full-file Web Audio. |
| **Edge** | Same as Chrome (Chromium) | Same as Chrome | Treat as Chrome in QA. |
| **Firefox** | Web Audio (no MPEG MSE) | **Progressive PCM** (same as iOS Web Audio plan) | Easy to miss if we only test Chrome. |
| **Safari** (macOS) | Web Audio (MSE skipped) | Progressive PCM + AudioContext unlock on click | Same code path as iPhone, mouse instead of tap. |
| **Opera / Brave / Arc** | Chromium | Same as Chrome | Spot-check one. |

### Apple phones and tablets

| Browser | Engine | Fast-start method | Notes |
|---------|--------|-------------------|--------|
| **Safari iPhone / iPad** | WebKit Web Audio | Progressive PCM. Unlock AudioContext **in the same tap**. Keep a detached silent WAV (not the player `<audio>`) until the first PCM buffer starts. | Hardware mute switch can still silence output. |
| **Chrome / Firefox / Edge on iOS** | WebKit (not Blink) | **Same as iOS Safari** | `mse=0` in traces. Never assume iOS Chrome = desktop Chrome. |
| **iPadOS desktop-mode Safari** | WebKit | Same as iPhone | `MacIntel` + `maxTouchPoints > 1` is already treated as broken MSE. |

### Android

| Browser | Engine today | Fast-start method | Notes |
|---------|----------------|-------------------|--------|
| **Chrome** | MSE | Keep MSE + server/parallel | Primary Android path. |
| **Samsung Internet** | Chromium | Same as Chrome | Spot-check. |
| **Edge / Opera** | Chromium | Same as Chrome | Spot-check one. |
| **Firefox** | Web Audio | Progressive PCM | Must be in the Firefox Web Audio QA, not “Android = Chrome.” |
| **In-app WebView** | Often Chromium | Follow `shouldUseMpegMediaSource()` at runtime | If MPEG MSE is false, Web Audio progressive. |

### Other

| Client | Plan |
|--------|------|
| **Confirmed user, Create + catalog + playlists** | Same player. No separate slow path for Create. |
| **Unconfirmed / logged out** | Unchanged: no play. |
| **Desktop Camxora app** | Out of scope for this plan (`music_web` only). |
| **Private/incognito** | RAM cache dies on close. Encrypted HTTP cache may be disabled by the browser. Fast start on first play still required. |

Runtime rule: **choose the engine with feature detection**, not with “if iPhone”. Chromium gets MSE; WebKit and Firefox get progressive Web Audio.

---

## Target architecture

```
Tap/click Play
  → license session (content_key, segment URL)
  → fetch+decrypt chunk 0
  → START audible playback   ← goal: 1–3s
  → fetch more chunks (2–4 in flight)
  → append to the playing engine
  → RAM keep current track for replay in this tab
```

### Path A — MSE (Chrome, Edge, Android Chrome, …)

Already starts on chunk 0. Keep it.

Changes:

1. Server returns one chunk without re-downloading the whole CXA1 blob from B2 each time.
2. Prefetch chunks 1..N in parallel (cap 3–4) while chunk 0 is playing.
3. Optional: keep MediaSource + object URL for the current track so Play again does not re-fetch.

Still: MediaSource object URL only, never `createObjectURL` of `audio/mpeg` bytes.

### Path B — Progressive Web Audio (Safari, all iOS, Firefox, any browser without MPEG MSE)

Do **not** wait for the full file.

1. Decrypt chunk 0, strip ID3/sync, decode **available MPEG frames** to PCM (mpg123 WASM; leftover partial frame carried to chunk 1).
2. `AudioContext.resume()` from the original tap; start `AudioBufferSourceNode` (or a short queue of buffers) as soon as there is ~0.5s+ of PCM.
3. Decrypt later chunks in the background, decode, schedule the next buffer at the previous buffer’s end time (gapless).
4. Wipe MP3 bytes after each decode. Keep PCM only in the graph.
5. Never assign concatenated MP3 to `audio.src`.

If the context is not `running` after decode, show “Tap play again” — do not fake a silent play_ok.

### Shared (both paths)

1. **Abort** the previous track’s fetches on a new Play (already started).
2. **Parallel chunk HTTP** with a small concurrency limit (Safari connection limits; Web Crypto flakes if too many decrypts).
3. **RAM cache** keyed by `subject_id + variant` for the current (and maybe previous) track: decrypted PCM buffers or MSE attachment. Drop on new track / page hide after TTL / tab close.
4. **Do not** persist plaintext audio.

---

## Server work (helps every device, including Chrome)

Today `GET /licenses/segments/{token}?chunk=N` downloads the **entire** packaged object from storage, then slices one 256 KB chunk. A 17-chunk song can mean 17 full B2 downloads.

Plan:

1. Cache the packaged blob in process/Redis for a short TTL keyed by `packaged_storage_key` (ciphertext only).
2. Or store/read **per-chunk** objects, or B2 range reads if the CXA1 layout allows a cheap slice.
3. Keep `Cache-Control: private, no-store` on **session-token URLs**.

Optional later (hard refresh speed, still safe):

4. A second URL shape keyed by **package id + chunk index** (not session token), still requiring a valid license to fetch, with `private, max-age=…` so the **browser may cache ciphertext**. Content key stays in the license JSON, memory-only, short TTL. Never cache the key.

Phase 4 is optional. Phases 1–3 of the client plus server slice are enough for “Play feels fast.”

---

## Implementation order (so no device is left on the slow path)

| Phase | What | Status |
|-------|------|--------|
| **0** | Plan + traces: `first_audio_ms`, `chunk=0` | **Done** |
| **1** | Server: one storage read per package | **Done** (in-process cache; not Redis / B2 range) |
| **2** | Parallel fetch (concurrency 3) | **Done** |
| **3** | Progressive Web Audio | **Done** |
| **4** | RAM cache for current track | **Partial** (Web Audio only; MSE still re-fetches) |
| **5** | Encrypted chunk HTTP cache | **Pending** (optional) |

Do not ship phase 3 only on iOS. Firefox desktop must ship in the same change.

---

## Web Audio progressive — details that are easy to miss

- **MP3 frames span chunk boundaries.** Keep a remainder byte buffer. Do not assume chunk 0 is a complete standalone MP3 file, but 256 KB is enough frames to start.
- **mpg123** is already incremental (`decode(Uint8Array)`). Prefer feeding frames as they arrive over `decodeAudioData` of the whole file.
- **Schedule**, don’t replace: if you `stop()` and start a new full buffer on every chunk, you get glitches. Use `source.start(nextTime)` with `audioContext.currentTime`.
- **Seek / skip / previous:** if the target is not decoded yet, show buffering or decode up to that point; don’t restart a full-file wait.
- **Duration:** use license/clip `duration_seconds` until all chunks are known; then refine.
- **iOS gesture:** first `resume()` + first `source.start` must not wait 30s after the tap. Chunk 0 must be the only wait before `start`.
- **Memory:** a full 3-minute stereo 48 kHz PCM is tens of MB. Acceptable for one track in RAM. Do not keep a queue of albums decoded.

---

## Test plan (gate for sandbox, then production on request)

Automated (extend existing theft tests, do not weaken them):

- Still forbid origin MP3 URLs, `blob:`/`data:audio/mpeg` play src, Range abuse.
- Segment responses remain `application/vnd.camxora.audio` (not `audio/mpeg`).
- Server chunk endpoint does not require a second full B2 GET for chunk 1 after chunk 0 in the same process (assert via mock storage).

Manual — **each row is a pass/fail**:

| # | Device | Browser | Check |
|---|--------|---------|--------|
| 1 | Windows PC | Chrome | Create Version 1+2: sound &lt; 3s, no MP3 blob in `audio.src` |
| 2 | Windows PC | Edge | Same |
| 3 | Windows PC | Firefox | Same, path=`webaudio`, not stuck until 100% |
| 4 | macOS | Safari | Same + ringer/output device |
| 5 | macOS | Chrome | MSE path, fast start |
| 6 | iPhone | Safari | Tap once, sound &lt; 3s, no skip-loop, no silent `play_ok` with `ctx=suspended` |
| 7 | iPhone | Chrome | Same as Safari (WebKit) |
| 8 | iPad | Safari | Same |
| 9 | Android | Chrome | MSE, fast start |
| 10 | Android | Firefox | Web Audio progressive, fast start |
| 11 | Any | Hard refresh, play same track | Still no plaintext file in Application/Cache; first sound still fast (phase 5 optional for instant) |
| 12 | Any | Switch Version 1 ↔ 2 mid-load | Previous fetch aborted; no OperationError storm |

Traces to confirm:

- `play_path=mse` on Chromium desktop/Android Chrome.
- `play_path=webaudio` on WebKit + Firefox.
- `play_ok` includes `ctx=running` on Web Audio.
- New: `first_audio_ms=` well under total file download time.

---

## Out of scope (this plan)

- HLS / fMP4 / AAC re-encode of the catalog.
- Putting MPEG MSE back on iOS.
- Desktop `camxora_python` player.
- Production deploy until sandbox QA on the matrix above and an explicit production request.

---

## Suggested ship shape

- One branch: `feature/protected-playback-fast-start`.
- Path-scope commits: API slice first, then player progressive Web Audio, then RAM cache.
- Sandbox file-scoped `music_web` hotfixes; no full `rebuild_music_web_sandbox.py` from a mixed tree.
- Production only on request, prefer merged `main`.
