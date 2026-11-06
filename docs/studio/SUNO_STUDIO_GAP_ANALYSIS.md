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
| Quality gates | n/a | 137 unit/component/API tests, 14 Playwright specs, axe-clean routes | **Present** — e2e is local until CI provisioning exists |

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
| G12 | Library lacks stems/projects/upload tabs | Sources scattered across surfaces | W3 | **partial** — Songs, Workspaces (with server-side song counts and a filter), Projects and Uploads tabs wired; the stems tab waits on a finished stems job (B-005) |
| G13 | No Studio test suite | Regressions found by hand | W5 | **done** — vitest: 139 tests (pure modules, components, API contract); Playwright: 38 specs, stable over repeated full runs (smoke, persistence, home, library, project menu, conflicts, offline, share page, versions, loop/seek, export bytes, zoom, tracks, clipboard, marquee, plugins dry/wet + live, live mute/solo, solo-aware bounce, help, keys, metronome, writes, metrics, axe ×3). e2e needs local services, so it is not in CI yet |
| G14 | No axe/Lighthouse pass on Studio routes | Unknown a11y debt | W5.5 | **done** - axe run on both routes, 0 violations after fixes |
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
- **A test suite**: 137 unit/component/API tests and 14 Playwright specs.

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
