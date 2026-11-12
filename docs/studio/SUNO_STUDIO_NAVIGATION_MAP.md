# SUNO STUDIO NAVIGATION MAP

Routes, regions and transitions for **our** Studio, mapped to the reference
surface it corresponds to. Route truth lives in `camxora.com/app/**`.

## 1. Route table

| Route | File | Auth | Purpose | Reference analogue |
|---|---|---|---|---|
| `/studio` | `app/(site)/studio/page.tsx` | public | Product/marketing page today; **must become the Studio home when signed in** (W1.1) | `suno.com/studio` (landing) |
| `/studio/editor` | `app/studio/editor/page.tsx` | required | The DAW: arrangement, mixer, inspector, library drawer | `suno.com/studio` project view |
| `/studio/editor?project=<id>` | same | required | Opens a specific project | project deep link |
| `/studio/shared/[token]` | `app/studio/shared/[token]/page.tsx` | public (token) | Read-only or editable shared project, comments, presence, fork | shared project link |
| `/create` | `app/(site)/create/page.tsx` | required | Song generation (simple/advanced), feed | `suno.com/create` |
| `/library` | `app/(site)/library/page.tsx` | required | Song library, filters, batch actions | `suno.com/library` |

Layout note: `/studio/editor` and `/studio/shared/*` use
`app/studio/editor/layout.tsx` → `.studio-standalone`, which suppresses the site
sidebar/topbar/player so the DAW owns the viewport. `/studio` is inside `(site)` and
keeps marketing chrome — intentional while it is a marketing page, and the reason
W1.1 needs its own layout treatment (a signed-in home that is still chrome-free).

## 2. Editor regions

```
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER   project switcher · title · undo/redo · versions · share ·   │
│          export · library · inspector · mixer                        │
├───────────────┬──────────────────────────────────────────────────────┤
│ TRACK PANEL   │ TIMELINE                                             │
│ # name        │ ruler (bars, loop, markers, playhead)                │
│ vol pan M S   │ lanes × clips (waveform, fades, take badge)          │
│ groups A–D    │ drop target from library                             │
│ + add track   │                                                      │
├───────────────┴──────────────┬───────────────────────────────────────┤
│ INSPECTOR (right, toggle)    │ LIBRARY DRAWER (right, toggle)        │
│ clip: timing/mix/fades/speed │ tabs: songs / liked / uploads / stems │
│ track: EQ, filter, FX sends  │ search, filters, drag-to-lane         │
│ lyrics, personas, MIDI roll  │                                       │
├──────────────────────────────┴───────────────────────────────────────┤
│ FOOTER  transport (start/play/end) · clock · bar.beat · BPM · grid · │
│         zoom · loop · metronome · master fader · Studio AI prompt    │
└──────────────────────────────────────────────────────────────────────┘
```

Region ownership:

- **Header** — project-level actions only. Never per-clip.
- **Track panel** — track identity and mix. Never clip content.
- **Timeline** — arrangement. All clip mutation starts here.
- **Inspector** — properties of the current selection (clip first, track second).
- **Library drawer** — sources. Adding to the arrangement happens by drag/click.
- **Footer** — transport and global toggles. Always visible.

## 3. Transitions

| From | Action | To | Notes |
|---|---|---|---|
| `/studio` | New project | `/studio/editor?project=<new>` | Project created before navigation so a reload is safe |
| `/studio` | Resume card | `/studio/editor?project=<last>` | Last project stored server-side (`updated_at`) |
| `/studio` | Song row → Edit in Studio | `/studio/editor?project=<id>` | Server creates/loads a project seeded with the clip |
| `/create` | Open in Studio | `/studio/editor?project=<id>` | Same seeding endpoint |
| Editor | Project switcher | same route, new `project` | Unsaved guard runs first (UX-019) |
| Editor | Share link → preview | `/studio/shared/<token>` | New tab |
| `/studio/shared/<token>` | Fork | `/studio/editor?project=<new>` | Fork returns a project you own |
| Editor | Sign out / 401 | `/login?next=/studio/editor` | Preserve intent |

## 4. Deep-link contract

- `project` is a UUID owned by the session user. Unknown id → editor error state
  with "Project not found" and a link back to `/studio`.
- A project owned by someone else → 403 → same state, never a data leak.
- `token` (shared route) is opaque; expired/revoked → terminal state with a
  request-access hint.
- No route may render editable controls before auth resolves; show a skeleton
  (UX: prevents flash of empty DAW).

## 5. Sidebar / global navigation

Studio is reachable from the site sidebar (`Studio` entry) and from the player
context menu (`Open in Studio`). Both must carry the same target: `/studio`.
Today they point at `/studio/editor`; after W1.1 they point at `/studio` so the
user always passes through a project choice (matching the reference).
