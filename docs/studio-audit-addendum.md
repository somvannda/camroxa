# Studio audit — addendum (surfaces the v2 pass did not cover)

Third pass: the editor surface, dialogs, menus, permissions, deep links and
feedback loops. Same evidence rules as `docs/studio-audit-a-z.md`.

**Ev:** `B` bundle · `H` help centre/release notes · `L` live · `?` not captured.

---

## N. Song editor (Edit ▸ Open in Editor)

Separate surface from the project view.

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| N1 | Section timeline | song split into sections on a timeline | H | miss |
| N2 | Lyrics field (left) | edit lyrics per section | H | miss |
| N3 | Section selection | click/highlight a section | H | miss |
| N4 | `+` new section | insert a section | H | miss |
| N5 | Beats-per-section control | bottom-left stepper | H | miss |
| N6 | Create Section | generate the new section | H | miss |
| N7 | Preview two takes | alternate versions | H | miss |
| N8 | Commit / Regenerate | accept or retry | H | miss |
| N9 | Edits Library (right) | list of generated edits | H | miss |
| N10 | Generate More | more options | H | miss |
| N11 | Boundary drag | adjust transition | H | miss |
| N12 | Fade In / Fade Out icons | per section ends | H | miss |
| N13 | Tempo display | bottom bar | H | miss |
| N14 | Stems icon (top right) | open stems | H | miss |
| N15 | Export selected range | from timeline | H | miss |

---

## O. Replace Section flow

| # | Step | Behaviour | Ev | Cam |
|---|---|---|---|---|
| O1 | Enter edit mode | opens song with waveform | H | miss |
| O2 | Select region | must be 10–30 s | H | miss |
| O3 | Lyrics autofill | existing lyrics populate | H | miss |
| O4 | Edit lyrics / add `[drum break]` | free text | H | miss |
| O5 | Recreate Section | submit | B | part (API wrapped) |
| O6 | Confirm dialog | confirms changes | H | miss |
| O7 | Two takes | listen + select | H | miss |
| O8 | Whole song regeneration | after selection | H | miss |
| O9 | `Section` / `Full Song` tags | label results | H | miss |

---

## P. Stems / MIDI

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| P1 | Get Stems entry | Edit ▸ Get Stems / MIDI | H | part |
| P2 | Mode choice | vocals / 2 stems / 12 stems | B | done (API) |
| P3 | Stems modal | progress + list | H | miss |
| P4 | Insert stem to timeline | arrow icon | H | miss |
| P5 | Stem three-dot menu | uses for that stem | H | miss |
| P6 | Insert All | all stems at once | H | miss |
| P7 | MIDI export | per instrument | H | miss |

---

## Q. Export

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| Q1 | Export button | opens dialog | H | miss |
| Q2 | Full Song | whole track | B H | blk |
| Q3 | Selected Time Range | partial render | B H | blk |
| Q4 | Multitracks | zip of stems | B H | blk |
| Q5 | MP4 / video export | elsewhere in app | H | n/a (Studio) |
| Q6 | Download count / credits | shown in dialog | H | miss |
| Q7 | Confirm | spends a download | H | miss |

---

## R. Share / collaborators

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| R1 | Invite link | `/api/project/{id}/invite` | B | miss |
| R2 | Member list | `/collaborators` | B | miss |
| R3 | Roles | owner/editor/viewer | H | miss |
| R4 | Presence | live cursors/avatars | B | miss |
| R5 | Comments | `/api/project/{id}/comments` | B | miss |
| R6 | Fork / clone shared project | `/studio/shares/{token}/fork` | B | part (route exists) |
| R7 | Share action menu | `share_action` field | B | miss |

---

## S. Project pill / switch menu (landing + editor)

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| S1 | Switch project | recent list | H | miss |
| S2 | New project | create | H | done |
| S3 | Rename | metadata | B | part |
| S4 | Archive | archive flag | B | miss |
| S5 | Delete | confirm + delete | H | miss |
| S6 | Pin | `/api/project/{id}/pin` | B | miss |
| S7 | Trash | `/api/project/trash` | B | miss |

---

## T. Landing Filters / New menus

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| T1 | Filter: model | v4/v5/v6 | H | miss |
| T2 | Filter: date | today/week/… | H | miss |
| T3 | Filter: liked | liked songs | H | miss |
| T4 | Filter: workspace | by workspace | H | miss |
| T5 | Sort | newest/oldest | H | miss |
| T6 | New: blank project | create | H | done |
| T7 | New: from upload | upload audio | H | miss |
| T8 | New: from sample | sample flow | H | miss |
| T9 | New: from playlist / inspo | reference tracks | H | miss |

---

## U. Feedback, errors, notifications

| # | Event | Behaviour | Ev | Cam |
|---|---|---|---|---|
| U1 | Saved indicator | subtle "saved" | H | miss |
| U2 | Save conflict banner | "newer version" + reload | B | miss |
| U3 | Save throttled | back-off, no error spam | B | miss |
| U4 | Moderation failure | message on generation/render | B | miss |
| U5 | Network error | retry affordance | ? | part |
| U6 | Credit exhausted | block + link to buy | B L | done |
| U7 | Export complete | toast + download | H | miss |
| U8 | Stems ready | toast / modal update | H | miss |

---

## V. URL / deep links

| # | Route | Behaviour | Ev | Cam |
|---|---|---|---|---|
| V1 | `/studio` | landing or last project | H | done |
| V2 | project deep link | `?project=<id>` opens it | ? | done (query) |
| V3 | `/studio/{id}` | canonical project URL | ? | miss |
| V4 | Share token URL | read-only / fork | B | part |
| V5 | Back/forward | restores project state | ? | part |

---

## W. Responsive / platform

| # | Case | Behaviour | Ev | Cam |
|---|---|---|---|---|
| W1 | Narrow width | panels collapse | H | part (details hidden) |
| W2 | Mobile Studio | different layout / unavailable | H | n/a |
| W3 | Touch drag | long-press to drag | H | miss |
| W4 | Zoom > 100% | timeline scrolls | H | part |

---

## X. Plan gates (Suno)

| # | Feature | Gate | Ev | Cam |
|---|---|---|---|---|
| X1 | Studio itself | Premier | H | n/a (credits) |
| X2 | Replace Section | Pro/Premier | H | n/a |
| X3 | Fade In/Out | Pro | H | n/a |
| X4 | Stems / MIDI | Pro | H | n/a |
| X5 | Downloads | monthly cap | H | n/a |

Camxora has no plan tiers — features are credit-gated, so these map to "costs
credits" instead of "requires plan". Deliberate difference, recorded in
`docs/studio-1to1.md`.

---

## Evidence capture plan (what to record, from where)

| Target | Where to capture | Unblocks |
|---|---|---|
| `state` document | Suno Studio save request (DevTools) or version read | F4/F5, K6–K8, B13, H3 |
| Prompt-bar request | Studio prompt bar send | E4 |
| `render-state` body/response | Export → full song | Q2, M6 |
| `render-state-multitrack` body | Export → multitracks | Q4, M7 |
| Clip context menu | right-click a clip | D11, H6 |
| Track context menu + add-track menu | right-click track / + menu | C8, C10, H5 |
| Toolbar modes | click each tool icon | F2–F5 |
| Version history dialog | project menu → versions | H2 |
| Share dialog | project menu → share | R1–R7 |
| Filters + New menus | landing | T1–T9 |
| Save conflict | edit in two tabs | U2 |
