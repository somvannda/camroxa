# Post for Me (postforme.dev) Publishing Integration — Plan

**Status:** Phase 1 backend implemented on this branch; desktop integration in progress
**Date:** 2026-10-31
**Branch:** `feat/postforme-publishing`
**Worktree:** `G:\Developments\Projects\Camxora-worktrees\postforme-publishing`
**Base:** `origin/main` @ `fccf6b05`

### Implementation status

- [x] Migration 178: job provider columns, account/result/webhook tables, 5-credit price row
- [x] Post for Me client with retries, accounts, media, posts, results, webhooks
- [x] `/publish` API (connect, accounts, quote, jobs, retry, cancel, webhook)
- [x] v3 `publish` op + `/credits/operation-costs` + admin pricing dropdown
- [x] Backend tests (24 focused tests; full suite 3172 passed)
- [ ] Desktop upload worker wiring (models/client/worker added, UI in progress)
- [ ] Sandbox end-to-end run against the live Post for Me project
- [ ] Webhook registration + production secret provisioning

---

## 1. Goal

Let the CAMXORA desktop app publish a finished (merged/exported) video to YouTube automatically, using **Post for Me** (`api.postforme.dev`) as the upload/publishing provider, and charge **5 credits per upload** from the existing credits wallet.

Phase 1 ships YouTube only. The data model and API are platform-neutral so TikTok, Instagram, Facebook, X, Threads, Pinterest, LinkedIn and Bluesky can be added later without a second migration.

### In scope (Phase 1)

- Connect a YouTube channel via Post for Me OAuth.
- Upload the merged MP4 from the desktop to Post for Me through a signed upload URL.
- Create the social post with CAMXORA's existing YouTube metadata (title, description, tags, category, visibility, scheduled publish, made-for-kids, AI disclosure, thumbnail).
- Track job state end-to-end and surface it in the desktop (Progress / Workflow / Settings).
- Charge **5 credits per upload job**, idempotently, with refunds on definitive failure.
- Admin visibility + pricing configuration.

### Out of scope (Phase 1)

- TikTok / Instagram / Facebook / X / Threads / Pinterest / LinkedIn / Bluesky publishing (schema-ready only).
- Post analytics, feeds, comment management.
- Post for Me "White Label" migration (own platform developer credentials).
- Replacing the existing direct-Google YouTube upload path for already-connected users.
- Desktop bulk "publish all runs" UI beyond the existing auto-upload toggle.

---

## 2. Current state (verified in this checkout)

### What already exists

| Area | Files | Notes |
|---|---|---|
| YouTube OAuth + channel connection | `platform_api/routers/youtube.py`, `platform_api/services/youtube_connection_service.py`, `platform_api/repositories/youtube_connection_repo.py` | Google OAuth, PKCE, refresh-token encryption (`KeyEncryption`), channel picker, disconnect, resync |
| Direct YouTube upload runtime | `platform_api/services/youtube_upload_runtime.py` | `videos.insert` resumable upload, thumbnail, playlist |
| YouTube upload jobs | `platform_api/migrations/versions/003_add_youtube_upload_jobs.py`, `016_...` | Table `youtube_upload_jobs` (user, batch, profile, role, file_path, status, video id/url) |
| Worker | `platform_api/worker.py`, `platform_api/services/job_types.py` | `run_youtube_uploads` job type |
| Status read paths | `platform_api/routers/progress.py`, `platform_api/routers/music_history.py`, `platform_api/services/admin_pipeline_service.py` | All read `youtube_upload_jobs` |
| Desktop connection UI | `camxora_python/features/settings/views/settings_view.py` (YouTube + Publication tabs) | Connect / resync / disconnect, publication defaults |
| Desktop API client | `camxora_python/shared/services/platform_api.py` | YouTube connection methods only |
| Desktop merge completion hook | `camxora_python/features/video/services/pipeline_automation_service.py` → `_on_merge_succeeded()` | Natural place to trigger auto-upload |
| Credits | `platform_api/services/credit_pricing_service.py`, `platform_api/services/v3/*`, `credit_pricing` table | v3 credits-only charge/quote/refund with `ref_id` idempotency |

### Gaps found

1. **The desktop never calls the upload endpoints.** `auto_upload_youtube` exists only as a setting (`shared/lib/music_settings.py`, `features/music/widgets/automation_card.py`); nothing in `camxora_python` calls `POST /youtube/profiles/{id}/uploads/merge` or `/youtube/uploads/run`.
2. **The server upload path assumes a local file.** `merged_mp4_path` is a path on the API host, which cannot work for a desktop on another machine.
3. **Uploads are not charged.** No pricing row and no credit call exists for YouTube uploads.
4. **No provider abstraction.** Everything is YouTube-specific.
5. **Playlist support cannot be preserved via Post for Me.** Post for Me's YouTube configuration has no playlist field.
6. **Existing users' Google tokens cannot be transparently migrated** to Post for Me without a reconnect through Post for Me's OAuth.

### Post for Me facts (from the live OpenAPI spec, fetched 2026-10-31)

- Base URL: `https://api.postforme.dev/v1`, `Authorization: Bearer <project API key>`.
- Media: `POST /media/create-upload-url` → `{ upload_url, media_url }`; client `PUT`s file bytes to `upload_url`; `media_url` is used in the post.
- Post: `POST /social-posts` with `caption`, `social_accounts[]`, `media[]`, optional `scheduled_at`, `account_configurations[]`, `platform_configurations`, `external_id`, `isDraft`.
- YouTube settings go in **account-level** configuration: `title`, `privacy_status`, `made_for_kids`, `contains_synthetic_media`, `has_paid_product_placement`, `tags`, `category_id`, `default_language`, `localizations`, `publish_at`, `embeddable`, `license`, `public_stats_viewable`, `recording_date`.
- Thumbnail: `media[0].thumbnail_url` (supported by YouTube long-form).
- Large files: `media[0].skip_processing = true` avoids Post for Me transcoding. CAMXORA exports are already H.264/AAC, so this is a good default.
- Accounts: `POST /social-accounts/auth-url` → `{ url, platform }`; supports `external_id`, `permissions`, `force_reauth`. `GET /social-accounts` filters by `platform`, `external_id`, `id`, `status`. `POST /social-accounts/{id}/disconnect` disconnects; `DELETE` removes.
- Results: `GET /social-post-results?post_id=...` returns per-account `success`, `error`, `platform_data.id`, `platform_data.url`.
- Webhooks: created only via `POST /webhooks` (no dashboard UI). Events: `social.post.created|updated|deleted`, `social.post.result.created`, `social.account.created|updated`. Payload is authenticated with the plain header **`Post-For-Me-Webhook-Secret`** (compare to the stored secret). Must answer `2XX` within **1 second**; retries ~8 times over 24h; handler must be idempotent.
- OAuth redirect: Post for Me redirects to the project's configured callback with `provider`, `projectId`, `isSuccess`, `accountIds`, `failedAccountIds`, `error`. With system credentials, `redirect_url_override` does **not** work; the redirect URL must be set in the Post for Me dashboard.
- Limits: 5 req/s and 40 req/min per project; honor `429` + `Retry-After`.
- Project model: one API key owns all accounts and posts. Multi-tenant isolation is our responsibility via `external_id`. **Duplicate accounts are not allowed**; if a second user connects the same platform account, Post for Me updates the existing record.
- Pricing: $10/mo for up to 1,000 successful posts → ~**$0.01/post** COGS at the cap (less at lower volume).
- The provided key was validated with `GET /v1/social-accounts`: it works and the project currently has **0 accounts**.

> The API key shared in chat is a live project credential. It has been exposed in conversation history. **Rotate it before implementation** and store the new key only in server-side environment/secret storage. Never commit it, never ship it in the desktop binary.

---

## 3. Decisions to confirm

| # | Decision | Recommended | Why |
|---|---|---|---|
| D1 | Account connection model | **Post for Me canonical for new connections; existing direct-Google YouTube stays as a fallback for one release** | No forced reconnect for current users; easy rollback; direct path can be retired later |
| D2 | Post for Me project type | **Quickstart for Phase 1** | No platform developer approvals; users will see "Post for Me" during OAuth. White Label later if branding matters |
| D3 | Charge scope | **5 credits per publish job (one uploaded video), regardless of how many target accounts that job posts to** | Matches "5 credits per upload"; predictable for users; our COGS is per successful post, so multi-target jobs are still profitable at 5 credits |
| D4 | Media transport | **Desktop uploads directly to the Post for Me signed URL; the API only brokers the signed URL and metadata** | Large MP4s never pass through our API; no server disk/storage cost; desktop can show real progress |
| D5 | Desktop trigger | **After local merge succeeds** (`_on_merge_succeeded`), if auto-upload is enabled for the profile | That is when a publishable file exists; matches existing "Auto-Upload" UI |
| D6 | Retry charging | **First attempt charges 5; retries after a definitive failure are free after a refund; retries of an in-flight job never charge again** | No double billing |
| D7 | Playlist behavior | **Drop playlist selection for Post for Me uploads in Phase 1** (keep the field for direct YouTube) | Post for Me has no playlist field; hides a false promise |
| D8 | Default auto-upload | **Off by default, opt-in per profile** | Avoid surprise 5-credit charges |
| D9 | Feature flag | **`publish_via_postforme` (env + admin setting), default off** | Sandbox-first rollout and instant rollback |
| D10 | New table vs. generalize old | **Generalize `youtube_upload_jobs` with provider/platform columns** | Keeps Progress, Music History, and Admin Pipeline queries working; much smaller blast radius |

If all ten are accepted, the rest of this document can be implemented as written.

---

## 4. Target architecture

```
Desktop (PyQt6)                              Platform API (FastAPI)                     Post for Me
────────────────                             ──────────────────────                     ────────────
Merge finished
  │
  ├─(1) POST /publish/jobs ─────────────────▶ create job row (status=pending_upload)
  │                                            create-upload-url ─────────────────────▶ POST /media/create-upload-url
  │◀── {job_uid, upload_url, media_url} ──────┘                                         {upload_url, media_url}
  │
  ├─(2) PUT file bytes ──────────────────────────────────────────────────────────────▶ signed upload_url
  │       (direct, with progress)
  │
  ├─(3) POST /publish/jobs/{uid}/complete ───▶ verify job, quote+charge 5 credits
  │                                            POST /social-posts ────────────────────▶ POST /social-posts
  │◀── {status=processing, post_id} ──────────┘                                         {social post}
  │
  │                                            webhook (Post-For-Me-Webhook-Secret) ◀── social.post.result.created
  │                                            update job + result, refund on failure
  │
  └─(4) GET /publish/jobs/{uid} (poll) ─────▶ status / url / error
```

Key properties:

- The Post for Me API key never leaves the server.
- The MP4 goes desktop → Post for Me directly.
- Charging happens only after the file is actually uploaded.
- Webhooks are the primary result path; polling is the fallback.
- `youtube_upload_jobs` remains the single status table, so existing progress/history/admin screens keep working.

---

## 5. Data model (migration `178_postforme_publishing.py`)

Latest applied revision is `177`. New migration is additive and reversible.

### 5.1 Generalize `youtube_upload_jobs`

```sql
ALTER TABLE youtube_upload_jobs
  ADD COLUMN IF NOT EXISTS provider              VARCHAR(32) NOT NULL DEFAULT 'youtube_direct',
  ADD COLUMN IF NOT EXISTS platform              VARCHAR(32) NOT NULL DEFAULT 'youtube',
  ADD COLUMN IF NOT EXISTS social_account_id     TEXT,
  ADD COLUMN IF NOT EXISTS postforme_post_id     TEXT,
  ADD COLUMN IF NOT EXISTS postforme_result_id   TEXT,
  ADD COLUMN IF NOT EXISTS media_url             TEXT,
  ADD COLUMN IF NOT EXISTS upload_url            TEXT,
  ADD COLUMN IF NOT EXISTS upload_expires_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS file_size_bytes       BIGINT,
  ADD COLUMN IF NOT EXISTS file_checksum         TEXT,
  ADD COLUMN IF NOT EXISTS thumbnail_path        TEXT,
  ADD COLUMN IF NOT EXISTS credits_charged_units BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS credit_ref_id         TEXT,
  ADD COLUMN IF NOT EXISTS error_code            VARCHAR(64),
  ADD COLUMN IF NOT EXISTS scheduled_at          TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS result_payload        JSONB;

CREATE INDEX IF NOT EXISTS idx_youtube_upload_jobs_provider_status
  ON youtube_upload_jobs(provider, status, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_upload_jobs_credit_ref
  ON youtube_upload_jobs(credit_ref_id)
  WHERE credit_ref_id IS NOT NULL;
```

Existing rows default to `youtube_direct`, so every current query keeps returning the same data.

> **Status-vocabulary constraint (important):** Post for Me jobs must never use the legacy status `pending`. `YouTubeConnectionRepository.claim_upload_jobs_for_run()` claims every row with `status = 'pending'` and flips it to `running` before uploading from `file_path` on the API host. A Post for Me job in `pending` would be stolen by the legacy worker and fail. The Post for Me lifecycle therefore starts at `pending_upload`, and the legacy worker must also be scoped with `AND provider = 'youtube_direct'` as defence in depth.

### 5.2 `publish_social_accounts`

```sql
CREATE TABLE publish_social_accounts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_id          UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
  provider            VARCHAR(32) NOT NULL DEFAULT 'postforme',
  platform            VARCHAR(32) NOT NULL,
  postforme_account_id TEXT NOT NULL,
  external_id         TEXT,
  username            TEXT,
  display_name        TEXT,
  avatar_url          TEXT,
  status              VARCHAR(24) NOT NULL DEFAULT 'connected',
  metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, profile_id, postforme_account_id)
);

CREATE INDEX ... ON publish_social_accounts(user_id, profile_id, platform);
CREATE INDEX ... ON publish_social_accounts(postforme_account_id);
```

### 5.3 `publish_connect_sessions`

Short-lived record of an OAuth attempt so the desktop can poll and show the right state.

```sql
CREATE TABLE publish_connect_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_id    UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
  platform      VARCHAR(32) NOT NULL,
  status        VARCHAR(32) NOT NULL DEFAULT 'pending_browser',
  account_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
  error_message TEXT,
  expires_at    TIMESTAMPTZ NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.4 `publish_job_results`

One row per platform/account outcome; Phase 1 writes exactly one.

```sql
CREATE TABLE publish_job_results (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id              UUID NOT NULL REFERENCES youtube_upload_jobs(id) ON DELETE CASCADE,
  platform            VARCHAR(32) NOT NULL,
  social_account_id   TEXT NOT NULL,
  postforme_result_id TEXT,
  success             BOOLEAN NOT NULL DEFAULT FALSE,
  platform_post_id    TEXT,
  platform_url        TEXT,
  error_message       TEXT,
  details             JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ... ON publish_job_results(postforme_result_id)
  WHERE postforme_result_id IS NOT NULL;
```

### 5.5 `publish_webhook_events`

```sql
CREATE TABLE publish_webhook_events (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type         VARCHAR(64) NOT NULL,
  postforme_post_id  TEXT,
  payload            JSONB NOT NULL,
  received_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at       TIMESTAMPTZ,
  error_message      TEXT
);
```

---

## 6. Credits and pricing — 5 credits per upload

### 6.1 Price row

Provider is a real external provider, so **do not** use the `local` provider registry.

```python
# platform_api/services/publish_pricing.py (new)
POSTFORME_AI_SERVICE = "postforme"
POSTFORME_UPLOAD_OPERATION = "upload"
POSTFORME_UPLOAD_CREDITS = 5          # display credits
POSTFORME_UPLOAD_COST_CREDITS = 1     # ~$0.01 Post for Me COGS at GCV $0.01
```

Seed row (migration + admin seed endpoint, `ON CONFLICT DO NOTHING` so an admin override is never overwritten):

| ai_service | operation_type | sub_model | credits_per_operation | external_cost_cents |
|---|---|---|---|---|
| `postforme` | `upload` | `""` | `50000` units (= 5 credits) | `10000` units (= 1 credit) |

`credit_pricing.external_cost_cents` is a legacy column name; it stores **cost micro-credit units**, not cents. 5 credits → `credits_to_units(5)` = 50,000 units.

### 6.2 v3 credits-only wiring

Because plans no longer set operation prices, the price must be discoverable by the v3 billing service:

`platform_api/services/v3/ops.py`

```python
DIRECT_PRICED_OPS = (*STUDIO_OPS, "publish")
SUPPORTED_OPS = (*PLAN_OP_COLUMNS.keys(), *DIRECT_PRICED_OPS)

PRICING_FALLBACKS["publish"] = (("postforme", "upload"),)
```

`platform_api/services/v3/list_prices.py`

```python
OP_SCAN_ALIASES["publish"] = ("upload", "publish")
```

No `plans` column and no `PLAN_OP_COLUMNS` entry — exactly like the studio ops, which are priced directly from `credit_pricing`.

### 6.3 Charge / refund rules

| Event | Credits |
|---|---|
| Job created, `pending_upload` | 0 |
| File uploaded, `complete` called, sufficient balance | **−5**, `ref_id = job_uid` |
| Insufficient balance at complete | 0; job → `pending_payment`; user tops up and retries |
| `create post` API error | refund **+5** with `ref_id = job_uid`, job → `failed` |
| Post for Me reports all targets failed | refund **+5**, job → `failed` |
| Post for Me reports success | keep the 5; job → `success` |
| Retry after refund | new charge with `ref_id = f"{job_uid}:retry:{attempt}"` |
| Retry while already charged | no second charge |
| Upload URL expires before upload | 0; job → `failed`; free re-init |

Idempotency uses the existing v3 `charge(..., ref_id=...)` and `refund(..., ref_id=...)` support. The `credit_ref_id` column stores the exact ref used so a retry can decide whether to charge or reuse.

### 6.4 Where the price is displayed

- API: `GET /credits/operation-costs` adds `{ operation_type: "publish", provider: "postforme", credits_per_operation: 5 }`.
- API: `GET /publish/quote` returns price + current balance.
- Desktop: pre-upload confirmation line, auto-upload settings label, and Progress upload panel ("Upload to YouTube · 5 credits").
- Admin: `/admin/pricing` dropdown gets provider `postforme` and operation `upload` (“YouTube upload (Post for Me)”).
- Admin plans: optional display-only line "YouTube upload — 5 credits" in `pricing_credit_lines`; no plan column change.

---

## 7. Backend API surface

New router `platform_api/routers/publish.py`, prefix `/publish`, dual-mounted on v1 and v3 in `main.py` (same pattern as `youtube.router`).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/publish/providers` | Platforms supported + connection state + price |
| `GET` | `/publish/accounts?profile_id=` | Accounts linked to a profile (never exposes tokens) |
| `POST` | `/publish/accounts/connect` | `{profile_id, platform}` → `{session_id, auth_url}` |
| `GET` | `/publish/accounts/callback` | Browser redirect target; verifies and links accounts, returns HTML |
| `DELETE` | `/publish/accounts/{account_id}` | Disconnect + delete mapping |
| `GET` | `/publish/quote` | `{credits_per_upload: 5, balance, available}` |
| `POST` | `/publish/jobs` | Create job + signed upload URL |
| `POST` | `/publish/jobs/{job_uid}/complete` | Charge + create social post |
| `GET` | `/publish/jobs/{job_uid}` | Job detail + results |
| `GET` | `/publish/jobs?batch_id=&status=` | List jobs for desktop |
| `POST` | `/publish/jobs/{job_uid}/retry` | Retry failed job |
| `POST` | `/publish/jobs/{job_uid}/cancel` | Cancel pending/in-flight job |
| `POST` | `/publish/webhooks/postforme` | Public webhook receiver (secret header) |

### 7.1 Create job request

```json
{
  "profile_id": "uuid",
  "batch_id": "uuid",
  "role": "OK",
  "title": "Song title",
  "description": "YouTube description",
  "tags": ["tag1", "tag2"],
  "category_id": "10",
  "visibility": "scheduled",
  "publish_at": "2026-11-02T14:35:00Z",
  "made_for_kids": false,
  "contains_synthetic_media": true,
  "file_name": "MERGED_OK_PRIMARY.mp4",
  "file_size_bytes": 412345678,
  "file_checksum": "sha256:...",
  "thumbnail_file_name": "thumb.png",
  "platforms": ["youtube"]
}
```

Response:

```json
{
  "job_uid": "…",
  "status": "pending_upload",
  "upload_url": "https://…signed…",
  "upload_expires_at": "2026-10-31T12:30:00Z",
  "media_url": "https://…",
  "credits_per_upload": 5,
  "platforms": ["youtube"]
}
```

The API creates one job row per `(profile, platform, role)` and calls `create-upload-url` once for the video and once for the thumbnail (if supplied).

### 7.2 Complete request

```json
{ "checksum": "sha256:..." }
```

Server verifies the job is owned, `pending_upload`, not expired, and the upload was reported complete by the client. It then:

1. quotes `publish` (5 credits) and charges with `ref_id = job_uid`;
2. builds the Post for Me payload;
3. calls `POST /social-posts`;
4. stores `postforme_post_id`, status `processing`;
5. returns `{status, post_id, credits_charged: 5, balance}`.

### 7.3 Post for Me payload mapping

```json
{
  "caption": "<description>",
  "media": [{
    "url": "<media_url>",
    "thumbnail_url": "<thumbnail_media_url>",
    "skip_processing": true
  }],
  "social_accounts": ["spc_..."],
  "external_id": "<job_uid>",
  "account_configurations": [{
    "social_account_id": "spc_...",
    "configuration": {
      "title": "<title>",
      "privacy_status": "private",
      "publish_at": "2026-11-02T14:35:00Z",
      "made_for_kids": false,
      "contains_synthetic_media": true,
      "tags": ["tag1"],
      "category_id": "10",
      "embeddable": true,
      "license": "youtube",
      "public_stats_viewable": true
    }
  }]
}
```

Visibility mapping:

| CAMXORA visibility | Post for Me `privacy_status` | `publish_at` |
|---|---|---|
| `public` | `public` | omitted |
| `unlisted` | `unlisted` | omitted |
| `private` | `private` | omitted |
| `scheduled` | `private` | computed UTC timestamp |

YouTube only honors `publish_at` with `privacy_status=private`. This matches the current direct path's behavior.

Playlist: not sent (see D7).

### 7.4 Webhook receiver

```python
@router.post("/publish/webhooks/postforme", include_in_schema=False)
async def postforme_webhook(request: Request):
    if not hmac.compare_digest(
        request.headers.get("Post-For-Me-Webhook-Secret", ""),
        settings.postforme_webhook_secret,
    ):
        raise HTTPException(status_code=401)
    raw = await request.body()
    payload = json.loads(raw)
    await repo.insert_webhook_event(payload)       # fast, idempotent
    await job_queue.enqueue_if_absent(             # background sync
        job_type=JOB_SYNC_PUBLISH_RESULTS,
        payload={"post_id": payload.get("data", {}).get("id")},
        priority=PRI_PUBLISH_SYNC,
    )
    return {"ok": True}                            # well under 1s
```

Then `JOB_SYNC_PUBLISH_RESULTS` calls `GET /social-post-results?post_id=...`, upserts `publish_job_results`, updates the job, and refunds if all targets failed. A periodic poller handles jobs stuck in `processing` older than 10 minutes (webhooks can be delayed/lost).

### 7.5 Post for Me client

`platform_api/services/postforme_client.py`

- `httpx.AsyncClient` with base URL from `settings.postforme_api_base_url` (default `https://api.postforme.dev/v1`).
- Timeout `settings.postforme_timeout_seconds` (default 30).
- Retries: `429` (respect `Retry-After`), `5xx`, network errors; max 3; exponential backoff; never retry non-idempotent `POST /social-posts` blindly — use `external_id` dedupe and a follow-up `GET /social-posts?external_id=`.
- Methods: `create_media_upload_url`, `create_post`, `get_post`, `list_post_results`, `get_post_result`, `create_auth_url`, `list_accounts`, `disconnect_account`, `create_webhook`.
- Structured logging with request id + status, never log the API key or tokens.

---

## 8. Desktop (PyQt6) changes

### 8.1 Models and client

New file `camxora_python/shared/models/publishing.py`:

- `PublishAccount`, `PublishAccountsResponse`
- `StartPublishConnectionResponse`
- `PublishQuote`
- `PublishJob`, `PublishJobListResponse`
- `CreatePublishJobRequest/Response`
- `CompletePublishJobRequest/Response`

Add to `camxora_python/shared/services/platform_api.py`:

- `list_publish_accounts(profile_id)`
- `start_publish_connection(profile_id, platform)`
- `disconnect_publish_account(account_id)`
- `get_publish_quote()`
- `create_publish_job(payload)`
- `complete_publish_job(job_uid, checksum)`
- `get_publish_job(job_uid)`
- `list_publish_jobs(batch_id=None, status=None)`
- `retry_publish_job(job_uid)`

### 8.2 Upload worker

New `PublishUploadWorker(QThread)` in `camxora_python/shared/workers/data_workers.py`:

1. `create_publish_job` on the API.
2. `PUT` the MP4 to `upload_url` with `Content-Type: video/mp4`, streaming in chunks, emitting `progress(bytes_sent, total)`.
3. `PUT` the thumbnail (if any) with `image/png` or `image/jpeg`.
4. `complete_publish_job`.
5. Poll `get_publish_job` every 5s for up to 10 minutes, or until the push workspace notification arrives.

Network work stays off the UI thread (project rule). All UI updates go through the existing signal pattern.

### 8.3 Auto-upload hook

`camxora_python/features/video/services/pipeline_automation_service.py` → `_on_merge_succeeded()`:

- after `mark_desktop_pipeline_complete(...)`, if `auto_upload_youtube` is enabled for the profile and a Post for Me YouTube account is linked:
  - skip if a job already exists for `(batch, profile, role)` in a non-failed state;
  - show a confirmation/preflight with the 5-credit cost if balance is below 5;
  - start `PublishUploadWorker`.
- failures must not mark the merge as failed; upload is a separate stage (`youtube`), matching `WorkflowSteps` today.

### 8.4 Settings UI

`features/settings/views/settings_view.py`, YouTube tab:

- Keep the existing Google "Connect Channel" button only when the legacy direct path is enabled.
- Add "Connect with Post for Me" for the new path.
- Show linked accounts, status, and a "Reconnect" action.
- Publication tab: keep metadata fields; remove/disable Playlist for Post for Me profiles with a short note.
- Add a "Publishing" summary: provider, account, price (`5 credits/upload`), auto-upload toggle.

### 8.5 Progress / Workflow

`youtube_upload_jobs` is still the source, so `progress.py` continues to return `meta.youtube_status`, `youtube_url`, counts. Extend the mapping so `provider='postforme'` statuses (`uploading`, `queued`, `processing`) count as pending. No desktop contract change is required beyond recognizing the new statuses.

Optional upgrade: add a "Retry upload" action in the run panel that calls `POST /publish/jobs/{uid}/retry`.

---

## 9. Configuration and operations

`platform_api/config.py` additions:

```python
postforme_api_key: str = ""
postforme_api_base_url: str = "https://api.postforme.dev/v1"
postforme_webhook_secret: str = ""
postforme_timeout_seconds: int = 30
postforme_enabled: bool = False
```

Environment:

```bash
PLATFORM_POSTFORME_API_KEY=...          # rotated key, server only
PLATFORM_POSTFORME_WEBHOOK_SECRET=...   # returned by POST /v1/webhooks
PLATFORM_POSTFORME_ENABLED=true         # sandbox first
```

Setup steps (one-time):

1. Rotate the exposed key in the Post for Me dashboard.
2. Create/confirm a **Quickstart** project.
3. Set the project OAuth redirect URL to `https://api.camxora.com/api/v3/publish/accounts/callback` (and the sandbox equivalent).
4. Register the webhook with `POST /v1/webhooks` for `social.post.result.created` (and optionally `social.post.updated`, `social.account.created`).
5. Store the returned `secret` in `PLATFORM_POSTFORME_WEBHOOK_SECRET`.
6. Add the key to the deploy secret store, never to git.

Webhook registration helper: `platform_api/scripts/register_postforme_webhook.py` (idempotent; lists existing webhooks and refuses duplicate URLs).

Feature flag: `publish_via_postforme` checked in the publish router and desktop settings. When off, all endpoints return `503` with a clear message and the desktop hides the new UI.

---

## 10. Security and correctness

- **API key rotation** is mandatory before go-live.
- Project key stays server-side; the desktop only ever receives short-lived signed upload URLs and our own auth token.
- Account ownership is enforced in SQL by `user_id` + `profile_id`; the client never sends a Post for Me account id without a server-side lookup.
- `external_id = f"camxora:{user_id}"` on connect; the callback verifies it before linking. After linking, ownership comes from our table, not `external_id`, because Post for Me may update it when another user connects the same account.
- Shared-account collision: Post for Me allows only one record per platform account. If two CAMXORA users connect the same channel, the second connect updates `external_id`. Our links still work, but the second user's connect flow must not delete the first user's link. Documented limitation; revisit if it happens in practice.
- Webhook header comparison uses `hmac.compare_digest`.
- Webhook handler does no slow work; it inserts and enqueues.
- Signed upload URLs expire; expired jobs fail cleanly without a charge.
- PII/media retention: we store only the public `media_url` and IDs; the MP4 itself stays on the user's machine and Post for Me storage.
- Rate limits: the client serializes media-upload URL creation per user and honors `Retry-After`.
- Idempotency: `job_uid` on create, `credit_ref_id` on charge/refund, `postforme_result_id` unique on results, `external_id = job_uid` on posts.
- No charge if the file never uploads.

---

## 11. Testing plan

### Unit (platform_api/tests)

- `test_postforme_client.py`: request shapes, Bearer header, 429 retry with `Retry-After`, 5xx retry, no retry on 4xx, timeout mapping, key never logged.
- `test_publish_service.py`: status transitions; charge only on complete; refund on create failure; refund on all-target failure; no double charge on retry; shared-account linking; ownership checks.
- `test_publish_router.py`: auth required, feature flag off → 503, create/complete/retry/cancel, response contracts.
- `test_publish_webhook.py`: wrong/missing secret → 401; valid → 200 < 1s; duplicate event is idempotent; background job enqueued.
- `test_publish_pricing.py`: seed row = 50,000 units; v3 quote returns 5 credits; admin update wins over seed.
- Extend `test_progress_router.py` to assert Post for Me statuses map to pending/success/failed.

### Desktop tests

- Model parsing for all new responses.
- Upload worker progress + failure paths with a fake HTTP session.
- Auto-upload trigger only when enabled and an account is linked.
- Settings tab binding for Post for Me accounts.

### Sandbox E2E

1. Connect a test YouTube channel via the sandbox redirect URL.
2. Run a short export + merge with auto-upload on.
3. Assert job goes `pending_upload → processing → success`, YouTube URL stored, 5 credits debited once.
4. Force a Post for Me failure (invalid title/target) and assert refund.
5. Replay the webhook twice and assert no double refund / no duplicate result.
6. Kill the desktop after upload; assert webhook/poller still completes the job.

### Regression

- Legacy direct YouTube jobs still list correctly in Progress, Music History, and Admin Pipeline.
- Existing YouTube connect/disconnect still works with the flag off.

---

## 12. Rollout and rollback

1. Ship migration + backend with `PLATFORM_POSTFORME_ENABLED=false` (no user-visible change).
2. Deploy to sandbox; run E2E; verify webhook latency and credit ledger.
3. Enable for internal accounts only (allowlist), then a small cohort.
4. Enable globally.
5. After one stable release, decide whether to retire the direct Google path.

Rollback:

- Flip `PLATFORM_POSTFORME_ENABLED=false` → desktop falls back to legacy direct YouTube (if connected) and hides Post for Me UI.
- Migration is additive; old code ignores new columns/tables. No destructive downgrade needed in production.
- Refund stuck `processing` jobs manually via the existing credit ledger tooling if the provider is unavailable.

---

## 13. Risks and open questions

| Risk | Impact | Mitigation |
|---|---|---|
| Users see "Post for Me" in OAuth (Quickstart) | Brand surprise | Accept for Phase 1; White Label later |
| Existing users must reconnect YouTube for Post for Me | Friction + support load | Keep direct path as fallback; in-app banner “Reconnect to enable auto-upload” |
| Playlist support lost | Feature regression for some users | Hide playlist for Post for Me profiles; keep direct path for them |
| Shared YouTube channel across users | Second connect changes `external_id` | Store ownership in our table; never delete another user's link; alert on conflict |
| Post for Me outage | Uploads fail | Retries + refund; direct path fallback |
| Upload URL expiry on slow connections | Failed uploads | 30-minute expiry check, free re-init, desktop pre-checks file size |
| Webhook lost/delayed | Jobs stuck `processing` | 10-minute poller + `GET /social-post-results` |
| Post for Me pricing changes | Margin erosion | Admin-editable 5-credit price + cost basis; monitor COGS |
| YouTube category/language values differ | Rejected posts | Reuse existing validated category list; default `10` (Music) |
| Thumbnail unsupported for Shorts | Cosmetic | Phase 1 long-form only; detect Shorts later |
| 5 credits per job with multiple targets | Undercharge for multi-platform | D3 decision; revisit when multi-platform ships |

Open questions for the product owner:

1. Approve D1–D10, especially **D1** (coexist vs. replace) and **D3** (per job vs. per target).
2. Is the Post for Me project Quickstart or White Label?
3. Should the 5 credits be charged for **failed** uploads? (Recommendation: no.)
4. Should auto-upload be opt-in per profile or a global default?
5. Do we need playlist parity in Phase 1? If yes, Post for Me cannot provide it; we would have to keep the direct YouTube path for those profiles.
6. Who rotates the exposed API key, and where is the production secret stored?

---

## 14. Implementation phases (estimate)

| Phase | Work | Estimate |
|---|---|---|
| 0 | Rotate key, project redirect URL, webhook registration, env/config | 0.5 day |
| 1 | Migration 178, pricing row, Post for Me client, publish service/repo, account connect, create/complete/retry, tests | 4–5 days |
| 2 | Desktop models/client, upload worker, merge hook, settings UI, progress statuses, tests | 4–5 days |
| 3 | Webhook + poller + refunds, admin job view, pricing dropdown, sandbox E2E | 2–3 days |
| 4 | Docs/changelog, rollout, monitoring | 1 day |
| **Total** | | **~12–14 working days** |

---

## 15. Acceptance criteria

- [ ] A merged MP4 from the desktop uploads to YouTube through Post for Me and the video URL appears in Progress and Workflow.
- [ ] Exactly **5 credits** are debited once per successful upload.
- [ ] A failed upload or failed post creation refunds the 5 credits exactly once.
- [ ] Retrying a failed job does not double-charge.
- [ ] Insufficient balance blocks the upload before any Post for Me call and shows a top-up prompt.
- [ ] Disconnecting an account prevents new jobs for that profile.
- [ ] Legacy direct YouTube jobs and connections still work with the flag off.
- [ ] Webhook handler responds in < 1s and is idempotent under replay.
- [ ] Admin can see and edit the `postforme/upload` price (default 5 credits).
- [ ] No API key or OAuth token is present in desktop code, logs, or git.

---

## 16. First step after approval

1. Rotate the exposed Post for Me key and place the new key in the sandbox secret store.
2. Confirm D1–D10 in this document.
3. Implement Phase 0 + Phase 1 on `feat/postforme-publishing`, commit in small checkpoints, and run the backend test suite before touching the desktop.
