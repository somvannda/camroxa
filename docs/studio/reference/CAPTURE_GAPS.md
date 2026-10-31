# CAPTURE GAPS — what was not captured, and why

Companion to `SCREEN_MANIFEST.md` and `SCREENSHOT_INDEX.md`. Every **DONE** row has an
image and a measured spec section.

As of the latest pass: **51 DONE · 4 PART · 10 OPEN**, spec through §87.

## Cleared on a Studio-native project

The decisive finding of this pass: opening an `Untitled Project` from the library
(not the legacy demo) made generation work, which cleared **S37** (§86) and **S29**
(§72.1 — two takes, commit/audition), and proved that **S50/S51 do not exist as
dialogs** (§87): export fires and forgets, with a toast as the only feedback.

The same test also closed one question permanently: the earlier export/generation
failures were the **project**, not the feature.

## Still PART

| Screen | Missing | Unblock |
|---|---|---|
| S32 | a CC lane with points | generate a part, then draw in `Modulation`; the lane still accepted no points on click |
| S44 | Convolution with an IR loaded | needs an impulse-response file; clicking the slot opens nothing without one |
| S45 | the designer surface | needs a successful `Make me a new plugin` generation |
| S62 | offline confirmation | cold-load while offline to prove §82 is a real absence |

## Still OPEN

| Screen | Why | Unblock |
|---|---|---|
| S30 warp markers | no warp marker or warp toggle rendered on an audio clip (native or legacy); `Clip editor` shows Clip Settings (§81) | find the warp entry point — possibly only on time-stretched clips |
| S46 preset browser | `None`/`Custom` are native selects and sidechain lists; no preset list opens | open a plugin's preset list from a saved custom preset |
| S47 mixer strips | no mixer surface found in any footer or panel state | confirm whether a mixer exists at all |
| S48 master limiter | `Main` cannot be selected, so no plugin can be added to master | select master another way, or confirm it is not supported |
| S54 clip permissions | Share dialog only offers view + fork-to-copy | share a clip, not a project |
| S56 shared project page | needs the public link opened logged out | copy link, open in a logged-out session |
| S58 empty library | home does not filter; no zero-results state | search inside a workspace's song list |
| S59 save conflict | needs two writers | two tabs on one project, edit both |
| S60 moderation refusal | needs a policy trigger | do not fabricate; capture if it happens |
| S61 insufficient credits | needs a spent balance | low-credit account |

## Next moves, in order of payoff

1. **Draw in the `Modulation` lane** on the native project → closes S32.
2. **Load any IR** (a short WAV) into Convolution → closes S44.
3. **Two tabs on the same project** → likely closes S59.
4. Open a **workspace's song list** and search nonsense → closes S58.
5. Share a **clip** (not the project) → S54; then open the link logged out → S56.
