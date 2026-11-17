# S61 — the captured "You're out of credits" modal

**Date:** 2026-11-17
**Agent:** S61 implementation (`feat/credits-modal`)
**Base:** `origin/main` @ `c5390ef1` ("fix(studio): kHz readouts, 768 header fit, and a dock placeholder for popped slots")
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-credits`
**Reference frame:** `docs/studio/reference/screens/S61-insufficient-credits.jpeg` (1440×900)
**Ledger row:** `docs/studio/reports/2026-11-17-pixel-adjudication.md` row 45 (S61, LAYOUT 12.67) and ranked fix #1.

**Result:** the modal exists, opens on a refused generate, and matches the frame's
anatomy. 402 Vitest cases pass, `tsc --noEmit` is clean, the Playwright spec was written
but not run (per instructions: no servers, so no `npm run dev` on 3103).

---

## 1. What the frame shows

The capture is the Create page with a centered dark card over a dimmed workspace:

| Region | Frame |
|---|---|
| Card | ~496×533 px, 20 px radius, near-black (`#1b1b1b`) on a 60% scrim, no visible border |
| Close | 36 px circular ghost button, top-right, `×` glyph |
| Title | `You're out of credits` — ~30 px, bold, left-aligned, straight apostrophe |
| Meter | `Monthly credits used` (11 px, muted) left, `100%` (magenta) right; 4 px full-width track, filled 100% in magenta |
| Body | Three lines: "Get back to creating. We'll top up your credits right away and automatically when they run low. Uses your saved payment method — cancel anytime." (13 px, muted, left) |
| Caption | `Auto-reload amount` (12 px, centered) |
| Stepper | 32 px outlined `−` circle · `$6` (~34 px bold) · 32 px outlined `+` circle, 22 px gaps |
| Accent line | `Better value than one-time credit packs` (12 px, magenta, centered) |
| Primary CTA | Full-width 48 px white pill, dark text, `Turn on auto-reload` |
| Dismiss | `Not now` (13.5 px, centered, ghost) |

Order, alignment, and the two-line label/value meter row are the parts the adjudication
scores; the pink hue is Suno's brand, not ours.

## 2. What was implemented

### 2.1 Component

New `camxora.com/components/CreateCreditsModal.tsx` (parent renders it only while open):

- **Title / close / body / meter / caption / stepper / accent line / switch / CTA / Not now**
  in the frame's order, with dedicated `.s-credits-*` classes in
  `camxora.com/app/globals.css` (card 480 px, 20 px radius, 28 px title, 48 px white pill).
- **Price is data, never the frame's `$6`.** Packs come from
  `fetchCreditPacks()` → `GET /api/v3/topups/packs/public`. That endpoint returns the three
  web-music packs seeded by `platform_api/migrations/versions/127_web_music_plans_v2.py`:
  Small **$5** / Medium **$10** / Large **$30**. The stepper therefore shows `$5`, `$10`,
  `$30` on this build. `formatPackPrice()` renders the API's `price_cents`; no price string
  is hard-coded anywhere in the component.
- **Stepper bounds** are `1 … packs.length` (currently 3) — `−` is disabled on the first
  pack, `+` on the last. It selects the pack tier because `POST /api/v3/topups/purchase`
  accepts exactly one `pack_slug` per checkout (see §3.1).
- **Meter** = `creditsUsedPercent(creditsRemaining, creditAllowance)` from auth; the frame's
  100% is reproduced whenever the balance cannot cover a song (that is the only way the
  modal opens), and a partial spend shows its true percentage.
- **Purchase** reuses the existing flow verbatim from `PricingView.startPack`:
  `purchaseTopup(pack.slug)` → store `camxora:checkout-payment` → `window.location.assign`
  to the CutLuy/ChmabaPay checkout URL returned by the API. No new payment path, no new
  provider, no card fields.
- **Auto-reload switch** uses the existing Radix `Switch` (`components/ui/switch.tsx`),
  labelled `Turn on auto-reload`, wired to `sessionStorage` via
  `readAutoReloadPreference` / `writeAutoReloadPreference` (key `camxora:credits-auto-reload`).
  Because the platform exposes no auto-reload capability it is rendered **disabled** with
  `title="Auto-reload isn't configured for this account yet"` plus a visible note, exactly
  as the brief asks for an unsupported capability (see §3.2).
- **Accessibility:** `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → the `<h2>`
  title (which is the initial focus target, `tabIndex={-1}`), Escape closes, scrim click
  closes, body scroll locks, Tab is trapped inside the dialog, the meter is a
  `role="progressbar"` with `aria-valuenow`, and every control has a name.

### 2.2 Wiring in `CreateStudio.tsx`

- `creditsGateOpen` state and the render site next to the other dialogs.
- **Server refusal:** the `generate` catch now calls `isCreditsRefusal(cause)` (new helper in
  `lib/studio-errors.ts`). A 402, or a 429 whose body/code names credits, opens the modal
  after refreshing the quota. A 429 that is only throttling (`RATE_LIMITED`) keeps the
  existing toast/inline path — `api/v3/web-music/generate` can surface the pooled provider's
  billing stop as 429 (`platform_api/services/key_pool_service.py`), which is why both
  statuses are handled.
- **Pre-flight:** a single song the balance cannot cover also opens the modal from
  `onSubmit`. `createDisabled` no longer counts `needsCredits` for a single song (it still
  blocks batches), so the click lands on the modal instead of a dead button — the frame's
  form is likewise usable.
- The inline line stays as trigger context
  (`Not enough credits for this selection. Top up or buy packs`), with **Top up** opening the
  same modal.

## 3. What could not be wired, and why

### 3.1 Stepper is a pack selector, not a quantity multiplier

The frame's `$6` stepper multiplies a recurring amount (`$6 → $12 → $18`). CAMXORA sells
discrete packs and `POST /api/v3/topups/purchase` takes a single `pack_slug` with no
`quantity` or `amount` field (`platform_api/routers/v2_topups.py`,
`PurchaseTopupRequest`). A multiplier would require inventing a multi-checkout/payment path,
which the brief forbids. The stepper therefore moves between the real packs, and the big
number is always the API price of the selected pack. To make it a true throttle, the
platform would need a `quantity`/`amount_cents` field on the purchase request.

### 3.2 No auto-reload capability exists

There is no recurring top-up endpoint, no saved-method mandate, and no auto-reload column in
`credit_packs`/`plans`/`topup_purchases`. The switch is rendered **disabled** with the
explanation; the session helpers are in place and unit-tested so enabling it later is a
one-constant change (`AUTO_RELOAD_SUPPORTED` in `components/CreateCreditsModal.tsx`).

### 3.3 Price differs from the frame on purpose

The capture's `$6` is Suno's amount. Our public pack ladder is `$5 / $10 / $30`; showing `$6`
would be a price we cannot charge. The report records the delta; the anatomy (stepper,
amount weight/position, accent line) matches.

### 3.4 Copy and colour deltas

- Primary pill reads **`Buy credits`**, not `Turn on auto-reload`: purchasing is what the
  button actually does (there is no auto-reload to turn on), and `Turn on auto-reload` is
  now the labelled switch above it. A pill that claimed to enable a non-existent
  subscription would be a false affordance.
- The frame's body copy promises automatic top-ups and a saved payment method
  ("…cancel anytime."). Our body keeps the frame's shape but states what is true: one-time
  packs, 30-day validity.
- The meter, accent line, and progress fill use our `--s-accent` purple instead of Suno's
  pink, consistent with the rest of the Studio surface.

## 4. Tests

| Where | What | Result |
|---|---|---|
| `camxora.com/tests/studio-credits-modal.test.tsx` | price formatting, meter math, pack clamping, session persistence; modal anatomy, disabled auto-reload switch + title, stepper bounds, focus-to-title, Escape, Not now / close, checkout for the selected pack, pricing-failure alert | 11 passed |
| `camxora.com/tests/studio-errors.test.ts` | `isCreditsRefusal`: 402, credit-flavoured 429, plain rate-limit 429, message-only, null | 6 passed (1 new case) |
| `camxora.com/tests/e2e/studio-credits-modal.spec.ts` | mocks `generate` → `429 {"error":{"message":"Insufficient credits."}}` plus quota and packs; asserts anatomy, stepper `$5→$10→$30`, Not-now dismissal (form still editable, Create live), Escape, and the zero-balance pre-flight (no generate call) | written, **not run** |

Commands run in the worktree (`camxora.com/`):

```
npm ci                       → 272 packages
npm run typecheck            → clean
npx vitest run               → 53 files, 402 tests passed
```

Playwright was not run: the brief forbids starting servers/ports, and the spec needs the
dev server on 3103 plus the sandbox account from `tests/e2e/studio-fixture.ts`.

## 5. Files

- `camxora.com/components/CreateCreditsModal.tsx` (new)
- `camxora.com/components/CreateStudio.tsx` (trigger wiring, quota refresh, inline trigger, `createDisabled`)
- `camxora.com/lib/studio-errors.ts` (`isCreditsRefusal`)
- `camxora.com/app/globals.css` (`.s-credits-*`)
- `camxora.com/tests/studio-credits-modal.test.tsx` (new)
- `camxora.com/tests/studio-errors.test.ts`
- `camxora.com/tests/e2e/studio-credits-modal.spec.ts` (new)

## 6. Follow-ups

1. Add `quantity`/`amount_cents` (or a saved-method auto-reload mandate) to
   `POST /api/v3/topups/purchase`, then flip `AUTO_RELOAD_SUPPORTED` and drop the extra
   stepper comment in §3.1.
2. Run `npx playwright test tests/e2e/studio-credits-modal.spec.ts` against the local stack
   and re-capture S61 for the pixel ledger.
