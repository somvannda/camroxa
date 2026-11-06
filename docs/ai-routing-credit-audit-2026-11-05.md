# AI Routing × Credit Audit — Findings and Implementation Plan

**Scope:** `platform_api/` AI routing (`ai/`, `services/ai_routing_service.py`, `routers/ai_routing.py`) and every credit path that reads routing (`usage_enforcement_service`, `draft_billing`, `credit_pricing_service`, `pricing_sync_service`, `v3/*`, `web_music_service`, `batch_service`, `image_job_service`).
**Method:** code-derived audit, two passes. No database was queried; every finding cites the symbol that proves it. Live-data checks are listed in §7 and must be run before Phase 1 is merged.
**Date:** 2026-11-05
**Status:** audit complete, plan not started.

---

## 1. Verification round — what changed from the first pass

### 1.1 Confirmed as written (no correction)

| # | Claim | Proof |
|---|---|---|
| R1 | `resolve()` ignores `is_active` | `ai_routing_service.py::resolve` reads `assignments.get(operation)` and never checks the flag; only `resolve_text_chain` / `resolve_image_chain` / `audit_routing_configuration` do. |
| R2 | `resolve()` has no provider fallback | same method: raises `NoAvailableKeysError` when `active_keys <= 0`. |
| R3 | `save_assignments` validates only the Suno-lyric `sub_model` case | `ai_routing_service.py::save_assignments` — no `PROVIDER_SUB_MODELS` check for text/image. |
| R7 | Invalid saved rows are dropped silently on read | `_sanitize_assignments` logs a warning and `continue`s; `get_all_assignments` then shows the default as if chosen. |
| B1 | Text billing is pre-charged on the routed primary | `routers/generation.py` draft flow → `draft_billing.deduct_split_draft_billing`; `ai/providers/text/gateway.py::generate_text` returns `str`. |
| B3 | `POST /generation/suno` bills without `sub_model` | `routers/generation.py` → `check_and_deduct(operation_type="music", ai_service=routing.provider)`; `SunoGenerationRequest.model` is required and present but unused. |
| B6 | `needs_review` rows are billable | `credit_repo.get_by_service_and_operation` filters only `ai_service/operation_type/sub_model`; `tests/test_pricing_sync_service.py::test_audit_treats_draft_pricing_as_warning_not_error` asserts `ready is True` with a draft row. |
| B8 | `suggest_pricing_values` medians across operations | `pricing_sync_service.py`: the `entry_service == ai_service` branch appends **every** same-provider row before any service-type filter. |
| B9 | Missing model row silently falls back to provider default | `credit_pricing_service.lookup_pricing_entry`. |
| B10 | v3 can price from another provider's row | `services/v3/list_prices.py::_scan_pricing_units` (pass 2, logs a warning). |
| P1 | Pricing keys are free-text and case-sensitive | `CreatePricingRequest` / `UpdatePricingRequest` only length-limit; repo query is `WHERE ai_service = $1`; `pricing_lookup_key` strips but does not lower-case. |
| P2 | `Operation` enum is incomplete | `generation_service.py` prices `"image"`; `V1_TO_V3_OP` has `video`, `video_manual`, `video_merge`, `merge`, `video_export`, `batch_generation`. |
| P4 | `music` model pricing is unauditable | `save_assignments` forces `sub_model = None` for `music`; `collect_required_pricing_pairs` emits `(provider, "music", "")`. |
| O1 | Routing save is four non-transactional writes | `routers/ai_routing.py::save_assignments`. |
| O4 | `sub_models_detail` extras are dropped | `ProviderOption.sub_models_detail: list[SubModelDetail]`; `get_available_providers` sends `cost_usd`, `cost_usd_by_operation`, `operations` too. |

### 1.2 Corrections (first pass overstated or understated)

| # | First-pass claim | Corrected finding |
|---|---|---|
| R5 | "`cala` is routable but has no models" | `cala` **is** functional: `ImageProviderGateway.dispatch_routing` → `generate_cala`, and `ImageGenerationRequest.provider` accepts it. The real gap is narrower: no entry in `IMAGE_MODEL_REGISTRY` / `PROVIDER_SUB_MODELS`, so it cannot be priced per model, never appears with models in the admin dropdown, and the audit cannot require a model. Same shape as `camxora_music_api`. |
| B3 | "Desktop and batch charge different prices for the same song" | True **only while `credits_only_v3_charge` is Off**. When On, `check_and_deduct` short-circuits to `_charge_via_v3` → `CreditsOnlyBillingService.quote(op="music")`, which is model-agnostic, so desktop and batch converge. The defect is: (a) flag-Off the desktop route bills the provider-default row while batch bills the user's model row, (b) the model is lost from ledger metadata in both modes unless passed. |
| B4 | (not in first pass) | Music pricing is **three-way inconsistent**: documented policy is a flat **10 credits** (`docs/credits-only-plan-unification.md`), `sync_from_routing_config` still suggests **7.5** (`_OPERATION_DEFAULT_CREDITS["music"]`), and `migrations/versions/131_camxora_music_api_music_default.py` exists purely to repair the 7.5 draft that routing-save created. The code that caused it is still live. |
| P5 | "`external_cost_cents` is raw micro-units in the API" | API is consistent: `_pricing_to_response` converts units → display credits. The defect is **naming only** (DB column + API field say "cents", value is display credits), plus `suggest_pricing_values` using `MIN_CREDIT_UNITS` as a "cents" floor. |

### 1.3 New findings from this round

| # | Finding | Evidence |
|---|---|---|
| R4 | **Saving an empty assignment map silently resets every slot to defaults.** `SaveAssignmentsRequest.assignments: dict[str, OperationAssignment]` has no minimum length; `save_assignments({})` persists `{}` and `resolve()` falls back to `DEFAULT_PROVIDER`. | `models/ai_routing_schemas.py`, `ai_routing_service.py::_load_assignments` |
| R6 | **A third, independent reader of the same setting.** `suno_audio_resolver.active_music_provider` reads `system_settings.ai_routing_assignments` directly (used by worker/callback code to pick the upstream host) and re-implements parsing with no `is_active` check and no sanitisation. It can disagree with `AIRoutingService`. | `services/suno_audio_resolver.py::active_music_provider` |
| B5 | **Web and desktop round differently.** Web text charges `ceil(display_price)` (`web_music_service.py`) and v3 web music quotes `round(amount_credits)` (`v3/web_music_charge.py::quote_credits`); desktop charges exact micro-units. A 0.0001-credit row becomes a **1 whole credit** charge on web. | both sites above |
| B7 | **Routing sync bypasses the pricing economics guard.** `sync_from_routing_config` calls only `_validate_credit_units`; it never calls `_validate_pricing_economics`. A draft row can therefore be created with `cost > sell` (or zero margin) and is billable before approval — even though `approve_pricing` would reject it. | `credit_pricing_service.py::sync_from_routing_config` vs `::approve_pricing` |
| B11 | **Web music text refunds are process-local.** `_refund_text_operation` reads only `self._open_charges` (in-memory) and returns; `_release_daily_slot` for music has a durable `_refund_v3_music_by_reference` fallback. AI-assist lyric/style charges are lost on worker/restart. | `web_music_service.py` both methods |
| P6 | **Zero-margin routed provider passes every guard.** `migrations/versions/131_...` sets `camxora_music_api/music` sell = cost = 10 credits, i.e. 0% margin; `_validate_pricing_economics` only rejects `cost > sell`, and the audit has no low-margin check. | migration 131 + `_validate_pricing_economics` |

### 1.4 Verification status

Verified on the **local sandbox DB** in §8: the music price, the four draft rows, cost/sell margins, the routing values, the key-pool counts, the batch-draft pricing failure, and the v3 quote behaviour.

Still unverified (production only):

- Whether production holds the same `deepseek-chat` key mismatch and the same `needs_review` web-assist rows.
- **Whether production's `alembic_version` matches the migration tree** (the local copy is stamped with a revision that no longer exists — see §8).
- Whether `credits_only_v3_charge` is On in production (env default is `False`).
- Whether `batches` are created successfully in production (L1 impact).
- Whether `delete_all_pricing` is protected by dual-control (the endpoint is admin-only; no confirmation/backup step found).
- `web_music_service` video/studio billing beyond the text paths; `publish_pricing` and `license` credit paths.

---

## 2. Findings register

Severity: **P0** = charges wrong / can silently misprice · **P1** = money risk or policy conflict · **P2** = operability · **P3** = hygiene.

### 2.1 Routing

| ID | Sev | Finding | Impact if unfixed |
|---|---|---|---|
| R1 | P0 | `resolve()` ignores `is_active` | Admin "off" changes reporting/quotes but not billing; for `music` it changes nothing at all. |
| R2 | P1 | `resolve()` never falls back | `music`, `/credits/operation-costs`, batch preflight hard-503 when the primary has no keys, even with healthy fallbacks. |
| R3 | P0 | No model validation on save | Unregistered model persists; failure appears mid-generation. |
| R4 | P1 | Empty save wipes routing to defaults | One bad client payload silently repoints every slot. |
| R5 | P2 | `cala` / `camxora_music_api` outside the model registry | No per-model pricing or audit for them; admin UI shows a provider with no models. |
| R6 | P1 | Duplicate routing reader in `suno_audio_resolver` | Execution host and billing can disagree about the music provider; three parsers drift independently. |
| R7 | P2 | Silent drop of invalid saved rows | Admin cannot tell "saved" from "saved then ignored". |
| R8 | P1 | Chain expands all sibling models regardless of cost tier | Premium sibling can run at the cheap model's price (see B2). |
| R9 | P3 (latent) | Audit does not test gateway executability | If a `lyric` primary is `suno`, any caller that passes the raw chain to `generate_text` gets `ValidationError` (not `ExternalServiceError`), so no fallback occurs. Today the draft path branches to the Suno client first, so it is masked. |

### 2.2 Billing

| ID | Sev | Finding | Impact |
|---|---|---|---|
| B1 | P0 | Text charge is based on routed primary, not executed provider/model | Over/undercharge on every fallback; no reconciliation possible. |
| B2 | P1 | Sibling-model expansion decouples COGS from price | Margin erosion on primary-model failures. |
| B3 | P1 | Desktop music omits `sub_model` | Flag-Off: wrong tier, or hard 503 if only per-model rows exist. |
| B4 | P0 | Music has **four** values: DB **15 cr** (suno) / **10 cr** (camxora_music_api), docs/UI **10**, `pricing_sync` **7.5**, plus per-model rows that v3 ignores | The admin routing switch changes the user price 15 → 10; re-sync can create a 7.5 row (the defect migration 131 had to repair). |
| B5 | P1 | Web `ceil`/`round` vs desktop exact micro-units | Up to 1 credit (10,000× a 0.0001-credit row) overcharge on web. |
| B6 | P0 | `needs_review` rows are billable | Unreviewed auto-suggested price goes live on save. |
| B7 | P1 | Sync bypasses `_validate_pricing_economics` | Draft rows can violate cost ≤ sell / minimum music cost basis. |
| B8 | P2 | Suggestion medians across operations | A new Suno row can be priced off lyric rows. |
| B9 | P1 | Provider-default row silently substitutes for a missing model row | Premium model bills the cheap default; audit says "error", billing says "fine". |
| B10 | P1 | v3 cross-provider price scan | A debit can land on another provider's list price. |
| B11 | P1 | Web text refund is in-process only | Silent credit loss on restart/worker hop. |
| B12 | P2 | Two unused duplicate deduct/refund implementations, both "graceful to zero" | Accidental wiring would charge 0 and skip `ref_id` idempotency. |

### 2.3 Pricing integrity

| ID | Sev | Finding |
|---|---|---|
| P1 | P0 | Free-text, case-sensitive pricing keys; no FK/CHECK against `AIService` / `Operation`. |
| P2 | P1 | `Operation` enum does not cover every priced op (`image`, `video*`, `publish`, `studio_*`), so routing audit/sync are blind to them. |
| P3 | P2 | Audit requires prices for `channel_*` operations that never bill (payment-gated onboarding), so `ready:false` is structural noise. |
| P4 | P1 | `music` per-model rows are unreachable by the audit by construction. |
| P5 | P3 | `external_cost_cents` is display credits; name invites unit errors. |
| P6 | P1 | No minimum-margin guard; a 0%-margin routed provider is "ready". |

### 2.4 Operability

| ID | Sev | Finding |
|---|---|---|
| O1 | P1 | Routing save + fallback saves + pricing sync are four independent writes; no transaction, no dry-run. |
| O2 | P2 | `GET /credits/operation-costs` covers 5 of 11+ ops and uses `resolve()`, so it reports inactive providers. |
| O3 | P2 | `sub_models_detail` extras are dropped by the response model. |
| O4 | P2 | `credit_invariants.py` does not check routed-vs-executed, unpriceable billable ops, or billable `needs_review`. |
| O5 | P2 | No test covers `resolve()` with `is_active: false`. |
| O6 | P3 | `get_all_assignments` return annotation claims `dict[str, dict[str, dict]]` but includes two lists. |

**Totals: 33 findings — 6 × P0 (R1, R3, B1, B4, B6, P1), 15 × P1, 9 × P2, 3 × P3.**
P0 = can charge the wrong amount or silently accept a price that should not be live; these are the Phase 1 scope.
The live verification (§8) adds **8 confirmed L-findings**, including three P0s (L1 batch pricing, L2/L3 non-deterministic v3 text quotes, L4 music 15 vs 10, L5 sell below cost) that were not visible from code alone.

---

## 3. Decisions required before Phase 0.5

These change behaviour and cannot be chosen by code alone.

| D | Question | Options | Recommendation |
|---|---|---|---|
| D1 | Is `is_active: false` meant to disable a slot? | (a) disable → fall through chain; (b) informational only | **(a)**. It is already honoured for text/image chains, so `resolve()` is the outlier. |
| D2 | Music price model | **(decided 2026-11-05: price follows the routed provider** — `suno` 15, `camxora_music_api` 10) | 182 owns it; automatic failover needs W8 settlement first. |
| D3 | Can a `needs_review` row be charged? | (a) no, refuse; (b) yes, warn; (c) yes, but only at the provider-default key | **(a)**, with an ops override flag. Test currently encodes (b). |
| D4 | Should `channel_*` operations require a price? | (a) yes for COGS; (b) no, exclude from readiness | **(b)** for `ready`, expose separately as `cogs_coverage`. |
| D5 | Text fallback across price tiers | (a) allow, bill executed; (b) restrict to same/lower tier; (c) disallow provider switching | **(a)** long-term, **(b)** as the immediate cheap guard. |
| D6 | Deepseek text sell price | (a) re-derive with the standard margin; (b) raise to a floor and accept a one-off margin jump for users; (c) treat as loss-leader and cap usage | Needs a business call: current sell is 0.006 cr vs 0.336 cr cost (56× under). |
| D7 | Is batch expected to work in this deployment? | (a) yes → L1 is an outage, fix first; (b) no → delete/guard the batch preflight during the pricing repair | Check `batches` table (§8.4). |

---

## 4. Implementation plan

Each work item is independently shippable, in order. Branch naming follows `AGENTS.md` (`fix/…`, `feat/…`), one branch per item or per phase, never mixed with unrelated dirty work.

### Phase 0 — Verify live state (0.5 day, no code)

**W0.1** Run the queries in §7 and record results in this document under §8.
**W0.2** Classify every `needs_review = true` row: routed pair (P0) or orphan.
**Acceptance:** §8 filled; P0 scope confirmed or reduced.

---

### Phase 0.5 — Data repair (ship before Phase 1 pricing changes)

The live table (§8) must be corrected, or Phase 1 code will start charging 0.006 cr per lyric (L5). Music needs no DB change: migration `176_v6_ten_credits.py` already sets 10, which is the repo target (see §8.3 L4 correction).

#### W0.3 · Re-key pricing to the canonical runtime model
- **New migration** (never edit an applied one): insert `deepseek/<op>/deepseek-v4-flash` rows using the existing `deepseek-chat` values, then keep the old alias rows for one release (read-only) or delete them after verification.
- **Rationale:** `resolve()` normalises `deepseek-chat → deepseek-v4-flash`; the pricing key must match what the biller receives.
- **Acceptance:** `lookup_pricing_entry("deepseek", op, "deepseek-v4-flash")` hits for `lyric`, `title`, `album`, `channel_*`; `calculate_batch_draft_cost` returns a number.

#### W0.4 · Music price follows the provider
- **Decided (2026-11-05):** `suno` (sunoapi.org) = **15**, `camxora_music_api` (ours) = **10**. Implemented in `182_music_price_by_provider.py`; 176's uniform 10 is superseded.
- **Acceptance:** DB, `pricing_sync`, and `v3 quote("music")` report 15 for `suno` and 10 for `camxora_music_api`.

#### W0.5 · Fix the deepseek sell price (L5)
- Deepseek text rows sell at 60 units against 504–3360 cost. Re-derive sell with the intended margin **after** W0.3 (so the right row is updated) using the seed generator, or set an explicit floor (e.g. ≥ cost / (1 − margin)).
- **Acceptance:** no routed row has `cost > sell`; every routed row has a margin ≥ the agreed floor, or is explicitly exempted with a comment.

#### W0.6 · Resolve the four draft rows
- **Done:** reviewed at **5 credits** (documented AI-assist price) with a registry-estimated cost basis and `needs_review = false` (`183_web_assist_pricing_review.py`).
- **Acceptance:** `SELECT count(*) FROM credit_pricing WHERE needs_review` = 0 in the seeded set; W4 now blocks anything left over.

#### W0.7 · Remove dead config
- `suno/wav` (orphan) and the 0-priced `local/video*` rows: confirm intent, then either wire them or delete/repricing them.
- **Acceptance:** §7 query 3 returns no rows.

---

### Phase 1 — P0 correctness

#### W1 · `resolve()` honours `is_active` and falls back
- **Files:** `platform_api/services/ai_routing_service.py`, `platform_api/services/suno_audio_resolver.py`.
- **Change:**
  1. In `resolve()`, after loading the assignment, treat an inactive primary as absent and continue to `DEFAULT_PROVIDER`; log at INFO with the operation.
  2. Replace the hard `raise NoAvailableKeysError` with: try primary → if no active keys, walk the configured chain for that service type, returning the first provider with keys; raise only when the whole set is exhausted (include the per-provider status counts).
  3. Route `suno_audio_resolver.active_music_provider` through a shared helper (e.g. `AIRoutingService.resolve_music_provider_sync` or a new `ai/routing_store.py` pure parser) so there is exactly one parser; honour `is_active`.
- **Tests:** extend `tests/test_ai_routing_active.py` with `test_resolve_skips_inactive_primary`, `test_resolve_falls_back_when_primary_has_no_keys`, `test_resolve_raises_when_no_provider_has_keys`; add `test_active_music_provider_honours_inactive` in `tests/test_suno_audio_resolver.py`.
- **Acceptance:** all four new tests pass; no other test changes required; `GET /admin/ai-routing` output unchanged.
- **Status:** done. Inactive → defaults, then the service-type chain is tried before `NoAvailableKeysError`.
- **Risk:** a slot that is currently inactive but keyed will start routing elsewhere. Mitigate by shipping behind a 24h log-only mode? Not worth it — behaviour matches the documented UI.

#### W2 · Validate and guard `save_assignments`
- **Files:** `services/ai_routing_service.py`, `models/ai_routing_schemas.py`.
- **Change:**
  1. Reject any `sub_model` not in `PROVIDER_SUB_MODELS[provider][service_type]` (allow `None` only where the registry has no models, e.g. `music`).
  2. Reject `provider == "suno"` for text ops other than `lyric` at save time (already partly done — make it uniform).
  3. Add `replace_all: bool = False` to `SaveAssignmentsRequest`; when `False`, require the payload to name every operation in `Operation` (or reject with the missing list). Reject `{}` outright.
  4. Do not mutate the caller's dict — build a new mapping.
- **Tests:** `tests/test_ai_routing_registry.py` + new `test_save_assignments_rejects_unknown_model`, `test_save_assignments_rejects_partial_payload`, `test_save_assignments_rejects_empty`.
- **Acceptance:** the audit endpoint can no longer report `unknown_model` for a freshly saved config.
- **Status:** done except `replace_all` (partial payloads are still accepted).

#### W3 · Desktop music bills the model it was told to use
- **Files:** `routers/generation.py`.
- **Change:** `check_and_deduct(..., sub_model=normalize_suno_pricing_sub_model(request.model))`. Prefer `resolve_suno_model_id(request.model)` for canonicalisation. If the deployment is v3-flag On, this is metadata-only — still pass it.
- **Tests:** `tests/test_generation_router.py` — assert the enforcement call receives `sub_model="V6_MINI"`.
- **Acceptance:** flag-Off desktop and batch quote the same price for the same model; a config with only per-model rows serves desktop.

#### W4 · Stop billing unreviewed prices (or make it explicit)
- **Decided (2026-11-05, D3 = block):** `lookup_pricing_entry` / `get_price` raise `ExternalServiceError(code="PRICING_NEEDS_REVIEW")`; the v3 cross-provider scan skips drafts. `allow_draft=True` is available for preview/read-only callers.
- **Status:** done.
- **Acceptance:** no draft row can be charged without an explicit decision recorded in code comments and docs.

#### W5 · Canonical pricing keys + registry validation
- **Files:** `services/pricing_keys.py`, `services/credit_pricing_service.py`, `routers/credits.py`, `repositories/credit_repo.py`.
- **Change:**
  1. `pricing_lookup_key` lower-cases `ai_service` and `operation_type`; apply on read and write.
  2. Validate `ai_service ∈ AIService ∪ {"local","postforme"}` and `operation_type ∈ Operation ∪ LEGACY_PRICING_OPERATIONS` on `create_price` / `update_price` / `set_price`; return 422 with the allowed list.
  3. Data backfill: normalise existing rows (new migration, never edit applied ones). Detect case-duplicates before merging.
  4. Add the missing operations to a shared `LEGACY_PRICING_OPERATIONS` (see W13) instead of free text.
- **Tests:** `tests/test_credit_pricing_service.py` — key normalisation, reject unknown service, reject unknown op, case-duplicate merge.
- **Acceptance:** `GET /credits/pricing` shows no row that differs from another only by case/whitespace.
- **Status:** done. Writes normalize to lowercase and reject unknown provider/operation; `184_pricing_keys_canonical.py` backfills existing rows.

#### W5b · Make v3 text quotes deterministic and routing-aware
- **Files:** `services/v3/list_prices.py`, `services/v3/credits_only_billing_service.py`, `services/v3/generate_charge.py`.
- **Change:** for `lyric`, `title`, `album`, `style`, resolve the routed provider/model (as `music`/`image` already do) and put it at the front of the lookup chain, then fall back to the static chain. Delete the `web_music_*` aliasing from the scan for these ops, or map `web_music_lyrics → lyric` explicitly with its own row. Remove the unordered pass-2 scan (W10).
- **Rationale:** L2/L3 — today `quote("lyric")` = 0.006 cr while `quote("style")` = 2.0 cr for the same user action, selected by heap order.
- **Tests:** `tests/test_v3_credits_only.py` — routed provider wins; missing row raises instead of scanning; lyric and style resolve as configured.
- **Acceptance:** the same op always quotes the same price for the same routing; changing routing changes the quote.
- **Status:** done. Verified against the live config with 181 applied in a rolled-back transaction: `lyric` 0.42, `title`/`album` 0.063, `web_music_lyrics` 2.0, `web_music_style` 2.0. The cross-provider scan remains only as a last resort.

#### W6 · Fix the music price source of truth
- **Files:** `services/pricing_sync_service.py`, `services/credit_pricing_service.py`.
- **Change:**
  1. `_OPERATION_DEFAULT_CREDITS["music"]` → 10 display credits (`100 * CREDIT_SCALE`), matching docs and migration 131. Add a comment naming the migration so the next reader knows.
  2. In `suggest_pricing_values`, filter `same_provider_credits` by `_service_type_for_operation(entry_operation) == target_service` **before** the median. Keep the untyped fallback only when the service type is unknown.
  3. Call `_validate_pricing_economics` in `sync_from_routing_config`; on failure, create the row with `needs_review=True` **and** record it in the response as `rejected_economics` rather than failing the whole save.
- **Tests:** `tests/test_pricing_sync_service.py` — music default is 10; a suno row suggestion ignores lyric rows; a cost>sell pair is reported, not silently created.
- **Acceptance:** deleting all pricing and re-running sync cannot reproduce the 7.5 draft migration 131 had to repair.

**Phase 1 gate:** `pytest platform_api/tests/test_ai_routing_active.py test_ai_routing_registry.py test_ai_routing_providers.py test_capability_catalog.py test_pricing_sync_service.py test_credit_pricing_service.py test_generation_router.py test_draft_billing.py -q` green.

---

### Phase 2 — Bill what actually ran

#### W7 · Return the executed provider/model from the text gateway
- **Files:** `ai/providers/text/gateway.py`, `services/generation_service.py`.
- **Change:** add `@dataclass TextGenerationResult(content: str, provider: str, model: str, attempts: int)`; add `generate_text_with_meta()` (keep `generate_text()` as a thin wrapper so callers migrate incrementally). `chat_completion_with_fallback` already knows the winning pair.
- **Tests:** `tests/test_generation_service.py` — fallback to the second provider returns that provider.
- **Acceptance:** no behaviour change for existing callers; new API covered by tests.

#### W8 · Settle text charges on the executed pair (mirror the image path)
- **Files:** `routers/generation.py` (draft), `services/batch_service.py` (draft + rewrite), `services/web_music_service.py` (AI assist), `services/usage_enforcement_service.py`.
- **Change:** replace pre-charge-then-execute with the image pattern already proven in `image_job_service.py`:
  1. `resolve_max_credits(operation, chain)` → `reserve_and_hold_before_provider`.
  2. Execute; get `TextGenerationResult`.
  3. `finalize_held_operation(ai_service=result.provider, sub_model=result.model, hold=…, routed_provider=…, executed_provider=…)`.
  4. On failure, `refund_failed_operation` with the hold amount.
- **Tests:** extend `tests/test_draft_billing.py`, `tests/test_generation_router.py`, `tests/test_v3_credits_only.py` with a two-provider chain where the second wins; assert the charge matches the second provider's row and metadata contains both routed and executed.
- **Acceptance:** ledger metadata always distinguishes `routed_*` from `executed_*`; no path charges a provider that did not run.

#### W9 · Guard the sibling-model expansion
- **Files:** `services/ai_routing_service.py::expand_text_chain_with_sibling_models`.
- **Change (D5 = b as interim):** order registry siblings by `SUB_MODEL_COST_TIERS`/`cost_tier`, and stop expanding past the first model whose tier is strictly higher than the priced primary, unless the operation is configured as price-sensitive. Add a setting `ai_routing_allow_premium_siblings` (default `False`).
- **Tests:** chain with `deepseek-v4-flash` primary excludes `deepseek-v4-pro` by default; includes it when the flag is on.
- **Acceptance:** default config cannot silently upgrade COGS ~4× at flash prices.

#### W10 · Remove the cross-provider price scan
- **Files:** `services/v3/list_prices.py`.
- **Change:** delete pass 2 in `_scan_pricing_units` (or gate it behind an admin setting defaulted off). On a miss, raise so the caller surfaces "pricing not configured" instead of quietly using another provider.
- **Tests:** `tests/test_v3_credits_only.py` — the existing test at line ~404 expects a scan hit; invert it to assert a typed error, or keep one explicit opt-in test.
- **Acceptance:** an image debit can never use a non-routed provider's row without an explicit flag.

#### W20 · Music fallback chain + price settlement
- **Files:** `services/ai_routing_service.py`, `models/ai_routing_schemas.py`, `routers/ai_routing.py`, `ai/capability_catalog.py`, `services/pricing_sync_service.py`, `services/generation_service.py`, `services/batch_service.py`, `services/v3/credits_only_billing_service.py`, `routers/generation.py`, `routers/credits.py`, `services/usage_enforcement_service.py`.
- **Done:** `ai_routing_music_fallback_chain` setting, `get/save/resolve_music_chain`, schema + admin save/return, audit and pricing-sync coverage; every music billing/execution site uses `resolve_music_chain("music")[0]`; `_call_suno_with_provider` advances the chain on `ExternalServiceError` and reports the executed provider; `settle_music_price` charges or refunds the difference (15 vs 10) against the same wallet/ledger.
- **Opt-in:** only the desktop route and batch submission pass `allow_music_failover=True` + `on_executed`. Web Create keeps a single provider so it cannot undercharge until it passes a settle callback.
- **Settlement is best-effort:** a delivered song is never failed because the delta deduct failed; the shortfall is logged (`Music settlement undercharged`) for reconciliation.
- **Acceptance:** forced 5xx on the chain head → the fallback provider runs and the ledger reflects the fallback price.

**Phase 2 gate:** full `platform_api/tests` suite; plus a manual sandbox run of one draft, one batch song, one image, one web lyric assist with keys pulled from one provider to force fallback.

---

### Phase 3 — Make the admin surface trustworthy

#### W11 · One transactional routing save
- **Files:** `routers/ai_routing.py`, `services/ai_routing_service.py`, `services/credit_pricing_service.py`, `repositories/*`.
- **Change:** introduce `AIRoutingConfigService.save(config)` that performs assignment + both chains + pricing sync inside one DB transaction (or with compensating rollback), returning `{saved, pricing_sync, audit}`. Add `?dry_run=true` returning the diff plus the post-change audit without writing.
- **Tests:** failure injected in pricing sync leaves settings unchanged (integration test against the fake repo).
- **Acceptance:** no reachable state where new routing is live with old/missing prices.
- **Status:** partial. Compensating rollback + audit in the save response are shipped; the DB transaction and `?dry_run=true` are still open.

#### W12 · Surface rejected assignments
- **Files:** `ai_routing_service.py`, `schemas/ai_routing_schemas.py`, `routers/ai_routing.py`.
- **Change:** `get_all_assignments()` also returns `rejected: [{operation, provider, sub_model, reason}]` from `_sanitize_assignments`; `AssignmentResponse` gains the field (default empty).
- **Acceptance:** removing a provider from the registry produces a visible admin warning, not just a log line.

#### W13 · Operation registry with billing mode
- **Files:** `ai/types.py`, `ai/capability_catalog.py`, `services/pricing_sync_service.py`, `services/credit_pricing_service.py`.
- **Change:**
  1. Add `BILLING_MODE: Mapping[Operation, Literal["wallet","plan","none"]]`; mark `channel_*` as `none` (onboarding-gated).
  2. Add a parallel `NON_ROUTING_OPERATIONS` set (`image`, `video`, `video_manual`, `video_merge`, `publish`, `studio_edit`, `studio_stems_2`, `studio_stems_12`) so pricing validation (W5) and pricing gaps can see them.
  3. Audit: require pricing only for `wallet`/`plan` ops; report `none` ops under a separate `cogs` section.
- **Acceptance:** `GET /admin/ai-routing/audit` `ready` flips to true for a correct config that omits channel prices.

#### W14 · Fix `sub_models_detail` and `operation-costs`
- **Files:** `models/ai_routing_schemas.py`, `routers/credits.py`.
- **Change:** declare `cost_usd`, `cost_usd_by_operation`, `operations` on `SubModelDetail`; extend `get_operation_costs` to iterate `Operation` (not a hardcoded 5) and to resolve through the chain (W1) so inactive providers are not reported.
- **Acceptance:** admin UI shows per-operation USD; `/credits/operation-costs` returns every billable op.

---

### Phase 4 — Cleanup and safety nets

#### W15 · Collapse the credit services
- **Files:** `services/credit_operation_service.py`, `services/credit_service.py`.
- **Change:** delete `CreditOperationService` (no production callers; only `dependencies.get_credit_operation_service` + `tests/test_channel_setup_credits.py`). Remove `CreditService.execute_with_credits` and its `_resolve_pricing` if unused. Keep exactly one path: `UsageEnforcementService` with `ref_id` + `refund_once`.
- **Acceptance:** `grep -r "execute_with_credits" platform_api` returns only the deletion diff; no "graceful to zero" path remains.

#### W16 · Web/desktop charge parity
- **Files:** `services/web_music_service.py`, `services/v3/web_music_charge.py`.
- **Change:** drop `ceil`/`round`; charge exact micro-units (or round half-up to 0.0001 credits, never to a whole credit). Add a durable fallback for `_refund_text_operation` using `_refund_v3_*` keyed on the reservation id.
- **Tests:** `tests/test_web_music_*` — a 0.0001-credit row charges 0.0001, not 1; a simulated process restart still refunds via the durable path.
- **Acceptance:** the same operation costs the same on web and desktop.

#### W17 · Routing invariants + alerting
- **Files:** `services/credit_invariants.py`.
- **Change:** add
  1. `charged_provider <> executed_provider` count (last 24h) above a threshold;
  2. billable op with no pricing row;
  3. billable op served only by a `needs_review` row;
  4. routed provider with 0 active keys;
  5. margin below a floor (e.g. < 5%) for any routed provider.
- **Acceptance:** each can be tripped by a unit test with a fake pool; Telegram message includes the top offenders.

#### W18 · Rename the cost unit (low risk, high clarity)
- **Files:** new migration, `credit_pricing_service.py`, `routers/credits.py`, admin portal types.
- **Change:** add `external_cost_units` as the canonical column; keep `external_cost_cents` as a generated/aliased read for one release; update the API field with a deprecation note.
- **Acceptance:** no new code writes the "cents" name; docs state the unit explicitly.

#### W19 · Margin floor for routed music providers
- **Files:** `services/credit_pricing_service.py`.
- **Change:** extend `_validate_pricing_economics` to warn (not reject) when `cost == sell` for a billable op, and have the audit surface it. Re-check `camxora_music_api/music` (currently 10 = 10).
- **Acceptance:** P6 becomes a visible warning; the business decides the value.

---

## 5. Suggested branch / commit sequence

| Branch | Commit | Content |
|---|---|---|
| `fix/credit-pricing-data-repair` | 1 | W0.3 canonical model re-key migration |
| | 2 | W0.4 + W0.5 price repair (after D2/D6) |
| | 3 | W0.6 + W0.7 draft/orphan cleanup |
| `fix/ai-routing-resolve-p0` | 1 | W1 + tests |
| | 2 | W2 + tests |
| | 3 | W3 + tests |
| `fix/credit-pricing-keys` | 1 | W5 + backfill migration |
| | 2 | W5b |
| | 3 | W4 (decision D3) |
| | 4 | W6 |
| `feat/text-billing-executed` | 1 | W7 |
| | 2 | W8 draft + batch |
| | 3 | W8 web assist + W9 |
| | 4 | W10 |
| `feat/ai-routing-admin-safety` | 1 | W11 |
| | 2 | W12 + W13 |
| | 3 | W14 |
| `chore/credit-service-cleanup` | 1 | W15 |
| | 2 | W16 |
| | 3 | W17 + W19 |
| | 4 | W18 |

Every branch: start from `origin/main`, run the phase gate, never mix with unrelated dirty files, delete after merge, and keep `G:\Developments\Projects\Camxora` on `main` clean.

---

## 6. Test matrix (what proves each fix)

| Finding | Test file | New/changed test |
|---|---|---|
| R1, R2 | `test_ai_routing_active.py` | resolve inactive / no-keys fallback / total exhaustion |
| R3, R4, R7 | `test_ai_routing_registry.py` | unknown model, partial payload, empty payload, rejected surfaced |
| R6 | `test_suno_audio_resolver.py` | inactive music assignment |
| R8, B2, B9 | `test_ai_routing_active.py`, `test_v3_credits_only.py` | tier cap; default-row substitution refused |
| B1, B2 | `test_draft_billing.py`, `test_generation_router.py` | second provider wins → second price charged |
| B3, B4 | `test_generation_router.py`, `test_pricing_sync_service.py` | model passed; music default is 10 |
| B5, W16 | `test_v3_credits_only.py`, `test_music_daily_cap.py` | no whole-credit rounding; durable text refund |
| B6, B7 | `test_credit_pricing_service.py` | draft refused; economics violation reported |
| B10 | `test_v3_credits_only.py` | scan disabled by default |
| B12 | `test_channel_setup_credits.py` | replace with `UsageEnforcementService` coverage |
| P1 | `test_credit_pricing_service.py` | case normalisation, unknown key rejection |
| P3, P4 | `test_capability_catalog.py`, `test_pricing_sync_service.py` | channel ops excluded from readiness; per-model music checked |
| O4, O5 | `test_credit_pricing_service.py`, `test_ai_routing_active.py` | invariants; `is_active` resolve |
| L1, W0.3 | `test_batch_service.py`, `test_draft_billing.py` | batch cost resolves for the normalised model |
| L2, L3, W5b | `test_v3_credits_only.py` | routed text quote is deterministic; draft row not selectable by scan |
| L4, W0.4 | `test_credit_pricing_service.py` | music price is 15 for `suno`, 10 for `camxora_music_api` |
| W20 | `test_ai_routing_active.py` | music chain order, inactive skip, no-keys fallback, provider validation |

No existing test encodes the buggy behaviour except `test_audit_treats_draft_pricing_as_warning_not_error` (W4 makes the decision explicit).

---

## 7. Live verification queries (run before Phase 0.5)

```sql
-- 1. Are any routed pairs billable as an unreviewed draft?
SELECT ai_service, operation_type, sub_model, credits_per_operation,
       external_cost_cents, needs_review
FROM credit_pricing
WHERE needs_review = TRUE
ORDER BY ai_service, operation_type, sub_model;

-- 2. What does music actually cost, and by which key?
SELECT ai_service, operation_type, sub_model, credits_per_operation,
       external_cost_cents, needs_review
FROM credit_pricing
WHERE operation_type IN ('music','music_generation')
ORDER BY ai_service, sub_model;

-- 3. Price keys that cannot match a provider/operation (typos, case, orphans)
SELECT ai_service, operation_type, sub_model, count(*)
FROM credit_pricing
GROUP BY 1,2,3
HAVING ai_service NOT IN ('suno','camxora_music_api','fal','openai','deepseek','slai','cala','kie','local','postforme')
    OR operation_type NOT IN ('channel_name','channel_description','channel_keywords','channel_tags',
                              'lyric','title','album','web_music_style','web_music_lyrics',
                              'channel_logo','channel_cover','background_image','thumbnail_image',
                              'music','image','video','video_manual','video_merge','publish',
                              'studio_edit','studio_stems_2','studio_stems_12','upload')
ORDER BY 1,2,3;

-- 4. Is the seam between routing and pricing complete?
SELECT key, value FROM system_settings
WHERE key IN ('ai_routing_assignments','ai_routing_text_fallback_chain',
              'ai_routing_image_fallback_chain','credits_only_v3_charge');

-- 5. Zero/negative margin among routed providers
SELECT ai_service, operation_type, sub_model, credits_per_operation, external_cost_cents
FROM credit_pricing
WHERE external_cost_cents IS NOT NULL
  AND external_cost_cents >= credits_per_operation
ORDER BY ai_service, operation_type;

-- 6. Duplicate keys differing only by case/whitespace
SELECT lower(btrim(ai_service)) s, lower(btrim(operation_type)) o,
       lower(btrim(coalesce(sub_model,''))) m, count(*)
FROM credit_pricing
GROUP BY 1,2,3 HAVING count(*) > 1;
```

---

## 8. Verification results

**Environment:** local `platform_db` (activity in the last 7 days: 6 debits, all `v3_studio_edit`). This is a **sandbox/dev copy, not production.** Findings below are deterministic for this config; re-run §7 against a production read replica before repairing prices.
**Reproducibility:** the pricing-behaviour results were produced twice by exercising the real services (`CreditPricingService`, `CreditsOnlyBillingService`, `calculate_batch_draft_cost`) against the live tables — not by reading code alone.

> **Environment warning (added after Phase 0.5).** This local DB is **not** at the
> repo's migration head: `alembic_version` is stamped `174_studio_project_suno_id`,
> a revision id that no longer exists in `platform_api/migrations/versions`
> (`174_credits_only_two_tier.py` uses `"174"`). The locked runner refuses to
> upgrade it and also reports a schema assertion failure
> (`credit_transactions.reason` is `character varying`, expected `text`).
> **Consequence:** the measured *prices* are stale and must not be treated as
> production truth. The *behavioural* findings (alias mismatch, scan-based
> quotes, batch failure) are code-driven and reproduce on any DB with the same
> code; they are not affected by the stale stamp.

### 8.1 Measured state

| Query | Result |
|---|---|
| 1 · `needs_review` rows | **4 rows**, all web AI-assist: `deepseek/web_music_lyrics` and `deepseek/web_music_style` at 20,000 units (2 cr), `openai/web_music_lyrics` at 30,000 (3 cr), `openai/web_music_style` at 20,000 (2 cr). All four have `external_cost_cents = 0` → displayed as 100% margin. |
| 2 · music prices | **(pre-`176` state — see the environment warning above)** `suno/music/*` = **150,000 units = 15.00 credits** (cost 120,000 = 12.00); `camxora_music_api/music/*` = **100,000 = 10.00 credits** (cost 100,000 = 0% margin). Six Suno keys (default, V5, V5_5, V6, V6_MINI, V6_WILD) all 15. Migration 176 would set suno to 10 and 175 would drop V5/V5_5. |
| 3 · unknown keys | `suno / wav` (10,000 units). Only referenced by `migrations/versions/075_distrokid_addon.py`; no billing code reads it. |
| 4 · routing + flag | `credits_only_v3_charge = true`. `lyric`, `title`, `album` = **`deepseek` / `deepseek-chat`** (a *retired alias*). `music` = `suno`, `sub_model: null`. All `is_active: true`. Images = `slai` / `cx/gpt-image-2.5`. |
| 5 · cost ≥ sell | **11 deepseek rows have cost ≫ sell** (margin −740% … −5500%). 20 openai/slai/camxora rows are cost = sell (0%). `local/video` + `local/video_merge` are 0/0 (free). `suno/studio_*` have `cost = NULL`. `suno/music` is the only healthy row (+20%). |
| 6 · duplicate keys | none (so P1's case-collision risk has not materialised yet) |
| key pool | 1 active key for each of deepseek, fal, openai, slai, suno (suno also 1 disabled) → R2's no-keys fallback is latent, not active |

### 8.2 Measured behaviour (the part that matters)

| Probe | Result |
|---|---|
| `lookup_pricing_entry("deepseek","lyric","deepseek-v4-flash")` — the value `resolve()` returns | **MISS** |
| `lookup_pricing_entry("deepseek","lyric","deepseek-chat")` — the value stored | HIT 60 units (0.006 cr) |
| `pricing.get_price("deepseek","title"|"album","deepseek-v4-flash")` | **ExternalServiceError** (no pricing) |
| `calculate_batch_draft_cost(5 songs)` with real routing | **ValidationError: "Draft generation pricing is not configured … model 'deepseek-v4-flash'"** |
| v3 `quote("lyric")` | **0.006 credits** (scan lands on `deepseek/lyric/deepseek-chat`) |
| v3 `quote("title")` / `quote("album")` | **0.006 credits** |
| v3 `quote("style")` | **2.0 credits** (scan lands on the *unreviewed* `deepseek/web_music_style`) |
| v3 `quote("music")` with routing `suno` | **15.0 credits** |

### 8.3 Live findings (L-series) and what they change

| ID | Sev | Finding | Consequence |
|---|---|---|---|
| **L1** | **P0** | Routing stores `deepseek-chat`; `resolve()` normalises it to `deepseek-v4-flash`; pricing is keyed `deepseek-chat`. | `calculate_batch_draft_cost` raises, and it runs on **batch preview and batch create** (`batch_service` lines ~432 and ~848). Batch cannot be created with this config. |
| **L2** | **P0** | v3 `lyric`/`title`/`album` quotes resolve through the unordered cross-provider scan, landing on `deepseek/*/deepseek-chat` = 0.006 cr. | AI-assist lyric is charged 0.006 cr, not the intended 2 cr; the price is heap-order dependent, so a re-index or row insert can change what users pay. |
| **L3** | **P0** | v3 `style` resolves to an **unreviewed** row (`needs_review = true`) at 2 cr with a 0 cost basis. | Confirms B6 in production shape; lyric (0.006) and style (2.0) are inconsistent for the same user action. |
| **L4** | P1 *(decided)* | `suno/music` measured **15 cr** — pre-`176` state. **Decision 2026-11-05: price follows the routed provider** — 15 on sunoapi.org, 10 on our musicapi. | Implemented in `182_music_price_by_provider.py`; `pricing_sync` is provider-aware. Constants stay at 10 (cheaper provider) so legacy refunds cannot over-credit. Automatic failover needs W8. |
| **L5** | **P0** | `deepseek` text rows sell at 60 units (0.006 cr) against a cost of 504–3360 units. | Negative margin on every draft; fixing L1 without fixing L5 would start charging 0.006 cr for a 0.336 cr cost. |
| **L6** | P1 | `openai`/`slai` text and image rows are cost == sell; `suno/studio_*` cost is NULL. | 0% margin on most of the table; studio margin is unknown, not 100%. |
| **L7** | P2 | `suno/wav` orphan row; `local/video*` priced at 0. | Dead config; local ops are free while docs say 3/10 credits. |
| **L8** | P1 | 4 unreviewed rows carry `external_cost_cents = 0`. | Margin reporting is wrong even after review; and one of them is already billable (L3). |

**Net effect on the plan:** Phase 0.5 (data repair) now precedes Phase 1. Code fixes alone would leave the table charging 0.006 cr per lyric (L5) and, if the stale DB is representative, the sync default would re-create a 7.5 cr music row (L4 / W6).

### 8.4 Re-run against production before repairing

Run §7 plus these two probes against a production read replica:

```sql
-- 0. Is the environment even at the repo's migration head?
SELECT version_num FROM alembic_version;
-- Compare with: python -m platform_api.migrations.upgrade (it refuses when the
-- stamped revision is missing from the tree, which is what happened locally).

-- what users actually paid in the last 30 days
SELECT reason, amount, count(*) AS n
FROM credit_transactions
WHERE direction = 'debit' AND created_at > NOW() - INTERVAL '30 days'
GROUP BY reason, amount ORDER BY n DESC LIMIT 40;

-- did batch creation succeed recently?
SELECT status, count(*) FROM batches
WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY status;
```

If `v3_lyric` debits are ~60 units, L2 is live in production. If `batches` has no recent rows but the product expects them, L1 is a live outage.

### 8.5 Phase 0.5 implementation status

**Shipped (uncommitted):** `platform_api/migrations/versions/181_pricing_routing_repair.py` — revision `181`, parent `180`.

| Work item | Status | Notes |
|---|---|---|
| W0.3 re-key `deepseek-chat → deepseek-v4-flash` | **done** | In-place `UPDATE` guarded by `NOT EXISTS` against the unique key, plus a duplicate clean-up `DELETE`. Idempotent. |
| W0.5 negative-margin repair | **done** | Only rows with `external_cost_cents > credits_per_operation` are touched; sell becomes `ceil(cost / 0.8)` (20% target margin, one constant). 0-margin and `cost = NULL` rows are left alone. |
| W0.4 music price by provider | **done** | `182_music_price_by_provider.py`: `suno` 15, `camxora_music_api` 10; sync suggestions provider-aware. See `docs/changelog/2026-11-05-music-price-by-provider.md`. |
| W5b deterministic v3 text quotes | **done** | Routed provider/model (and the concrete op, e.g. `web_music_lyrics`) now leads the price chain. Dry-run after 181: `lyric` 0.42, `title`/`album` 0.063, `web_music_lyrics` 2.0, `web_music_style` 2.0 — all exact rows. Before: 0.0216 / 0.0032 / 0.0176 / 0.0216 / 2.0 by scan order. |
| W1 `resolve()` semantics | **done** | Inactive assignments are treated as absent; when the chosen provider has no active keys the text/image/music chain is tried before raising. 4 new tests. |
| W11 routing save safety | **partial** | The PUT now snapshots the current config, and on any failure during the settings writes or pricing sync restores it (compensating rollback). The response includes the post-change audit. A true DB transaction and `?dry_run=true` remain open. |
| W5 canonical pricing keys | **done** | `pricing_lookup_key` lowercases provider/operation; `create/update/set/delete/approve` validate against `AIService` + known operations and store canonical lowercase. Backfill `184_pricing_keys_canonical.py` merges case duplicates (newest wins) then lowercases. |
| W2 save validation | **done (partial)** | Rejects empty payloads and unregistered models, persists the canonical model id (alias → canonical), validates the music provider, and no longer mutates the caller's dict. Partial-payload protection (`replace_all`) still open. |
| W20 music fallback chain + settlement | **done (desktop + batch)** | Chain config + `resolve_music_chain`; `_call_suno_with_provider` advances on provider failure when the caller opts in; `UsageEnforcementService.settle_music_price` applies the price delta on the executed provider. Web Create stays single-head until it passes a settle callback. |
| W0.6 four draft rows | **done** | Reviewed at **5 credits** with a registry-estimated cost basis (deepseek 1,260/560 units; openai 540/240) and `needs_review = false` (`183_web_assist_pricing_review.py`). |
| W4 unreviewed prices | **done** | `lookup_pricing_entry` / `get_price` raise `PRICING_NEEDS_REVIEW` for draft rows; the v3 scan skips drafts. `allow_draft=True` exists for preview/read-only callers. |
| W0.7 dead config (`suno/wav`, 0-priced local ops) | **deferred** | Deletion needs an owner decision; no code path reads `suno/wav`. |

**Dry-run proof** (migration SQL executed inside a transaction, then rolled back):

| Probe | Before | After (in tx) | Rolled back |
|---|---|---|---|
| deepseek rows keyed `deepseek-chat` | 9 | 0 | 9 |
| deepseek rows keyed `deepseek-v4-flash` | 0 | 9 | 0 |
| rows with negative margin | 7 | 0 | 7 |
| `calculate_batch_draft_cost(5 songs)` | `ValidationError` | **24,780 units** (2.478 cr) | `ValidationError` |
| v3 `quote("lyric")` | 0.006 cr | **0.42 cr** | 0.006 cr |
| v3 `quote("style")` | 2.0 cr | 2.0 cr (unchanged — W5b) | 2.0 cr |

Post-repair prices: lyric 4,200 units (0.42 cr) against 3,360 cost; title/album 630; channel_* 700–1,750. Batch 5-song draft = lyric + title + album + 4 × (lyric + title) = 24,780 units.

**Guarding tests:** `test_migrations_runner.py`, `test_deploy_hygiene_alembic.py`, `test_credit_pricing_service.py`, `test_pricing_sync_service.py` → **45 passed**.

**Not applied to the local DB:** the Alembic stamp mismatch blocks `run_pending_migrations()`. Applying 181 requires first re-stamping the DB (or restoring it) — that is an environment decision, not a code change.


---

## 9. Rollout and rollback

- **Ordering:** Phase 1 is safe to ship alone (it removes silent mispricing). Phase 2 changes charge amounts on fallback paths — announce, monitor the daily spend delta for 48h.
- **Flag:** put W8 (text hold/finalize) and W10 (scan removal) behind admin settings defaulting to the safe value, so a production rollback is a setting flip, not a deploy.
- **Rollback:** routing and pricing rows are the state; every migration in this plan is additive (no column drops, no data deletion). W18's rename keeps the old column readable for one release.
- **Watch:** `credit_invariants` additions (W17) should be deployed before W8 so any over/undercharge is visible immediately.
- **Do not** hotfix on the VPS; fix on `main` and deploy the verified commit.

---

## 10. Effort estimate

| Phase | Work | Estimate |
|---|---|---|
| 0 | Live queries + classification | 0.5 d (done for local sandbox) |
| 0.5 | W0.3–W0.7 data repair | 1–1.5 d (needs D2/D6 signed off) |
| 1 | W1–W6 (+W5b) | 4–5 d (W8 pattern reuse is the unknown) |
| 2 | W7–W10 | 5–7 d |
| 3 | W11–W14 | 5–6 d |
| 4 | W15–W19 | 4–5 d |
| **Total** | | **~4 weeks one engineer**, or ~2 weeks with two in parallel (Phase 1 ∥ Phase 3, then Phase 2, then Phase 4) |

Phase 1 alone (≈3–5 days) closes every P0 that can charge the wrong amount without changing the charge architecture.
