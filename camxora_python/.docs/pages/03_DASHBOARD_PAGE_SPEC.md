# Dashboard Page — Full Specification

> **Route:** `/app/home` · **Sidebar label:** Dashboard  
> **Electron source:** `camxora/src/renderer/src/features/shell/HomePage.tsx`  
> **Python target:** `camxora_python/features/dashboard/views/dashboard_view.py`  
> **Phase:** 3 (first page — complete to 100% before Profile)  
> **Last updated:** 2026-07-07

---

# 1. Purpose

The Dashboard is the **default landing page** after login/onboarding. It gives a read-only overview of:

- Account usage (credits spent, content generated)
- Weekly generation trend (7-day chart)
- Remaining monthly quotas (credits, songs, images placeholder)
- Recent activity feed from the backend

It does **not** edit data, navigate to batches, or show channel profiles (profiles are fetched but unused on this page in Electron).

---

# 2. Navigation & shell chrome

## 2.1 Route metadata

From `camxora/src/renderer/src/features/shell/shellNavigation.ts` (mirrored in `shared/constants/navigation.py`):

| Field | Value |
|-------|-------|
| `key` | `home` |
| `path` | `/app/home` |
| `label` | Dashboard |
| `title` | Dashboard |
| `eyebrow` | Workspace |
| `description` | Overview of the current CAMXORA account, profile readiness, and studio status. |
| `icon` | Gauge (Electron only — sidebar uses text buttons in PySide6) |

## 2.2 Router behavior (Electron)

- `AppRouter.tsx`: `/app` index redirects to `/app/home`
- `bootstrap.ts`: successful session → `redirectTo: '/app/home'`
- Onboarding wizard finish → `navigate('/app/home')`

## 2.3 Shell layout (PySide6)

- **Page header** visible (hidden only on video workspace routes)
- Header shows eyebrow + title + description from `ShellRouteMeta`
- Page body scrolls independently below header (`QScrollArea` acceptable)

---

# 3. Data layer

## 3.1 Hook / aggregator

**File:** `camxora/src/renderer/src/features/shell/useDashboardOverviewQuery.ts`

```typescript
useQuery({
  queryKey: ['dashboard-overview'],
  queryFn: async () => {
    const [me, profiles, license, stats] = await Promise.all([
      apiGetMe(),
      apiListProfiles().catch(() => []),
      apiValidateLicense().catch(() => null),
      apiGetDashboardStats(),
    ])
    return { me, profiles, license, stats }
  },
})
```

### Fetch semantics

| Call | Required? | On failure |
|------|-----------|------------|
| `GET /users/me` | **Yes** | Whole query fails → error banner |
| `GET /stats/dashboard` | **Yes** | Whole query fails → error banner |
| `GET /profiles` | No | Empty array `[]` |
| `GET /licenses/validate` | No | `null` (404 = no active license) |

- **No polling** — fetch once on mount (React Query default)
- **No manual refresh button** on Dashboard (Electron tests assert no Refresh button)
- **Parallel fetch** — all four requests in parallel

### Python equivalent

- `PlatformApi.get_dashboard_overview()` in `shared/services/platform_api.py` — already matches aggregation
- Worker: `DashboardOverviewWorker` in `shared/workers/data_workers.py`
- Trigger: `activate_page()` when route navigates to `home` (router lifecycle)
- Re-fetch when user navigates away and back to Dashboard

---

# 4. API contracts

Base URL: `http://localhost:8000/api/v1`  
Auth: `Authorization: Bearer <access_token>`

## 4.1 `GET /users/me`

**Types:** `UserMeResponse` (`platformEndpoints.ts`)

| Field | Type | Used on Dashboard? |
|-------|------|-------------------|
| `id` | string | No |
| `email` | string | No |
| `email_confirmed` | boolean | No |
| `display_name` | string | No |
| `credit_balance` | number | **Yes** — fallback for wallet in quota summary |
| `plan_name` | string \| null | **Yes** — plan label fallback |
| `profile_allowance` | number \| null | No |
| `channel_profile_count` | number | No |

## 4.2 `GET /licenses/validate`

**Types:** `ValidateLicenseResponse`

| Field | Type | Used on Dashboard? |
|-------|------|-------------------|
| `plan_type` | string | **Yes** — primary plan label |
| `profile_allowance` | number | No |
| `monthly_song_quota` | number \| null | **Yes** — song bar total + summary row |
| `songs_remaining` | number \| null | **Yes** — song bar value (preferred over stats) |
| `wallet_balance` | number | **Yes** — primary credits balance |
| `expiration_date` | string \| null | **Yes** — plan badge + activity header |

404 → treat as `null` (Trial fallback handled by API in some cases).

## 4.3 `GET /profiles`

Fetched but **not rendered** on `HomePage`. Keep fetching for parity (shared hook with Profile page) but no UI required on Dashboard.

## 4.4 `GET /stats/dashboard`

**Backend:** `platform_api/routers/stats.py`  
**Types:** `DashboardStatsResponse`

| Field | Type | Dashboard usage |
|-------|------|-----------------|
| `credits_spent` | number | KPI #1 “Suno Credit Spent” |
| `credits_remaining` | number | Credits progress bar **value** |
| `credits_total` | number | Credits progress bar **total** (`spent + remaining`) |
| `songs_generated` | number | KPI #2 |
| `songs_remaining` | number \| null | Song bar fallback if no license |
| `songs_quota` | number \| null | Song bar total fallback |
| `images_generated` | number | KPI #3 |
| `videos_generated` | number | KPI #4 **and** KPI #5 (see note) |
| `usage_by_day` | `DailyUsage[]` | Chart + day columns |
| `recent_activity` | `RecentActivity[]` | Activity table |

### `DailyUsage`

| Field | Type |
|-------|------|
| `date` | string (ISO date, 7 consecutive days) |
| `songs` | number |
| `images` | number |
| `videos` | number |

Backend builds **exactly 7 days** from `seven_days_ago` through today (UTC).

### `RecentActivity`

| Field | Type |
|-------|------|
| `timestamp` | datetime / ISO string |
| `kind` | string — `"Song"`, `"Image"`, `"Video"` |
| `detail` | string — title, image kind, or `"YouTube Upload"` |
| `status` | string — raw DB status |

Backend merges up to 10 songs + 10 images + 10 videos, sorts desc, takes top 20.

---

# 5. UI layout (top → bottom)

Electron uses `grid gap-6` vertical stack. PySide6: `QVBoxLayout` spacing ~12–24px.

```
┌─────────────────────────────────────────────────────────────┐
│ [ERROR BANNER] — only when stats/me fetch fails             │
├─────────────────────────────────────────────────────────────┤
│ [KPI][KPI][KPI][KPI][KPI]  — 5 cards, equal width row       │
├──────────────────────────────┬──────────────────────────────┤
│ WEEKLY USAGE (≈1.45 width)   │ REMAINING THIS MONTH (≈0.95) │
│  - title + subtitle          │  - 3 progress rows           │
│  - plan badge (top-right)    │  - quota summary box         │
│  - SVG chart 620×240         │                              │
│  - 7-day date columns        │                              │
│  - legend (Songs/Images/Vid) │                              │
├──────────────────────────────┴──────────────────────────────┤
│ RECENT ACTIVITY — full width table                          │
│  - header + plan/expiry (top-right)                         │
└─────────────────────────────────────────────────────────────┘
```

Responsive (Electron): KPIs `md:2 cols`, `xl:5 cols`; middle row `xl: 1.45fr / 0.95fr`.

---

# 6. Section-by-section specification

## 6.1 Error banner

**When:** `isError === true` (React Query) / worker `failed` signal (Python)

**Copy (exact):**
> Unable to load dashboard statistics right now. The shell still works, but dashboard data needs the backend stats endpoint to respond successfully.

**Style (Electron):** rose border/background card (`border-rose-500/25 bg-rose-500/10`)

**Python gap:** Plain `QLabel` — needs styled `QFrame` error card.

---

## 6.2 KPI row (5 cards)

Each `KpiCard`: title (11px uppercase), value (2xl semibold), icon in tinted rounded box.

| # | Title | Value source | Icon (Lucide) | Accent background |
|---|-------|--------------|-----------------|-------------------|
| 1 | Suno Credit Spent | `stats.credits_spent` | `Music4` | `bg-violet-500/20` |
| 2 | Songs Generated | `stats.songs_generated` | `Music4` | `bg-sky-500/20` |
| 3 | Images Generated | `stats.images_generated` | `Image` | `bg-emerald-500/20` |
| 4 | Videos Generated | `stats.videos_generated` | `Video` | `bg-amber-500/20` |
| 5 | YouTube Uploaded | `stats.videos_generated` | `Youtube` | `bg-rose-500/20` |

**Loading:** all values show `"--"` while loading.

**Formatting:** `Intl.NumberFormat('en-US')` → Python: `format_compact_number()` (`1,234`).

**Known Electron quirk:** KPI #5 uses `videos_generated`, not a separate YouTube count — **match this behavior** unless product changes API.

**Python gaps:**
- [ ] No icons on stat cards
- [ ] No per-card accent colors
- [ ] No loading `"--"` state before first fetch

---

## 6.3 Weekly Usage card

### Header row

| Left | Right (plan badge) |
|------|-------------------|
| **Title:** `Weekly Usage` (uppercase eyebrow) | **Label:** `Current Plan` |
| **Subtitle:** `Songs, images, and videos generated over the recent 7-day window.` | **Value:** `license.plan_type ?? me.plan_name ?? 'No plan'` |
| | **Sub:** `Expires {shortDate}` or `Expiration not provided` |

**Python gaps:**
- [ ] Missing subtitle paragraph
- [ ] Plan badge should be right-aligned inset card, not single line label

### Chart area

- Container: dark inset `#081028`, rounded border
- SVG viewBox `0 0 620 240`, height 240px
- **Grid:** 4 horizontal dashed lines at y = 20, 70, 120, 170 (20 + line×50)
- **Polylines:** three series from `usage_by_day`:
  - Songs — stroke `#7466F1`, width 3
  - Images — stroke `#1ABCFE`, width 3
  - Videos — stroke `#0ACF83`, width 3
- **Algorithm:** `buildPolylinePoints(values, 620, 240, 20)` — normalize Y by max value across series for that line (each series scaled independently)

### Day columns (below chart)

- 7-column grid (one per `usage_by_day` entry)
- Each cell: short date (e.g. `Jul 7`) + `{songs+images+videos} items`
- Empty: single message `No usage data available yet.`

### Legend

| Color | Label |
|-------|-------|
| `#7466F1` | Songs |
| `#1ABCFE` | Images |
| `#0ACF83` | Videos |

**Python gaps:**
- [ ] Chart exists but day columns are inline text, not 7-column grid
- [ ] Plan badge layout wrong
- [ ] Verify polyline scaling matches Electron (per-series max, not shared max)

---

## 6.4 Remaining This Month card

### Progress rows (`ProgressSummaryRow`)

Each row: label, `value / total` (formatted), percentage right-aligned, colored bar.

| Row | Label | Value | Total | Bar color |
|-----|-------|-------|-------|-----------|
| Credits | `Credits` | `stats.credits_remaining` | `max(stats.credits_total, 1)` | violet (`bg-violet-400`) |
| Songs | `Songs` | `license.songs_remaining ?? stats.songs_remaining ?? 0` | `max(license.monthly_song_quota ?? stats.songs_quota ?? 0, 1)` | sky (`bg-sky-400`) |
| Images | `Images` | `0` (hardcoded) | `1` (hardcoded) | emerald (`bg-emerald-400`) |

**Percentage:** `round(value / total * 100)` clamped 0–100.

**Python gap:** Songs row shows `"X remaining"` instead of `"X / total"` format — **must match Electron display**.

### Quota summary box (below bars)

| Label | Value logic |
|-------|-------------|
| Credits balance | `license.wallet_balance` if number, else `me.credit_balance`, else `--` |
| Song quota | `license.monthly_song_quota` formatted, else `Not provided` |
| Image quota | `0` (hardcoded) |

---

## 6.5 Recent Activity card

### Header

| Left | Right |
|------|-------|
| **Title:** `Recent Activity` | Plan type (same fallback as above) |
| **Subtitle:** `Latest events returned by the dashboard stats API.` | `Expires: {formatDateTime}` or `Not provided` |

### Table columns

| Column | Source | Notes |
|--------|--------|-------|
| Time | `formatDateTime(activity.timestamp)` | e.g. `Jul 7, 2026, 02:30 PM` |
| Type | `activity.kind` | Song / Image / Video |
| Batch | `--` | **Always placeholder in Electron** |
| Channel | `--` | **Always placeholder in Electron** |
| Stage | `activity.status` | Rendered as **pill badge** in Electron |
| Detail | `activity.detail` | |

### Empty / loading states

| State | Cell message |
|-------|--------------|
| Loading | `Loading recent activity...` (colspan 6) |
| Empty | `No recent activity found.` |

**Python gaps:**
- [ ] Missing activity header right column (plan + expiry)
- [ ] Missing subtitle under title
- [ ] Status shown as plain text, not pill badge
- [ ] No loading row state

---

# 7. Formatting helpers

| Function | Electron | Python target |
|----------|----------|---------------|
| Compact number | `Intl.NumberFormat('en-US')` | `shared/lib/formatting.format_compact_number` |
| Short date | `MMM d` | `format_short_date` |
| Date/time | `MMM d, yyyy, hh:mm AM/PM` | `format_datetime` |
| Percent | `round(part/total*100)` clamped | `percent_of` |

---

# 8. States & behavior matrix

| State | KPI values | Error banner | Chart | Activity table |
|-------|------------|--------------|-------|----------------|
| Initial load | `--` | hidden | empty message | “Loading recent activity…” |
| Success | formatted numbers | hidden | data | rows |
| API error | `--` or stale | **visible** | empty | “No recent activity found.” |
| Empty account | `0` | hidden | “No usage data available yet.” | “No recent activity found.” |

**No refresh button. No polling timer.**

---

# 9. Electron tests (must pass in spirit)

**File:** `HomePage.test.tsx`

1. While loading → sections visible, KPIs show `--`, **no Refresh button**
2. On error → error banner with exact copy substring

**Python tests to add:**

- `test_dashboard_shows_loading_placeholders`
- `test_dashboard_shows_error_banner`
- `test_dashboard_binds_kpi_values` (mock overview)
- `test_dashboard_songs_bar_uses_value_total_format`

---

# 10. Python file map (target structure)

```text
features/dashboard/
  views/
    dashboard_view.py       ← main page (layout + bind)
  widgets/                  ← optional split
    kpi_card.py             ← icon + accent StatCard
    progress_summary_row.py ← matches ProgressSummaryRow
    weekly_usage_card.py    ← chart + plan badge + legend
    recent_activity_card.py ← table + header
  viewmodels/               ← optional
    dashboard_viewmodel.py  ← pure bind logic (easier to test)

shared/
  models/platform.py        ← DashboardOverview, DashboardStatsResponse (exists)
  workers/data_workers.py   ← DashboardOverviewWorker (exists)
  lib/formatting.py         ← formatters (exists)
```

---

# 11. Gap analysis — current Python vs 100%

| Item | Electron | Python now | Done? |
|------|----------|--------------|-------|
| 4 API parallel fetch | Yes | Yes | ✅ |
| Profiles fetched | Yes (unused) | Yes | ✅ |
| License 404 → null | Yes | Yes | ✅ |
| Error banner copy | Exact | Similar | ⚠️ |
| Error banner styling | Rose card | Plain label | ❌ |
| Loading KPI `--` | Yes | Shows 0 after load only | ❌ |
| KPI icons + accents | Yes | Missing | ❌ |
| Weekly subtitle | Yes | Missing | ❌ |
| Plan badge layout | Top-right card | Inline label | ❌ |
| Chart grid lines | 4 dashed | Partial | ⚠️ |
| Chart 7-column days | Grid | Joined string | ❌ |
| Legend dots | Yes | Text only | ⚠️ |
| Credits bar format | `remaining / total` | Correct | ✅ |
| Songs bar format | `remaining / quota` | `X remaining` only | ❌ |
| Images bar hardcoded 0/1 | Yes | Yes | ✅ |
| Quota summary 3 rows | Yes | Yes | ✅ |
| Activity header right | Plan + expiry | Missing | ❌ |
| Activity status pill | Yes | Plain text | ❌ |
| Activity loading row | Yes | Missing | ❌ |
| No refresh button | Yes | Yes | ✅ |
| No polling | Yes | Yes | ✅ |

**Estimated completion: ~70%**

---

# 12. Acceptance checklist (100%)

Copy this into PR / status doc when done.

### Data
- [ ] Parallel fetch: me, profiles (catch []), license (catch null), stats (required)
- [ ] Navigate to Dashboard triggers fetch; leaving stops nothing (no timer)
- [ ] Return to Dashboard re-fetches

### Error & loading
- [ ] Loading: all 5 KPIs show `--`
- [ ] Loading: activity table shows “Loading recent activity…”
- [ ] Error: rose-styled banner with exact Electron copy
- [ ] Success: error banner hidden

### KPI row
- [ ] 5 cards with correct titles and data bindings
- [ ] Icons (music/image/video/youtube) with accent backgrounds
- [ ] YouTube KPI uses `videos_generated` (Electron parity)

### Weekly Usage
- [ ] Title + subtitle
- [ ] Plan badge top-right with plan type + expiry
- [ ] Chart: 3 polylines, correct colors, 4 grid lines
- [ ] 7 day columns with date + item count
- [ ] Legend with colored dots

### Remaining This Month
- [ ] Credits bar: remaining / total + violet bar
- [ ] Songs bar: remaining / quota + sky bar
- [ ] Images bar: 0 / 1 + emerald bar
- [ ] Summary: credits balance, song quota, image quota = 0

### Recent Activity
- [ ] Header with subtitle + plan/expiry right
- [ ] 6 columns; Batch and Channel always `--`
- [ ] Status as pill/badge widget
- [ ] Empty and loading messages

### Quality
- [ ] Tests listed in §9 passing
- [ ] Manual verify with live `platform_api` logged in
- [ ] `02_IMPLEMENTATION_STATUS.md` updated: Dashboard ✅

---

# 13. References

| Path | Role |
|------|------|
| `camxora/src/renderer/src/features/shell/HomePage.tsx` | UI source |
| `camxora/src/renderer/src/features/shell/useDashboardOverviewQuery.ts` | Data hook |
| `camxora/src/renderer/src/features/shell/HomePage.test.tsx` | Tests |
| `camxora/src/renderer/src/shared/api/platformEndpoints.ts` | Types + API fns |
| `platform_api/routers/stats.py` | Dashboard stats backend |
| `platform_api/routers/licenses.py` | License validate |
| `camxora_python/features/dashboard/views/dashboard_view.py` | Current Python impl |

---

# 14. Revision history

| Date | Change |
|------|--------|
| 2026-07-07 | Initial full gather from Electron + API + gap analysis |
