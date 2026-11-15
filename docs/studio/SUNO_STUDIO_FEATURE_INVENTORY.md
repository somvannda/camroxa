# SUNO STUDIO FEATURE INVENTORY

Reconciled 2026-11-15 against origin/main 274b27e8 — see CLONE_DEFINITION.md for the gate.

Every feature that has been **observed** in the reference or **is required** for the
workflow it implies. IDs are permanent; never renumber, only add.

- `Ref` — evidence tag (`B` bundle, `H` help, `L` live, `P` prior capture, `?` unknown).
- `Ref loc.` — where it appears in the reference.
- `Ours` — Camxora status in the **web Studio** (`camxora.com/components/studio`,
  `camxora.com/app/studio`), scored at `origin/main 274b27e8`.
- Feature-level requirements/acceptance live in
  `SUNO_STUDIO_INTERACTION_SPECIFICATION.md`; status/coverage lives in
  `SUNO_STUDIO_FEATURE_MATRIX.md`.

Legend for `Ours`: ✅ implemented · ◐ partial (reason given in the row) · ✗ absent ·
N/A deliberate divergence.

✅ means the surface ships in the web Studio; it collapses the old `IMP`/`TST`/`VER`
grades, which still apply per row in `README.md`'s vocabulary (a ✅ row is *implemented*,
not necessarily *verified*). The old `—` ("not started") is now `✗`, so any row that
still reads `—` in the `Ours` column is a documentation bug. **No row is `✗` at this
commit**: every captured feature is either shipped (`✅`), shipped with a named gap
(`◐`), or a recorded decision not to copy it (`N/A`). Where a feature ships only in the
legacy `/studio/editor/classic` editor, the row says so.

---

## 1. Application shell & navigation (`APP`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| APP-001 | Studio landing with resume card for the last project | H P | `/studio` | ✅ resume card opens the most recently edited project |
| APP-002 | Recent projects list on the landing | H P | `/studio` left column | ✅ the landing grid *is* the project list, newest first |
| APP-003 | "New empty project" creation from the landing | H P | `/studio` | ✅ `New project` |
| APP-004 | "See all projects" list view | H P | `/studio` | ◐ home lists the newest 50 with search/sort; the full S04 `My Projects` dialog (Projects / Recently Deleted tabs) lives in the editor and there is no paging past 50 on home |
| APP-005 | Start-from-a-song column with search | H P | `/studio` right column | ◐ `Start from a song` section ships with the six most recent seedable songs; no search inside it |
| APP-006 | Song row metadata: title, style summary, length | H P | `/studio` right column | ✅ title, style summary, `m:ss` |
| APP-007 | "Edit in Studio" per song (creates/opens a project seeded with that clip) | B P | song row menu | ✅ the whole song card is the action and creates a new project seeded with the clip; there is no per-song overflow menu on the home |
| APP-008 | Project switcher in the editor header | H P | editor header | ✅ |
| APP-009 | Undo / redo in header, mirrored by shortcuts | H | editor header | ✅ |
| APP-010 | Project title with inline rename | B P | editor header | ✅ |
| APP-011 | Project overflow menu (rename, versions, share, duplicate, archive, delete) | B H | editor header | ✅ nine captured items in captured order |
| APP-012 | Export entry point in header | B H | editor header | ✅ |
| APP-013 | Library drawer toggle | H | editor header | ✅ |
| APP-014 | Inspector toggle | H | editor | ✅ clip-info rail |
| APP-015 | Mixer toggle | H | editor | N/A the reference has no mixer surface at all (S47 negative capture); our master dock is additive |
| APP-016 | Signed-out gate (no editor without a session) | H | `/studio/*` | ✅ |
| APP-017 | Standalone editor layout (no marketing chrome) | H | `/studio` | ✅ |
| APP-018 | Responsive behaviour for narrow viewports | H | all | ◐ home and library are responsive; the editor is desktop-only — `.se-shell` is hidden under 768 px behind a desktop gate |
| APP-019 | Loading skeleton for a project being fetched | H | editor | ✅ |
| APP-020 | Fatal-error state when a project cannot load | H | editor | ✅ |

## 2. Music generation (`GEN`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| GEN-001 | Text prompt → generate into the timeline at the playhead | B H | prompt bar | ✅ |
| GEN-002 | Prompt bar placement hint when no position is selected | H | prompt bar | ✅ |
| GEN-003 | Model selector on the prompt bar | H | prompt bar | ✅ `se-prompt-model` menu |
| GEN-004 | Attach reference audio to a prompt | H | prompt bar `+` | ◐ the `+` menu attaches a project track or clip as context; an arbitrary uploaded reference file cannot be attached to a prompt |
| GEN-005 | Lyrics input (write) for generation | H P | advanced create | N/A the Create page owns lyrics |
| GEN-006 | Lyrics prompt/auto-generate | H P | advanced create | N/A the Create page owns lyrics |
| GEN-007 | Instrumental toggle | H P | create options | N/A the Create page owns the instrumental toggle |
| GEN-008 | Style / exclude-style descriptors | H P | create options | N/A the Create page owns style/exclude |
| GEN-009 | Vocal gender / weirdness / style influence / variety controls | H P | more options | N/A the Create page owns the generation options |
| GEN-010 | Generation job progress in the editor | B | clip placeholder | ✅ |
| GEN-011 | Generation failure surfaced with the provider message | B | clip placeholder | ✅ |
| GEN-012 | Credit cost shown before a paid action | B | prompt bar / dialogs | ✅ |
| GEN-013 | "Not enough credits" path with purchase CTA | B | dialogs | ✅ |
| GEN-014 | Add vocals to an existing clip | B | clip actions | ✅ clip menu `Vocals…` |
| GEN-015 | Add instrumental to an existing clip | B | clip actions | ✅ clip menu `Instrumental…` |
| GEN-016 | Cover (re-sing) an existing clip | B | clip actions | ✅ clip menu `Cover…` |
| GEN-017 | Extend a clip from a point | B | clip actions | ✅ clip menu `Extend` |
| GEN-018 | Replace a section by time range + lyrics | B | clip actions | ✅ clip menu `Replace…` behind the ruler range |
| GEN-019 | Remaster a clip | B | clip actions | ✅ clip menu `Remaster` |
| GEN-020 | Mashup of two clips | B | clip actions | ✅ clip menu `Mashup…` with two selected clips |
| GEN-021 | Cover-art generation for a clip | B | clip actions | ✅ classic editor rail (`/studio/editor/classic`); the reference-layout clip info rail shows artwork but does not generate it |
| GEN-022 | Extend an uploaded audio file | B | uploads / clip actions | ✅ |
| GEN-023 | Cover an uploaded audio file | B | uploads / clip actions | ✅ |
| GEN-024 | Studio AI natural-language edit command | H | footer prompt | ✅ |
| GEN-025 | Persona creation from a clip's vocal | B | inspector | ✅ |
| GEN-026 | Persona reuse when replacing a section | B | replace-section | ✅ |
| GEN-027 | Generation history for a project | H | project menu | ◐ each clip carries a provenance strip (source song, model, date, style); there is no project-wide generation history list |

## 3. Transport & player (`PLY`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| PLY-001 | Play / pause | H | transport | ✅ |
| PLY-002 | Space toggles playback | H | global | ✅ |
| PLY-003 | Go to start | H | transport | ✅ |
| PLY-004 | Go to end | H | transport | ✅ |
| PLY-005 | Seek by clicking the ruler | H | ruler | ✅ |
| PLY-006 | Seek by clicking a lane | H | lanes | ✅ |
| PLY-007 | Draggable playhead | H | ruler | ✅ |
| PLY-008 | Arrow-key nudge of the playhead | H | global | ✅ |
| PLY-009 | Time readout (mm:ss.mmm) | H | transport | ✅ |
| PLY-010 | Bar.beat readout | H | transport | ✅ |
| PLY-011 | BPM display and edit | H | transport | ✅ |
| PLY-012 | Time-signature display | H | transport | ✅ editable 2/4, 3/4, 4/4, 6/8 |
| PLY-013 | Metronome with downbeat accent | H | transport | ✅ audible click, bar accent |
| PLY-014 | Loop region with start/end | H | transport | ✅ |
| PLY-015 | Follow playhead while scrolling | H | timeline | ✅ |
| PLY-016 | Multi-clip scheduling with per-clip gain | — | engine | ✅ |
| PLY-017 | Playback continues while editing | H | engine | ✅ |
| PLY-018 | Playback of uploaded/imported audio | H | engine | ✅ |
| PLY-019 | Silence-with-reason for unplayable clips | — | clip | ✅ |
| PLY-020 | Playback speed control | H | transport | ✅ header cycles 1× / 0.5× / 2× |
| PLY-021 | Queue / continuous play across projects | H | player | N/A single-project editor |

## 4. Arrangement & clip editing (`ARR`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| ARR-001 | Multitrack timeline with one lane per track | H | timeline | ✅ |
| ARR-002 | Bar ruler with bar numbers and ticks | H | timeline | ✅ |
| ARR-003 | Grid lines at bar/beat subdivisions | H | timeline | ✅ |
| ARR-004 | Zoom in/out of the timeline | H | footer / ruler | ✅ |
| ARR-005 | Horizontal scroll keeping track headers aligned | H | timeline | ✅ |
| ARR-006 | Clip block with title and colour | H | clip | ✅ |
| ARR-007 | Clip waveform rendering from decoded audio | H | clip | ✅ |
| ARR-008 | Clip drag along a lane | H | clip | ✅ |
| ARR-009 | Clip drag across lanes | H | clip | ✅ |
| ARR-010 | Clip trim (start/end) with handles | H | clip | ✅ |
| ARR-011 | Clip split at playhead | H | clip menu | ✅ Ctrl E / clip menu |
| ARR-012 | Clip duplicate | H | clip menu | ✅ |
| ARR-013 | Clip delete | H | clip menu / Delete | ✅ |
| ARR-014 | Clip copy/paste | H | clip menu | ✅ Ctrl C / Ctrl V, multi-clip aware |
| ARR-015 | Clip reverse | B | clip menu | ✅ |
| ARR-016 | Clip fades (in/out) | B | inspector | ✅ fade handle + Shift F |
| ARR-017 | Clip speed / time-stretch with pitch preservation | B | inspector | ✅ |
| ARR-018 | Clip volume | B | inspector | ✅ |
| ARR-019 | Clip pan | B | inspector | ✅ |
| ARR-020 | Clip colour | H | clip menu | ✅ |
| ARR-021 | Alternate takes per clip | B | inspector | ✅ |
| ARR-022 | Snap to grid (toggle) | H | footer | ✅ |
| ARR-023 | Signal-chain / clip context menu | H | clip | ✅ |
| ARR-024 | Multi-select clips | H | timeline | ✅ Ctrl/Shift click and marquee |
| ARR-025 | Selection box (marquee) | H | timeline | ✅ empty-lane drag |
| ARR-026 | Section markers (verse/chorus) | H | timeline | ✅ |
| ARR-027 | Track groups (A–D) with collapse and group mix | H | track panel | ✅ membership, submix level, control collapse |
| ARR-028 | Drag a clip from the library onto a lane at the drop position | H | library drawer | ✅ |
| ARR-029 | Undo / redo across arrangement edits | H | header | ✅ |
| ARR-030 | Undo depth bounded and predictable | — | history | ✅ 50-document history |
| ARR-031 | Virtualised rendering for very long projects | — | timeline | ✅ clips culled to the visible window plus one screen of slack |

## 5. Tracks & mixer (`TRK`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| TRK-001 | Add audio track | H | track panel | ✅ |
| TRK-002 | Add MIDI track | H | track panel | ✅ creates a four-bar clip and opens the piano roll |
| TRK-003 | Import audio file as a track | H | track panel | ✅ |
| TRK-004 | Import MIDI file as a track | H | track panel | ✅ Standard MIDI File import into the open MIDI clip |
| TRK-005 | Record (arm + capture) | H | track panel | ✅ `MediaRecorder` take with input picker and opt-in count-in |
| TRK-006 | Track name (rename) | H | track row | ✅ |
| TRK-007 | Track reorder (up/down) | H | track menu | ✅ |
| TRK-008 | Track duplicate | H | track menu | ✅ |
| TRK-009 | Track delete with confirm | H | track menu | ✅ |
| TRK-010 | Track colour | H | track menu | ✅ |
| TRK-011 | Track volume fader | H | track row | ✅ |
| TRK-012 | Track pan knob (stereo panner) | H | track row | ✅ |
| TRK-013 | Track mute | H | track row | ✅ persisted, live on the running graph |
| TRK-014 | Track solo | H | track row | ✅ solo-aware playback and bounce |
| TRK-015 | Track level meter | H | track row / mixer | ✅ |
| TRK-016 | Track EQ (low/mid/high) | H | inspector | ✅ |
| TRK-017 | Track filter (cutoff/resonance) | H | inspector | ✅ |
| TRK-018 | FX sends: delay, reverb, chorus | H | inspector | ✅ shared Delay and Reverb send buses (playback + export) |
| TRK-019 | Dynamics: compression, drive, duck | H | inspector | ✅ |
| TRK-020 | Plugin presets (save/apply) | H | inspector | ✅ |
| TRK-021 | Volume automation lane | H | inspector | ✅ |
| TRK-022 | Pan automation lane | H | inspector | ✅ |
| TRK-023 | Copy / paste mix settings between tracks | H | track menu | N/A never evidenced in the reference (STUDIO_VS_SUNO_3COL §14.1); the clip menu copies *clip* settings instead |
| TRK-024 | Reset mix | H | track menu | N/A never evidenced in the reference; the classic editor's reset is not carried into the shell |
| TRK-025 | Master fader | H | footer / mixer | ✅ persisted volume + mute, live and in mix/range exports |
| TRK-026 | Master EQ + reset | H | mixer | ✅ master dock |
| TRK-027 | Master compression / drive | H | mixer | ✅ |
| TRK-028 | Master spectrum analyser | H | mixer | ✅ 32-band canvas driven by the master analyser |
| TRK-029 | Master true-peak / loudness readout | H | mixer | ◐ sample peak + RMS + a 4× inter-sample estimate in the header; no BS.1770 integrated loudness (LUFS) |
| TRK-030 | Track collaborator avatars | H | track row | ✅ presence avatars + remote cursors |

## 6. MIDI (`MIDI`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| MIDI-001 | Piano-roll editor per MIDI clip | H | inspector | ✅ bottom sheet: piano gutter, note grid, velocity/pitch-bend/modulation tabs |
| MIDI-002 | Draw / move / resize notes | H | piano roll | ✅ |
| MIDI-003 | Note length and velocity editing | H | piano roll | ✅ |
| MIDI-004 | Note delete | H | piano roll | ✅ double-click or Delete |
| MIDI-005 | Quantize | H | piano roll | ✅ `Shift Q` on the selection |
| MIDI-006 | Octave up/down and transpose | H | piano roll | ✅ `Shift ↑/↓`, byte-identical to the capture's key map |
| MIDI-007 | On-screen playable keyboard | H | footer | ✅ |
| MIDI-008 | Computer-keyboard musical typing | H | global | ✅ |
| MIDI-009 | Web MIDI device input | H | footer | ✅ |
| MIDI-010 | MIDI rendered to audio for playback/export | — | engine | ✅ synth voices feed the same per-track input as audio |
| MIDI-011 | MIDI file import/export | H | project menu | ✅ `Download MIDI` (format-0 SMF, PPQ 480) and `Import MIDI` |
| MIDI-012 | Arpeggiator / chord mode | H | footer | ✅ `Chord mode` off/major/minor and `Arpeggiator` off/up/down in the piano-roll toolbar |

## 7. Advanced audio (`ADV`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| ADV-001 | Separate stems (2-stem) | B | clip actions | ✅ `Get Stems` dialog picks the depth |
| ADV-002 | Separate stems (multi-stem) | B | clip actions | ✅ |
| ADV-003 | Place separated stems on new tracks | B | clip actions | ✅ |
| ADV-004 | Stem cost from the pricing table | — | dialog | ✅ |
| ADV-005 | Lyrics view for a clip (with timings) | B | inspector | ✅ |
| ADV-006 | Export full mix | B H | export menu | ✅ Full Song |
| ADV-007 | Export selected range | B H | export menu | ✅ Selected Time Range |
| ADV-008 | Export multitrack/stems | B H | export menu | ✅ Multitrack |
| ADV-009 | Export per-track WAV | H | export menu | ✅ one file per track at unity so balance survives |
| ADV-010 | Export project JSON | H | project menu | ✅ round-trips the arrangement |
| ADV-011 | Import project JSON | H | project menu | ✅ `Import project.` validates lanes/tracks first |
| ADV-012 | MP3 encode for export | H | export | ✅ bundled LAME encoder after the offline render |
| ADV-013 | WAV encode for export | H | export | ✅ 16-bit PCM |
| ADV-014 | Mixdown respects master chain | — | engine | ✅ |
| ADV-015 | Export progress + cancel | H | export | ✅ |
| ADV-016 | Render moderation error surfaced | B | export | ✅ |
| ADV-017 | Mastering presets | H | mixer | ✅ Default / Clean / Warm / Loud on the master dock |
| ADV-018 | Loudness normalisation on export | — | export | ◐ optional gain match of mix/range to a −1 dBFS **sample peak** (D-010); it is not LUFS normalisation |

## 8. Projects, library & sharing (`PRJ`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| PRJ-001 | List own projects with search | B | editor dialog / landing | ✅ |
| PRJ-002 | Sort projects (recent/title) | H | landing | ✅ `Sort: Last edited / Title` |
| PRJ-003 | Pin project | B | project dialog | ✅ |
| PRJ-004 | Archive / restore project | B | project dialog | ✅ |
| PRJ-005 | Tags on a project | B | project dialog | ✅ home search matches tags |
| PRJ-006 | Fork / duplicate project | B | project menu | ✅ |
| PRJ-007 | Delete project with confirm | B | project menu | ✅ soft delete (`deleted_at`) with a `Recently Deleted` tab and Restore |
| PRJ-008 | Version history list | B H | project menu | ✅ left `History` panel, automatic entries grouped by date |
| PRJ-009 | Save named version | B H | project menu | ✅ |
| PRJ-010 | Restore a version | B H | project menu | ✅ |
| PRJ-011 | Share link (view/edit, expiry) | B H | share dialog | ✅ view-and-copy link, 7-day expiry |
| PRJ-012 | Revoke share link | B H | share dialog | ✅ |
| PRJ-013 | Open shared project read-only | B | `/studio/shared/[token]` | ✅ without an account |
| PRJ-014 | Edit a shared project with permission | B | shared route | ◐ the share token carries a `view`/`edit` permission and the page polls for updates, but the surface itself is a read-only view: editing means forking a copy (matching the captured share dialog, which is view-and-copy, not live collaboration) |
| PRJ-015 | Fork a shared project into your account | B | shared route | ✅ forks into its own copy |
| PRJ-016 | Comments on a shared project | B | shared route | ✅ threaded, with replies |
| PRJ-017 | Presence (who is here, playhead) | H | shared route | ✅ avatars in the editor header |
| PRJ-018 | Live update polling for collaborators | H | shared route | ✅ |
| PRJ-019 | Project comments from the owner's editor | B | project menu | ✅ the clip info rail carries the captured S55 `Comments and notes` section — flat, anonymous, authorless notes on that clip (`Write a comment`) |
| PRJ-020 | Library drawer: own songs | H | drawer | ✅ `All Songs` tile |
| PRJ-021 | Library drawer: liked songs | H | drawer | ✅ `Liked` tile filters the viewer's liked clips |
| PRJ-022 | Library drawer: uploads | H | drawer | ✅ `Uploads` tile + `Uploads` toolbar chip |
| PRJ-023 | Library drawer: stems | H | drawer | ✅ `Stems` tile reads `GET /studio/stems` |
| PRJ-024 | Library drawer: projects tab | H | drawer | ✅ `Studio Projects` section with `See all ›` |
| PRJ-025 | Library search | H | drawer | ✅ |
| PRJ-026 | Library filters | H | drawer | ✅ `Liked only / New / In Project / Stems / Uploads` chips |
| PRJ-027 | Upload audio into the project | B | track panel | ✅ |
| PRJ-028 | Storage of uploads with duration | — | API | ✅ |

## 9. UX, states, accessibility (`UX`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| UX-001 | Hover affordances on every interactive element | H | all | ✅ |
| UX-002 | Visible focus ring for keyboard users | H | all | ✅ |
| UX-003 | Context menus via right-click | H | clips/tracks | ✅ |
| UX-004 | Drag ghost while dragging a clip | H | timeline | ✅ |
| UX-005 | Snap guideline while dragging | H | timeline | ✅ `.se-snap-line` while a drag is snapped |
| UX-006 | Toast feedback for save/add/delete | H | all | ✅ |
| UX-007 | Autosave indicator | H | header | ✅ four save states |
| UX-008 | Destructive-action confirmation | H | delete paths | ✅ |
| UX-009 | Empty state: no tracks | H | editor | ✅ |
| UX-010 | Empty state: no projects | H | landing/dialog | ✅ |
| UX-011 | Empty state: no search results | H | dialog | ✅ |
| UX-012 | Network error with retry | H | all | ✅ |
| UX-013 | Reduced-motion support | H | all | ✅ `prefers-reduced-motion` disables the studio transitions and animations |
| UX-014 | Screen-reader labels on icon buttons | H | all | ✅ |
| UX-015 | Contrast ≥ 4.5:1 on text | H | tokens | ✅ axe-clean on `/studio` and the editor |
| UX-016 | Touch targets ≥ 44 px | H | editor | ✅ coarse pointers get 44×44 hit plates |
| UX-017 | Keyboard shortcut help | H | footer | ✅ Learn → Keyboard Shortcuts, `?` |
| UX-018 | First-run onboarding | H | editor | ✅ empty projects open a start overlay, remembered per project |
| UX-019 | Unsaved-changes guard | H | navigation | ✅ `beforeunload` while a save is pending, failed or offline |
| UX-020 | Offline draft recovery | — | editor | ✅ draft stored on failure and offered on reopen, replayed when online |
| UX-021 | Learn menu (Keyboard Shortcuts · YouTube Tutorials · Learning Center · What's This?) | H | footer | ◐ three of the four captured rows ship; **YouTube Tutorials is dropped by product decision** (CLONE_DEFINITION.md §5) |

## 10. Backend & integration (`BE`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| BE-001 | Project CRUD API scoped to the owner | B | `/v1/studio/projects` | ✅ |
| BE-002 | Versioned project documents | B | `studio_project_versions` | ✅ |
| BE-003 | Share tokens with permission + expiry | B | `studio_project_shares` | ✅ |
| BE-004 | Comments API | B | `studio_share_comments` | ✅ |
| BE-005 | Presence API | — | shares/presence | ✅ |
| BE-006 | Uploads API with duration | — | `/studio/uploads` | ✅ |
| BE-007 | Generation operations API (stems/extend/cover/…) | B | `/studio/generations/*` | ✅ |
| BE-008 | Operation status polling | B | `/studio/operations/:id` | ✅ |
| BE-009 | Credits charged from `pricing`, never hardcoded | — | pricing table | ✅ |
| BE-010 | Provider isolation behind an adapter | — | `suno.ts` / provider layer | ✅ |
| BE-011 | Rate limiting and retry on provider calls | — | limiter/queue | ✅ |
| BE-012 | Audit trail for paid Studio actions | — | operations table | ✅ |
| BE-013 | Error envelope compatible with the web client | — | `error.message` | ✅ |
| BE-014 | Studio API contract tests | — | — | ✅ `camxora.com/tests/studio-api.test.ts` (version field, 409 mapping, error message, 204) |
