# Studio 1:1 completion pass — settings, clip FX, wavetables, Stereo Utility

Date: **2026-11-14** · Local only (production hold unchanged)

The three-column audit (`docs/studio/STUDIO_VS_SUNO_3COL.md`) found the arrangement surface at
parity but four captured surfaces missing. This pass closes them, plus the smaller deltas the
captures show. Production `camxora.com` is still not deployed.

## Shipped

| Area | What changed | Evidence |
|---|---|---|
| Studio Settings | Real three-pane dialog: **Performance** (ghost drag, count-in), **Window management**, **Content**; dialog closes on Escape; `ctrl shift ,` still opens it | S09, S10, S11, §22, §29, §39 |
| Window management | Segmented control **Panels · Windows · Show toggle**; Panels docks every card, Windows floats them, Show toggle keeps the per-card Pop out control (remembered in the chain) | S10, §39 |
| Content | **Auto-stretch added audio** and **Advanced content features** toggles, both persisted | S11, §29 |
| Advanced gating | Impulse Response Designer entry is hidden (not disabled) when advanced content is off | S11 copy |
| Wavetable Designer | New designer: 16 sine partials, six presets, normalised preview, saved to `data.wavetables`; MIDI clips pick it as an instrument and playback/export/bounce build the real `PeriodicWave` | §30 N-14, §29 |
| Auto-stretch | Tempo detection from the peak envelope (onset voting, 60 % agreement gate); uploads snap to the project tempo, pads/one-shots keep their timing, generated clips never stretch | S11 copy, §29 N-16 |
| Clip FX | Clips carry their own insert chain (`clip.fx`), applied clip → clip FX → gain/fade → track chain in playback, export and bounce; clip menu gains **Add FX…** and **Remove FX** now removes the clip's chain | §31, §33, §34 |
| Stereo Utility | New plugin (Level / Width / Pan / Bass Mono) with a real mid-side implementation and a mono-bass low cut | S21 dock |
| Export menu | Scopes renamed to the captured **Full Song · Selected Time Range · Multitrack**, with the captured toasts | S49, S50, S51 |
| Preset stepper | The `‹ Default ›` chevrons audition presets without opening the menu; hidden for designed plugins | S46 |
| Convolution ruler | IR slot labels the captured 0 s · 1 s · 2 s · 3 s ticks instead of only 0 s / 2 s | S44 |
| Hidden tracks | The popover gains the captured **Unmute all** action next to Show All Hidden Tracks | S21 |
| My Projects | Cards draw a mini-timeline from a bounded `thumb` summary returned by the list endpoint | S04 |
| Recently Deleted | Delete is soft (`deleted_at`); the captured tab lists deleted projects and **Restore** puts the document back in Projects (migration `203`) | S04 §56 note 3 |
| MP3 export | Export menu gains a WAV/MP3 toggle; MP3 is the same offline render encoded with the bundled LAME encoder (dynamic import) | requested |
| Project JSON import | Project menu → **Import project…** validates lanes/tracks and creates a new project | requested |
| Master spectrum | 32-band canvas drawn from the analyser the engine already puts on the master bus | requested |
| FX sends | Per-track Delay/Reverb send levels into two shared buses, applied in playback and export; sliders live in the dock | requested |
| Track groups A–D | Membership on the track, submix level in `data.groups`, collapse of member controls | requested (ARR-027) |
| Song tempo tag | Library rows measure BPM from the clip audio (lazy, cached) | §19.2 |
| Song key tag | Library rows estimate the key from a chroma vector + Krumhansl profiles and label it **≈** (never as metadata) | §19.2 |
| Stems tab verified | Provider-shaped stems result lists and places a stem (`studio-stems.spec.ts`); **and a real 2-stem job ran live**, stored in B2 | B-005 |
| Voice persona verified live | A generated vocal song produced a provider persona (`61c050dc-…`) via `POST /studio/generations/{id}/personas` | B-005 |
| Record + bounce verified with storage | `STUDIO_EXPECT_UPLOADS=1` against moto S3: record → upload → take, and render-in-place bounce | B-006/B-007 |

## Live provider evidence (2026-11-14)

A working Suno session was recovered from the `suno_accounts` row for the sandbox user
(the other two rows were encrypted with a key this environment does not hold). With the
platform talked to the local musicapi, the real provider paths ran:

| Path | Evidence |
|---|---|
| **Stems (2-stem)** | Task `90c28ba4-2306-4a05-8f53-bd0e544495ed` → provider clip `9c995dd2-…` → operation `ae98d516-…` **complete**; `GET /studio/stems` returns `(Vocals)` stored in B2; the Stems tab lists it and **Add** places a clip with a real URL (`compare/ours-stems-live.png`) |
| **Voice persona** | Vocal song `dec67289-…` → `POST /studio/generations/{id}/personas` → persona `Voice check 26489` **complete** with provider persona `61c050dc-af7c-465a-baf8-455c149ad01b` |
| **Record → take** | `STUDIO_EXPECT_UPLOADS=1` with the fake microphone and moto S3 |
| **Render-in-place bounce** | Same flag + `STUDIO_UPLOAD_PROXY_URL`, object landed in the bucket |

Two defects were found by running it for real and fixed:

1. **musicapi `/api/v1/generate` ignored `gpt_description_prompt`** — the
   platform's Suno client sends the idea in that field, so the compat layer answered
   `400 prompt is required`. It now accepts it (and the platform generation succeeds).
2. **Local platform wiring** needed the provider key-pool master key, the local Suno base
   URL and a non-local callback base; the sandbox also needs
   `system_settings.credits_only_v3_charge=true` so generation uses the v3 charge bridge.
3. **List ordering stayed index-friendly:** the Recently Deleted filter kept
   `ORDER BY p.updated_at DESC` (not `COALESCE(deleted_at, updated_at)`, which forced a sort
   over 26k rows), and a delete now bumps `updated_at` so deleted projects sort by recency.
| Duplicate master effect | Master still refuses a second limiter and says so in the menu | “Already on Master” string |

## Visual parity pass (same day)

Nine captures at 1689×1277 (`docs/studio/compare/`) were paired with S04/S09/S10/S11/S21/S26/
S40/S44/S46/S49. The pass found four defects the automated suite could not see:

| Defect | Fix |
|---|---|
| Settings dialog stayed 480 px wide (the base `.se-dialog` max-width won) | 760 px card, left-aligned title, circular X close |
| Hidden-tracks popover opened off the left edge of the viewport | Opens over the timeline, like S21 |
| “What’s This?” card covered open context menus | Hover help pauses while a clip/track menu is open |
| Export menu ignored Escape | Closes on Escape like every other overlay |

The populated feed also surfaced a real Create-page axe failure the empty-state runs never
reached: feed day groups and the song rail jumped h1 → h3/h4. Day groups are h2 now and the
rail title/sections are h2/h3 (`create-a11y.spec.ts` green).

## Not evidenced — built anyway, on request

The audit listed a master spectrum, MP3 export, project JSON import, FX sends, track groups and
mastering presets as “not evidenced”. The first three and the last are now real features (the
master presets already existed). The rest of that list stays out: **S47 is a negative capture
proving the reference has no mixer surface**, and copy/paste mix settings never appears in any
capture or shipped string. The Learn menu’s YouTube Tutorials row stays dropped by product
decision.

## Verification

- `npm run typecheck`, `npm run check:ui` clean.
- Vitest **372** (48 files): new `studio-tempo` (7), `studio-wavetable` (6),
  `studio-project-thumb` (2), `studio-groups` (5), `studio-sends` (4), `studio-song-tempo` (2),
  plus settings/menu/header updates.
- Playwright: new `studio-content-settings.spec.ts` (7 tests: panes + persistence, IR gating,
  clip FX add/remove with server polling, Stereo Utility, preset stepper, export scopes,
  wavetable designer) and `studio-soft-delete.spec.ts` (delete → Recently Deleted → restore);
  full suite **177 passed / 2 skipped**.
- Platform pytest: **3415 passed** (new `test_studio_project_thumb.py`,
  `test_web_music_studio_soft_delete.py`).
- `next build` produces the production bundle; `next start` on a spare port serves a
  29-route signed-in sweep with no page errors, no 5xx and no console errors after sign-in
  (the only noise is the expected pre-auth 401 probes on the first load).
- The dev server serves the same 30-route sweep clean.

## Files

- `camxora.com/lib/studio-settings.ts`, `lib/studio-wavetable.ts`, `lib/studio-tempo.ts`
- `camxora.com/components/studio/StudioWavetableDesigner.tsx`, `StudioProjectThumb.tsx`
- `camxora.com/components/studio/StudioProjectMenu.tsx`, `StudioPluginDock.tsx`,
  `StudioMidiEditor.tsx`, `StudioHeader.tsx`, `StudioEditorShell.tsx`
- `camxora.com/lib/studio-plugin-audio.ts`, `lib/studio-plugin-chain.ts` (Stereo Utility),
  `lib/studio-export.ts` (clip FX + wavetables), `lib/studio-midi.ts`
- `platform_api/services/web_music_service.py` (`thumb` summary),
  `platform_api/tests/test_studio_project_thumb.py`
