# Studio audit — round 4 (model, mixer, collaboration, accessibility, limits)

Fourth pass. Same rules as `docs/studio-audit-a-z.md`; `?` means not captured, so
not implemented.

---

## Y. Clip & track model

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| Y1 | Track types | audio vs MIDI vs stems | H | miss (audio only) |
| Y2 | Track colour | colour picker | ? | miss |
| Y3 | Clip properties panel | gain, fade, pan per clip | ? | miss |
| Y4 | Clip gain envelope | volume automation on clip | ? | miss |
| Y5 | Clip fade handles | drag fades at edges | ? | miss |
| Y6 | Clip name | rename independent of song title | ? | miss |
| Y7 | Clip source badge | original vs generated vs stem | ? | miss |
| Y8 | Clip metadata popover | model, seed, prompt | ? | miss |
| Y9 | Duplicate clip | ⌘D | ? | miss |
| Y10 | Linked clips | edits follow source | ? | miss |

---

## Z. Mixer, routing, effects

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| Z1 | Channel strip | fader + meter per track | H | miss |
| Z2 | Pan | L/R | ? | miss |
| Z3 | Inserts / FX slots | per-track effects | H | miss |
| Z4 | Send / return buses | reverb/delay sends | ? | miss |
| Z5 | Master bus | master fader + meter | H | part |
| Z6 | Metering | peak / RMS | ? | miss |
| Z7 | Plugins | Suno Studio 2.0 plugin rack | H | miss |
| Z8 | Wavetable synth | instrument track | H | miss |
| Z9 | Automation lanes | parameter automation | H | miss |

---

## AA. Project settings

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AA1 | Project name | rename | B | part |
| AA2 | BPM | editable tempo | H | miss |
| AA3 | Time signature | 4/4, 3/4… | H | miss |
| AA4 | Key | musical key | H | miss |
| AA5 | Project artwork | cover image | ? | miss |
| AA6 | Description / tags | metadata | B | miss |
| AA7 | Archive | flag | B | miss |
| AA8 | Delete | confirm | H | miss |

---

## AB. Import & files

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AB1 | Upload audio | drag/drop or picker | H | miss |
| AB2 | Accepted formats | mp3/wav… | ? | miss |
| AB3 | Size / duration limits | caps | ? | miss |
| AB4 | Stem import | import separate stems | ? | miss |
| AB5 | Import from library | song → add to project | B | done |
| AB6 | Import progress | upload state | ? | miss |
| AB7 | Duplicate import guard | same clip twice | ? | miss |

---

## AC. Collaboration depth

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AC1 | Invite by link | `/invite` | B | miss |
| AC2 | Roles | owner / editor / viewer | H | miss |
| AC3 | Presence avatars | who is in the project | B | miss |
| AC4 | Live cursors | realtime positions | ? | miss |
| AC5 | Comments | per clip / timeline | B | miss |
| AC6 | Comment notifications | badges | ? | miss |
| AC7 | Edit locks | prevent concurrent edit | ? | miss |
| AC8 | Fork shared project | `/shares/{token}/fork` | B | part |
| AC9 | Remove member | revoke access | ? | miss |

---

## AD. Notifications & activity

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AD1 | Saved toast | after autosave | H | miss |
| AD2 | Conflict banner | newer version | B | miss |
| AD3 | Generation queued | "adding part…" | H | miss |
| AD4 | Generation failed | reason + retry | H | miss |
| AD5 | Export ready | download link | H | miss |
| AD6 | Stems ready | notification | H | miss |
| AD7 | Activity feed | project history | ? | miss |

---

## AE. Onboarding

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AE1 | "What's This?" card | first-run tip | H | miss |
| AE2 | Dismiss / Turn off | hide tour | H | miss |
| AE3 | Learn button | help entry | H | miss |
| AE4 | Empty-project coach | "Select a spot…" | H | miss |
| AE5 | Tooltips on tools | hover hints | H | miss |

---

## AF. Accessibility & keyboard navigation

| # | Item | Expectation | Ev | Cam |
|---|---|---|---|---|
| AF1 | Focus order | header → tracks → timeline → prompt | H | part |
| AF2 | Visible focus ring | all interactive | H | part |
| AF3 | ARIA roles | toolbar/menu/dialog | H | part |
| AF4 | Keyboard reachable clips | tab into timeline | ? | miss |
| AF5 | Screen-reader labels | icon-only buttons | H | part |
| AF6 | Reduced motion | no autoplay animation | H | miss |
| AF7 | Contrast | ≥4.5:1 body text | H | done |
| AF8 | Zoom 200% | layout still usable | H | part |

---

## AG. Limits & performance

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AG1 | Max tracks | cap per project | ? | miss |
| AG2 | Max clips | cap per project | ? | miss |
| AG3 | Max project length | minutes | ? | miss |
| AG4 | Timeline virtualisation | long projects | ? | miss |
| AG5 | Save payload size | large state | ? | miss |
| AG6 | Concurrent edits | conflict strategy | B | blk |

---

## AH. Loading / empty / error per panel

| # | Panel | Loading | Empty | Error | Cam |
|---|---|---|---|---|---|
| AH1 | Landing projects | skeleton | "No projects yet" | retry | part |
| AH2 | Landing songs | skeleton | "No songs" | retry | part |
| AH3 | Project document | spinner | — | "failed to load" | miss |
| AH4 | Timeline | skeleton | "Add a track" | retry | part |
| AH5 | Library drawer | skeleton | per-tab copy | retry | part |
| AH6 | Save | saving… | — | conflict banner | blk |
| AH7 | Export | rendering… | — | moderation msg | miss |

---

## AI. Search & discoverability

| # | Item | Behaviour | Ev | Cam |
|---|---|---|---|---|
| AI1 | Landing song search | filters list | H | done |
| AI2 | Library drawer search | filters drawer | H | miss |
| AI3 | Timeline search | find clip | H | miss |
| AI4 | Command palette | ⌘K | ? | miss |
| AI5 | Recent/favourites | quick access | ? | miss |

---

## Capture checklist (round 4)

| Target | Capture in Suno Studio |
|---|---|
| Clip properties panel | select a clip, inspect right panel |
| Track context menu | right-click a track header |
| Mixer / FX racks | open mixer, add an effect |
| Project settings | project menu → settings |
| Upload flow | drag a file onto the canvas |
| Collaboration | invite a second account, watch presence/comments |
| Onboarding | fresh account, first Studio visit |
| Limits | try adding many tracks/clips until refused |
| Command palette | ⌘K |
