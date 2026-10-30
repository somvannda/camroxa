# SUNO STUDIO UI COMPONENT CATALOG

Our Studio components, where they live, and the reuse rule for each. New UI must
compose from this catalog before adding a one-off.

## 1. Primitives (shared)

| Component | Path | Used for | Rule |
|---|---|---|---|
| `Icon` | `components/Icon.tsx` | FontAwesome-ish icon wrapper | Never inline an `<i>` with its own sizing |
| `SelectField` | `components/ui/select-field.tsx` | native-backed select with styling | All dropdown selects in Studio |
| `Checkbox` | `components/ui/checkbox.tsx` | Radix checkbox | All binary toggles with a label |
| `AuthProvider` | `components/AuthProvider.tsx` | session + `useAuth()` | Only source of user identity |
| `PlayerProvider` | `components/PlayerProvider.tsx` | global player | Studio pauses the global player on transport start |

## 2. Studio regions (inside `StudioEditorView`)

These are currently functions/JSX blocks rather than files. Names match the code so
a future extraction is mechanical (architecture weakness A1).

| Region | Responsibility | Key handlers |
|---|---|---|
| `Header` | title, project switcher, undo/redo, versions, share, export, panel toggles | `openProjects`, `undo`, `redo`, `saveVersion`, `shareProject` |
| `TrackPanel` | one row per lane: index, name, colour, volume, pan, M/S, meter, avatars, menu | `updateLane`, `toggleMute`, `toggleSolo`, `reorderTrack` |
| `Timeline` | ruler, grid, lanes, clips, markers, playhead, drop target | `seekTo`, `startDrag`, `trimClip`, `splitAtPlayhead` |
| `Clip` | waveform, title, fades, take badge, context menu | drag/trim/menu |
| `Inspector` | clip properties, track FX, automation, lyrics, personas, piano roll | `updateLane`, `addAutomationPoint`, `requestStems` |
| `LibraryDrawer` | songs/liked, search, filters, drag-to-lane | `addClipFromItem` |
| `Footer` | transport, clock, bar.beat, BPM, grid, zoom, loop, metronome, master, Studio AI | `togglePlay`, `seekTo`, `runStudioAi` |
| `Mixer` | per-track strips + master strip + spectrum | `updateLane`, `setMaster*` |
| `ProjectDialog` | list/search/sort/pin/archive/tag/open/delete | `loadProjectList`, `openProject` |
| `VersionsDialog` | list/save/restore | `listVersions`, `saveVersion`, `restoreVersion` |
| `ShareDialog` | create/copy/revoke links, comments | `createShare`, `revokeShare` |
| `MidiKeyboard` | playable keys, octave, chord/arp mode | `playNote` |

## 3. Studio home (new, W1)

| Component | Path | Responsibility |
|---|---|---|
| `StudioHome` | `components/studio/StudioHome.tsx` | Signed-in studio home: resume, projects, search, sort, create, per-card actions. Signed-out: renders the marketing node it is given. |
| `StudioMarketing` | `components/studio/StudioMarketing.tsx` | The existing public product page, unchanged in content. |
| `StudioProjectCard` | inside `StudioHome` | One project: title, meta, updated time, actions. |

Rules for `StudioHome`:

- No dead controls: every action either works or is absent.
- Empty state must create a project, not apologise.
- Loading uses skeletons with the card's final height (no layout shift).
- Errors are inline with a retry, never a bare toast.
- Keyboard: cards are links/buttons, menu is a real button with `aria-haspopup`.

## 4. Style system

| Scope | Classes | Guard |
|---|---|---|
| Marketing/Create/Library `.s-*` | `s-page`, `s-btn`, `s-card`, `s-row`, `s-empty` | `npm run check:ui` enforces type scale, control heights, palette |
| Studio editor | `studio-*` | shared CSS variables only; no new raw hex without adding it to the palette |
| Studio home | `studio-home*` | same variables; keep to the documented type scale |
| Standalone layout | `studio-standalone` | removes site chrome for the DAW |

Token sources: `app/globals.css` (`--s-*` scale, `--text`, `--muted`, `--line`,
`--panel`). Never introduce a second colour scale.

## 5. Composition rules

1. A control that mutates arrangement state must call `commitLanes` so undo and
   autosave are automatic.
2. A control that spends credits must first read `getStudioPricing` and show the
   number in the confirming dialog.
3. A destructive control must require a second, explicit confirmation.
4. Any async control must own three states: idle, busy, error (with retry).
5. Icon-only buttons require `aria-label` and a `title`.
6. Overlays close on `Escape` and restore focus to the trigger.

## 6. Anti-patterns found in the current tree

| Anti-pattern | Where | Fix |
|---|---|---|
| One 6.9k-line component | `StudioEditorView` | extract regions by name (A1) |
| Inline `style={{...}}` for one-off geometry | timeline/clip | acceptable only for computed geometry (x/width), never for colour/type |
| Repeated save-status markup | header + footer | single `SaveStatus` component |
| Duplicated project-loading logic | editor `openProject` + shared load + home | one `loadProjectDocument(id)` helper |
