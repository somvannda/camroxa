# SUNO STUDIO GAP ANALYSIS

Honest comparison: what the reference exposes, what we have, what is missing, and
what we deliberately do not copy.

Scoring for this document:

- **Parity** — the workflow exists and behaves comparably.
- **Partial** — exists but a meaningful part of the workflow is missing.
- **Missing** — no implementation.
- **Deliberate** — we choose not to reproduce it (with reason).

## 1. Headline

Scoped to the **web Studio** (`camxora.com/components/studio`), not the legacy desktop app.

| Area | Reference surface | Ours | Verdict |
|---|---|---|---|
| Studio entry | Landing + project chooser + start-from-song | `/studio` home: list, resume, create, duplicate, archive, delete, start from a song | **Parity** |
| Arrangement editor | Multitrack clips, drag, marquee, zoom, loop | Drag with snap + guideline, marquee, multi-drag, C/V/D, delete focus, undo/redo, loop range, two rulers | **Parity** for the captured surface; fades/split/markers/automation have no captured menu (C-03) and are not invented |
| Mixing | Per-track mix, master chain, FX | Track volume / mute / solo, master chain (EQ, comp, limiter, drive), plugin dock with presets | **Partial** — no sends or group buses in this editor |
| MIDI | Piano roll + instrument + keyboard | Not in the web Studio (desktop app only) | **Missing** (deliberate: no captured contract for a browser piano roll) |
| Generation in the DAW | Prompt bar + clip transforms | Generation lives on `/create`; **stems** is wired from the provenance strip; extend/cover/remaster/mashup/replace-section APIs exist in `lib/studio-api.ts` but their menu was never captured | **Partial** |
| Export | Mix, range, multitrack | Browser render: full mix, one file per track, loop range, project JSON, optional −1 dBFS normalisation | **Parity** for the browser path (server render not wired) |
| Collaboration | Share links, comments, presence | View + copy links, comments and presence APIs, fork; the editor exposes sharing only | **Partial** — comments/presence have no captured panel |
| Library | Songs / liked / stems / uploads / workspaces / projects | Songs, workspaces (with counts + filter), projects, uploads | **Partial** — stems tab waits on a real stems job (B-005); "liked" is per clip, not a song corpus |
| Reliability | Autosave with silent overwrite | Save status, 409 reload/overwrite, offline draft, unsaved guard | **Beyond parity** (deliberate, D-004 family) |
| Quality gates | n/a | 175 unit/component/API tests, 58 Playwright tests, axe-clean routes | **Present** — e2e is local until CI provisioning exists |

## 2. Detailed gaps

| # | Gap | Impact | Roadmap | Status |
|---|---|---|---|---|
| G1 | No Studio home; `/studio` is marketing | Users cannot discover, resume, or manage projects without entering the DAW | W1.1-W1.3 | **done** — route added 2026-11-01; the home component already had the rest |
| G2 | No deep link `?project=` in the editor | Home cannot open a specific project; refreshes fall back to "most recent" | W1.2 | **done** — home navigates with `?project=`; the editor reads it on mount and every e2e fixture opens that way |
| G3 | No conflict resolution UI on save | Concurrent edits can overwrite | W2.2 | **done** — version check + reload/overwrite panel; both buttons are covered by e2e (keep mine wins, reload theirs replaces the document) |
| G4 | No offline draft | A network blip loses the last edit burst | W2.3 | **done** — draft stored on failure, offered on reopen |
| G5 | No unsaved-changes guard | Navigation can drop a pending write | W2.4 | **done** — `beforeunload` while a save is pending, failed or offline |
| G6 | No marquee multi-select / multi-drag / copy-paste | Slower bulk arrangement work | W3 | **done** — marquee, multi-drag and C/V/D |
| G7 | No snap guideline while dragging | Users cannot tell where a clip will land | W3 | **done** — clip renders at the snapped position with a guideline |
| G8 | No drag threshold | 2 px pointer jitter repositions a clip | W3 | **done** — 3 px before a press becomes a drag |
| G9 | No clip focus management on delete | Keyboard users lose their place | W3 | **done** — delete keeps focus on the nearest clip |
| G10 | No master loudness/true-peak readout | Cannot verify a master professionally | W4.4 | **done** - peak + RMS + 4x inter-sample estimate in the header |
| G11 | No mastering presets / export normalisation | Export loudness varies | W4.1 | **done** — export menu can gain-match the mix/range to a −1 dBFS sample peak (`lib/studio-normalise.ts`, optional, off by default; per-track exports stay at unity so balance survives) |
| G12 | Library lacks stems/projects/upload tabs | Sources scattered across surfaces | W3 | **partial** — two-level library: level 1 is the reference's tile chooser (All Songs / Liked / Stems / Uploads) plus Workspaces (with the captured `New workspace` create row) and Studio Projects sections (four rows each, See all); level 2 is the list (songs grouped under Today / Yesterday / date headers per §19.2, each collapsible from its heading), with the captured toolbar (Liked only / New / In Project / Stems / Uploads) and 44 px artwork + Play/Like row actions + draggable rows + model/variant/length tag strip; double-click opens the captured song detail rail (§100/D-018). Liked filters on the viewer's liked clips; In Project filters on the `songId` already recorded on clips. Stems stays visible-but-disabled until a finished stems job exists (B-005); library upload needs streaming storage (B-006); key/BPM are absent because the corpus does not carry them (D-016) |
| G13 | No Studio test suite | Regressions found by hand | W5 | **done** — vitest: 175 tests; Playwright: 58 tests covering every surface exercised here, green over repeated full runs (smoke, persistence, home + search, library + date grouping, project menu incl. new/duplicate/share gate, clip menu + split, clip info, conflicts, offline, share page, versions, transport, meter, shortcuts, trim, fade, snap guideline, track colour, loop/seek, export bytes, zoom, tracks/sliders/collapse, clipboard, marquee, plugins dry/wet + live, mute/solo, solo-aware bounce, master, help, keys, metronome, writes, metrics, classic editor route, axe ×3). Workers capped at 4 so audio-timing specs are not starved. e2e needs local services, so it is not in CI yet |
| G14 | No axe/Lighthouse pass on Studio routes | Unknown a11y debt | W5.5 | **done** - axe run on both routes, 0 violations; Lighthouse 100 accessibility / 100 best-practices / 100 SEO on /studio and the editor (the signed-out marketing and loading skeleton now both render a <main> landmark) |
| G15 | 6.9k-line editor component | Slow review, hard extraction | after W3 | **done** - six components extracted (header, footer, library, provenance, track panel, timeline); shell 1,967 -> 1,560 lines |
| G16 | No generation history view | Users cannot retrace how a clip was made | W3 | **done** - clips record their source generation and show model, date and style |
| G17 | No playback speed control | Cannot audition at half speed | W3 | **done** - 1x/0.5x/2x applied to sources and the tick |
| G18 | No first-run onboarding in the DAW | New users face a dense UI | W3 | **done** - empty projects open a start overlay, remembered per project |
| G19 | Long-project rendering not virtualised | Perf cliff | W3 | **done** - clips culled to the visible window (300 -> 80..140 rendered) |
| G20 | No touch-target sizing | Unusable on tablets | W3 | **done** - coarse pointers get 44x44 hit plates |

| G21 | Track mute / solo / arm were visual-only | The reference has working per-track mute and solo (spec 52.1) | W3 | **partial** - mute + solo wired and persisted; arm needs recording |

| G22 | Undo / redo were placeholders | The reference binds CTRL Z / CTRL SHIFT Z (spec 36) | W3 | **done** - single write path + 50-document history |

| G23 | The project chip was disabled (no menu) | No rename/duplicate/open/versions from the editor, though the reference's menu is captured (§18.1) | W3 | **done** - 9 captured items in order; New/Open/Rename/Duplicate/Version History/Share/Quick Start/Settings wired; v1 copy disabled with a reason (D-011, D-012) |

| G24 | No Studio settings; clip drags touched audio live | The captured ghost-drag behaviour (§22) was absent, and a drop never applied the new arrangement to the running engine | W3 | **done** - settings panel with the one captured setting (ghost drag), read at gesture start; on = hold audio and apply once on drop, off = apply per move (D-013) |

| G25 | No Learn menu or hover help | The captured "What's This?" system (§7/§38) was missing; the footer's Learn link went nowhere useful | W3 | **done** - Learn popover with the four captured rows, `?` shortcut list, and hover/focus cards on annotated controls, toggled globally and remembered (D-014) |

| G26 | Add-track was a single button; no transport keys | The captured add-track menu (§8.3) and the §11 keys (Space, Home/End, A/U) did not exist, though the help list implied Space worked | W3 | **done** - menu with Audio A / MIDI M / Upload U (MIDI disabled: no MIDI tracks in this editor), Space/Home/End/A/U bound with dialog and typing guards |

| G27 | Metronome was visual-only | The capture lists the button as "Click track" (H-09); ours toggled a state with no sound and said so | W3 | **done** - audible click per beat with a bar accent, lookahead-scheduled from the playhead (survives loop/seek), beat readout on the button, silenced on pause/off |

| G28 | Versions were manual snapshots | §25 captures automatic versions ("Projects are saved automatically") clustering seconds apart; ours only appeared when someone pressed save in code | W3 | **done** - every successful save asks for a snapshot; the server throttles to one per 20 s and keeps the newest 50 (D-015) |

| G29 | Two quick edits could fake a conflict | Both PATCHes carried the same `expected_updated_at`, so on any slow connection the second returned 409 and the user saw "changed since you loaded it" for their own edits | W2.2 | **done** - one write in flight, newest pending write coalesced and sent with the version the previous response produced (e2e with a 600 ms PATCH delay) |

| G30 | Going back online claimed "Saved"; the offline draft held the pre-edit document | The chip flipped to saved without sending anything, and the draft was read from a ref that had not seen the edit yet, so a reconnect could lose the change | W2.3 | **done** - unsaved data is captured after the edit, replayed on `online`, and the chip only says Saved once the server has it (e2e toggles the network) |

| G31 | Home card menus were painted under later cards | The card's hover transform created a stacking context, so the popover could be covered; clicking Archive/Pin hit the card below and navigated into it | W1 | **done** - the card lifts with `is-menu-open` while its menu is open; e2e asserts the menu item is the element at its own point before clicking |

| G32 | A share link's Fork opened "/studio/editor" | The fork navigated without the new project id, so the editor picked the most recent project instead of the copy | W2 | **done** - the fork's returned id is used; a public share page opens read-only without an account and forks into its own copy (e2e) |

| G33 | Loop armed a range but never repeated it; seeking desynced audio | The transport wrapped at the 240 s project end, not `loopEnd`, and clicking the ruler or pressing End moved the playhead without re-scheduling the engine | §68 | **done** - wrap at the loop range with a guarded engine restart, and `seekTo()` restarts playback from the new position; e2e plays until the loop wraps and seeks mid-playback |

| G34 | "Fit to content" reset to a preset instead of fitting | The button set the default 96 px/bar, so a long arrangement stayed off-screen and a short one did not fill the canvas | W3 | **done** - the pitch is derived from the viewport and the content end (clamped 8–192), and the e2e checks every clip ends inside the canvas |

| G35 | Per-track plugin chains never reached the audio engine | `buildPluginChain` existed but nothing called it: effects persisted and looked live while playback and exports were dry | W4.1 | **done** - playback and `renderMix` route each track through its chain once (shared per track), disposed on stop; an e2e adds an EQ, exports dry vs wet and compares RMS |

| G36 | Chain edits did not affect running audio | Even once the chain was wired, nodes were built at play time and never updated; an EQ knob moved during playback did nothing until a restart | W4.1 | **done** - parameter changes update the live nodes, a shape change (add/remove/reorder/bypass) rebuilds once; e2e counts AudioParam writes while playing |

| G37 | Mute / solo / volume only applied when sources were scheduled | Pressing M or S during playback changed the button and nothing else; a track that started muted could not be unmuted without restarting | G21 | **done** - sources are always scheduled and the per-track gain follows the mix live; e2e mutes and solos during playback and watches the master peak drop to -inf and return |

| G38 | First play with a chain built the graph twice | The live-chain effect fired while `startAudio` was still decoding and mistook "not yet built" for a shape change, restarting playback and duplicating effect nodes | W4.1 | **done** - the chain structure is recorded before the first await, and the e2e asserts no second filter node appears after playback starts |

| G39 | The mix export ignored solo | Playback silences non-soloed tracks, but the bounce included them, so the file did not match what the user heard | W4.3 | **done** - mix/range renders honour solo; per-track exports opt out (bouncing a non-soloed track must not be silent). e2e compares RMS windows with and without solo |

| G40 | No master fader or main mute | The reference's footer has a Main fader and Mute main (F-01/F-02); ours went straight from track gains to the master chain at a fixed level | W4.1 | **done** - persisted master volume + mute, live on the running graph, applied to mix/range exports (per-track files stay at unity); e2e measures playback and bounced silence |

| G41 | Track level/pan bars were decorative, and "Collapse controls" was a no-op | The two bars under each track were `aria-hidden` divs with no input, and the menu item only closed the menu | T-02/T-03 | **done** - real range sliders (volume 0–100, pan −100…100) commit on release, plus a persisted per-track `collapsed` that hides them; e2e checks both values on the server |

| G42 | Stop and Back to start shared one handler | Stop rewound instead of halting, so the two captured transport controls did the same thing | H-05/H-08 | **done** - Stop halts at the playhead (and silences the click), Back to start rewinds to zero; e2e plays, stops, checks the clock held, then rewinds |

| G43 | Time signature was a read-only label, and bar maths assumed 4/4 | The meter could not be changed, and every bar count, beat readout, snap grid and metronome accent assumed four beats | H-13 | **done** - an editable meter (2/4, 3/4, 4/4, 6/8) persisted on the project drives bar length, `bar.beat`, snapping and the click accent; e2e changes to 3/4 and checks the clock/readout and reload |

| G44 | Most captured shortcuts were unbound | The shortcut overlay (C-07) lists loop, metronome, select all, cut, mute/solo, hide/show, rename, add track, panel toggles; only a handful worked | §36/C-07 | **done** - Ctrl L, Shift C/T/M/S/H, Shift Alt H, F2, Ctrl A/X and `4` are bound with the same guards; the overlay lists exactly what works |

| G45 | Clips could not be trimmed, and the pointer handlers read stale state | S25 captures trim grips at both ends; we had none, and the global pointer effect captured `projectId = null` from the first render, so a handler that only runs on release could not write | S25 | **done** - right grip changes duration, left grip moves start and content offset together (audio under the clip does not shift), playback and export honour the offset; the effect now re-registers with the project and reads the document through a ref |

| G46 | No fade handle, and drags could be cancelled by text selection | S25 shows a diagonal fade handle at the clip's top-left and SHIFT F toggles a fade; a marquee also left page text selected, so the next drag started a native text drag (pointercancel) and moved nothing | S25 | **done** - a fade handle sets a fade-in that playback and export apply, Shift F toggles a short default, one stable pointer listener pair replaces per-frame re-registration, drops commit from the release position, cancels abort, and the canvas is `user-select: none` |

| G47 | No clip context menu, no split, and the ruler could not seek | §47/S26 capture a 13-item state-built menu (copy/paste/duplicate/delete/split/rename/colour/info/stems/download) and ctrl E for split; clicking the bar ruler moved nothing | §47 | **done** - right-click selects and opens a menu built from clip state; Split (Ctrl E or the item) cuts at the playhead and carries the offset into the right half; Rename, Clip Color and Download .WAV work, Get Stems gates on a source generation, Clip Info opens the inspector; clicking the ruler seeks |

| G48 | No clip info panel | §70 captures the right rail swapping to a song inspector (identity, waveform, Info/Stems tabs, styles, lyrics); Clip Info was a disabled menu item | §70 | **done** - the rail shows timing, fade, trim offset, track, the source generation's model/date/style/lyrics and a waveform decoded from the clip's own audio; the Stems tab exposes the request; comments/Magic Bar chip have no captured contract here and are absent |

| G49 | Version history was a centred dialog | §25 captures a left side panel, 300 px full height, headed `History` with "Projects are saved automatically" and entries grouped under date headings | §25 | **done** - the panel is a fixed left aside with date-grouped times and per-row Restore; automatic snapshots (G28) supply the entries |

## 3. Deliberate non-parity

| Item | Why |
|---|---|
| Branding, logo, copy, artwork | Must be original (mission rule, D-004) |
| Provider-specific model names and marketing labels | We surface our own models and let the provider adapter map them |
| Reference private API usage | Forbidden as a product dependency (D-002) |
| Reproducing the reference's exact pixel metrics | We match interaction quality and density, not pixels; our tokens are ours |

## 4. What we have that the reference does not (or does not obviously expose)

These are wins to protect, not to remove — all of them exist in the web Studio:

- **Four save states** (saved / saving / failed / offline) with retry, plus a 409
  reload-or-overwrite choice and an offline draft. The reference overwrites silently
  (§93, §96).
- **Serialized writes**: one save in flight, newest pending edit coalesced, so a slow
  connection cannot make the editor report a conflict the user did not cause.
- **Offline replay**: a change made while offline is sent when the connection returns,
  and the chip only says "Saved" once the server has it.
- **Export normalisation**: mix and range renders can be gain-matched to a −1 dBFS
  sample peak (D-010).
- **Project JSON export** that round-trips the arrangement.
- **Workspace filtering with server-side song counts** in the library drawer.
- **Keyboard focus management** on delete, 44 px coarse-pointer targets, and axe-clean
  routes — including the Learn popover.
- **A test suite**: 175 unit/component/API tests and 58 Playwright tests.

## 5. Verification debt

What is proven today: the arrangement interactions, persistence across reloads, share
links (resolved without editor auth), project rename/duplicate/versions, library tabs and
workspace filtering, ghost-drag settings persistence, help copy and toggling, transport
keys, metronome scheduling, metric parity against the captured numbers, and zero axe
violations on three surfaces.

What is still *not* proven, and why:

| Item | Blocked by |
|---|---|
| Receiving an actual stem set | B-005 — no genuinely generated clip whose Suno account is recorded |
| Extend / cover / remaster / mashup / replace-section from the editor | No captured menu to place them (C-03); APIs exist and are tested at the service level only |
| Comments and presence panels | No captured panel (C-10) |
| e2e in CI | The workflow has no app + API + database provisioning |
| The five capture gaps (S30, S32, S44, S60, S61) | A signed-in reference session (B-001) |
