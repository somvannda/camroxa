# Dashboard Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-03-DASHBOARD  
> **Version:** 1.0.0  
> **Status:** Approved for implementation  
> **Phase:** 3  
> **Source of truth:** `camxora/src/renderer/src/features/shell/HomePage.tsx`  
> **Target:** `camxora_python/features/dashboard/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

This is the **complete requirements document** for the Dashboard page. Implementation must match **100% functional parity** with the Electron Camxora app. UI is rebuilt with **native PySide6 widgets** and **`shared/themes/deep_blue.py`** QSS — not a pixel-perfect CSS clone.

**Build rule:** Do not mark Dashboard complete until every item in **§14 Definition of Done** is checked.

**Companion doc:** [03_DASHBOARD_PAGE_SPEC.md](03_DASHBOARD_PAGE_SPEC.md) (technical gather + gap notes).

---

# 2. Overview

## 2.1 What the Dashboard is

The Dashboard (`/app/home`) is the **default landing page** after login or onboarding. It is a **read-only overview** of account usage, weekly generation trends, remaining quotas, and recent backend events.

## 2.2 What the Dashboard is not

- Not an editor — no create/update/delete actions
- Not a navigation hub — no links to batches or channels from KPIs
- Not a profile manager — channel profiles are fetched but **not displayed** on this page (Electron parity)
- No manual refresh button
- No auto-polling timer

## 2.3 User goals

| User need | Dashboard answer |
|-----------|------------------|
| How much have I used? | KPI row + credits spent |
| What's my trend this week? | Weekly usage chart (7 days) |
| What's left on my plan? | Remaining This Month + quota summary |
| What happened recently? | Recent Activity table |

---

# 3. Entry points & navigation

## 3.1 Route

| Property | Value |
|----------|-------|
| Path | `/app/home` |
| Sidebar key | `home` |
| Sidebar label | Dashboard |
| Page title | Dashboard |
| Eyebrow | Workspace |
| Description | Overview of the current CAMXORA account, profile readiness, and studio status. |

**PySide6:** Metadata from `shared/constants/navigation.py`. Page header visible (same as Electron shell).

## 3.2 When user lands here

| Flow | Electron behavior | PySide6 requirement |
|------|-------------------|---------------------|
| Successful login/bootstrap | Redirect to `/app/home` | Same via `SessionService` → app shell |
| Onboarding wizard complete | `navigate('/app/home')` | Same when wizard implemented |
| Sidebar click "Dashboard" | Route change + data fetch | `AppRouter.navigate('home')` → `activate_page()` |

## 3.3 Data refresh trigger

| Event | Fetch dashboard data? |
|-------|----------------------|
| First navigate to Dashboard | **Yes** |
| Navigate away and back | **Yes** |
| Timer / polling | **No** |
| User clicks Refresh | **No** (no button exists) |

---

# 4. Data requirements

## 4.1 Aggregated payload

Dashboard loads one aggregated object (Electron: `useDashboardOverviewQuery`; Python: `DashboardOverview`):

```text
{
  me: UserMeResponse,
  profiles: ProfileResponse[],   // fetched, not displayed
  license: ValidateLicenseResponse | null,
  stats: DashboardStatsResponse
}
```

## 4.2 API calls (parallel)

All four requests run **in parallel** on each load.

| # | Method | Path | Required | On failure |
|---|--------|------|----------|------------|
| 1 | GET | `/api/v1/users/me` | **Yes** | Entire page → error state |
| 2 | GET | `/api/v1/stats/dashboard` | **Yes** | Entire page → error state |
| 3 | GET | `/api/v1/profiles` | No | Use `[]` |
| 4 | GET | `/api/v1/licenses/validate` | No | Use `null` (404 = no license) |

**Auth:** `Authorization: Bearer <access_token>` on all calls.

**Python implementation:**
- `PlatformApi.get_dashboard_overview()` — already exists
- `DashboardOverviewWorker` — background thread; session **must be hydrated on main thread** before worker starts

## 4.3 Response schemas

### UserMeResponse (fields used on Dashboard)

| Field | Type | Dashboard use |
|-------|------|---------------|
| `credit_balance` | number | Fallback for "Credits balance" when license wallet missing |
| `plan_name` | string \| null | Fallback plan label when `license` is null |

*Other fields (`id`, `email`, etc.) are fetched but not shown on Dashboard.*

### ValidateLicenseResponse

| Field | Type | Dashboard use |
|-------|------|---------------|
| `plan_type` | string | Primary plan label |
| `monthly_song_quota` | number \| null | Songs bar total; "Song quota" row |
| `songs_remaining` | number \| null | Songs bar value (preferred over stats) |
| `wallet_balance` | number | Primary "Credits balance" |
| `expiration_date` | string \| null | Plan badge + activity header |

### DashboardStatsResponse

| Field | Type | Dashboard use |
|-------|------|---------------|
| `credits_spent` | number | KPI #1 |
| `credits_remaining` | number | Credits progress bar value |
| `credits_total` | number | Credits progress bar total |
| `songs_generated` | number | KPI #2 |
| `songs_remaining` | number \| null | Songs bar fallback value |
| `songs_quota` | number \| null | Songs bar fallback total |
| `images_generated` | number | KPI #3 |
| `videos_generated` | number | KPI #4 and KPI #5 |
| `usage_by_day` | DailyUsage[] | Chart + day columns |
| `recent_activity` | RecentActivity[] | Activity table |

### DailyUsage

| Field | Type | Notes |
|-------|------|-------|
| `date` | string (ISO date) | Backend returns **7 consecutive days** |
| `songs` | number | Chart series + day item count |
| `images` | number | Chart series + day item count |
| `videos` | number | Chart series + day item count |

### RecentActivity

| Field | Type | Notes |
|-------|------|-------|
| `timestamp` | datetime / ISO string | "Time" column |
| `kind` | string | `"Song"`, `"Image"`, or `"Video"` |
| `detail` | string | Song title, image kind, or `"YouTube Upload"` |
| `status` | string | Shown as pill in "Stage" column |

**Backend:** `platform_api/routers/stats.py` — merges up to 20 events (10 songs + 10 images + 10 videos, sorted desc).

---

# 5. Functional requirements

## FR-1 Error handling

**FR-1.1** When `GET /users/me` or `GET /stats/dashboard` fails, show the error banner (§6.1) and do not render success data as if loaded.

**FR-1.2** Error banner copy (exact):

> Unable to load dashboard statistics right now. The shell still works, but dashboard data needs the backend stats endpoint to respond successfully.

**FR-1.3** When `GET /profiles` fails, continue with `profiles = []`.

**FR-1.4** When `GET /licenses/validate` fails (including 404), continue with `license = null`.

## FR-2 Loading state

**FR-2.1** While data is loading, all **5 KPI values** display `"--"`.

**FR-2.2** While loading, Recent Activity table body shows single row: **"Loading recent activity..."** (colspan 6).

**FR-2.3** Section titles ("Weekly Usage", "Remaining This Month", "Recent Activity") remain visible during load.

**FR-2.4** No Refresh button on Dashboard (Electron test requirement).

## FR-3 KPI row

**FR-3.1** Display exactly **5 KPI cards** in one horizontal row.

| Order | Title | Value when loaded | Value when loading |
|-------|-------|-------------------|-------------------|
| 1 | Suno Credit Spent | `stats.credits_spent` | `--` |
| 2 | Songs Generated | `stats.songs_generated` | `--` |
| 3 | Images Generated | `stats.images_generated` | `--` |
| 4 | Videos Generated | `stats.videos_generated` | `--` |
| 5 | YouTube Uploaded | `stats.videos_generated` | `--` |

**FR-3.2** **Electron parity note:** KPI #5 uses `videos_generated`, not a separate YouTube count. Match this unless product explicitly changes API.

**FR-3.3** Each KPI card includes:
- Uppercase title label
- Large formatted number
- Icon in tinted rounded box (see §7.2)

**FR-3.4** Numbers formatted with US locale grouping: `1,234` (`format_compact_number`).

## FR-4 Weekly Usage section

**FR-4.1** Section title: **Weekly Usage**

**FR-4.2** Subtitle (exact): **Songs, images, and videos generated over the recent 7-day window.**

**FR-4.3** Plan badge (top-right of section header):

| Line | Content |
|------|---------|
| Label | Current Plan |
| Value | `license.plan_type ?? me.plan_name ?? 'No plan'` |
| Sub | `Expires {shortDate}` if `license.expiration_date`, else `Expiration not provided` |

**FR-4.4** Chart area:
- Dark inset panel (`#081028` equivalent)
- Height ~240px
- **4 horizontal dashed grid lines**
- **3 polylines** — one per series, scaled independently by each series' max value:
  - Songs: `#7466F1`
  - Images: `#1ABCFE`
  - Videos: `#0ACF83`
- Stroke width 3

**FR-4.5** Chart algorithm (must match Electron `buildPolylinePoints`):

```text
width=620, height=240, padding=20
max = max(values, 1)   // per series
xStep = (width - 2*padding) / max(count-1, 1)
y = height - padding - (value/max) * (height - 2*padding)
```

**FR-4.6** Below chart: **7-column grid** (one column per `usage_by_day` entry):
- Line 1: short date (`MMM d`, e.g. `Jul 7`)
- Line 2: `{songs + images + videos} items`

**FR-4.7** If `usage_by_day` is empty: single message **No usage data available yet.**

**FR-4.8** Legend below day grid:

| Dot color | Label |
|-----------|-------|
| `#7466F1` | Songs |
| `#1ABCFE` | Images |
| `#0ACF83` | Videos |

## FR-5 Remaining This Month section

**FR-5.1** Section title: **Remaining This Month**

**FR-5.2** Three progress summary rows. Each shows:
- Uppercase label
- **`{value formatted} / {total formatted}`** (not "X remaining" text)
- Percentage right-aligned
- Colored progress bar

| Row | Label | Value | Total | Bar color |
|-----|-------|-------|-------|-----------|
| 1 | Credits | `stats.credits_remaining ?? 0` | `max(stats.credits_total, 1)` | Violet |
| 2 | Songs | `license.songs_remaining ?? stats.songs_remaining ?? 0` | `max(license.monthly_song_quota ?? stats.songs_quota ?? 0, 1)` | Sky blue |
| 3 | Images | `0` (hardcoded) | `1` (hardcoded) | Emerald |

**FR-5.3** Percentage: `round(value / total * 100)` clamped to 0–100.

**FR-5.4** Quota summary box below bars:

| Label | Value logic |
|-------|-------------|
| Credits balance | `license.wallet_balance` if number → else `me.credit_balance` if number → else `--` |
| Song quota | `license.monthly_song_quota` formatted → else **Not provided** |
| Image quota | **0** (hardcoded) |

## FR-6 Recent Activity section

**FR-6.1** Header left:
- Title: **Recent Activity**
- Subtitle: **Latest events returned by the dashboard stats API.**

**FR-6.2** Header right (right-aligned):
- Line 1: `license.plan_type ?? me.plan_name ?? 'No plan'`
- Line 2: `Expires: {formatDateTime(license.expiration_date)}` or **Not provided**

**FR-6.3** Table with 6 columns:

| Column | Source | Notes |
|--------|--------|-------|
| Time | `formatDateTime(timestamp)` | e.g. `Jul 7, 2026, 02:30 PM` |
| Type | `kind` | |
| Batch | `--` | Always literal `--` |
| Channel | `--` | Always literal `--` |
| Stage | `status` | **Pill/badge widget**, not plain text |
| Detail | `detail` | |

**FR-6.4** Empty state (loaded, no rows): **No recent activity found.**

**FR-6.5** Loading state: **Loading recent activity...**

---

# 6. UI requirements

## 6.1 Layout (top → bottom)

```text
┌─────────────────────────────────────────────────────────────────┐
│ ERROR BANNER (conditional)                                      │
├─────────────────────────────────────────────────────────────────┤
│ [KPI 1] [KPI 2] [KPI 3] [KPI 4] [KPI 5]   ← equal-width row    │
├────────────────────────────────────┬────────────────────────────┤
│ WEEKLY USAGE (~59% width)            │ REMAINING THIS MONTH (~41%)│
│  title + subtitle    [plan badge]    │  3 progress rows           │
│  chart panel                       │  quota summary box         │
│  7 day columns + legend            │                            │
├────────────────────────────────────┴────────────────────────────┤
│ RECENT ACTIVITY (full width)                                    │
│  header (left + right) + table                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Spacing:** Vertical gap between major sections ~24px (Electron `gap-6`).

**Scroll:** Page body scrolls if content exceeds viewport (`QScrollArea` acceptable).

## 6.2 Error banner styling

- Rose-tinted card (border + background), not plain text label
- Padding ~24px
- Copy from FR-1.2

## 6.3 KPI card styling

Each card:
- Card frame with padding
- Title: small uppercase muted text
- Value: large semibold white text
- Icon box: 40×40px rounded, bordered, tinted background

| KPI | Icon (semantic) | Accent tint |
|-----|-----------------|-------------|
| Suno Credit Spent | Music | Violet (`violet-500/20`) |
| Songs Generated | Music | Sky (`sky-500/20`) |
| Images Generated | Image | Emerald (`emerald-500/20`) |
| Videos Generated | Video | Amber (`amber-500/20`) |
| YouTube Uploaded | YouTube | Rose (`rose-500/20`) |

**PySide6:** Qt standard icons or small SVG/emoji acceptable if Lucide not available — must have visual icon + distinct accent per card.

## 6.4 Progress summary row styling

- Inset dark panel per row
- Label uppercase muted
- Value line: `{part} / {total}` large white
- Percentage right side
- Bar: 8px height, rounded, colored fill on muted track

## 6.5 Activity status pill

- Rounded pill/chip around status text
- Border + subtle background
- Small text (~12px)

## 6.6 Theme

- Use `shared/themes/deep_blue.py` (`account_card` objectName for card panels)
- Do not import `python_app/design_system/`

---

# 7. Formatting requirements

| ID | Rule | Electron | Python |
|----|------|----------|--------|
| FMT-1 | Compact number | `Intl.NumberFormat('en-US')` | `format_compact_number` |
| FMT-2 | Short date | `MMM d` | `format_short_date` |
| FMT-3 | Date/time | `MMM d, yyyy, hh:mm AM/PM` | `format_datetime` |
| FMT-4 | Percent | `round(part/total*100)` clamp 0–100 | `percent_of` |

**Null handling:**
- Missing numeric → `0` for KPIs after load
- Missing quota → **Not provided**
- Missing expiry → **Expiration not provided** / **Not provided**

---

# 8. State matrix

| State | KPIs | Error banner | Chart | Activity table |
|-------|------|--------------|-------|----------------|
| **Loading** | `--` | Hidden | Empty / no polylines | "Loading recent activity..." |
| **Success** | Formatted numbers | Hidden | Data or empty message | Rows or "No recent activity found." |
| **Error** | `--` or last stale | **Visible** | Empty | "No recent activity found." |
| **Success + empty account** | `0` | Hidden | "No usage data available yet." | "No recent activity found." |

---

# 9. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | API fetch runs off UI thread (`QThread` worker) |
| NFR-2 | UI thread never blocked by httpx |
| NFR-3 | Session tokens hydrated on main thread before worker (Windows DPAPI) |
| NFR-4 | No memory leaks from repeated navigate-away/back (worker cancelled or single-flight) |
| NFR-5 | Page usable at 1280×800 minimum window size |

---

# 10. Test requirements

Port Electron test scenarios from `HomePage.test.tsx`:

| Test ID | Scenario | Assert |
|---------|----------|--------|
| T-1 | Loading | "Weekly Usage" and "Remaining This Month" visible; KPIs show `--`; **no Refresh button** |
| T-2 | Error | Error banner contains "unable to load dashboard statistics right now" |
| T-3 | Success bind | Mock overview → KPI values match stats |
| T-4 | Songs bar format | Displays `remaining / quota` not "X remaining" |
| T-5 | Activity loading | Loading message in table before data |
| T-6 | Activity empty | "No recent activity found." when rows empty |

---

# 11. Implementation structure

```text
features/dashboard/
  views/
    dashboard_view.py          ← page layout + state wiring
  widgets/                     ← recommended split from monolith
    error_banner.py
    kpi_card.py
    weekly_usage_card.py
    remaining_month_card.py
    recent_activity_card.py

shared/
  models/platform.py           ← DashboardOverview, DTOs (exists)
  services/platform_api.py     ← get_dashboard_overview (exists)
  workers/data_workers.py      ← DashboardOverviewWorker (exists)
  lib/formatting.py            ← formatters (exists)

app/router.py                  ← route home → DashboardView; activate_page()
```

---

# 12. Out of scope (this page)

- Channel profiles list/table (fetched only for shared hook parity)
- Edit profile / plan upgrade actions
- Click-through from activity rows to batches
- Pull-to-refresh / polling / manual refresh
- Separate YouTube upload count KPI (Electron uses `videos_generated`)
- Image quota from API (hardcoded `0` in Electron)

---

# 13. Electron source reference map

| Requirement area | Electron file |
|------------------|---------------|
| Full UI | `camxora/src/renderer/src/features/shell/HomePage.tsx` |
| Data hook | `camxora/src/renderer/src/features/shell/useDashboardOverviewQuery.ts` |
| API types | `camxora/src/renderer/src/shared/api/platformEndpoints.ts` |
| Tests | `camxora/src/renderer/src/features/shell/HomePage.test.tsx` |
| Route meta | `camxora/src/renderer/src/features/shell/shellNavigation.ts` |
| Stats API | `platform_api/routers/stats.py` |
| License API | `platform_api/routers/licenses.py` |

---

# 14. Definition of Done (100% checklist)

Copy and check off at implementation sign-off.

### Data & lifecycle
- [ ] **D-1** Parallel fetch: me + stats (required), profiles (catch []), license (catch null)
- [ ] **D-2** Fetch on `activate_page()` when navigating to Dashboard
- [ ] **D-3** Re-fetch when returning to Dashboard; no polling timer
- [ ] **D-4** No Refresh button

### Error & loading
- [ ] **D-5** Rose error banner with exact FR-1.2 copy
- [ ] **D-6** Loading: all 5 KPIs show `--`
- [ ] **D-7** Loading: activity table shows "Loading recent activity..."

### KPI row (FR-3)
- [ ] **D-8** Five cards with correct titles and data bindings
- [ ] **D-9** Icons + distinct accent tint per card
- [ ] **D-10** YouTube KPI uses `videos_generated`

### Weekly Usage (FR-4)
- [ ] **D-11** Title + subtitle (exact copy)
- [ ] **D-12** Plan badge top-right with plan + expiry
- [ ] **D-13** Chart: 3 polylines, 4 grid lines, correct colors
- [ ] **D-14** 7 day columns with date + item count
- [ ] **D-15** Legend with colored dots
- [ ] **D-16** Empty chart message when no usage data

### Remaining This Month (FR-5)
- [ ] **D-17** Credits bar: `remaining / total` + violet bar
- [ ] **D-18** Songs bar: `remaining / quota` + sky bar (not "X remaining")
- [ ] **D-19** Images bar: `0 / 1` + emerald bar
- [ ] **D-20** Quota summary: credits balance, song quota, image quota = 0

### Recent Activity (FR-6)
- [ ] **D-21** Header subtitle + plan/expiry on right
- [ ] **D-22** Six columns; Batch and Channel always `--`
- [ ] **D-23** Stage column uses pill/badge
- [ ] **D-24** Loading and empty messages

### Quality
- [ ] **D-25** Tests T-1 through T-6 passing
- [ ] **D-26** Manual verify with live `platform_api` while logged in
- [ ] **D-27** `02_IMPLEMENTATION_STATUS.md` updated: Dashboard ✅

---

# 15. Revision history

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-07-07 | AI + user | Initial complete requirements from Electron HomePage |
