# SPEC → CODE — what the captures actually produced

Answers one question: **is the Studio we are building actually derived from the Suno
reference?** Each row is a measured reference behaviour (spec section), the code that
implements it, and how it was verified. Only rows that exist are listed.

## 1:1 — behaviour copied from the capture

| Reference behaviour | Spec | Code |
|---|---|---|
| Save-status is silent; we added four states | §93 (their absence) | `components/studio/StudioSaveStatus.tsx` + `persist()` in `StudioEditorShell` |
| Two-tab writes overwrite silently | §93 (their absence) | `platform_api/services/web_music_service.py` (`expected_updated_at`) |
| No offline state at all | §96 (their absence) | `lib/studio-draft.ts` |
| Track row: 85 px, step 86, volume 172 / pan 48 | §52.1 | `.se-track` / `.se-lane` in `StudioEditorShell` |
| Drag threshold ≈3 px before a press becomes a drag | §69 / gap G8 | `lib/studio-snap.ts` `isDrag` |
| Snap to the grid with a guideline | §69 / gap G7 | `lib/studio-snap.ts` `dragToStart` + `.se-snap-line` |
| Marquee select, multi-drag, C/V/D | §26 / gap G6 | selection + `insertClips` in `StudioEditorShell` |
| Delete keeps focus on a neighbour | gap G9 | `deleteSelection` + `focusPendingRef` |
| Master is a chain target, ships with a Limiter | §91 | `lib/studio-master-bus.ts` (default `{type:"limiter"}`) |
| Export = 3 scopes, fires without a dialog | §87 | Export menu → `lib/studio-export.ts` |
| Preset stepper `‹ name ›` + save/clear menu | §90 | `StudioPluginDock` (captured surface) |
| Take model: audition vs commit, newest on top | §72.1 | captured in spec; take UI still reference-only |
| Clip remembers its source generation | §70 | `songId` on clip + provenance strip |
| Library panel: songs with Add, workspace filter with counts, projects with Open, uploads with Add | §19.1 / gap G12 | `components/studio/StudioLibrary.tsx` + `selectLibraryWorkspace` |
| Project menu: 9 captured items anchored under the project chip | §18.1 / §44.2 / gap G23 | `components/studio/StudioProjectMenu.tsx` (8 wired, 1 disabled with a reason) |
| Share: view + copy link, naming gate first | §24 / §24.1 | `StudioProjectMenu` share dialog + `createStudioProjectShare` / `listStudioProjectShares` |
| Public share page: read-only render, comments, fork to a copy | §24 | `app/studio/shared/[token]/page.tsx`; fork opens the returned project id |
| Ghost drag: hold the pre-drag audio, apply once on drop; read at gesture start | §22 / gap G24 | `lib/studio-settings.ts` (`dragApplyPlan`) + `restartAudio` in `StudioEditorShell` |
| Learn menu: four rows, `?` shortcut list, "What's This?" hover cards | §7 / §38 / §62.2 / gap G25 | `components/studio/StudioLearn.tsx` + `lib/studio-help.ts` |
| Add-track menu: Audio A / MIDI M / Upload U | §8.3 / gap G26 | `StudioTrackPanel` add menu; Upload opens the library's Uploads tab |
| Keyboard: Space, Home/End, A, U, plus the modifiers | §11 / gap G26 | keydown handler in `StudioEditorShell`; list in `lib/studio-help.ts` |
| Metronome click track with bar accent | H-09 / gap G27 | `lib/studio-metronome.ts` + `scheduleClicks` in `StudioEditorShell` |
| Loop repeats the selected range; seeking follows while playing | §68 / gap G33 | transport tick + `seekTo` in `StudioEditorShell` |
| Zoom presets 48–192 px/bar, fit derives from content | §44.3 / gap G34 | `zoomBy` / `zoomToFit` in `StudioEditorShell` |
| Version history: automatic snapshots, throttled, newest 50 kept | §25 / gap G28 | `persist()` → `autoSnapshotStudioProject` + `AUTO_VERSION_MIN_SECONDS` in `web_music_service.py` |
| Empty project asks how to start | §10 / gap G18 | `components/studio/StudioOnboarding.tsx` |
| Coarse pointers get 44 px targets | gap G20 | `app/touch-targets.css` |
| Clips culled outside the visible window | gap G19 | `view` state in `StudioEditorShell` |

## Not copied — by rule, not by accident

| Item | Why |
|---|---|
| Branding, logo, copy, artwork | mission rule D-004; all copy in this app is written fresh |
| Reference private API | D-002; everything goes through our own `platform_api` |
| Exact pixel metrics | project rule: match density and interaction, not pixels; our tokens are `.s-*`/`hsl(var(--…))` |

## Added — they don't have it, we do

Save status · conflict resolution · offline draft · unsaved guard · master peak
readout · **export normalisation** (`lib/studio-normalise.ts`: mix/range gained to a
−1 dBFS sample peak) · project JSON export · 3-tile onboarding (theirs has 5, three of
which we cannot honour).

## Captured as negatives (so there is nothing to clone)

| Screen | What the capture proved |
|---|---|
| S47 mixer | no mixer exists — mixing is the track row + master chain |
| S50/S51 export dialog | no dialog — a toast and a download |
| S54/S56 sharing | project-level view+copy only; no public page |
| S59 conflict UI | no banner; silent overwrite |
| S62 offline | browser error page on cold load |

## How to check this yourself

- Screenshots: `reference/screens/` (78 files) + `reference/SCREENSHOT_INDEX.md`
- Measurements: `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §1–§96
- Gap status: `SUNO_STUDIO_GAP_ANALYSIS.md` (32 of 34 closed; G12 and G21 partial)
- Audio claims: `window.__buildMasterBus`, `__studioExport`, `__studioMeter`,
  `__studioNormalise` in dev
