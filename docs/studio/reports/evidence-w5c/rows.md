| ID | Verdict | Evidence (measured) |
|---|---|---|
| C-01 | **PASS** | menu "Project options", 11 rows: New Project \| Open Project \| Rename \| Duplicate Project \| Version History \| Share Project \| Open a copy in v1 \| Studio Settings ctrl shift , \| Show Quick Start again \| Import project… \| Send to Suno Sync |
| C-02 | **PASS** | order = New Project → Open Project → Rename → Duplicate Project → Version History → Share Project → Open a copy in v1 → Studio Settings ctrl shift , → Show Quick Start again → Import project… → Send to Suno Sync |
| C-03 | **PASS** | disabled=true, title="There is no v1 Studio in this product" |
| C-04 | **PASS** | hint = "ctrl shift ," |
| C-05 | **PASS** | Escape closed the menu; 0 dialogs opened |
| C-06 | **PASS** | pointerdown outside the chip closed the menu |
| C-07 | **PASS** | aria-expanded true → false, menu toggled closed |
| C-08 | **FAIL** | Two paths measured. Playwright's synthetic `Control+Shift+,` reports `key=","` and opens Studio Settings; a hardware `keydown` with the value a US keyboard actually sends for Shift+Comma (`key="<"`, `code="Comma"`) opens nothing. The handler compares `event.key !== ","`, so the documented accelerator is dead on a real keyboard. — `C-08.png` |
| C-09 | **PASS** | focus in the rename field: Settings did not open |
| C-10 | **PASS** | rename dialog open: Settings did not stack |
| C-11 | **FAIL** | With `POST /studio/projects` delayed then aborted, the menu is already closed (every row calls `setOpen(false)` before its action) and **no error renders anywhere**: 0 `.se-dialog-error`, no toast, 0 disabled rows observed. A failed menu action is silent. — `C-11.png` |
| C-12 | **PASS** | after reload the menu is closed (aria-expanded=false) |
| C-13 | **PASS** | new id 668c90fd-71e0-465a-8be1-b26edfa59e08; empty state "Your session is empty Add a track to start arranging." |
| C-14 | **PASS** | h2="My Projects", tabs=1, search=1, Filters disabled=true, sort=1 |
| C-15 | **PASS** | tabs = Projects / Recently Deleted, selected = Projects |
| C-16 | **PASS** | first card is-new=true; 20 project cards; sample "Untitled project" / 11/17/2026 |
| C-17 | **PASS** | filtered to W5C Versions; no-match note = "No projects match that search." |
| C-18 | **PASS** | Filters disabled, title="Project filters are not built" |
| C-19 | **PASS** | Newest First [Untitled project, Master dvv2tk, Spectrum probe…] reversed under Oldest First |
| C-20 | **PASS** | card "W5C Versions" navigated to http://127.0.0.1:3105/studio/editor?project=f42f72d7-4344-47a0-a2f7-72fe4dd2b7dc (chip "W5C Versions") |
| C-21 | **PASS** | deleted card "Restore W5C Deleted" shows "W W5C Deleted Deleted 11/17/2026 Restore" |
| C-22 | **PASS** | tab returned to Projects; restored card present (first card = W5C Deleted) |
| C-23 | **PASS** | empty deleted view note = "Nothing here. Deleted projects stay restorable." (shared DB has other runs' deletions, so the note was reached through the search filter) |
| C-24 | **PASS** | dialog closed; project unchanged ("W5C P1") |
| C-25 | **PASS** | prefilled with "W5C P1" |
| C-26 | **PASS** | inline error "A project title is required.", 0 writes issued |
| C-27 | **PASS** | chip "W5C P1 renamed"; next-edit save chip = "Saved" |
| C-28 | **PASS** | Escape closed without saving; chip still "W5C P1 renamed" |
| C-29 | **PASS** | fork opened: id ca58c605-c0b2-4b02-9361-83be156041e1, chip "W5C Fork Source copy" |
| C-30 | **PASS** | original still has 4 tracks / 5 clips |
| C-31 | **PASS** | panel opened; first note "Loading versions…" → "History Projects are saved automatically No versions yet. Versions are captured automatically as you edit." |
| C-32 | **PASS** | no-version note = "No versions yet. Versions are captured automatically as you edit." |
| C-33 | **PASS** | 1 version row(s) under "11/17/2026" with ‹ › stepper |
| C-34 | **PASS** | Restore version from 12:21 PM restored: reload produced 4 tracks (3 visible rows; Scratch stays hidden) |
| C-35 | **FAIL** | ✕ closes the panel correctly (that half passes), but the visible note reads `Projects are saved automatically`; the sentence the row quotes (`Restoring replaces the arrangement and reloads the editor.`) does not exist in the tree (grep: 0 hits). — `C-35.png` |
| C-36 | **PASS** | gate "Name project before sharing" shown for an unnamed project |
| C-37 | **PASS** | Skip opened share for "Share “Untitled project”" |
| C-38 | **PASS** | name saved, share opened for "Share “W5C Shared Name”" |
| C-39 | **PASS** | named project: Share opened with no naming gate |
| C-40 | **PASS** | lead = "Anyone with the link can view this project and create their own editable copy." |
| C-41 | **PASS** | readonly link /studio/shared/tlkcVUjHwtoOMF1vGP7Vub6ArUI1xeH8… ; note "The link is view-and-copy only; it is not live collaboration. It expires on Nov " |
| C-42 | **PASS** | label "Copied"; clipboard = http://127.0.0.1:3105/studio/shared/tlkcVUjHwtoOMF1vGP7V… |
| C-43 | **PASS** | clipboard denied: "Could not reach the clipboard — select and copy the link above." |
| C-44 | **PASS** | re-opened share reuses the same live link (ub6ArUI1xeH8) |
| C-45 | **PASS** | Done closed the share dialog |
| C-46 | **PASS** | opened with "Pushing this project to Suno…" |
| C-47 | **BLOCKED** | **BLOCKED / ENVIRONMENT.** Real push: `The Suno Studio mirror did not accept this project.` (the local mirror refuses a localhost callback — W4 §1.1; `readiness` also reports `musicapi:false`). With the platform result mocked to `Queued`, the dialog renders `Queued — Suno picks it up in the background.`, so the sentence path itself is sound. — `C-47-1689x1277.png` |
| C-48 | **PASS** | Note renders once a push result carries `skipped_clips`: `2 clips stay local: no Suno asset yet.` (result supplied by the same mocked push as C-47; the real mirror returns no result at all). |
| C-49 | **PASS** | Close cleared the result (a reopened dialog starts without a status row: true) |
| C-50 | **PASS** | native chooser opened; accept="application/json,.json" |
| C-51 | **PASS** | imported and opened: chip "W5C Import (imported)" |
| C-52 | **PASS** | title "Studio Settings", nav = Performance / Window management / Content |
| C-53 | **PASS** | default pane = Performance |
| C-54 | **PASS** | checked=true; copy mentions the apply-on-drop behaviour |
| C-55 | **PASS** | Count-in before recording default = off |
| C-56 | **PASS** | radiogroup = Panels / Windows / Show toggle; default = Show toggle |
| C-57 | **PASS** | Panels mode: 0 pop-out buttons, 0 popped slots |
| C-58 | **PASS** | Windows mode: 0 popped card(s) + 2 rail placeholder(s) for 2 slot(s) |
| C-59 | **PASS** | Auto-stretch on; Advanced content off |
| C-60 | **PASS** | Advanced content on without reload: .se-midi-design visible |
| C-61 | **PASS** | localStorage keys persist after reload: advancedContent=true, windowMode=windows |
| C-62 | **PASS** | ✕ closed the dialog |
| C-63 | **PASS** | same preference on a different project (browser-scoped), advancedContent=true |
| C-64 | **PASS** | opens at the pointer (clip x=260), box 356,125 163×1076 within 1689×1277; maxHeight=1144px; overflow-y=auto; rows past the viewport=0 |
| C-65 | **PASS** | first six rows = Copy ctrl C \| Paste ctrl V \| Duplicate ctrl D \| Delete backspace \| Copy settings \| Paste settings |
| C-66 | **PASS** | after a reload (empty clipboard) Paste is disabled |
| C-67 | **PASS** | Copy → Paste enabled in the re-opened menu |
| C-68 | **PASS** | no settings copied: Paste settings disabled |
| C-69 | **PASS** | toast "Clip settings copied."; Paste settings enabled on another clip |
| C-70 | **PASS** | toast "Settings pasted to 1 clip."; fadeIn=0.5, fadeOut=0.75, audio copied |
| C-71 | **PASS** | Heal Edits disabled, title="No generated edits to heal" |
| C-72 | **PASS** | P2 clip: Heal Edits enabled, title="Restore the audio from before the generated edits" |
| C-73 | **PASS** | toast "Edits healed to the original clip."; take-lane bands visible = 0 |
| C-74 | **PASS** | playhead at the clip start: Split disabled |
| C-75 | **PASS** | playhead inside: Split enabled, label "Split ctrl E" |
| C-76 | **FAIL** | `Split on Transients` opened with `No transients found in this clip.` — no `Finding transients…`, no split, clip count stayed 5. The negative branch is correct product copy; the fixture WAV (`/seed/demo-loop.wav`) has no detectable onsets, so the split path is unproven. — `C-76.png` |
| C-77 | **PASS** | MIDI clip: disabled, title="This clip has no audio to analyse" |
| C-78 | **PASS** | toast "Clip moved to the bar line at 2.00s."; start now 2s |
| C-79 | **PASS** | toast "This clip already starts on a bar line." |
| C-80 | **PASS** | marker on the ruler labelled "Drums A" |
| C-81 | **PASS** | Enter saves, Escape discards, an empty name is ignored |
| C-82 | **PASS** | library was open (1) and closed; Clip info inspector opened |
| C-83 | **PASS** | group opened: Auto + 20 swatches (checklist says 5; the palette was widened to 20 in b3d718f4) |
| C-84 | **PASS** | Clip colour #1d4ed8 applied; clip background rgb(56, 189, 248); menu closed; 1 clip stays selected |
| C-85 | **PASS** | Auto pressed; clip falls back to the track colour (rgb(56, 189, 248)); stored colour cleared |
| C-86 | **PASS** | song-backed clip: dialog "Separate stems" opened and cancelled |
| C-87 | **PASS** | uploaded clip: disabled, title="No source generation for this clip" |
| C-88 | **PASS** | MIDI clip disabled=true ("Download .WAV"); audio clip started "Drums A.wav" |
| C-89 | **PASS** | disabled without songId; toast "Transcribing MIDI..." → "MIDI added as a track (3 notes)." (4 tracks) |
| C-90 | **PASS** | Remove FX disabled with no fx; Add FX… opened the clip-effect dialog (closed with Cancel — no Escape handler) |
| C-91 | **PASS** | uploaded clip without songId → Extend:disabled (No source generation for this clip); Cover…:disabled (No source generation for this clip); Remaster:disabled (No source generation for this clip); Vocals…:disabled (No source generation for this clip); Instrumental…:disabled (No source generation for this clip); Mashup…:disabled (Select two clips that have a source generation); Replace…:disabled (Select a time range over this clip first) |
| C-92 | **PASS** | one clip selected: Mashup disabled, title="Select two clips that have a source generation" |
| C-93 | **PASS** | no range: Replace disabled, title="Select a time range over this clip first" |
| C-94 | **PASS** | audio clip selected: Download MIDI disabled, title="Select a MIDI clip with notes first" |
| C-95 | **PASS** | inspector closed via "Back to arrangement"; selection kept (1) |
| C-96 | **PASS** | Escape closed the menu without an action (clips=6) |
| C-97 | **PASS** | pointerdown outside closed the menu |
| C-98 | **PASS** | menu moved from x=356 to x=548 and now targets Vox (Get Stems disabled) |
| C-99 | **PASS** | menu with range header "00:02 – 00:04" |
| C-100 | **PASS** | right-click with no range opened no menu |
| C-101 | **PASS** | loop band covers the range and the Loop toggle is pressed |
| C-102 | **PASS** | "Arrangement split at the playhead."; clips 5 → 7 |
| C-103 | **PASS** | clips c-d1:0,c-d2:8,c-bass:0,c-vox:4,c-scratch:0 → c-d1:0,c-d1~d:4,c-d1~m:2,c-d2:10,c-bass:0,c-bass~d:4,c-bass~m:2,c-bass~r:6,c-vox:6,c-scratch:0 |
| C-104 | **PASS** | Drums B start 8 → 6s (ripple-left); 6 clips remain |
| C-105 | **PASS** | no focused track (0) → disabled, title="Focus a track first" |
| C-106 | **PASS** | range export downloaded "W5C C5 export - selection.wav" |
| C-107 | **PASS** | Clear selection removed the range |
| C-108 | **PASS** | menu "Drums options" with 7 rows: Rename track \| Color \| Collapse controls \| Duplicate \| Hide & Mute Track \| Delete \| Bounce track |
| C-109 | **FAIL** | `Rename track` focuses the inline field (✓) but leaves the caret at the end (`selectionStart=5`, `selectionEnd=5`, length 5) — the current name is **not** selected as the row requires. Enter/Escape/blur all behave. — `C-109.png` |
| C-110 | **PASS** | 5 swatches in order; choosing one applied #a78bfa and closed the menu |
| C-111 | **PASS** | label flips to "Expand controls"; sliders 0 → 1 |
| C-112 | **PASS** | track count 3 → 4; copy "Drums blurred copy" carries 2 clips (their stored trackId still points at "t-drums" — ownership is by clipIds) |
| C-113 | **PASS** | track leaves the list (4 → 3); pill "2 hidden tracks"; stored hidden+muted |
| C-114 | **PASS** | Bass and its clip removed (3 → 2 tracks) |
| C-115 | **PASS** | clip-less track: disabled, title="This track has no clips to bounce" |
| C-116 | **PASS** | sawBouncing=0; toast "Bounce on Drums blurred added as a new track."; clips 6 → 7 |
| C-117 | **PASS** | menu "Add a track" = Audio A \| MIDI M \| Upload U |
| C-118 | **PASS** | Audio row appended (3 → 4); "A" appended again (→ 5) |
| C-119 | **PASS** | MIDI row appended a track (5 → 6), last = "MIDI 8" |
| C-120 | **PASS** | library opened on the Upload actions toolbar ("Filter New In Project Stems"); no track added |
| C-121 | **PASS** | Escape and outside click close it; after a scroll it is still open |
| C-122 | **PASS** | pill "2 hidden tracks"; popover with 2 row(s) |
| C-123 | **PASS** | Scratch returned to the track list; hidden rows now 1 |
| C-124 | **PASS** | label Unmute → Mute; the track stays hidden |
| C-125 | **PASS** | Unmute all cleared muted on 2 hidden track(s) without showing them |
| C-126 | **PASS** | every hidden track returned; the pill disappeared |
| C-127 | **PASS** | Escape closed the hidden-tracks popover |
| C-128 | **PASS** | group row A with a level slider (1); member labels = 2 |
| C-129 | **PASS** | group A level stored = 40; Vox's own fader still 82 |
| C-130 | **FAIL** | Clicking the group chip leaves `aria-pressed=false`: only the last member collapses. `groupsInUse` iterates `members.forEach(track => onUpdateTrack(track.id, {collapsed: next}))`, and `updateTrack` builds `tracks.map(...)` from the render's `tracks` snapshot (`StudioEditorShell.tsx:2544`), so each call overwrites the previous one. — `C-130.png` |
| C-131 | **PASS** | menu "Export options" open; button aria-expanded=true and shows the pressed class |
| C-132 | **PASS** | rows = Full Song \| Selected Time Range \| Multitrack \| WAV \| MP3 \| Normalise mix to −1 dBFS \| Project (JSON) |
| C-133 | **PASS** | no range and no loop range: Selected Time Range disabled |
| C-134 | **PASS** | with a range the row is enabled |
| C-135 | **PASS** | aria-checked moved to MP3 (WAV=false); the next export encodes MP3 |
| C-136 | **PASS** | Normalise toggled to aria-checked=true with a leading ✓ ("✓ Normalise mix to −1 dBFS") |
| C-137 | **PASS** | Full Song downloaded "W5C C7.mp3" |
| C-138 | **PASS** | Project (JSON) downloaded "W5C C7.json" with data.lanes=5 and data.tracks=4 |
| C-139 | **PASS** | 3 rows: Keyboard Shortcuts shift ? \| Learning Center \| What's This? Off; no YouTube row |
| C-140 | **PASS** | dialog with search + 5 groups: Playback / Tracks / Editing / View / Project |
| C-141 | **PASS** | 3 filtered row(s): Zoom the roll in / out MIDI editor · Ctrl/⌘ + = / − \| Zoom to the selected notes MIDI editor · Z \| Zoom in / out Ctrl/⌘ + + / − |
| C-142 | **PASS** | ? opened the shortcut dialog with the search focused |
| C-143 | **PASS** | typing "?" into the rename field inserted it and opened no dialog (value="W5C C8?") |
| C-144 | **PASS** | 5 numbered steps (Start an arrangement / Create a part / Shape the sound / Edit the timeline / Save and mirror) + Close |
| C-145 | **PASS** | row reads "What's This? Off"; hovering the tempo shows no card |
| C-146 | **PASS** | card "Tempo Sets the song's BPM. Bar width on the canvas follows it, so clips keep their musical position when you change it."; hidden on leave; page scrollable=false (the editor shell is height:100dvh/overflow:hidden, so the scroll dismissal cannot be exercised here) |
| C-147 | **PASS** | Undo and Redo both disabled at load |
| C-148 | **PASS** | undo/redo states tracked the stack (edit → undo → redo) |
| C-149 | **PASS** | parked 00:08.000 → song start 00:04.000 → beat 1 00:00.000 |
| C-150 | **PASS** | no armed track: disabled, title="Arm a track first" |
| C-151 | **PASS** | armed + Record → "Stop recording" aria-pressed=true; clock 00:00.008 → 00:01.541 |
| C-152 | **PASS** | "System default" + 3 device row(s) + "Count-in (1 bar)" (Escape does not close this menu) |
| C-153 | **PASS** | status "Count-in 1" appears and Record is disabled during the count (true) |
| C-154 | **PASS** | Stop froze the transport at 00:02.696 |
| C-155 | **PASS** | Play ↔ Pause swapped; meter samples -inf dB pk → -27.0 dB pk → -26.7 dB pk → -26.6 dB pk → -39.7 dB pk |
| C-156 | **PASS** | aria-pressed false → true; loop band covers the first four bars (0–8s) |
| C-157 | **PASS** | label "Metronome (click track)" → "Metronome (click track) — beat 1" (data-beat=1) |
| C-158 | **PASS** | 999 → 300, 5 → 20; project saved bpm=20 |
| C-159 | **PASS** | 2/4,3/4,4/4,6/8; chose 4/4, saved; 0 bar labels re-drawn |
| C-160 | **PASS** | cycle 1× → 0.5× → 2× → 1× |
| C-161 | **PASS** | no track selected: Plugins and Automation disabled, Clip editor enabled |
| C-162 | **PASS** | with Drums selected the bottom panel opened "Plugins for Drums" |
| C-163 | **PASS** | automation band opened: "Drums Volume Pan Clear Click to add a volume point - ←/→ and ↑/↓ nudge the selected one, d" |
| C-164 | **PASS** | toast "Select a clip to edit." |
| C-165 | **PASS** | MIDI clip → MIDI editor; audio clip → Clip Settings (warp) editor |
| C-166 | **PASS** | take-lane band opened; automation band closed (0) |
| C-167 | **PASS** | empty state "Add master effect"; with effects chips = Limiter + compact + |
| C-168 | **PASS** | ruler widths 11520 → in 17280 → out 7680 → fit 23040 (bars 0) |
| C-169 | **PASS** | All projects → http://127.0.0.1:3105/studio |
| C-170 | **PASS** | 3 radios (Vocals + instrumental (12 credits) \| Core stems (12 credits) \| Full 12-stem split (60 credits)); cost shown = yes |
| C-171 | **PASS** | default selection = Core stems ("Core stems (12 credits)") |
| C-172 | **PASS** | dialog closed; tracks 3 → 6 (Vocals, Drums, Bass); .se-stem-status rendered = false |
| C-173 | **PASS** | Cancel closed the stems dialog |
| C-174 | **PASS** | dialog with one text field + "Generate cover"; credit note = shown (G-11) |
| C-175 | **PASS** | Vocals dialog (action 1) and Instrumental dialog (action 1) opened with their own copy |
| C-176 | **PASS** | 5 clips selected (2 with a source generation) → Mashup enabled; dialog action count 1 |
| C-177 | **PASS** | dialog with a lyrics textarea, optional Persona select and the Replace section action (1) |
| C-178 | **PASS** | notice = "That edit did not run The operation failed before anything was placed. Replace section needs lyrics." |
| C-179 | **PASS** | persona created and listed in #se-persona-select: No persona,W5C Persona,Voice check 26489 |
| C-180 | **PASS** | Escape and Cancel closed both dialogs; 0 generation requests issued |
| C-181 | **PASS** | 10 plugin rows + Cancel; Cancel closed the dialog |
| C-182 | **PASS** | dialog "Suno has newer changes" with 4 actions: Decide later / Duplicate locally / Keep mine / Load Suno version |
| C-183 | **PASS** | Decide later closed the prompt; sync state still conflict |
| C-184 | **PASS** | Keep mine closed the dialog; sync dot synced → synced (synced after the push) |
| C-185 | **PASS** | two-tab write produced "This project changed in another tab. This project changed since you loaded it. Reload before saving. Reload theirs Keep mine" |
| C-186 | **PASS** | Reload theirs cleared the banner; save chip = "Saved" |
| C-187 | **PASS** | eyebrow "Camxora Studio", h1 "Your projects", sub "Pick up where you left off, or start a new arrangement.", actions "Create a song New project" |
| C-188 | **PASS** | resume block for "W5C Home Pinned ZTN2" with Open project (53 cards in the grid) |
| C-189 | **PASS** | search filtered to "W5C Home Alpha ZTN2"; no-match state "No projects match “zzzz-no-such-project”" + Clear search; clearing restored 53 cards |
| C-190 | **PASS** | Archived toggle revealed 1 archived card(s): W5C Home Archived ZTN2 |
| C-191 | **PASS** | pinned block leads both modes (8 card(s), incl. W5C Home Pinned ZTN2); 42 others sort alphabetically under Title |
| C-192 | **PASS** | card menu = Open \| Rename \| Duplicate \| Pin \| Archive \| Delete |
| C-193 | **PASS** | prefilled, Save disabled while empty, Enter saved the new title |
| C-194 | **PASS** | confirm dialog explains Recently Deleted; Keep project cancels; Delete removed the card |
| C-195 | **PASS** | the home deletion is listed in the editor's Recently Deleted tab and is restorable |
| C-196 | **FAIL** | 0 `.studio-sync-dot` on the home cards. The list payload from `GET /studio/projects` has no `sync` object at all (checked through the API: `sync` absent on every item), and `StudioHome.tsx:412` renders the dot only `project.sync ? …`. The five mirror states are therefore unreachable from My Projects. — `C-196.png` |
| C-197 | **PASS** | signed out: brand "CAMXORA", badge "Read-only Studio share", "W5C Shared Song", "120 BPM · 4/4 · 5 tracks", duration 0:12 |
| C-198 | **PASS** | 5 lane rows, 5 clips positioned in % (0%/33.3333%, 66.6667%/33.3333%, 0%/66.6667%); editable fields outside the comment form = 2 |
| C-199 | **PASS** | comment at the top by W5C Guest (11/17/2026, 1:21:05 PM); textarea cleared |
| C-200 | **PASS** | banner "Replying to W5C Guest Cancel"; the reply nested under the comment; Cancel cleared the banner |
| C-201 | **PASS** | Post is disabled for an empty or whitespace-only body |
| C-202 | **PASS** | no-comments note = "No comments yet." |
| C-203 | **PASS** | signed out "Sign in to fork Create your own"; signed in "Fork to Studio Create your own"; fork opened a copy ("W5C Shared Quiet (shared copy)") |
| C-204 | **PASS** | "Project unavailable": "Shared Studio project not found or expired." |
| C-205 | **PASS** | overlay "How do you want to start?" with 5 tiles |
| C-206 | **PASS** | tiles in order = Edit Your Song \| Upload Audio \| Create a song \| Open a project \| Empty Project |
| C-207 | **PASS** | overlay closed; library opened (active "undefined") |
| C-208 | **PASS** | overlay closed; library opened on Uploads (Library Filter New In Project Stems Loading uploads……) |
| C-209 | **PASS** | Start empty closed it; studio:onboarded:68435be8… = "1"; absent after reload |
| C-210 | **PASS** | Show Quick Start again re-opened the overlay after it had been dismissed |