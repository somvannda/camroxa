# Platform API

Centralized Python backend service for the music generation ecosystem. Acts as the authenticated middleware layer between client applications (Desktop App, Web Portal, Marketing Website) and external AI services (Suno, Fal AI, SLAI/DeepSeek).

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Transport Layer (FastAPI routers, WebSocket)    │
├─────────────────────────────────────────────────┤
│  Application Layer (Service classes)            │
├─────────────────────────────────────────────────┤
│  Domain Layer (Models, business rules)          │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer (DB repos, HTTP clients)  │
└─────────────────────────────────────────────────┘
```

**Technology Stack:**
- Python 3.11+ with FastAPI (async-first)
- PostgreSQL 15+ (asyncpg driver)
- Redis (rate limiting, token blocklist, caching)
- PyJWT + bcrypt for authentication
- Alembic for database migrations
- Hypothesis for property-based testing

---

## Project Structure

```
platform_api/
├── main.py                     # App factory, lifespan, middleware stack, router registration
├── config.py                   # Pydantic Settings (env vars: DB, Redis, JWT, API keys)
├── dependencies.py             # FastAPI DI: pools, repos, services, clients
├── exceptions.py               # Error hierarchy (PlatformAPIError + subclasses)
│
├── models/
│   ├── domain.py               # Dataclasses: User, Plan, License, Batch, Song, etc.
│   ├── enums.py                # UserRole, TaskStatus, ImageKind, ChannelRole, etc.
│   └── schemas.py              # Pydantic request/response models
│
├── ports/                      # Protocol interfaces (dependency inversion)
│   ├── auth_port.py            # AuthServicePort
│   ├── credit_port.py          # CreditServicePort
│   ├── generation_port.py      # GenerationServicePort
│   └── notification_port.py    # NotificationServicePort
│
├── middleware/
│   ├── auth.py                 # JWT validation, authorization chain (401→403→402)
│   ├── rate_limit.py           # Sliding window rate limiter (Redis sorted sets)
│   └── audit.py                # Auto-logs state-changing requests (POST/PUT/PATCH/DELETE)
│
├── routers/                    # HTTP endpoint handlers
│   ├── auth.py                 # POST /login, /register, /refresh, /logout
│   ├── users.py                # GET/PATCH /users/me, Admin user management
│   ├── licenses.py             # License CRUD (Admin)
│   ├── plans.py                # Plan config + offers (Admin)
│   ├── credits.py              # Balance, packs, purchase, pricing (User + Admin)
│   ├── profiles.py             # Channel profile CRUD (User + Admin stats)
│   ├── prompts.py              # Music descriptions & structures (Admin)
│   ├── generation.py           # POST /generation/draft, /suno, /image
│   ├── batch.py                # POST /batches, GET /batches/{id}
│   ├── callbacks.py            # POST /callbacks/suno (HMAC-validated, no JWT)
│   ├── settings_router.py      # GET/PATCH /settings (merged user+system)
│   ├── admin.py                # Suno balance, audit log, rate limits (Admin)
│   ├── health.py               # GET /health (no auth, checks DB + services)
│   └── ws.py                   # WebSocket /ws (real-time notifications)
│
├── services/                   # Business logic layer
│   ├── auth_service.py         # JWT issuance, password hashing, token rotation
│   ├── lockout.py              # Account lockout (5 failures → 15 min lock)
│   ├── user_service.py         # User CRUD, suspend/reactivate, soft-delete
│   ├── license_service.py      # License lifecycle, quota enforcement, plan offers
│   ├── credit_service.py       # Wallet ops, quota consumption order, pack purchase
│   ├── credit_pricing_service.py # Per-model pricing CRUD, margin calculation
│   ├── profile_service.py      # Profile CRUD with plan-based limit enforcement
│   ├── prompt_service.py       # Music prompt management, matchKey pairing, cycling
│   ├── generation_service.py   # LLM/Suno/Image proxy, validation, retries, refunds
│   ├── batch_service.py        # Batch orchestration, cost pre-check, image jobs
│   ├── settings_service.py     # Merged settings, patch validation, sensitive filtering
│   ├── notification_service.py # WebSocket push + offline queue (24h expiry)
│   ├── audit_service.py        # Append-only audit logging
│   ├── suno_balance_service.py # External Suno credit monitoring (cached in Redis)
│   └── data_scope_service.py   # User-scoped data isolation (User vs Admin access)
│
├── repositories/               # Database access layer
│   ├── user_repo.py            # Users table CRUD + pagination
│   ├── license_repo.py         # Licenses + plans + plan_offers + plan_usage
│   ├── credit_repo.py          # Wallets, transactions, packs, pricing (atomic ops)
│   ├── profile_repo.py         # Channel profiles (user-scoped)
│   ├── prompt_repo.py          # Music descriptions & structures
│   ├── batch_repo.py           # Batches, songs, suno_tasks, image_jobs, aggregation
│   ├── settings_repo.py        # User settings + system settings (key-value)
│   ├── audit_repo.py           # Append-only audit log (no update/delete)
│   └── rate_limit_repo.py      # Rate limit configuration CRUD
│
├── clients/                    # External API HTTP clients
│   ├── suno_client.py          # Suno API (submit, status, credits) — 30s timeout
│   ├── fal_client.py           # Fal AI image generation — 60s timeout
│   ├── slai_client.py          # SLAI image generation — 60s timeout
│   └── llm_client.py           # DeepSeek/SLAI LLM (song drafts) — 30s timeout
│
├── migrations/                 # Alembic schema versioning
│   ├── env.py
│   └── versions/
│
└── tests/                      # 605 tests (unit + property-based)
    ├── test_auth_router.py
    ├── test_auth_middleware.py
    ├── test_generation_service.py
    ├── test_credit_repo.py
    ├── test_audit.py
    ├── test_data_scope.py
    ├── test_health_router.py
    └── ... (22 test files total)
```

---

## Core Logic Breakdown

### 1. Authentication & Authorization

**Flow:** Email/password → JWT access token (30 min) + refresh token (7 days)

| Component | Responsibility |
|-----------|---------------|
| `auth_service.py` | Password hashing (bcrypt, work factor 12), JWT issuance/rotation, refresh token management |
| `lockout.py` | Redis-based lockout: 5 failures → 15 min lock per email |
| `middleware/auth.py` | Authorization chain: Token validity (401) → Account suspension (403) → License status (403) → Credit balance (402) |

**Key behaviors:**
- Refresh tokens are rotated on use (old one revoked via Redis blocklist)
- Registration validates: email format, password (8-128 chars, uppercase+lowercase+digit), display name (2-50 chars)
- Returns ALL validation errors at once (not just the first one)

---

### 2. Credit System

**Architecture:** Two-tier consumption — Plan quota first, then wallet credits.

```
Monthly/Yearly User → Plan quota (420-840 songs/month) → Wallet credits
Lifetime User → Wallet credits only (gets 1,000 bonus on activation)
```

| Component | Responsibility |
|-----------|---------------|
| `credit_repo.py` | Atomic deduction (`UPDATE WHERE balance >= amount`), bounds enforcement (0 to 10M) |
| `credit_service.py` | Quota consumption order, pack purchases, admin adjustments |
| `credit_pricing_service.py` | Per-model pricing config (model_id + op_type → credits), margin calculation |

**Key behaviors:**
- Atomic deduction prevents concurrent overdraw
- Credits are refunded on external service failure (network error, timeout)
- Each AI operation has configurable credit cost (Admin sets price above actual API cost for margin)
- Credit packs: Starter ($49/500), Creator ($149/2000), Agency ($699/10000) — all Admin-configurable

---

### 3. Generation Pipeline

**Draft Generation (LLM):**
```
Request → Credit deduction → LLM call → Validate lyrics structure → Check avoid lists → Return draft
         (retry up to 8x)                (headers in order,         (title/album uniqueness,
                                           min content lines)        retry up to 6x)
```

**Suno Music Generation:**
```
Request → SHA-256 dedup check → Credit deduction → Forward to Suno → Return task ID
                                                         ↓
                             Callback (async) → Update task → Store audio URLs → WebSocket notify
```

**Image Generation:**
```
Request → Validate (resolution 512-2048, prompt ≤2000, base64 ≤10MB) → Credit deduction → Provider call → Return PNG
```

| Component | Responsibility |
|-----------|---------------|
| `generation_service.py` | Orchestrates all three generation types with validation, retries, dedup, and refund-on-failure |
| `batch_service.py` | Multi-song batch: cost pre-check, sequential draft generation, partial failure handling, image job creation on Suno completion |
| `clients/` | Async HTTP clients with timeout handling and error classification (retryable vs permanent) |

**Key behaviors:**
- Song structure validation: headers in exact order, min content lines = max(16, headers×4)
- Forced values (title/album/opening) bypass LLM generation and avoid list checks
- Suno request deduplication via SHA-256 hash of normalized request fields
- Batch cost pre-check: `(LLM_price + Suno_price) × song_count` verified against balance before starting

---

### 4. License & Plan Management

**Plan types:**
| Plan | Price | Profiles | Songs/month | AI included |
|------|-------|----------|-------------|-------------|
| Monthly | $79/mo | 3 | 420 (7/day/channel) | Within quota |
| Yearly | $699/yr | 4 | 840 (7/day/channel) | Within quota |
| Lifetime | $1,499 | 5 | N/A | Credit packs only |

| Component | Responsibility |
|-----------|---------------|
| `license_service.py` | Create/assign/revoke licenses, daily+monthly quota enforcement, plan offer logic, plan deactivation |
| `license_repo.py` | License keys, plan table, offers (promo pricing with max redemptions), usage tracking |

**Key behaviors:**
- Daily song limit: configurable per channel (default 7/day)
- Plan offers: promotional pricing with auto-revert when max redemptions reached
- License revocation recalculates profile allowance (existing profiles preserved, no new ones until under limit)
- Plan changes don't affect existing subscribers until renewal

---

### 5. Channel Profiles

| Component | Responsibility |
|-----------|---------------|
| `profile_service.py` | CRUD with plan-based limit enforcement (Lifetime=5, Monthly=3, max=20 with additional slots) |
| `profile_repo.py` | User-scoped queries, uniqueness per user (user_id + name) |

Profiles store: folder paths, image prompts, video templates, YouTube upload settings, output resolution.

---

### 6. Music Prompts (Admin-only, hidden from users)

| Component | Responsibility |
|-----------|---------------|
| `prompt_service.py` | CRUD, matchKey pairing, cyclic/shuffle structure assignment per batch |
| `prompt_repo.py` | Descriptions (genre/mood/energy) and structures (section headers) |

**Key behaviors:**
- Descriptions paired with structures by `matchKey`
- Cycle mode: structures assigned sequentially, wrapping after last
- Shuffle mode: seeded random per batch for reproducibility
- Users never see descriptions/structures — only the generated title, album, lyrics

---

### 7. Real-time Notifications (WebSocket)

| Component | Responsibility |
|-----------|---------------|
| `notification_service.py` | Push to connected clients, queue for offline users (24h expiry) |
| `routers/ws.py` | WebSocket endpoint with JWT auth on handshake, max 3 connections/user, ping/pong (60s idle → ping, 10s timeout → close) |

---

### 8. Rate Limiting

| Component | Responsibility |
|-----------|---------------|
| `middleware/rate_limit.py` | Redis sorted set sliding window per user/endpoint-type |

**Defaults:** 60 requests/min general, 20 requests/10s for Suno. Admin can update live (applies within 5s). Returns 429 with `Retry-After` header. Credits NOT deducted for rejected requests.

---

### 9. Audit Logging

| Component | Responsibility |
|-----------|---------------|
| `audit_service.py` | `log_event()` — append-only, never fails the request |
| `audit_repo.py` | Paginated filtered queries (actor, action_type, resource_type, date range). No update/delete. |
| `middleware/audit.py` | Auto-intercepts POST/PUT/PATCH/DELETE → creates audit entries |

---

### 10. Data Isolation

| Component | Responsibility |
|-----------|---------------|
| `data_scope_service.py` | Centralizes user-scoped filtering. User role → only own records. Admin role → all records. |

Applies to: profiles, songs, batches, suno_tasks, settings.

---

### 11. Health Check

`GET /health` (no auth) → concurrent checks of DB, Suno, Fal, SLAI (3s timeout each)

- **healthy** — all services reachable
- **degraded** — DB up, some external services down
- **unhealthy** — database unreachable

---

## API Endpoints Summary

| Group | Endpoint | Method | Auth | Description |
|-------|----------|--------|------|-------------|
| Auth | `/api/v1/auth/login` | POST | None | Email/password login |
| Auth | `/api/v1/auth/register` | POST | None | New user registration |
| Auth | `/api/v1/auth/refresh` | POST | None | Refresh access token |
| Auth | `/api/v1/auth/logout` | POST | User | Revoke refresh token |
| Users | `/api/v1/users/me` | GET/PATCH | User | Current user profile |
| Users | `/api/v1/users` | GET | Admin | Paginated user list |
| Users | `/api/v1/users/{id}` | PATCH/DELETE | Admin | Update/delete user |
| Users | `/api/v1/users/{id}/suspend` | POST | Admin | Suspend user |
| Users | `/api/v1/users/{id}/reactivate` | POST | Admin | Reactivate user |
| Licenses | `/api/v1/licenses` | POST | Admin | Create license |
| Licenses | `/api/v1/licenses/{id}/assign` | POST | Admin | Assign to user |
| Licenses | `/api/v1/licenses/{id}/revoke` | POST | Admin | Revoke license |
| Licenses | `/api/v1/licenses/validate` | GET | User | Validate own license |
| Plans | `/api/v1/plans` | GET | Admin | List plans |
| Plans | `/api/v1/plans/{id}` | PATCH | Admin | Update plan config |
| Plans | `/api/v1/plans/offers` | GET/POST | Admin | Launch offers |
| Credits | `/api/v1/credits/balance` | GET | User | Wallet balance + txns |
| Credits | `/api/v1/credits/packs` | GET | User | Available packs |
| Credits | `/api/v1/credits/purchase` | POST | User | Buy credit pack |
| Credits | `/api/v1/credits/pricing` | GET/POST/PUT | Admin | Pricing config |
| Credits | `/api/v1/credits/adjust` | POST | Admin | Manual balance adjust |
| Profiles | `/api/v1/profiles` | GET/POST | User | List/create profiles |
| Profiles | `/api/v1/profiles/{id}` | PUT/DELETE | User | Update/delete profile |
| Profiles | `/api/v1/profiles/{id}/stats` | GET | Admin | Usage statistics |
| Prompts | `/api/v1/prompts/descriptions` | GET/POST | Admin | Song descriptions |
| Prompts | `/api/v1/prompts/structures` | GET/POST | Admin | Song structures |
| Generation | `/api/v1/generation/draft` | POST | User | Generate song draft |
| Generation | `/api/v1/generation/suno` | POST | User | Submit to Suno |
| Generation | `/api/v1/generation/suno/{id}` | GET | User | Task status |
| Generation | `/api/v1/generation/image` | POST | User | Generate image |
| Batch | `/api/v1/batches` | POST | User | Create batch run |
| Batch | `/api/v1/batches/{id}` | GET | User | Batch status |
| Callbacks | `/api/v1/callbacks/suno` | POST | HMAC | Suno completion |
| Settings | `/api/v1/settings` | GET/PATCH | User | Merged settings |
| Admin | `/api/v1/admin/suno-balance` | GET | Admin | External Suno credits |
| Admin | `/api/v1/admin/audit-log` | GET | Admin | Query audit log |
| Admin | `/api/v1/admin/rate-limits` | GET/PUT | Admin | Rate limit config |
| Health | `/health` | GET | None | Service health |
| WebSocket | `/api/v1/ws` | WS | User | Real-time events |

---

## Running

```bash
# Install dependencies
pip install -e ".[dev]"

# Set environment variables (or use .env file)
export PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db
export PLATFORM_REDIS_URL=redis://localhost:6379/0
export PLATFORM_JWT_SECRET=your-secret-here

# Run migrations
alembic upgrade head

# Start the server
uvicorn platform_api.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest tests/ -q
```

---

## Testing

605 tests across 22 test files covering:
- Unit tests for all services and repositories
- Property-based tests (Hypothesis) for correctness properties
- Router integration tests with httpx AsyncClient
- Middleware tests (auth chain, rate limiting, audit logging)

```bash
pytest tests/ -q                    # All tests
pytest tests/ -q --co               # List tests without running
pytest tests/test_generation_service.py -q  # Specific module
```
