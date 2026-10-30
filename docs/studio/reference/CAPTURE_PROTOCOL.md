# CAPTURE PROTOCOL — how to guarantee nothing is missed

Ad-hoc clicking cannot produce a 1:1 clone. This protocol defines **completeness**
per surface so "every button, label, flow" is a measurable state rather than a hope.

## 1. Definition of "captured"

A surface is captured only when **all five layers** exist for it:

| Layer | What it proves | How |
|---|---|---|
| **L1 Structure** | every element and its hierarchy | accessibility snapshot saved to file |
| **L2 Geometry** | placement, size, spacing | `getBoundingClientRect` for every element + screenshot |
| **L3 Text** | every label, placeholder, tooltip, error | full `innerText` + string inventory (`ui-strings.json`) |
| **L4 Behaviour** | what each control does, states, shortcuts | interaction transcript: action → observable change |
| **L5 Data** | what it sends/receives | network request/response per action |

A surface with only L3 is *named*, not *cloned*. Today most surfaces have L3 only.

## 2. The walk (every surface, in order)

1. Signed-out marketing `/studio-welcome` — sections, CTAs, copy, links
2. Sign-in transition
3. Studio home / project list — cards, sort, search, archive, empty
4. New project paths — empty, demo, upload, from song, video
5. Onboarding dialog — 4 cards + 2 entries + skip
6. Editor shell — header, all 15 controls, panel toggles
7. Track panel — row anatomy, all 17 tracks, hidden state, collapse
8. Track options menu — full item list
9. Add-track menu — Audio / MIDI / Upload + sub-flows
10. Timeline — ruler, lanes, clips, markers, loop, playhead, grid
11. Clip — trim handles, fades, split, warp markers, takes, heal, FX, Clip Info
12. Magic Bar — prompt, model, conversation, placement, generation result
13. Inspector — Plugins chain, Automation (CC + velocity), Clip editor (audio/MIDI), Take lanes
14. Mixer / master — faders, limiter, meters
15. Library — workspaces, per-workspace view, search, liked, audition
16. Project menu — 9 items → each destination
17. Version History — entries, actions per entry
18. Share — copy, link behaviour, fork
19. Settings — Performance, Window management, Content (all sub-options)
20. Export — menu → dialog → progress → result
21. Get Stems / Get MIDI / Personas — dialog → cost → result
22. Learn — menu, tutorials, Learning Center, What's This?
23. Keyboard overlay — full map (captured)
24. Notifications — toasts, panels
25. States — loading, empty, error, offline, credits, moderation
26. Responsive — 1280 / 1024 / 768
27. Accessibility — focus order, canvas semantics

## 3. Automation recipe (per surface)

```
open surface (real pointer or ref click)
  → snapshot          save  capture/<n>-<surface>.a11y.txt
  → screenshot        save  capture/<n>-<surface>.png
  → innerText         save  capture/<n>-<surface>.txt
  → geometry dump     save  capture/<n>-<surface>.json
  → network.list      save  capture/<n>-<surface>.net.json
  → interact once     append to capture/<n>-<surface>.flow.md
```

Saving to files (not chat) is what makes the pass exhaustive: 27 surfaces × 5
artifacts is a corpus, not a conversation.

## 4. Completeness metric

| Layer | Surfaces complete |
|---|---|
| L1 structure | 3 / 27 |
| L2 geometry | 1 / 27 (editor shell only, one viewport) |
| L3 text | **27 / 27** — the bundle string inventory covers the vocabulary; screen attribution partial |
| L4 behaviour | 6 / 27 |
| L5 data | 1 / 27 (endpoint inventory, no per-surface request capture) |

**So the honest answer to "is everything captured": no — L1 11%, L2 4%, L4 22%, L5 4%.**
L3 (labels/text) is the only layer that is genuinely complete, and only as a
vocabulary, not yet attributed to screens.

## 5. Why this matters for a 1:1 clone

A clone is only as good as its weakest layer. With L3 only, we can write copy that
matches and still place controls wrong (L2), miss states (L4), and mis-shape the API
(L5). That is exactly the failure mode of the earlier `feat/studio-shell` attempt:
correct labels, wrong model.

## 6. Prerequisites the environment must provide

| Need | Why | Status |
|---|---|---|
| Viewport resize / device emulation | L2 at 3 breakpoints | **missing** |
| Stable signed-in session | L1–L5 on gated surfaces | flaky (logged out twice) |
| Second account | collaboration surfaces | not available |
| Credit budget | paid flows | approved, but trigger not yet solved |
| File output | corpus, not chat | available |

## 7. Immediate next three runs

1. **Editor shell full pass** — snapshot + screenshot + geometry for every element in
   the header, track panel, timeline, Magic Bar, footer. This alone moves L1/L2 for the
   most-used surface from 0 to complete.
2. **Track + clip surfaces** — open track options, clip menu, Clip Info, take lanes,
   plugins, automation, MIDI editor; capture each with L1–L5.
3. **Remaining dialogs** — export, versions, share, settings sub-options, onboarding.

Each run produces files under `docs/studio/capture/` and updates the completeness table
in §4. Nothing is "done" until the table reads 27/27 on L1, L2, L4 and L5.
