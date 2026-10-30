# Studio audit — ten further rounds (R5–R14)

Ten more lenses, each audited separately. `?` = not captured; nothing ships
without evidence (see `docs/studio-1to1.md`).

---

## R5 — First-run experience

| # | Case | Expectation | Ev | Cam |
|---|---|---|---|---|
| R5.1 | New account, no songs | landing explains how to make one | H | part |
| R5.2 | First Studio visit | "What's This?" tour | H | miss |
| R5.3 | No projects | resume column shows only "New empty project" | H | done |
| R5.4 | Plan without Studio | upgrade prompt, not an empty editor | H | n/a (credits) |
| R5.5 | Signed out | redirect to sign-in, return to Studio | H | done (site gate) |
| R5.6 | Returning user | resumes last project | H | part |
| R5.7 | Slow first load | skeleton, not blank canvas | H | part |

## R6 — Copy & microcopy

| # | Surface | Text to match | Ev | Cam |
|---|---|---|---|---|
| R6.1 | Resume heading | "Pick up where you left off" | H | done |
| R6.2 | Songs heading | "Or start from one of your songs" | H | done |
| R6.3 | Search placeholder | "Search your songs…" | H | done |
| R6.4 | Empty project | "Add new track" | H | done |
| R6.5 | Prompt placeholder | "Select a spot on the timeline and ask me to add a part" | H | done |
| R6.6 | Project pill | "No project loaded" | H | done |
| R6.7 | Save states | saving / saved / conflict | ? | miss |
| R6.8 | Error copy | moderation, credits, conflict | ? | part (credits) |
| R6.9 | Tooltips | each toolbar icon | ? | miss |

## R7 — IA & navigation

| # | Item | Expectation | Ev | Cam |
|---|---|---|---|---|
| R7.1 | `/studio` | landing | H | done |
| R7.2 | Project open | `/studio/{id}` or `?project=` | ? | part |
| R7.3 | Back button | returns to landing | H | part |
| R7.4 | Library link | opens library | H | done |
| R7.5 | Editor link | song editor from Edit menu | H | part |
| R7.6 | Share link | read-only view | B | miss |
| R7.7 | 404 project | clear not-found | ? | miss |

## R8 — Data lifecycle

| # | Stage | Expectation | Ev | Cam |
|---|---|---|---|---|
| R8.1 | Create | project on Suno | B L | done |
| R8.2 | Add clip | membership persisted | B | done |
| R8.3 | Arrange | persisted via save-project | B | blk |
| R8.4 | Version | new version per edit burst | B | blk |
| R8.5 | Restore | clone a revision | B | miss |
| R8.6 | Export | render → download | B | blk |
| R8.7 | Archive | hidden from active list | B | miss |
| R8.8 | Delete | removed + confirm | H | miss |
| R8.9 | Trash | recoverable | B | miss |
| R8.10 | Purge | permanent | H | miss |

## R9 — Concurrency & sync

| # | Case | Expectation | Ev | Cam |
|---|---|---|---|---|
| R9.1 | Two tabs same project | conflict detected | B | blk |
| R9.2 | Conflict resolution | reload latest, replay | B | blk |
| R9.3 | Rapid edits | debounce, one save | B | blk |
| R9.4 | Save while offline | queued or clear error | ? | miss |
| R9.5 | Second collaborator | presence + locks | B | miss |
| R9.6 | Stale project tab | refresh prompt | ? | miss |
| R9.7 | Reload mid-edit | dirty changes warned | ? | miss |

## R10 — Error taxonomy → UI

| # | Status | Meaning | UI | Cam |
|---|---|---|---|---|
| R10.1 | 401 | session expired | re-auth prompt | part |
| R10.2 | 402/credits | no credits | block + buy link | done |
| R10.3 | 403 | not your project | hide/deny | miss |
| R10.4 | 404 | project gone | not-found | miss |
| R10.5 | 409 | version conflict | reload banner | miss |
| R10.6 | 422 | invalid payload | inline reason | miss |
| R10.7 | 429 | too many saves | silent back-off | miss |
| R10.8 | 5xx | provider down | retry toast | part |
| R10.9 | moderation | content refused | message + reason | miss |

## R11 — Performance budgets

| # | Path | Budget | Ev | Cam |
|---|---|---|---|---|
| R11.1 | Landing first paint | < 1.5 s | ? | part |
| R11.2 | Project open | < 2 s | ? | miss |
| R11.3 | Clip drag | 60 fps | ? | part |
| R11.4 | Timeline with 50 clips | smooth scroll | ? | miss |
| R11.5 | Save round-trip | < 800 ms | ? | blk |
| R11.6 | Audio start | < 300 ms | ? | part |
| R11.7 | Library 500 songs | virtualised | ? | miss |

## R12 — Security & permissions

| # | Item | Expectation | Ev | Cam |
|---|---|---|---|---|
| R12.1 | Auth on every route | session required | H | done |
| R12.2 | Project ownership | cannot open others' | B | part |
| R12.3 | Share token scope | read-only vs fork | B | miss |
| R12.4 | Rate limits | per user, per action | B | part |
| R12.5 | No provider URLs in browser | proxy only | H | done |
| R12.6 | Pool account isolation | one account can't read another's project | ? | blk |
| R12.7 | Audit trail | log project actions | ? | miss |

## R13 — Observability

| # | Event | Why | Ev | Cam |
|---|---|---|---|---|
| R13.1 | project.created | funnel | ? | miss |
| R13.2 | project.opened | engagement | ? | miss |
| R13.3 | clip.added / removed | usage | ? | miss |
| R13.4 | save.ok / save.conflict / save.throttled | sync health | ? | miss |
| R13.5 | export.started / completed / failed | revenue + reliability | ? | miss |
| R13.6 | generation.failed | provider health | ? | miss |
| R13.7 | latency per route | SLOs | ? | part (API access log) |

## R14 — QA test matrix

| # | Axis | Cases | Cam |
|---|---|---|---|
| R14.1 | Accounts | no credits, with credits, expired session | part |
| R14.2 | Projects | empty, with clips, many clips, archived | miss |
| R14.3 | Devices | 1280, 1440, 1920, 375 (mobile) | part |
| R14.4 | Browsers | Chrome, Edge, Firefox, Safari | miss |
| R14.5 | States | loading, empty, error, offline, conflict | part |
| R14.6 | Flows | F1–F15 smoke pass | part |
| R14.7 | A11y | keyboard-only pass, SR labels | miss |
| R14.8 | Regression | Studio vs Suno side-by-side screenshots | miss |

---

## What these rounds change about implementation order

1. **R10 (errors) + R9 (sync)** must land with the save loop — shipping autosave
   without conflict/429 handling would be worse than shipping none.
2. **R14.2/R14.5** become the release gate: empty, many-clip and conflict states
   tested before Studio is called "done".
3. **R12.6** is a real risk to verify: all our Studio projects live on one pool
   account, so ownership checks must be enforced by Camxora, not Suno.
4. **R13** is cheap: emit events from the platform proxy we already own.
