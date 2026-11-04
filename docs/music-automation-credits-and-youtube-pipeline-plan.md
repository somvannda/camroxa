# Music automation: credits, YouTube upload, and pipeline progress

**Status:** approved for implementation (2026-11-04)
**Surfaces:** `camxora_python` (Music page, Progress), `platform_api` (batch preflight, operation costs)

## Problem statement

Five requests came out of one screen (Music → Automation):

1. The automation toggle says **Auto-Upload**; it should say **YouTube Upload** and make clear it
   publishes through Post for Me.
2. The credit panel must show **all** credits a plan requires, priced **live from the database**
   for the **routed provider**, and include **YouTube upload** credits.
3. The progress pipeline has no YouTube stage; there is no way to manually upload a finished
   video to YouTube from Progress.
4. Find bugs in this area.
5. List improvement/gaps.

Observed on production (screenshot, 5 batches / 50 songs / 20 image jobs / 100 exports / 10 merges):

```
panel total 940 = draft 100 + suno 500 + image 120 + video/merge 220
preflight    "Insufficient credits for this plan. Required 1050.0, available 288.7854"
delta        +110, unexplained by the panel
```

## Current architecture (as implemented today)

| Concern | Source of truth | Notes |
|---|---|---|
| Unit prices | `credit_pricing` table via `GET /api/v3/credits/operation-costs` | Already **routing-aware** for AI ops (`routing_service.resolve(op)` → `pricing_service.get_price(provider, op, sub_model)`) and includes `video`, `video_merge`, `publish` (postforme upload, 5 credits default) |
| Client plan math | `shared/lib/music_costs.py` | `get_music_plan_cost_breakdown()` covers draft/suno/image/video/merge; **no publish** |
| Client display | `features/music/widgets/automation_card.py` | 5 metric cells: batches, songs, image jobs, video/merge; 5 credit cells: total/draft/suno/image/video-merge |
| Batch preflight | `platform_api/services/batch_service.py` | `total_wallet_cost` = draft+suno+image+`_local_operation_price(video)`×ops+`_local_operation_price(video_merge)`×ops; **no publish** |
| Pipeline data | `features/workflow/lib/workflow_steps.py` | `STEP_ORDER` already ends in `youtube`; rows carry `youtube_pending/success/failed/url` |
| Upload API | `platform_api/routers/publish.py`, `routers/youtube.py` | `POST /publish/jobs`, `/publish/quote`, plus legacy `/youtube/uploads/run` |

## Bugs found (evidence)

1. **Saved preference is silently cleared.** `AutomationCard.set_auto_upload_enabled(False)` calls
   `setChecked(False)`; whenever readiness is not ready (no channel yet, or the page loads before
   readiness resolves) the stored `autoUploadYouTube: true` is overwritten with `False` on save.
2. **Upload credits missing from preflight.** A plan that will publish N videos passes the credit
   check; the upload credits are only taken at publish time (`/publish/jobs`). This is the most
   likely explanation for the +110 delta if uploads were part of it.
3. **Button total ≠ preflight total.** The Generate label uses the client breakdown; the 422 uses
   `total_wallet_cost`. They are computed by two code paths and can disagree, with no explanation
   shown to the user.
4. **`publish` is invisible in the panel.** Even a correct total would not show *why* it is higher.
5. **Missing price prints as failure.** `format_operation_cost_label` renders
   "YouTube upload: unavailable" inline when the row is missing, which reads as an error.

## Decisions

- **One price source.** Both the panel and the preflight read `credit_pricing` through
  `pricing_service.get_price`. AI ops keep the routed provider; local ops use `provider="local"`;
  publishing uses `provider="postforme", operation="upload"`.
- **Upload count = 1 per merged video** (one publish job per merge result), i.e.
  `upload_ops = merge_ops` when YouTube Upload is on. If a plan later publishes per channel
  variant, change it in one place (`upload_ops_for_plan()` in `music_costs.py`).
- **Server is authoritative.** The preflight includes upload credits, so the API and the panel
  agree; the panel shows the same breakdown the API charges.
- **Never mutate a saved preference on disable.** Only the widget enablement changes.
- YouTube stage status comes from existing `youtube_*` row fields; no schema change is needed for
  the first iteration.

## Work breakdown

### A. Credits (client + server) — implemented

- [x] `music_costs.py`: `publish_unit_cost`, `upload_ops`, `publish_total_cost` in
      `MusicPlanCostBreakdown`, included in `total_cost`; `upload_ops_for_plan()`.
- [x] `automation_card.py`: 6th credit cell **YouTube**; `set_plan_summary(..., upload_ops,
      upload_credits)`.
- [x] `music_view.py`: passes `publish_cost` + `auto_upload`, and the flag into both the preflight
      request and `BatchCreateRequest`.
- [x] `batch_service.py`: `publish_ops`/`publish_wallet_cost` added to `total_wallet_cost`, returned
      in every preflight payload, named in the insufficient-credits note; `_publish_operation_price()`
      reads `credit_pricing` (postforme/upload) with a 5-credit fallback.
- [x] `set_auto_upload_enabled`: never unchecks; `apply_automation_flags` restores the saved value
      even while disabled (bug 1).

Acceptance: for one plan, `panel total == preflight total`, and the difference vs today equals
`uploads × publish_unit_price` when YouTube Upload is on.

### B. Progress pipeline

- [ ] Batch progress card: YouTube stage chip per batch — `queued / uploading / uploaded / failed`
      from `youtube_pending`, `youtube_status`, `youtube_failed`, `youtube_url`.
- [ ] Row action **Upload to YouTube** for a completed merge: `POST /publish/jobs` (quote first via
      `POST /publish/quote`, confirm cost in the dialog); disabled with a tooltip when no channel is
      connected, already uploaded, or no merge exists.
- [ ] Reuse the publish worker pattern from Settings so the UI never blocks.

### C. Follow-ups

- [ ] Surface "5 credits per upload" beside the toggle and in the Generate confirmation.
- [ ] Retry/failure copy for Post for Me (webhook lag vs hard failure).
- [ ] Consider counting per-channel-variant uploads if product wants both versions published.

## Open questions

1. Upload count: **1 per merged video** (assumed) or 1 per channel variant (2 per merge)?
2. Should upload credits be reserved at plan creation (preflight) or charged per upload as today?
   Assumption above: included in preflight totals, still charged per upload.
3. The +110 delta on the reported plan: needs the account's resolved `/credits/operation-costs`
   dump (or the plan's op counts) to attribute exactly; the fix makes the two totals identical
   regardless of which op differed.

## Test plan

- Unit: `music_costs` breakdown with/without uploads, and `upload_ops_for_plan()`.
- Unit: `set_auto_upload_enabled(False)` keeps `isChecked()` and the saved settings value.
- API: preflight adds `publish_wallet_cost` and fails with the same total the panel shows.
- UI smoke (headless): automation card renders the YouTube cell; Progress row exposes the action.
