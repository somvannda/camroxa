# SUNO STUDIO TECHNICAL ARCHITECTURE

How Camxora Studio is built today, and the boundaries that keep it independent.

## 1. Stack

| Layer | Tech | Location |
|---|---|---|
| Studio UI | Next.js 16 (App Router), React 19, TypeScript, CSS modules-free global classes | `camxora.com/` |
| Editor surface | Single client component `StudioEditorView` (~6.9k lines) | `camxora.com/components/StudioEditorView.tsx` |
| API client | Typed helpers over `musicAuthFetch` | `camxora.com/lib/studio-api.ts` |
| Platform API | FastAPI, ownership + credits + shaping | `platform_api/routers/web_music.py` |
| Core API | Fastify 5 + TypeScript | `musicapi/src/server.ts` |
| Persistence | PostgreSQL (`studio_projects`, versions, shares, comments, operations) | `musicapi/migrations/` |
| Audio engine | Web Audio API (native nodes + custom impulse/curve builders) | `StudioEditorView.tsx` |
| Encode | WAV writer in-house, MP3 via `@breezystack/lamejs`, ZIP via `jszip` | `StudioEditorView.tsx` |

## 2. Editor architecture (the important part)

`StudioEditorView` is one client component with a deliberately flat internal
structure. This is a known trade-off (D-005): splitting it is a refactor with real
risk and no user-visible change, so it is scheduled after W1–W3.

### 2.1 State

```
project        StudioProject | null        // server document
lanes          Clip[]                      // arrangement (tracks are derived)
midiLanes      MidiLane[]                  // MIDI clips + notes
markers        TimelineMarker[]
groups         TrackGroup[]                // A–D, collapse + group mix
history        HistorySnapshot[]           // bounded undo stack
playhead       number (seconds)
loopStart/End  number
zoom, snap, metronome, loop flags
selection      { clipId, laneId }
saveStatus     "idle" | "saving" | "saved" | "error"
```

Invariants:

1. Every mutation that changes the arrangement goes through `commitLanes`, which
   pushes a history snapshot and schedules an autosave.
2. `history` is bounded; the oldest snapshot is dropped, never the current one.
3. Playback never mutates arrangement state.
4. Derived values (bar/beat, duration, groups) are memoised, never stored.

### 2.2 Audio engine

- One `AudioContext`, created lazily on first user gesture (autoplay policy).
- Per clip: `AudioBufferSourceNode → clip gain (fade envelope) → track chain`.
- Per track chain: EQ (low/mid/high biquads) → filter → sends (delay/reverb/chorus)
  → dynamics (compressor/drive/duck) → pan (`StereoPannerNode`) → master.
- Master: EQ → compressor → drive → analyser → destination.
- Automation: volume and pan are scheduled as parameter curves at playback start;
  the visual editors edit the same points the scheduler reads.
- Metronome: scheduled clicks with a downbeat accent using the first time signature
  entry; mid-song signature changes are a known limitation (see `PROJECT_BLOCKERS.md`).
- MIDI: notes are synthesised into an `AudioBuffer` (`renderMidiBuffer`) so playback
  and export share one code path.
- Unplayable clip (decode failure, policy refusal): the clip is skipped and the UI
  states why; it never plays silence silently.

### 2.3 Persistence flow

```
edit → commitLanes → debounce (~1.5 s) → updateStudioProject({data})
                        ↓ failure
                  saveStatus="error" + retry action
```

- Saves send the whole arrangement document (`data`), which is what the API stores.
- Shared-project writes use `expectedUpdatedAt` for optimistic concurrency; a
  conflict surfaces as a resolution choice, not an overwrite.
- Project JSON import/export uses the same document shape, so an export can be
  re-imported losslessly.

### 2.4 Export pipeline

| Target | Path |
|---|---|
| Full mix WAV/MP3 | schedule all clips offline → `OfflineAudioContext` render → `encodeWav` / `encodeMp3` |
| Selected range | same render with `start`/`end` window |
| Per-track | render each track solo, one file per track |
| Multitrack ZIP | bundle per-track files |
| MIDI | `buildMidiFile` (VLQ writer) |
| Project JSON | serialise the arrangement document |

Server-side render endpoints exist in musicapi for paid, high-fidelity renders; the
browser path is the free, offline one. Both must produce the same arrangement.

## 3. Security boundaries

- Ownership is checked at platform_api for every project route; musicapi never
  trusts a client-supplied `user_id`.
- Share tokens are opaque, expiring, revocable, and permission-scoped; the shared
  route can only read/update within that scope.
- Uploads are validated for type and size before storage; playback URLs are
  short-lived.
- No provider credential ever reaches the browser.

## 4. Provider isolation

`musicapi` is our integration layer. Provider-specific request shapes, retries,
rate limits and CAPTCHA handling stay inside it (`suno.ts`, `client.ts`, `pool.ts`).
The Studio's contract is `/internal/studio/*` and never a provider endpoint. This
means a provider can be swapped or augmented (see `PROVIDER_SWITCHING.md`) without a
Studio release.

## 5. Known structural weaknesses

| # | Weakness | Impact | Plan |
|---|---|---|---|
| A1 | `StudioEditorView` is a 6.9k-line component | Hard to review, test, or extend | Split into hook + region components after W1 |
| A2 | No Studio test suite | Regressions are found by hand | W5 |
| A3 | Autosave has no conflict UX | Shared edits can overwrite | W2.2 |
| A4 | No offline draft | Network blip loses the last burst | W2.3 |
| A5 | No landing surface | Users cannot find their projects | W1 |
| A6 | Long projects render every clip | Perf cliff past a few hundred clips | W3 (virtualise) |
| A7 | Global CSS classes hold editor styling | Style drift, dead CSS risk | Tokenise with the split |

## 6. Performance budget (adopted)

| Metric | Target |
|---|---|
| Time to interactive on `/studio/editor` (warm) | < 2.5 s |
| Interaction (`drag clip`) frame time | < 16 ms p95 |
| Timeline with 200 clips | 60 fps while scrolling |
| Autosave round trip | < 400 ms p95 |
| Export a 3-minute stereo mix (browser) | < 15 s |

No measurement exists yet; W5 and W4.4 add the harness.
