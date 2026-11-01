# CAPTURE GAPS — what was not captured, and why

Companion to `SCREEN_MANIFEST.md` and `SCREENSHOT_INDEX.md`.

**Final state: 60 DONE · 3 PART · 2 OPEN** of 65. Spec through §96, 69 images.

Everything `DONE` has an image and a measured section — including six captured
**negatives** where the screen we expected does not exist (S47 mixer, S50/S51 export
dialog, S54/S56 sharing, S59 conflict, S62 offline).

## One insight worth carrying forward

`Drum & Bass Demo` is a **legacy project**: it cannot export or generate (§77).
Opening an `Untitled Project` from the library fixed both instantly, which is what
cleared S37, S29, S50/S51 and S45. **Any future capture involving export, generation,
takes or plugins must start from a native project.**

## The 5 that remain

| Screen | State | Exactly what is missing |
|---|---|---|
| S30 warp markers | PART §94 | The system is captured (Stretch modes with "Markers placed on transients and note starts"), but no marker ticks ever drew — tried at 174 BPM source and at 110 BPM project tempo. Two possibilities recorded: markers need a **stretched** clip (source BPM ≠ project BPM *and* stretch enabled on that clip), or marker drawing is not shipped. |
| S32 CC lane | PART §74 | The `Modulation` lane renders but accepts no drawn points; needs a workflow we have not found (likely a modifier or a right-click). |
| S44 convolution IR | PART §78 | The IR slot opens nothing when clicked; it needs an **impulse-response file** dropped or chosen. |
| S60 moderation | OPEN | Needs a policy-violating prompt. **Do not fabricate** — capture it only if it happens naturally. |
| S61 credits | OPEN | Needs an account with no credits. Ours has balance, so this cannot be produced honestly. |

## If a next session wants to finish them

1. **S44** — drop any short WAV onto the Convolution slot; if drag-and-drop works the
   card fills in and the screen is done.
2. **S30** — enable stretch on a clip, then change the project tempo by a large step
   *while the clip editor is open*, and inspect the waveform at 2× zoom.
3. **S32** — try right-click, alt-drag and double-click in the lane; one of them is
   the draw gesture.
4. **S60 / S61** — only with a genuine trigger. Both would be captured as
   "error taxonomy" evidence, not as a screen we can stage.

## Editing caveat

While testing warping, the `Drum & Bass Demo` tempo was changed from **174 → 110 BPM**
and left there. It is a library copy; revert with the tempo popover or `CTRL Z`.
