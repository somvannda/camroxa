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

## Deliberately not built
The audit’s first draft listed a mixer, FX sends, track groups, a master spectrum, mastering
presets and MP3 export as Suno features. None of them appears in a capture or a shipped string;
S47 is an explicit **negative** capture proving the reference has no mixer surface. Building
them would be inventing surfaces, which D-034 forbids. The Learn menu’s YouTube Tutorials row
stays dropped by product decision.

## Verification

- `npm run typecheck`, `npm run check:ui` clean.
- Vitest **355** (44 files): new `studio-tempo` (7), `studio-wavetable` (6),
  `studio-project-thumb` (2), plus settings/menu/header updates.
- Playwright: new `studio-content-settings.spec.ts` (7 tests: panes + persistence, IR gating,
  clip FX add/remove with server polling, Stereo Utility, preset stepper, export scopes,
  wavetable designer); full suite **170 passed / 2 skipped**.
- Platform pytest: **3409 passed** (new `test_studio_project_thumb.py`).

## Files

- `camxora.com/lib/studio-settings.ts`, `lib/studio-wavetable.ts`, `lib/studio-tempo.ts`
- `camxora.com/components/studio/StudioWavetableDesigner.tsx`, `StudioProjectThumb.tsx`
- `camxora.com/components/studio/StudioProjectMenu.tsx`, `StudioPluginDock.tsx`,
  `StudioMidiEditor.tsx`, `StudioHeader.tsx`, `StudioEditorShell.tsx`
- `camxora.com/lib/studio-plugin-audio.ts`, `lib/studio-plugin-chain.ts` (Stereo Utility),
  `lib/studio-export.ts` (clip FX + wavetables), `lib/studio-midi.ts`
- `platform_api/services/web_music_service.py` (`thumb` summary),
  `platform_api/tests/test_studio_project_thumb.py`
