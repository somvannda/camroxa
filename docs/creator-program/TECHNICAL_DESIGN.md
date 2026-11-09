# Camxora Creator Program — Technical Design

**Version:** 1.0 (proposal)
**Date:** 2026-11-09
**Related:** [README](./README.md) · [BRD](./BRD.md) · [Product Spec](./PRODUCT_SPEC.md) · [Roadmap](./ROADMAP.md)

---

## 1. Architecture decision

**The creator domain belongs in `platform_api` (FastAPI), database `platform_db`.**

Why:

- `users`, `stream_albums`, `stream_tracks`, `suno_tasks`, payments, credits, and admin APIs already live there.
- The public streaming API (`/api/v3/public/streaming/*`) and admin streaming console are there.
- `musicapi` is the generation proxy and uses a separate database (`sunoapi`); putting creator identity or payouts there would require cross-database joins for every page and payout.

**New code layout**

```
platform_api/
  routers/
    creators_public.py        # /api/v3/creators/*
    creator_studio.py         # /api/v3/creator/*
    admin_creators.py         # /api/v3/admin/creators/*
    admin_royalty.py          # /api/v3/admin/royalty/*
    admin_payouts.py          # /api/v3/admin/payouts/*
  services/
    creator_profile_service.py
    creator_application_service.py
    creator_release_service.py
    creator_analytics_service.py
    creator_earnings_service.py
    royalty_policy_service.py      # MISSING today; referenced by streaming_admin.py
    royalty_engine.py
    stream_validation_service.py
    payout_service.py
    kyc_service.py
    creator_fraud_service.py
  repositories/
    creator_repo.py
    royalty_repo.py
    payout_repo.py
    stream_event_repo.py
  models/
    creator.py
    royalty.py
    payout.py
  migrations/versions/186_*.py ... 199_*.py
```

**Frontend**

- `camxora.com/app/(site)/creators/*` — public pages (server components).
- `camxora.com/app/(site)/creator/*` — Creator Studio (client components + server shells).
- `camxora.com/lib/creator-api.ts` — typed client, follows existing `lib/*-api.ts` conventions.
- `admin_portal/src/pages/creators/*` — admin consoles, React Query + existing UI kit.

**Hard rule:** the Studio editor never writes creator/catalog/payout tables. It calls the creator release API.

---

## 2. Integration model

```
camxora.com ──/api/v3/*──► platform_api ──► platform_db
     │                         │
     │                         ├── stream_albums/stream_tracks (public catalog)
     │                         ├── suno_tasks (web-music generations)
     │                         ├── creator_* / royalty_* / payout_* (new)
     │                         └── mail_* / notification_queue
     │
     └── Next.js rewrite (PLATFORM_API_URL) — no direct DB access

Studio (camxora.com/studio) ──POST /api/v3/creator/releases──► creator_release_service
                                  └── reads suno_tasks, never writes studio tables

admin_portal ──/api/v3/admin/*──► platform_api
```

### Dependency on the parallel Studio work

| Contract | Owner | Shape |
|---|---|---|
| Publish a generation | Creator Program | `POST /api/v3/creator/releases` with `{source:{type:"web_music_generation",task_id,variant}, metadata:{...}}` |
| Open Studio from a release | Studio | `GET /studio/editor?task_id=...&variant=...` |
| Deep link after publish | Creator Program | `/creator/releases/[id]` |
| Shared UI | Design system | `CreatorBadge`, `CreatorAvatar`, `FollowButton`, `ReleaseCard` |

The Studio agent should **not** create a second publish flow, release metadata schema, or profile editor. Coordinate migration numbers: creator program reserves `186–199`; Studio should use `200+` or a timestamped revision to avoid conflicts.

---

## 3. Current-state audit

### 3.1 What exists and is reusable

| Area | Evidence | Reuse |
|---|---|---|
| Users | `platform_api/migrations/versions/001_initial_schema.py` (`users`) + `099` avatar | `users.id` is the creator ID |
| Catalog | `043_streaming_catalog.py` (`stream_albums`, `stream_tracks`) | Publish target |
| Play counts | `072_stream_track_play_count.py`, `stream_tracks.play_count` | Seed analytics |
| Likes | `073_stream_track_likes.py`, `099`/`172` web-music likes/dislikes | Saves metric |
| Web-music library | `suno_tasks` (`source='web_music'`), `/api/v3/web-music/generations` | Publish source |
| Upload pipeline | `streaming_upload_service.py`, B2 + signed playback | Asset hosting |
| Public API | `routers/streaming_public.py` (home/albums/artists/search/play) | Extend, don't duplicate |
| Reports | `173_web_music_reports.py` | Unify into moderation |
| Mail | `mail_*` tables, `mailAutomations.ts`/`mail.ts` | Lifecycle emails |
| Notifications | `notification_queue` | In-app notifications |
| Payments | ChmabaPay + KHQR (`billing.py`, admin config) | Tips/payout rails |
| Credits | `credit_wallets`, micro-credit migration `028` | Bonus prizes |
| Admin | `admin_portal` + `admin.py` | New consoles |
| Marketplace | `041_add_marketplace_items.py` | Phase 4 packs |
| Paid downloads | `musicapi/migrations/0016_download_purchases.sql` (sunoapi DB) | Phase 4; cross-DB bridge |

### 3.2 What is broken or missing

| # | Finding | Evidence | Severity |
|---|---|---|---|
| B1 | `valid_streams` table is queried but **never created** | `streaming_catalog_service.py:110-120`, `streaming_admin.py:212-225`; no `CREATE TABLE valid_streams` anywhere | **Blocker** |
| B2 | `royalty_ledger` table is queried but **never created** | `streaming_admin.py:226-235`; no migration | **Blocker** |
| B3 | `RoyaltyPolicyService` is imported but **does not exist** | `streaming_admin.py:206`; only `royalty_math.py` exists | **Blocker** — `GET /streaming/admin/catalog` 500s |
| B4 | `stream_tracks.origin` is read but **never added** | `streaming_admin.py:240`; no migration | **Blocker** for weighting |
| B5 | No creator profile/handle/bio table | — | High |
| B6 | No follow graph | — | High |
| B7 | No application/verification/badge tables | — | High |
| B8 | No release workflow; web-music generations are not publishable to the catalog | `callbacks.py:48-59` only does B2 backfill | High |
| B9 | No earnings/payout ledger | — | High |
| B10 | Public artist pages are static fictional data | `camxora.com/lib/artist-data.ts` | High (trust) |
| B11 | `/discover`, `/community` have non-functional follow buttons and mock counts | `app/(site)/discover/page.tsx`, `community/page.tsx` | Medium |
| B12 | No public creator page backed by data | `artist/[id]/page.tsx` uses `artist-data` | High |
| B13 | `artist-program` applies by email only | `app/(site)/artist-program/page.tsx` | Medium |
| B14 | `valid_streams` failure is swallowed, so stats silently show 0 | `streaming_catalog_service.py:121-122` | Medium |
| B15 | `download_purchases` lives in `sunoapi`, creator earnings in `platform_db` | cross-DB | Medium (design decision) |

> **Phase 0 action:** fix B1–B4 before anything else. They are small migrations + one service, and they unblock both analytics and monetization. The admin catalog endpoint is likely broken on `main` today.

---

## 4. Domain model

### 4.1 Entity overview

```
users (existing)
  │ 1:1
  ├── creator_profiles
  │     ├── creator_follows (follower ↔ creator)
  │     ├── creator_badges
  │     ├── creator_applications
  │     ├── creator_verifications
  │     ├── creator_payout_accounts
  │     ├── creator_kyc
  │     └── creator_earnings ──► creator_payout_items ──► creator_payouts
  │
  └── stream_albums (existing)
        └── stream_tracks (existing)
              ├── creator_releases (workflow wrapper)
              ├── creator_track_credits
              ├── listen_events (raw)
              ├── valid_streams (qualified)
              └── royalty_ledger

royalty_policies ──► royalty_periods ──► royalty_ledger
```

### 4.2 Core tables (DDL sketches)

> Use `gen_random_uuid()`, `timestamptz`, and integer micro-USD. Do not use floats for money.

#### `creator_profiles`

```sql
CREATE TABLE creator_profiles (
  user_id            UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  handle             VARCHAR(30) NOT NULL,
  display_name       VARCHAR(50) NOT NULL,
  tagline            VARCHAR(120),
  bio                TEXT,
  country_code       CHAR(2),
  city               VARCHAR(80),
  avatar_url         TEXT,
  banner_url         TEXT,
  links              JSONB NOT NULL DEFAULT '[]',      -- [{label,url}]
  genres             TEXT[] NOT NULL DEFAULT '{}',
  influences         TEXT[] NOT NULL DEFAULT '{}',
  pronouns           VARCHAR(20),
  ai_disclosure      VARCHAR(20) NOT NULL DEFAULT 'none'
                     CHECK (ai_disclosure IN ('none','ai_assisted','ai_artist')),
  tier               VARCHAR(20) NOT NULL DEFAULT 'creator'
                     CHECK (tier IN ('creator','verified','partner')),
  status             VARCHAR(20) NOT NULL DEFAULT 'active'
                     CHECK (status IN ('draft','active','at_risk','suspended','offboarded')),
  verified_at        TIMESTAMPTZ,
  verification_expires_at TIMESTAMPTZ,
  follower_count     INTEGER NOT NULL DEFAULT 0,
  program_joined_at  TIMESTAMPTZ,
  payout_currency    CHAR(3) NOT NULL DEFAULT 'USD',
  support_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_creator_handle ON creator_profiles (LOWER(handle));
CREATE INDEX idx_creator_status ON creator_profiles (status, tier);
CREATE INDEX idx_creator_genres ON creator_profiles USING GIN (genres);
```

#### `creator_handle_history`

```sql
CREATE TABLE creator_handle_history (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  old_handle  VARCHAR(30) NOT NULL,
  new_handle  VARCHAR(30) NOT NULL,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  redirect_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '12 months'
);
```

#### `creator_applications`

```sql
CREATE TABLE creator_applications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  version         INTEGER NOT NULL DEFAULT 1,
  requested_tier  VARCHAR(20) NOT NULL DEFAULT 'verified',
  status          VARCHAR(30) NOT NULL DEFAULT 'submitted'
                  CHECK (status IN ('draft','submitted','in_review','changes_requested','approved','rejected','withdrawn')),
  payload         JSONB NOT NULL,          -- identity, links, pitch, track picks
  submitted_at    TIMESTAMPTZ,
  sla_due_at      TIMESTAMPTZ,
  reviewed_by     UUID REFERENCES users(id),
  reviewed_at     TIMESTAMPTZ,
  decision_reason TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_creator_app_open
  ON creator_applications (user_id)
  WHERE status IN ('submitted','in_review','changes_requested');
```

#### `creator_verifications`

```sql
CREATE TABLE creator_verifications (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind          VARCHAR(30) NOT NULL
                CHECK (kind IN ('identity','authenticity','business','voice_consent')),
  status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','approved','rejected','expired')),
  evidence_ref  TEXT,                      -- encrypted object key; never a raw URL
  reviewer_id   UUID REFERENCES users(id),
  reviewed_at   TIMESTAMPTZ,
  expires_at    TIMESTAMPTZ,
  reason        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `creator_badges`

```sql
CREATE TABLE creator_badges (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  badge       VARCHAR(30) NOT NULL
              CHECK (badge IN ('verified','founding','top_creator','partner','label','ai_artist','ai_assisted','staff')),
  granted_by  UUID REFERENCES users(id),
  granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at  TIMESTAMPTZ,
  revoked_at  TIMESTAMPTZ,
  reason      TEXT
);
CREATE UNIQUE INDEX uq_creator_badge_active
  ON creator_badges (user_id, badge)
  WHERE revoked_at IS NULL;
```

#### `creator_follows`

```sql
CREATE TABLE creator_follows (
  follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  creator_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (follower_id, creator_id),
  CHECK (follower_id <> creator_id)
);
CREATE INDEX idx_creator_follows_creator ON creator_follows (creator_id, created_at DESC);
```

#### `creator_blocks`

```sql
CREATE TABLE creator_blocks (
  blocker_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  blocked_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (blocker_id, blocked_id)
);
```

#### `creator_releases`

```sql
CREATE TABLE creator_releases (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_type     VARCHAR(30) NOT NULL
                  CHECK (source_type IN ('web_music_generation','upload','desktop_batch')),
  source_task_id  UUID,
  source_variant  VARCHAR(8),
  album_id        UUID REFERENCES stream_albums(id) ON DELETE SET NULL,
  track_id        UUID REFERENCES stream_tracks(id) ON DELETE SET NULL,
  status          VARCHAR(30) NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','submitted','in_review','changes_requested','approved','scheduled','published','taken_down','rejected')),
  metadata        JSONB NOT NULL,          -- title, cover, genre, language, explicit, credits, rights
  ai_disclosure   VARCHAR(20) NOT NULL DEFAULT 'none',
  origin          VARCHAR(20) NOT NULL DEFAULT 'ai_generated'
                  CHECK (origin IN ('original','ai_assisted','ai_generated')),
  scheduled_for   TIMESTAMPTZ,
  submitted_at    TIMESTAMPTZ,
  reviewed_by     UUID REFERENCES users(id),
  reviewed_at     TIMESTAMPTZ,
  published_at    TIMESTAMPTZ,
  takedown_reason TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_creator_releases_creator ON creator_releases (creator_id, created_at DESC);
CREATE INDEX idx_creator_releases_status ON creator_releases (status, submitted_at);
CREATE UNIQUE INDEX uq_creator_release_source
  ON creator_releases (creator_id, source_type, source_task_id, source_variant)
  WHERE source_task_id IS NOT NULL;
```

#### `creator_track_credits`

```sql
CREATE TABLE creator_track_credits (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id    UUID NOT NULL REFERENCES stream_tracks(id) ON DELETE CASCADE,
  user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
  credit_name VARCHAR(120) NOT NULL,
  role        VARCHAR(30) NOT NULL
              CHECK (role IN ('primary_artist','featured','songwriter','producer','lyricist','composer','mixer','other')),
  split_bp    INTEGER NOT NULL DEFAULT 0 CHECK (split_bp BETWEEN 0 AND 10000),
  status      VARCHAR(20) NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending','invited','accepted','declined')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_creator_credits_track ON creator_track_credits (track_id);
```

#### `listen_events` (raw, partitioned)

```sql
CREATE TABLE listen_events (
  id              BIGSERIAL,
  subject_type    VARCHAR(30) NOT NULL DEFAULT 'stream_track',
  subject_id      UUID NOT NULL,
  owner_user_id   UUID NOT NULL,
  listener_user_id UUID,
  session_id      VARCHAR(64),
  event_type      VARCHAR(20) NOT NULL,   -- start|progress|complete|skip
  position_s     INTEGER,
  duration_s      NUMERIC(8,2),
  source          VARCHAR(30),            -- discover|search|profile|playlist|chart|external|direct
  ip_hash         VARCHAR(64),
  ua_hash         VARCHAR(64),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
-- create monthly partitions; default partition for overflow
```

#### `valid_streams`

```sql
CREATE TABLE valid_streams (
  id               BIGSERIAL PRIMARY KEY,
  subject_type     VARCHAR(30) NOT NULL DEFAULT 'stream_track',
  subject_id       UUID NOT NULL,
  owner_user_id    UUID NOT NULL,
  listener_user_id UUID NOT NULL,
  session_id       VARCHAR(64),
  played_seconds   INTEGER NOT NULL,
  duration_seconds NUMERIC(8,2),
  completed        BOOLEAN NOT NULL DEFAULT FALSE,
  status           VARCHAR(20) NOT NULL
                   CHECK (status IN ('valid','royalty','excluded_owner','excluded_short','excluded_fraud','capped')),
  reason           TEXT,
  dedupe_key       VARCHAR(160) NOT NULL,
  ip_hash          VARCHAR(64),
  ua_hash          VARCHAR(64),
  played_at        TIMESTAMPTZ NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (dedupe_key)
);
CREATE INDEX idx_valid_streams_subject ON valid_streams (subject_id, played_at);
CREATE INDEX idx_valid_streams_owner ON valid_streams (owner_user_id, played_at);
CREATE INDEX idx_valid_streams_listener ON valid_streams (listener_user_id, played_at);
```

`dedupe_key = subject_type || ':' || subject_id || ':' || listener_user_id || ':' || floor(epoch(played_at)/21600)`.

#### `royalty_policies`

```sql
CREATE TABLE royalty_policies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version       INTEGER NOT NULL UNIQUE,
  document      JSONB NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to  TIMESTAMPTZ,
  created_by    UUID REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Policy document example:

```json
{
  "version": 1,
  "currency": "USD",
  "pool": {"mode": "fixed", "amount_usd": 3000, "revenue_share_pct": 15, "floor_usd": 3000, "cap_pct_gross": 25},
  "eligibility": {"min_valid_streams": 500, "min_unique_listeners": 50, "min_account_age_days": 30},
  "weights": {"original": 1.0, "ai_assisted": 0.6, "ai_generated": 0.3},
  "caps": {"per_track_weighted_streams": 500000, "per_creator_pool_pct": 40},
  "holdback_days": 30,
  "new_creator_holdback_days": 90,
  "reserve_pct": 10,
  "min_payout_usd": 20
}
```

> `per_creator_pool_pct` starts at **40** while the creator base is small and tightens to **20** at scale. It is a versioned policy value, never hardcoded in the engine.

#### `royalty_periods`

```sql
CREATE TABLE royalty_periods (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  period_start  DATE NOT NULL,
  period_end    DATE NOT NULL,
  policy_id     UUID NOT NULL REFERENCES royalty_policies(id),
  pool_micros   BIGINT NOT NULL DEFAULT 0,
  total_weighted_streams BIGINT NOT NULL DEFAULT 0,
  rate_micros   NUMERIC(18,8) NOT NULL DEFAULT 0,
  status        VARCHAR(20) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','calculated','locked','paid')),
  calculated_at TIMESTAMPTZ,
  locked_at     TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (period_start, period_end)
);
```

#### `royalty_ledger`

```sql
CREATE TABLE royalty_ledger (
  id                BIGSERIAL PRIMARY KEY,
  period_id         UUID NOT NULL REFERENCES royalty_periods(id),
  policy_id         UUID NOT NULL REFERENCES royalty_policies(id),
  creator_id        UUID NOT NULL REFERENCES users(id),
  track_id          UUID NOT NULL REFERENCES stream_tracks(id),
  entry_type        VARCHAR(20) NOT NULL
                    CHECK (entry_type IN ('accrual','cap_adjustment','reserve','release','clawback','payout')),
  weighted_streams  BIGINT NOT NULL DEFAULT 0,
  rate_micros       NUMERIC(18,8) NOT NULL DEFAULT 0,
  amount_micros     BIGINT NOT NULL DEFAULT 0,
  reason            TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_royalty_ledger_creator ON royalty_ledger (creator_id, period_id);
CREATE INDEX idx_royalty_ledger_track ON royalty_ledger (track_id, period_id);
```

#### `creator_earnings` (unified ledger for all sources)

```sql
CREATE TABLE creator_earnings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source        VARCHAR(20) NOT NULL
                CHECK (source IN ('royalty','tip','download','license','marketplace','service','bonus','adjustment')),
  source_id     TEXT,
  period        DATE,
  gross_micros  BIGINT NOT NULL,
  fee_micros    BIGINT NOT NULL DEFAULT 0,
  net_micros    BIGINT NOT NULL,
  currency      CHAR(3) NOT NULL DEFAULT 'USD',
  status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','available','held','paid','clawed_back')),
  available_at  TIMESTAMPTZ,
  description   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_creator_earnings_creator ON creator_earnings (creator_id, created_at DESC);
CREATE INDEX idx_creator_earnings_status ON creator_earnings (status, available_at);
```

#### `creator_payout_accounts` / `creator_kyc`

```sql
CREATE TABLE creator_payout_accounts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  method         VARCHAR(20) NOT NULL CHECK (method IN ('aba','wing','khqr','bank','paypal','wise')),
  account_name   VARCHAR(120) NOT NULL,
  account_number TEXT NOT NULL,            -- encrypted at application level
  bank_code      VARCHAR(30),
  currency       CHAR(3) NOT NULL DEFAULT 'USD',
  status         VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','verified','rejected','disabled')),
  verified_at    TIMESTAMPTZ,
  is_default     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_creator_payout_default
  ON creator_payout_accounts (user_id) WHERE is_default;

CREATE TABLE creator_kyc (
  user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  legal_name      VARCHAR(120) NOT NULL,
  date_of_birth   DATE NOT NULL,
  country_code    CHAR(2) NOT NULL,
  id_type         VARCHAR(30) NOT NULL,
  id_number_enc   TEXT NOT NULL,
  id_document_ref TEXT NOT NULL,
  selfie_ref      TEXT,
  tax_id          VARCHAR(40),
  status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','verified','rejected','expired')),
  verified_at     TIMESTAMPTZ,
  expires_at      TIMESTAMPTZ,
  reason          TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `creator_payouts` / `creator_payout_items`

```sql
CREATE TABLE creator_payouts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id    UUID NOT NULL REFERENCES users(id),
  period_start  DATE NOT NULL,
  period_end    DATE NOT NULL,
  amount_micros BIGINT NOT NULL,
  currency      CHAR(3) NOT NULL DEFAULT 'USD',
  method        VARCHAR(20) NOT NULL,
  status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','approved','processing','paid','failed','cancelled')),
  requested_at  TIMESTAMPTZ,
  approved_by   UUID REFERENCES users(id),
  approved_at   TIMESTAMPTZ,
  paid_at       TIMESTAMPTZ,
  payment_ref   VARCHAR(120),
  statement_key TEXT,
  failure_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (creator_id, period_start, period_end)
);

CREATE TABLE creator_payout_items (
  payout_id   UUID NOT NULL REFERENCES creator_payouts(id) ON DELETE CASCADE,
  earning_id  UUID NOT NULL REFERENCES creator_earnings(id),
  PRIMARY KEY (payout_id, earning_id),
  UNIQUE (earning_id)
);
```

> `UNIQUE (creator_id, period_start, period_end)` makes payout creation idempotent. `UNIQUE (earning_id)` guarantees an earning can never be paid twice, even across runs.

#### `creator_daily_stats` / `creator_track_stats`

```sql
CREATE TABLE creator_daily_stats (
  creator_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  stat_date        DATE NOT NULL,
  plays            INTEGER NOT NULL DEFAULT 0,
  valid_streams    INTEGER NOT NULL DEFAULT 0,
  unique_listeners INTEGER NOT NULL DEFAULT 0,
  saves            INTEGER NOT NULL DEFAULT 0,
  followers        INTEGER NOT NULL DEFAULT 0,
  completion_rate  NUMERIC(5,4) NOT NULL DEFAULT 0,
  skip_rate        NUMERIC(5,4) NOT NULL DEFAULT 0,
  PRIMARY KEY (creator_id, stat_date)
);
```

#### Moderation

```sql
CREATE TABLE creator_reports (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,
  subject_type VARCHAR(20) NOT NULL CHECK (subject_type IN ('track','creator','profile_image','release')),
  subject_id  UUID NOT NULL,
  reason      VARCHAR(40) NOT NULL,
  details     TEXT,
  status      VARCHAR(20) NOT NULL DEFAULT 'open'
              CHECK (status IN ('open','triaged','actioned','dismissed','appealed')),
  priority    SMALLINT NOT NULL DEFAULT 2,
  assigned_to UUID REFERENCES users(id),
  resolved_at TIMESTAMPTZ,
  resolution  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE creator_strikes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        VARCHAR(30) NOT NULL,
  severity    SMALLINT NOT NULL DEFAULT 1,
  source_report_id UUID REFERENCES creator_reports(id),
  reason      TEXT NOT NULL,
  starts_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ends_at     TIMESTAMPTZ,
  created_by  UUID REFERENCES users(id)
);

CREATE TABLE creator_appeals (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subject_type VARCHAR(30) NOT NULL,
  subject_id  UUID NOT NULL,
  message     TEXT NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'open'
              CHECK (status IN ('open','in_review','granted','denied')),
  decided_by  UUID REFERENCES users(id),
  decided_at  TIMESTAMPTZ,
  decision    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 5. Migration plan (ordered)

| # | Migration | Contents | Gate |
|---|---|---|---|
| 186 | `fix_stream_royalty_foundation` | Create `valid_streams`, `royalty_ledger`, `royalty_policies`, `royalty_periods`; add `stream_tracks.origin`; backfill origin | Unblocks B1–B4 |
| 187 | `creator_profiles` | `creator_profiles`, `creator_handle_history` | Identity |
| 188 | `creator_program_workflow` | `creator_applications`, `creator_verifications`, `creator_badges` | Program |
| 189 | `creator_follows` | `creator_follows`, `creator_blocks`, follower count | Social |
| 190 | `creator_releases` | `creator_releases`, `creator_track_credits` | Publishing |
| 191 | `listen_events` | Partitioned raw events + indexes | Analytics |
| 192 | `creator_stats` | `creator_daily_stats`, `creator_track_stats` | Analytics |
| 193 | `creator_earnings` | `creator_earnings`, `creator_payout_accounts`, `creator_kyc` | Money |
| 194 | `creator_payouts` | `creator_payouts`, `creator_payout_items` | Money |
| 195 | `creator_moderation` | `creator_reports`, `creator_strikes`, `creator_appeals` | Trust |
| 196 | `creator_tips` | Tip intents, supporter badges (Phase 3) | Money |
| 197 | `creator_admin_roles` | Granular admin permissions + audit | Ops |
| 198 | `creator_challenges` | Challenges + entries (Phase 2) | Community |
| 199 | `creator_backfill` | Handles for existing users, release mapping | Launch |

**Rules**

- Never edit an applied migration.
- Every migration is idempotent (`IF NOT EXISTS`) where possible.
- Every migration has a tested `downgrade()`.
- Backfills are separate scripts, not in the migration transaction, with progress logging.
- Coordinate numbering with the Studio agent.

---

## 6. API design

### 6.1 Conventions

- Prefix: `/api/v3`.
- Auth: existing session/JWT middleware (`get_current_user`, admin guard).
- Money: integer **micro-USD** in responses (`amount_micros`), plus a formatted field for display.
- Time: ISO-8601 UTC.
- Pagination: cursor (`?cursor=&limit=`), max 100.
- Errors: existing envelope `{error:{code,message,details}}`.
- All creator-scoped endpoints derive `user_id` from auth; never from the body.
- Idempotency keys for publish, tip, payout request.

### 6.2 Public endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/creators` | Directory (search, genre, country, verified, sort) | No |
| GET | `/creators/{handle}` | Profile + counts + links + support | No |
| GET | `/creators/{handle}/tracks` | Top tracks / paginated | No |
| GET | `/creators/{handle}/releases` | Releases | No |
| GET | `/creators/{handle}/playlists` | Public playlists | No |
| GET | `/creators/{handle}/similar` | Recommendations | No |
| POST | `/creators/{handle}/follow` | Follow | Yes |
| DELETE | `/creators/{handle}/follow` | Unfollow | Yes |
| GET | `/creators/{handle}/followers/count` | Count | No |
| POST | `/creators/{handle}/reports` | Report | Yes |
| GET | `/creator-program/config` | Program copy, thresholds, current rate | No |

**Profile response sketch**

```json
{
  "handle": "sokha",
  "display_name": "Sokha",
  "badges": ["verified"],
  "tier": "verified",
  "tagline": "Khmer pop for the ride home",
  "bio": "...",
  "avatar_url": "...",
  "banner_url": "...",
  "genres": ["Khmer pop", "Ballad"],
  "country_code": "KH",
  "city": "Phnom Penh",
  "links": [{"label":"YouTube","url":"..."}],
  "ai_disclosure": "ai_assisted",
  "stats": {"monthly_listeners": 1240, "followers": 312, "releases": 4, "valid_streams": 18200},
  "support_enabled": true,
  "joined_at": "2026-05-01T00:00:00Z",
  "is_following": false
}
```

### 6.3 Creator Studio endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/creator/apply` | Submit application |
| GET | `/creator/application` | Current application + status |
| GET | `/creator/me` | Studio profile + tier + checklist |
| PATCH | `/creator/me` | Update profile |
| POST | `/creator/me/handle` | Claim/change handle |
| GET | `/creator/me/analytics` | Metrics (`?range=28d&group_by=track`) |
| GET | `/creator/me/audience` | Followers/geography/sources |
| GET | `/creator/me/earnings` | Ledger + balance |
| GET | `/creator/me/statements` | Statement list |
| GET | `/creator/me/statements/{period}.csv` | Signed download |
| PUT | `/creator/me/payout-account` | Add/update account |
| POST | `/creator/me/kyc` | Submit KYC |
| GET | `/creator/me/kyc` | KYC status |
| POST | `/creator/me/payouts/request` | Request payout (if eligible) |
| GET | `/creator/me/payouts` | Payout history |
| GET | `/creator/me/releases` | List |
| POST | `/creator/me/releases` | Create draft |
| PATCH | `/creator/me/releases/{id}` | Edit draft/changes |
| POST | `/creator/me/releases/{id}/submit` | Submit for review |
| POST | `/creator/me/releases/{id}/unpublish` | Unpublish |
| DELETE | `/creator/me/releases/{id}` | Delete draft |
| GET | `/creator/me/notifications` | In-app |
| PATCH | `/creator/me/notifications/{id}` | Mark read |
| GET | `/creator/me/opportunities` | Challenges/briefs |
| POST | `/creator/me/opportunities/{id}/entries` | Enter |

**Publish request**

```json
{
  "source": {"type": "web_music_generation", "task_id": "uuid", "variant": "ok"},
  "metadata": {
    "title": "Bassac Moon",
    "release_type": "single",
    "cover_upload_id": "uuid",
    "genre": "Khmer pop",
    "genres": ["Khmer pop"],
    "language": "km",
    "explicit": false,
    "release_date": "2026-12-01",
    "lyrics": "...",
    "description": "...",
    "credits": [{"name": "Sokha", "role": "primary_artist"}],
    "rights_attested": true,
    "ai_disclosure": "ai_assisted",
    "distribution": ["camxora"]
  }
}
```

### 6.4 Admin endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/creators` | List + filters |
| GET | `/admin/creators/{id}` | Detail + timeline |
| PATCH | `/admin/creators/{id}` | Status/tier/notes |
| POST | `/admin/creators/{id}/badges` | Grant/revoke |
| GET | `/admin/creator-applications` | Queue |
| POST | `/admin/creator-applications/{id}/decision` | Approve/changes/reject |
| GET | `/admin/creator-verifications` | Identity queue |
| POST | `/admin/creator-verifications/{id}/decision` | Approve/reject |
| GET | `/admin/creator-releases` | Release queue |
| POST | `/admin/creator-releases/{id}/decision` | Approve/changes/reject |
| GET | `/admin/creator-reports` | Moderation queue |
| POST | `/admin/creator-reports/{id}/action` | Strike/dismiss/takedown |
| GET | `/admin/creator-appeals` | Appeals |
| POST | `/admin/creator-appeals/{id}/decision` | Grant/deny |
| GET | `/admin/royalty/policies` | List |
| POST | `/admin/royalty/policies` | Create version |
| POST | `/admin/royalty/policies/{id}/simulate` | Dry-run on a period |
| POST | `/admin/royalty/periods/{period}/calculate` | Compute |
| POST | `/admin/royalty/periods/{period}/lock` | Lock |
| GET | `/admin/payouts` | Runs |
| POST | `/admin/payouts` | Create run |
| POST | `/admin/payouts/{id}/approve` | Maker-checker |
| POST | `/admin/payouts/{id}/mark-paid` | Reference required |
| GET | `/admin/fraud/alerts` | Fraud queue |
| POST | `/admin/fraud/alerts/{id}/action` | Quarantine/clawback |

**Authz matrix**

| Action | Support | Moderator | Finance | Admin |
|---|---|---|---|---|
| View creator | ✅ | ✅ | ✅ | ✅ |
| View KYC docs | ❌ | ❌ | ✅ | ✅ |
| Approve application | ❌ | ✅ | ❌ | ✅ |
| Approve release | ❌ | ✅ | ❌ | ✅ |
| Issue strike | ❌ | ✅ | ❌ | ✅ |
| Create payout run | ❌ | ❌ | ✅ | ✅ |
| Approve payout | ❌ | ❌ | ✅ | ✅ |
| Mark paid | ❌ | ❌ | ✅ | ❌ |
| Edit policy | ❌ | ❌ | ❌ | ✅ |
| Clawback >$50 | ❌ | ❌ | ✅ | ✅ |

> Maker-checker: the user who creates a payout run cannot approve or mark it paid. Enforce in the service layer, not only the UI.

---

## 7. Metrics and royalty engine

### 7.1 Ingestion pipeline

```
Playback (signed URL request) ──► listen_events (raw)
        │
        ├─ owner check
        ├─ duration check (30s / 50%)
        ├─ dedupe (6h bucket)
        ├─ fraud rules (IP/ASN/UA/velocity)
        ▼
valid_streams (status=valid)
        │
        ├─ daily rollup ──► creator_daily_stats / creator_track_stats
        └─ monthly close ──► royalty calc ──► royalty_ledger
```

**Where to emit events**

- `streaming_public.py` `stream_track` and `get_track_play_url` already authenticate and rate-limit. Emit a `listen_events` row on the first byte served and on completion (client beacon for completion).
- **Measure playback server-side.** Count bytes served for the signed audio range (or a signed, per-session heartbeat), clamp `played_seconds` to `duration_seconds`, and reject impossible values. Never trust a single client claim.
- Do **not** rely on client-only beacons; the server-side play request is the source of truth. Client beacons only improve completion accuracy.
- Anonymous playback (if enabled) is recorded but never royalty-eligible.

### 7.2 Validation rules

```python
def classify(ev, track):
    if ev.listener_user_id == ev.owner_user_id: return "excluded_owner"
    if ev.played_seconds < 30 and ev.played_seconds < 0.5 * track.duration: return "excluded_short"
    if fraud_flag(ev): return "excluded_fraud"
    return "valid"

# Duplicates are not stored as rows: valid_streams is upserted on dedupe_key,
# and a longer replay in the same 6h bucket upgrades the existing row.
#   INSERT ... ON CONFLICT (dedupe_key) DO UPDATE
#   SET played_seconds = GREATEST(valid_streams.played_seconds, EXCLUDED.played_seconds),
#       status = CASE WHEN EXCLUDED.status = 'valid' THEN 'valid' ELSE valid_streams.status END
```

Daily cap per listener: 20 royalty streams. Excess is marked `capped` at period close. At close, eligible `valid` rows are promoted to `royalty`; the rest stay `valid` (counted, not paid).

### 7.3 Royalty calculation

```python
# 1. Aggregate weighted streams per creator/track
weighted = sum(valid_count * weight(origin))

# 2. Apply per-track cap
paid_track = min(weighted, policy.caps.per_track_weighted_streams)

# 3. Apply per-creator cap (iterative water-filling)
cap_amount = pool * policy.caps.per_creator_pool_pct
while any(creator_amount > cap_amount):
    scale_over_capped_creators()
    redistribute_to_uncapped()
    # max 3 iterations; assert sum(paid) <= pool

# 4. Rate
rate = pool / total_paid_weighted
amount = round(paid_weighted * rate)

# 5. Reserve
reserve = pool * policy.reserve_pct
available_pool = pool - reserve

# 6. Ledger accruals
for each creator/track:
    insert royalty_ledger(entry_type='accrual', amount_micros=...)
```

**Invariants (property tests)**

- `sum(accruals) + reserve == pool` (± 1 micro rounding, reconciled to a rounding bucket).
- No creator exceeds the per-creator cap.
- No track exceeds the per-track cap.
- Weighted streams never exceed raw valid streams.
- Re-running the calculation for the same period yields identical output (deterministic).
- Locked periods cannot be recalculated without a new adjustment entry.

### 7.4 Pool funding

```python
pool_usd = clamp(
    max(floor_usd, revenue_share_pct * net_listening_revenue_usd),
    floor_usd,
    cap_pct_gross * gross_platform_revenue_usd,
)
```

`net_listening_revenue_usd` must be defined by finance:

- Subscriptions attributable to listening, plus
- Listener-side credit spend attributable to streaming, **excluding** generation costs.

Document the attribution formula. Do not silently use total revenue.

### 7.5 Rounding

- Compute in `NUMERIC`, store micro-USD `BIGINT`.
- Round half-up per creator; keep a `rounding_bucket_micros` on the period.
- Statements show the exact ledger sum; the bucket is retained by the platform (documented).

---

## 8. Jobs and scheduling

| Job | Cadence | Purpose | Failure behavior |
|---|---|---|---|
| `listen_event_partition` | monthly | Create next partition | Alert |
| `stream_validation` | every 15 min | Validate new events → `valid_streams` | Retry with backoff |
| `stats_rollup` | hourly | Update daily stats | Retry; stale marker |
| `fraud_scan` | daily 03:00 | Velocity/concentration/device graph | Alert |
| `application_sla` | hourly | Escalate overdue applications | Alert |
| `release_sla` | hourly | Escalate overdue releases | Alert |
| `royalty_calculate` | monthly, 1st 02:00 | Compute period | Stop; no partial lock |
| `royalty_lock` | monthly, 4th 02:00 | Lock + statements | Alert finance |
| `payout_run` | monthly, 5th 02:00 | Create payouts | Alert finance |
| `payout_reconcile` | monthly, 6th | Verify paid vs ledger | Alert |
| `creator_digest` | weekly Mon | Email digest | Retry |
| `badge_expiry` | daily | Expire Top Creator / verification | Log |
| `kyc_expiry` | daily | Notify 30/7 days | Log |
| `handle_redirect_cleanup` | monthly | Expire old redirects | Log |

Use the existing job queue/worker (`platform_api/worker.py`, `job_queue` migration 080) where possible; keep money jobs idempotent with a run key.

---

## 9. Security & privacy

### 9.1 Access control

- Creator endpoints: derive user from auth; never accept `creator_id` from the client.
- Admin endpoints: role check + resource-level check.
- KYC/payout docs: separate permission; every read logged.
- Maker-checker enforced server-side.
- Re-authentication (password/TOTP) required to change payout account; 24h cooling period before first payout to a new account.

### 9.2 Data protection

- Encrypt KYC IDs, bank numbers, and tax IDs at the application layer (envelope encryption with a KMS/env key).
- Store documents in private object storage with short-TTL signed URLs.
- Hash IP/UA with a rotating salt; retain ≤90 days.
- No listener PII in creator analytics; aggregate only.
- Data export and deletion endpoints for creators.
- Backup encryption; restore drills.

### 9.3 Fraud & abuse

- Rate limits: follow 60/h, apply 1/day, report 10/day, tip 10/h, payout request 1/day.
- Device/IP graph stored as hashes; no raw IP retention.
- Stream validation rules versioned; changes require a policy version.
- Clawbacks >$50 require finance approval; all clawbacks notify the creator with evidence summary.

### 9.4 Audit

- Immutable `creator_audit` (or extend `audit_logs`) for: application decisions, badge grants, release decisions, strikes, policy changes, payout approvals, KYC access, earnings adjustments.
- Include actor, role, IP hash, before/after JSON, reason.

---

## 10. Frontend data fetching

- Public creator page: Next.js server component fetches `GET /api/v3/creators/{handle}` with `next: { revalidate: 60 }`; client islands for follow/play/tip.
- Studio: React Query/SWR with optimistic updates for follow and profile save.
- Analytics: server-side aggregation; avoid loading raw events.
- Images: `next/image` with AVIF/WebP; cover CDN.
- Error boundaries per section; never blank the whole page.
- Cache headers: `public, s-maxage=60, stale-while-revalidate=300` for public pages; `no-store` for earnings/KYC.

---

## 11. Performance & scale

| Concern | Target | Approach |
|---|---|---|
| Public page p95 | < 1.5s | ISR, CDN, narrow queries, indexes |
| Analytics p95 | < 800ms | Daily rollups, no raw scans |
| Follow toggle | < 200ms | Single-row write + cached count |
| Payout report | < 30s for 10k creators | Pre-aggregated ledger, streaming CSV |
| Event ingest | 1k events/s | Partitioned table, batch insert |
| Storage | 13 months raw | Monthly partitions; drop old partitions |
| Concurrency | 10k listeners | Signed URL + CDN; no per-play DB write on hot path? (batch) |

**Hot-path note:** writing a `listen_events` row per play at 10k concurrent listeners is fine with batching; if not, emit to a queue and batch-insert. Do not block audio streaming on the analytics write.

---

## 12. Testing strategy

### 12.1 Unit

- Royalty math: weights, caps, water-filling, reserve, rounding, determinism.
- Validation: owner, short, duplicate, fraud, daily cap.
- Eligibility thresholds.
- Split sums (Phase 4).
- Fee calculations (tips, downloads).

### 12.2 Integration (test DB)

- Apply → verify → publish → stream → validate → rollup → royalty → payout.
- Maker-checker enforcement.
- IDOR: creator A cannot read creator B's earnings/KYC.
- Policy simulation equals actual calculation.
- Migration up/down.

### 12.3 Contract

- Studio → `POST /creator/me/releases` (schema, idempotency, errors).
- Web → public creator endpoints (response shape, caching).
- Admin → decision endpoints (RBAC).

### 12.4 E2E (Playwright)

- Creator journey: sign up → profile → apply → verify (admin) → publish → see analytics → earnings → payout.
- Listener journey: discover → creator page → follow → play → tip.
- Admin journey: queue → approve → moderation → payout run.

### 12.5 Load & security

- 10k concurrent plays; 1k events/s ingest.
- Payout run with 10k creators.
- OWASP: IDOR, privilege escalation, payout tampering, KYC access, rate limits, file upload.

---

## 13. Rollout & backfill

### 13.1 Feature flags

| Flag | Default | Purpose |
|---|---|---|
| `creator_program_enabled` | off | Public pages + applications |
| `creator_publishing_enabled` | off | Release pipeline |
| `creator_tips_enabled` | off | Tips |
| `creator_payouts_enabled` | off | Payout runs |
| `creator_analytics_public` | off | Public stats |

### 13.2 Backfill

1. **Handles:** for each user with a published `stream_track`, generate a handle from `display_name` (slug + numeric suffix); create `creator_profiles` with `status='draft'`; invite claim.
2. **Releases:** one `creator_releases` row per `stream_album` with `status='published'`; link `track_id` for singles.
3. **Origin:** default `ai_generated` for desktop-batch tracks; `original` for uploaded tracks; creators can correct during claim.
4. **Static artists:** remove `artist-data.ts`; 301 `/artist/kanya` → `/creators/kanya` only if a real profile exists; otherwise 404 with a "creator not found" page.
5. **Stats:** seed `creator_daily_stats` from `stream_tracks.play_count` (clearly labeled "historical").
6. **Sample pack:** keep `docs/creator-program/sample-creators/` as a fixture. When Phase 4 needs demo data, add a separate idempotent `seed_sample_creators.py` (not a migration) that tags every row and can be removed in one command. Never run it in production. See `SAMPLE_CREATORS.md`.

### 13.3 Launch sequence

1. Deploy schema + service behind flags.
2. Backfill + internal test creators.
3. Closed beta (25–50 creators), collect feedback.
4. Fix, then open applications.
5. Enable payouts only after two reconciled sandbox cycles.

---

## 14. Observability

**Metrics**

- `creator_application_queue_depth`, `creator_release_queue_depth`
- `creator_payout_run_status{period,status}`
- `royalty_calculation_duration`, `royalty_reconciliation_diff_micros`
- `stream_validation_rate{status}`
- `fraud_alerts_open`
- `api_latency{route}`

**Alerts**

- Payout reconciliation diff ≠ 0.
- Royalty job failed or exceeded 30 min.
- Queue SLA breach > 20%.
- Stream spike > 10× median.
- KYC access outside business hours.
- Failed payout count > 5.

**Dashboards**

- Creator funnel: apply → verify → publish → earn.
- Earnings distribution (top 1%, Gini).
- Fraud quarantine volume.

---

## 15. Technical risks & mitigations

| Risk | Mitigation |
|---|---|
| Missing tables/service already break admin | Fix in migration 186 before any UI work |
| Cross-DB downloads (`sunoapi` vs `platform_db`) | Emit purchase events to `platform_db`; never join across DBs |
| Migration conflicts with Studio agent | Reserve 186–199; coordinate |
| Royalty rounding disputes | Integer micros, deterministic, publish rounding policy |
| Hot-path analytics writes | Batch/queue; never block streaming |
| KYC breach | Encryption, least privilege, audit, short retention |
| Payout double-pay | Idempotency key per (creator, period), unique constraint, maker-checker |
| Handle squatting | Reserved list, claim window, 90-day change limit |
| Fake streams | Validation + quarantine + caps + fraud console |
| Public page staleness | ISR + revalidate on publish/unpublish |
| Backfill errors | Dry-run, counts, rollback script, feature flags |

---

## 16. Definition of done

- [ ] All migrations 186–199 applied in sandbox and production.
- [ ] `GET /api/v3/streaming/admin/catalog` returns 200 (B3 fixed).
- [ ] Creator profile, public page, directory, follows live.
- [ ] Application → verification → badge flow works end-to-end.
- [ ] Publish → review → catalog → public page works end-to-end.
- [ ] Analytics match seeded definitions; owner/duplicate/fraud excluded.
- [ ] Royalty calculation passes invariants and reconciles.
- [ ] Payout run: maker-checker, mark-paid, statement, retry.
- [ ] KYC + payout account + tax fields captured and encrypted.
- [ ] Moderation queue, strikes, appeals, audit.
- [ ] Khmer localization, accessibility, SEO.
- [ ] Runbooks: payout failure, fraud spike, KYC incident, policy rollback.
- [ ] Two sandbox payout cycles reconcile to $0.00.
