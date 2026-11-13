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
| Library panel: level-1 tile chooser (All Songs / Liked / Stems / Uploads) + Workspaces and Studio Projects sections, then level-2 lists with Add/Open | §19.1 / gap G12 | `components/studio/StudioLibrary.tsx` (`LibraryView`) + `openLibrarySongs` / `openLibraryWorkspace` in `StudioEditorShell.tsx` |
| Level-1 rows: hover `Open` on workspace/project rows (workspaces also show `More` in the reference; its menu was not captured) | §19.1 | `StudioLibrary` `.se-lib-row-action` |
| Level-2 toolbar: Liked only / New / In Project / Stems-disabled / Uploads | §19.2 / D-016 | `StudioLibrary` toolbar chips; `setLibrarySongFilter`, `uploadLibraryAudio` in `StudioEditorShell.tsx` |
| New workspace row (creates a default-named workspace) | §19.1 / D-017 | `StudioLibrary` + `createLibraryWorkspace` in `StudioEditorShell.tsx` |
| Song rows: 44 px artwork, model/variant/length tag strip, In Project filter | §19.2 / D-016 | `primaryClip` / `songTags` in `StudioLibrary.tsx` |
| Song row actions: Play/Pause audition (one at a time) and Like toggle, plus our Add | §19.2 / D-016 | `StudioLibrary` row actions; `toggleSongPreview` / `toggleSongLike` in `StudioEditorShell.tsx` |
| Drag a library song onto a lane; clip lands at the drop point, grid-snapped | §19.2 / D-016 | `SONG_DRAG_TYPE` + draggable rows; `dropSongOnLane` in `StudioEditorShell.tsx`, lane drop props in `StudioTimeline.tsx` |
| Uploads list: date-grouped rows with Play/Pause audition and Add | §19.2 / D-016 | `StudioLibrary` uploads view; `toggleUploadPreview` in `StudioEditorShell.tsx` |
| Song detail rail on row double-click: back, Remix/Like/Dislike/More, big Play, Info/Stems, Styles/Lyrics copy + show-more, comments | §100 / D-018 | `components/studio/StudioSongDetail.tsx`; `detailSong` in `StudioEditorShell.tsx` |
| Arm one track + record a microphone take (upload → `Take N` clip at the playhead) | G21 / D-020 | `StudioTrackPanel` arm button; `startRecording` / `finishRecording` in `StudioEditorShell.tsx`; `StudioHeader` Record |
| Recording input picker: `enumerateDevices()` menu next to Record, device stored in browser settings | G21 / D-020 | `StudioHeader` menu; `toggleInputPicker` / `pickInputDevice`; `StudioSettings.inputDeviceId` |
| One-bar count-in (opt-in) before capture, with beat status | G21 / D-021 | `StudioHeader` count-in checkbox + status; `runCountIn` in `StudioEditorShell.tsx` |
| Songs grouped under Today / Yesterday / date headers, each collapsible from its heading | §19.2 | `lib/studio-library-grouping.ts`; `StudioLibrary` day headings |
| Project menu: 9 captured items anchored under the project chip | §18.1 / §44.2 / gap G23 | `components/studio/StudioProjectMenu.tsx` (8 wired, 1 disabled with a reason) |
| Share: view + copy link, naming gate first | §24 / §24.1 | `StudioProjectMenu` share dialog + `createStudioProjectShare` / `listStudioProjectShares` |
| Public share page: read-only render, comments, fork to a copy | §24 | `app/studio/shared/[token]/page.tsx`; fork opens the returned project id |
| Ghost drag: hold the pre-drag audio, apply once on drop; read at gesture start | §22 / gap G24 | `lib/studio-settings.ts` (`dragApplyPlan`) + `restartAudio` in `StudioEditorShell` |
| Learn menu: four rows, `?` shortcut list, "What's This?" hover cards | §7 / §38 / §62.2 / gap G25 | `components/studio/StudioLearn.tsx` + `lib/studio-help.ts` |
| Add-track menu: Audio A / MIDI M / Upload U | §8.3 / gap G26 | `StudioTrackPanel` add menu; Upload opens the library at its level-2 Uploads list |
| Keyboard: Space, Home/End, A, U, plus the modifiers | §11 / gap G26 | keydown handler in `StudioEditorShell`; list in `lib/studio-help.ts` |
| Metronome click track with bar accent | H-09 / gap G27 | `lib/studio-metronome.ts` + `scheduleClicks` in `StudioEditorShell` |
| Loop repeats the selected range; seeking follows while playing | §68 / gap G33 | transport tick + `seekTo` in `StudioEditorShell` |
| Zoom presets 48–192 px/bar, fit derives from content | §44.3 / gap G34 | `zoomBy` / `zoomToFit` in `StudioEditorShell` |
| Plugin chain per track, applied to playback and export | §48 / §50 / gap G35 | `lib/studio-plugin-audio.ts` (`buildPluginChain`) + track input in `startAudio` / `renderMix` |
| Live chain edits: params update nodes, shape rebuilds | §50 / gap G36 | chain runtime map + structure signature in `StudioEditorShell` |
| Track mute/solo/volume follow the running mix | G21 / gap G37 | per-track gain nodes + mix effect in `StudioEditorShell` |
| Mix export follows solo (per-track exports do not) | §87 / gap G39 | `honourSolo` in `renderMix` |
| Master Main fader + Mute main, live and persisted | F-01 / F-02 / gap G40 | footer master section + `masterGain` in `renderMix` |
| Track level/pan sliders + collapsed controls | T-02 / T-03 / gap G41 | `StudioTrackPanel` range inputs + `collapsed` on `StudioTrack` |
| Stop halts in place; Back to start rewinds | H-05 / H-08 / gap G42 | `onStop` / `onBackToStart` in `StudioHeader` + shell |
| Editable meter drives bar maths and the click accent | H-13 / gap G43 | `lib/studio-signature.ts` + header select |
| Captured shortcut map (loop, metronome, select all, cut, mute/solo, hide, rename, panels) | §36 / C-07 / gap G44 | keydown handler in `StudioEditorShell`; overlay list in `lib/studio-help.ts` |
| Shortcut map additions: ALT Space plays from the selection start, CTRL ↑/↓ reorder the focused track, SHIFT A toggles automation, 1/3/4 toggle assistant / take lanes / library | §36 / gap G44 | same keydown handler; rows in `lib/studio-help.ts` |
| Trim grips at each end; left trim moves the content offset | S25 / gap G45 | `se-trim` grips + `offset` on clips in `startAudio` / `renderMix` |
| Fade handle + Shift F; fade applied to playback and export | S25 / gap G46 | `se-fade-handle` + `fadeIn` envelope in `startAudio` / `renderMix` |
| Clip menu from clip state; split carries the offset | §47 / S26 / gap G47 | `se-clip-menu` in `StudioEditorShell` + `splitClips`; ruler click seeks |
| Clip info panel: timing, source, decoded waveform, Stems tab | §70 / gap G48 | `components/studio/StudioClipInfo.tsx` |
| Version history as a dated left side panel | §25 / gap G49 | `se-history` aside in `StudioProjectMenu` |
| Version history: automatic snapshots, throttled, newest 50 kept | §25 / gap G28 | `persist()` → `autoSnapshotStudioProject` + `AUTO_VERSION_MIN_SECONDS` in `web_music_service.py` |
| Empty project asks how to start | §10 / gap G18 | `components/studio/StudioOnboarding.tsx` |
| Coarse pointers get 44 px targets | gap G20 | `app/touch-targets.css` |
| Clips culled outside the visible window | gap G19 | `view` state in `StudioEditorShell` |
| Automation points select on click and nudge with `←/→` / `↑/↓` (`SHIFT` coarse) | §36 / gap G44 | keydown handler in `components/studio/StudioAutomationPanel.tsx` |
| Audio clip editor steps the warp quantize grid with `SHIFT 1` / `SHIFT 2` | §36 / gap G44 | keydown handler in `components/studio/StudioAudioEditor.tsx` |
| `0` toggles the arrangement (master) mute | §36 / gap G44 | `toggleMasterMute` + `Mute main` in the track panel |
| Back to Start alternates the song start and beat 1 | S14 hint / gap G44 | `backToStart` + `backToStartAnchorRef` in `StudioEditorShell` |
| `SHIFT 1` / `SHIFT 2` double or halve the arrangement grid | S14 overlay / gap G44 | `scaleGrid` in `lib/studio-snap.ts` + `gridDivisions` in the shell |
| Project menu sends the project to Suno on demand | S14 overlay "Send to Suno Sync" | `syncStudioProject` in `lib/studio-api.ts` + the menu's sync dialog |
| Library `↓`/`↑` audition the next/previous song and `→` replays the current one | S14 library panel / gap G44 | `onAudition` + `handleAuditionKeys` in `StudioLibrary` (cursor follows visible, expanded rows) |
| Split Arrangement cuts every clip crossing the playhead | S14 overlay | time-selection menu → `splitClips` with every clip id |
| Split on Transients cuts a clip at the onsets in its audio | S14 overlay | clip menu → `computePeaks` + `detectOnsets` + `splitClipAtTimes` |
| Make Beat 1 snaps a clip's start onto its bar line | S14 overlay | clip menu → `makeClipBeatOne` |

### S14 shortcut coverage still open

| Binding | Why it is not wired yet |
|---|---|
| `2` bottom panel | this build has no persistent bottom panel; Plugins and Clip editor open on demand |
| `SHIFT L` arrangement panel | there is no collapsible arrangement panel to toggle |
| `CTRL S` save | saving is automatic and already reports through the save-status chip |
| `CTRL K` toggle keyboard | there is no musical typing keyboard to show; `SHIFT ?` already opens this list |
| `CTRL SHIFT ,` Studio settings | settings are a stored preference object, not a dialog |
| `ENTER` Ask Studio / promote take lane | `ENTER` already commits inline renames and prompt edits |
| Playable keyboard | musical typing needs a captured surface; its `Z`/`X`/`C`/`V` collide with the zoom and clipboard keys |

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
- Gap status: `SUNO_STUDIO_GAP_ANALYSIS.md` (47 of 49 closed; G12 and G21 partial)
- Audio claims: `window.__buildMasterBus`, `__studioExport`, `__studioMeter`,
  `__studioNormalise` in dev
