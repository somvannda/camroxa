# SUNO STUDIO FEATURE INVENTORY

Every feature that has been **observed** in the reference or **is required** for the
workflow it implies. IDs are permanent; never renumber, only add.

- `Ref` — evidence tag (`B` bundle, `H` help, `L` live, `P` prior capture, `?` unknown).
- `Ref loc.` — where it appears in the reference.
- `Ours` — Camxora status (see vocabulary in `README.md`).
- Feature-level requirements/acceptance live in
  `SUNO_STUDIO_INTERACTION_SPECIFICATION.md`; status/coverage lives in
  `SUNO_STUDIO_FEATURE_MATRIX.md`.

Legend for `Ours`: `—` not started · `IMP` implemented (typechecks, not verified) ·
`TST` testing · `VER` verified · `BLK` blocked · `N/A` deliberate.

---

## 1. Application shell & navigation (`APP`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| APP-001 | Studio landing with resume card for the last project | H P | `/studio` | — |
| APP-002 | Recent projects list on the landing | H P | `/studio` left column | — |
| APP-003 | "New empty project" creation from the landing | H P | `/studio` | — |
| APP-004 | "See all projects" list view | H P | `/studio` | — |
| APP-005 | Start-from-a-song column with search | H P | `/studio` right column | — |
| APP-006 | Song row metadata: title, style summary, length | H P | `/studio` right column | — |
| APP-007 | "Edit in Studio" per song (creates/opens a project seeded with that clip) | B P | song row menu | — |
| APP-008 | Project switcher in the editor header | H P | editor header | IMP |
| APP-009 | Undo / redo in header, mirrored by shortcuts | H | editor header | IMP |
| APP-010 | Project title with inline rename | B P | editor header | IMP |
| APP-011 | Project overflow menu (rename, versions, share, duplicate, archive, delete) | B H | editor header | IMP |
| APP-012 | Export entry point in header | B H | editor header | IMP |
| APP-013 | Library drawer toggle | H | editor header | IMP |
| APP-014 | Inspector toggle | H | editor | IMP |
| APP-015 | Mixer toggle | H | editor | IMP |
| APP-016 | Signed-out gate (no editor without a session) | H | `/studio/*` | IMP |
| APP-017 | Standalone editor layout (no marketing chrome) | H | `/studio` | IMP |
| APP-018 | Responsive behaviour for narrow viewports | H | all | — |
| APP-019 | Loading skeleton for a project being fetched | H | editor | IMP |
| APP-020 | Fatal-error state when a project cannot load | H | editor | IMP |

## 2. Music generation (`GEN`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| GEN-001 | Text prompt → generate into the timeline at the playhead | B H | prompt bar | IMP |
| GEN-002 | Prompt bar placement hint when no position is selected | H | prompt bar | IMP |
| GEN-003 | Model selector on the prompt bar | H | prompt bar | — |
| GEN-004 | Attach reference audio to a prompt | H | prompt bar `+` | — |
| GEN-005 | Lyrics input (write) for generation | H P | advanced create | — (Create page owns it) |
| GEN-006 | Lyrics prompt/auto-generate | H P | advanced create | — (Create page owns it) |
| GEN-007 | Instrumental toggle | H P | create options | — (Create page owns it) |
| GEN-008 | Style / exclude-style descriptors | H P | create options | — (Create page owns it) |
| GEN-009 | Vocal gender / weirdness / style influence / variety controls | H P | more options | — (Create page owns it) |
| GEN-010 | Generation job progress in the editor | B | clip placeholder | IMP |
| GEN-011 | Generation failure surfaced with the provider message | B | clip placeholder | IMP |
| GEN-012 | Credit cost shown before a paid action | B | prompt bar / dialogs | IMP |
| GEN-013 | "Not enough credits" path with purchase CTA | B | dialogs | IMP |
| GEN-014 | Add vocals to an existing clip | B | clip actions | IMP |
| GEN-015 | Add instrumental to an existing clip | B | clip actions | IMP |
| GEN-016 | Cover (re-sing) an existing clip | B | clip actions | IMP |
| GEN-017 | Extend a clip from a point | B | clip actions | IMP |
| GEN-018 | Replace a section by time range + lyrics | B | clip actions | IMP |
| GEN-019 | Remaster a clip | B | clip actions | IMP |
| GEN-020 | Mashup of two clips | B | clip actions | IMP |
| GEN-021 | Cover-art generation for a clip | B | clip actions | IMP |
| GEN-022 | Extend an uploaded audio file | B | uploads / clip actions | IMP |
| GEN-023 | Cover an uploaded audio file | B | uploads / clip actions | IMP |
| GEN-024 | Studio AI natural-language edit command | H | footer prompt | IMP |
| GEN-025 | Persona creation from a clip's vocal | B | inspector | IMP |
| GEN-026 | Persona reuse when replacing a section | B | replace-section | IMP |
| GEN-027 | Generation history for a project | H | project menu | — |

## 3. Transport & player (`PLY`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| PLY-001 | Play / pause | H | transport | IMP |
| PLY-002 | Space toggles playback | H | global | IMP |
| PLY-003 | Go to start | H | transport | IMP |
| PLY-004 | Go to end | H | transport | IMP |
| PLY-005 | Seek by clicking the ruler | H | ruler | IMP |
| PLY-006 | Seek by clicking a lane | H | lanes | IMP |
| PLY-007 | Draggable playhead | H | ruler | IMP |
| PLY-008 | Arrow-key nudge of the playhead | H | global | IMP |
| PLY-009 | Time readout (mm:ss.mmm) | H | transport | IMP |
| PLY-010 | Bar.beat readout | H | transport | IMP |
| PLY-011 | BPM display and edit | H | transport | IMP |
| PLY-012 | Time-signature display | H | transport | IMP |
| PLY-013 | Metronome with downbeat accent | H | transport | IMP |
| PLY-014 | Loop region with start/end | H | transport | IMP |
| PLY-015 | Follow playhead while scrolling | H | timeline | IMP |
| PLY-016 | Multi-clip scheduling with per-clip gain | — | engine | IMP |
| PLY-017 | Playback continues while editing | H | engine | IMP |
| PLY-018 | Playback of uploaded/imported audio | H | engine | IMP |
| PLY-019 | Silence-with-reason for unplayable clips | — | clip | IMP |
| PLY-020 | Playback speed control | H | transport | — |
| PLY-021 | Queue / continuous play across projects | H | player | N/A (single project) |

## 4. Arrangement & clip editing (`ARR`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| ARR-001 | Multitrack timeline with one lane per track | H | timeline | IMP |
| ARR-002 | Bar ruler with bar numbers and ticks | H | timeline | IMP |
| ARR-003 | Grid lines at bar/beat subdivisions | H | timeline | IMP |
| ARR-004 | Zoom in/out of the timeline | H | footer / ruler | IMP |
| ARR-005 | Horizontal scroll keeping track headers aligned | H | timeline | IMP |
| ARR-006 | Clip block with title and colour | H | clip | IMP |
| ARR-007 | Clip waveform rendering from decoded audio | H | clip | IMP |
| ARR-008 | Clip drag along a lane | H | clip | IMP |
| ARR-009 | Clip drag across lanes | H | clip | IMP |
| ARR-010 | Clip trim (start/end) with handles | H | clip | IMP |
| ARR-011 | Clip split at playhead | H | clip menu | IMP |
| ARR-012 | Clip duplicate | H | clip menu | IMP |
| ARR-013 | Clip delete | H | clip menu / Delete | IMP |
| ARR-014 | Clip copy/paste | H | clip menu | — |
| ARR-015 | Clip reverse | B | clip menu | IMP |
| ARR-016 | Clip fades (in/out) | B | inspector | IMP |
| ARR-017 | Clip speed / time-stretch with pitch preservation | B | inspector | IMP |
| ARR-018 | Clip volume | B | inspector | IMP |
| ARR-019 | Clip pan | B | inspector | IMP |
| ARR-020 | Clip colour | H | clip menu | IMP |
| ARR-021 | Alternate takes per clip | B | inspector | IMP |
| ARR-022 | Snap to grid (toggle) | H | footer | IMP |
| ARR-023 | Signal-chain / clip context menu | H | clip | IMP |
| ARR-024 | Multi-select clips | H | timeline | — |
| ARR-025 | Selection box (marquee) | H | timeline | — |
| ARR-026 | Section markers (verse/chorus) | H | timeline | IMP |
| ARR-027 | Track groups (A–D) with collapse and group mix | H | track panel | IMP |
| ARR-028 | Drag a clip from the library onto a lane at the drop position | H | library drawer | IMP |
| ARR-029 | Undo / redo across arrangement edits | H | header | IMP |
| ARR-030 | Undo depth bounded and predictable | — | history | IMP |
| ARR-031 | Virtualised rendering for very long projects | — | timeline | — |

## 5. Tracks & mixer (`TRK`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| TRK-001 | Add audio track | H | track panel | IMP |
| TRK-002 | Add MIDI track | H | track panel | IMP |
| TRK-003 | Import audio file as a track | H | track panel | IMP |
| TRK-004 | Import MIDI file as a track | H | track panel | IMP |
| TRK-005 | Record (arm + capture) | H | track panel | IMP |
| TRK-006 | Track name (rename) | H | track row | IMP |
| TRK-007 | Track reorder (up/down) | H | track menu | IMP |
| TRK-008 | Track duplicate | H | track menu | IMP |
| TRK-009 | Track delete with confirm | H | track menu | IMP |
| TRK-010 | Track colour | H | track menu | IMP |
| TRK-011 | Track volume fader | H | track row | IMP |
| TRK-012 | Track pan knob (stereo panner) | H | track row | IMP |
| TRK-013 | Track mute | H | track row | IMP |
| TRK-014 | Track solo | H | track row | IMP |
| TRK-015 | Track level meter | H | track row / mixer | IMP |
| TRK-016 | Track EQ (low/mid/high) | H | inspector | IMP |
| TRK-017 | Track filter (cutoff/resonance) | H | inspector | IMP |
| TRK-018 | FX sends: delay, reverb, chorus | H | inspector | IMP |
| TRK-019 | Dynamics: compression, drive, duck | H | inspector | IMP |
| TRK-020 | Plugin presets (save/apply) | H | inspector | IMP |
| TRK-021 | Volume automation lane | H | inspector | IMP |
| TRK-022 | Pan automation lane | H | inspector | IMP |
| TRK-023 | Copy / paste mix settings between tracks | H | track menu | IMP |
| TRK-024 | Reset mix | H | track menu | IMP |
| TRK-025 | Master fader | H | footer / mixer | IMP |
| TRK-026 | Master EQ + reset | H | mixer | IMP |
| TRK-027 | Master compression / drive | H | mixer | IMP |
| TRK-028 | Master spectrum analyser | H | mixer | IMP |
| TRK-029 | Master true-peak / loudness readout | H | mixer | — |
| TRK-030 | Track collaborator avatars | H | track row | IMP |

## 6. MIDI (`MIDI`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| MIDI-001 | Piano-roll editor per MIDI clip | H | inspector | IMP |
| MIDI-002 | Draw / move / resize notes | H | piano roll | IMP |
| MIDI-003 | Note length and velocity editing | H | piano roll | IMP |
| MIDI-004 | Note delete | H | piano roll | IMP |
| MIDI-005 | Quantize | H | piano roll | IMP |
| MIDI-006 | Octave up/down and transpose | H | piano roll | IMP |
| MIDI-007 | On-screen playable keyboard | H | footer | IMP |
| MIDI-008 | Computer-keyboard musical typing | H | global | IMP |
| MIDI-009 | Web MIDI device input | H | footer | IMP |
| MIDI-010 | MIDI rendered to audio for playback/export | — | engine | IMP |
| MIDI-011 | MIDI file import/export | H | project menu | IMP |
| MIDI-012 | Arpeggiator / chord mode | H | footer | — |

## 7. Advanced audio (`ADV`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| ADV-001 | Separate stems (2-stem) | B | clip actions | IMP |
| ADV-002 | Separate stems (multi-stem) | B | clip actions | IMP |
| ADV-003 | Place separated stems on new tracks | B | clip actions | IMP |
| ADV-004 | Stem cost from the pricing table | — | dialog | IMP |
| ADV-005 | Lyrics view for a clip (with timings) | B | inspector | IMP |
| ADV-006 | Export full mix | B H | export menu | IMP |
| ADV-007 | Export selected range | B H | export menu | IMP |
| ADV-008 | Export multitrack/stems | B H | export menu | IMP |
| ADV-009 | Export per-track WAV | H | export menu | IMP |
| ADV-010 | Export project JSON | H | project menu | IMP |
| ADV-011 | Import project JSON | H | project menu | IMP |
| ADV-012 | MP3 encode for export | H | export | IMP |
| ADV-013 | WAV encode for export | H | export | IMP |
| ADV-014 | Mixdown respects master chain | — | engine | IMP |
| ADV-015 | Export progress + cancel | H | export | IMP |
| ADV-016 | Render moderation error surfaced | B | export | IMP |
| ADV-017 | Mastering presets | H | mixer | — |
| ADV-018 | Loudness normalisation on export | — | export | — |

## 8. Projects, library & sharing (`PRJ`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| PRJ-001 | List own projects with search | B | editor dialog / landing | IMP |
| PRJ-002 | Sort projects (recent/title) | H | landing | — |
| PRJ-003 | Pin project | B | project dialog | IMP |
| PRJ-004 | Archive / restore project | B | project dialog | IMP |
| PRJ-005 | Tags on a project | B | project dialog | IMP |
| PRJ-006 | Fork / duplicate project | B | project menu | IMP |
| PRJ-007 | Delete project with confirm | B | project menu | IMP |
| PRJ-008 | Version history list | B H | project menu | IMP |
| PRJ-009 | Save named version | B H | project menu | IMP |
| PRJ-010 | Restore a version | B H | project menu | IMP |
| PRJ-011 | Share link (view/edit, expiry) | B H | share dialog | IMP |
| PRJ-012 | Revoke share link | B H | share dialog | IMP |
| PRJ-013 | Open shared project read-only | B | `/studio/shared/[token]` | IMP |
| PRJ-014 | Edit a shared project with permission | B | shared route | IMP |
| PRJ-015 | Fork a shared project into your account | B | shared route | IMP |
| PRJ-016 | Comments on a shared project | B | shared route | IMP |
| PRJ-017 | Presence (who is here, playhead) | H | shared route | IMP |
| PRJ-018 | Live update polling for collaborators | H | shared route | IMP |
| PRJ-019 | Project comments from the owner's editor | B | project menu | IMP |
| PRJ-020 | Library drawer: own songs | H | drawer | IMP |
| PRJ-021 | Library drawer: liked songs | H | drawer | IMP |
| PRJ-022 | Library drawer: uploads | H | drawer | — |
| PRJ-023 | Library drawer: stems | H | drawer | — |
| PRJ-024 | Library drawer: projects tab | H | drawer | — |
| PRJ-025 | Library search | H | drawer | IMP |
| PRJ-026 | Library filters | H | drawer | IMP |
| PRJ-027 | Upload audio into the project | B | track panel | IMP |
| PRJ-028 | Storage of uploads with duration | — | API | IMP |

## 9. UX, states, accessibility (`UX`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| UX-001 | Hover affordances on every interactive element | H | all | IMP |
| UX-002 | Visible focus ring for keyboard users | H | all | IMP |
| UX-003 | Context menus via right-click | H | clips/tracks | IMP |
| UX-004 | Drag ghost while dragging a clip | H | timeline | IMP |
| UX-005 | Snap guideline while dragging | H | timeline | — |
| UX-006 | Toast feedback for save/add/delete | H | all | IMP |
| UX-007 | Autosave indicator | H | header | IMP |
| UX-008 | Destructive-action confirmation | H | delete paths | IMP |
| UX-009 | Empty state: no tracks | H | editor | IMP |
| UX-010 | Empty state: no projects | H | landing/dialog | IMP |
| UX-011 | Empty state: no search results | H | dialog | IMP |
| UX-012 | Network error with retry | H | all | IMP |
| UX-013 | Reduced-motion support | H | all | — |
| UX-014 | Screen-reader labels on icon buttons | H | all | IMP |
| UX-015 | Contrast ≥ 4.5:1 on text | H | tokens | IMP |
| UX-016 | Touch targets ≥ 44 px | H | editor | — |
| UX-017 | Keyboard shortcut help | H | footer | IMP |
| UX-018 | First-run onboarding | H | editor | — |
| UX-019 | Unsaved-changes guard | H | navigation | — |
| UX-020 | Offline draft recovery | — | editor | — |

## 10. Backend & integration (`BE`)

| ID | Feature | Ref | Ref loc. | Ours |
|---|---|---|---|---|
| BE-001 | Project CRUD API scoped to the owner | B | `/v1/studio/projects` | IMP |
| BE-002 | Versioned project documents | B | `studio_project_versions` | IMP |
| BE-003 | Share tokens with permission + expiry | B | `studio_project_shares` | IMP |
| BE-004 | Comments API | B | `studio_share_comments` | IMP |
| BE-005 | Presence API | — | shares/presence | IMP |
| BE-006 | Uploads API with duration | — | `/studio/uploads` | IMP |
| BE-007 | Generation operations API (stems/extend/cover/…) | B | `/studio/generations/*` | IMP |
| BE-008 | Operation status polling | B | `/studio/operations/:id` | IMP |
| BE-009 | Credits charged from `pricing`, never hardcoded | — | pricing table | IMP |
| BE-010 | Provider isolation behind an adapter | — | `suno.ts` / provider layer | IMP |
| BE-011 | Rate limiting and retry on provider calls | — | limiter/queue | IMP |
| BE-012 | Audit trail for paid Studio actions | — | operations table | IMP |
| BE-013 | Error envelope compatible with the web client | — | `error.message` | IMP |
| BE-014 | Studio API contract tests | — | — | — |
