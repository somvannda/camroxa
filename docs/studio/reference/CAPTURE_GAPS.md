# CAPTURE GAPS — what was not captured, and why

Companion to `SCREEN_MANIFEST.md` and `SCREENSHOT_INDEX.md`. Everything **DONE** has
an image and a measured spec section. This file exists so the remainder is not a vague
backlog: each row says what is missing and what would unblock it.

As of 2026-10-31: **47 DONE · 5 PART · 13 OPEN**, 60 images, spec through §85.

## Group A — one generation away (5 screens)

All five are blocked by the same thing: `Drum & Bass Demo` is a **legacy project**
whose source audio is not materialised in Studio, so it can neither export nor
generate (§77). Evidence: `EXTRA-project-load-error.jpeg`,
`EXTRA-generation-refused-legacy.jpeg`.

| Screen | Missing | Unblock |
|---|---|---|
| S29 | take lanes with actual alternates | regenerate a clip over itself in a new project |
| S32 | a CC lane with points | same project, then draw points in `Modulation` |
| S37 | generation result on the timeline | any successful generation |
| S50 | export dialog | export from a Studio-native project |
| S51 | export progress + result | same |

**One action clears all five:** new empty project → send one short prompt.

## Group B — needs a forced state (3 screens)

| Screen | Why not captured | Unblock |
|---|---|---|
| S59 | save conflict needs two writers | two tabs on one project, edit both, wait for autosave |
| S60 | moderation refusal needs a policy trigger | do not fabricate; capture if it happens naturally |
| S61 | insufficient credits needs a spent balance | low-credit account, or a very large request |

## Group C — needs a second session or an absent feature (2 screens)

| Screen | Why not captured | Unblock |
|---|---|---|
| S56 | shared project page is the **public** view | share a project, open the link logged out |
| S62 | PART: no offline affordance exists on the tested path (§82) | cold-load while offline to confirm absence |

## Group D — UI the demo does not expose (8 screens)

| Screen | Tried | Why it failed |
|---|---|---|
| S30 warp markers | double-click clip, `Clip editor`, Clip Settings | audio editor opens as Clip Settings (§81); no warp marker or warp toggle was ever rendered |
| S46 preset browser | preset chip, `None` selector | the chip is a dirty indicator with `Update`; the selector lists **sidechain routing**, not presets (§83) |
| S47 mixer strips | footer tools, `Main`, panel toggles | no mixer surface was found in any footer or panel state |
| S48 master limiter | select `Main`, Add effect | selecting `Main` never switches the chain chips, so a plugin cannot be added to master |
| S54 clip permissions | Share dialog | the dialog only offers view + fork-to-copy; no per-clip permission control surfaced |
| S58 empty library | search nonsense + Enter | the library **home** does not filter; no zero-results state exists |
| S44 | Add effect → Convolution | PART: card captured without an impulse response loaded |
| S45 | Create new plugin | PART: design-mode prompt captured; the designer surface needs a successful generation |

## What a next session should do first

1. **Create a new project and generate one short loop** → clears Group A (5 screens).
2. Share that project and open the link in a logged-out tab → clears S56.
3. Re-attempt Group D with a **fresh project**: several of them (S30, S47, S48, S54)
   may simply be surfaces that a legacy demo project does not provide, and the answer
   may be "not present on this project type" rather than "not captured".

Do not re-spend time on the eight dead ends listed in `SESSION_HANDOFF.md`.
