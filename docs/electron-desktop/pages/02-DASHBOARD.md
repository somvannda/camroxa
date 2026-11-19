# 2. Dashboard

> **Feature prefix:** `DB-`
> **Route:** `/app/home`
> **Phase:** P2
> **Sources of truth:**
> - `camxora_python/features/dashboard/views/dashboard_view.py`
> - `camxora_python/.docs/pages/03_DASHBOARD_REQUIREMENTS.md`
> - `camxora_python/.docs/pages/03_DASHBOARD_PAGE_SPEC.md`
> - `platform_api/routers/stats.py`, `licenses.py`, `users.py`, `profiles.py`

---

## 1. Purpose

A read-only overview of account usage, weekly trends, remaining quota and recent backend
events. It is the default landing page after login or onboarding.

It is **not** an editor, a navigation hub, or a profile manager. It has no refresh button and
no polling timer.

---

## 2. Data

One aggregated load on every page activation:

| # | Method | Path | Required | Failure behaviour |
|---|---|---|---|---|
| 1 | GET | `/users/me` | Yes | Whole page error state |
| 2 | GET | `/stats/dashboard` | Yes | Whole page error state |
| 3 | GET | `/profiles` | No | `[]` |
| 4 | GET | `/licenses/validate` | No | `null` (404 = no license) |

The four requests run in parallel. The renderer queries through `window.camxora.api`, so the
main process attaches auth and retries once on 401.

`activate_page` semantics: fetch on first visit and on every return; no timer.

---

## 3. Layout

```
[ error banner (conditional) ]
[ KPI 1 ] [ KPI 2 ] [ KPI 3 ] [ KPI 4 ] [ KPI 5 ]
┌──────────────────────────────────────┬─────────────────────────────┐
│ Weekly Usage (~59%)                  │ Remaining This Month (~41%) │
│ title + subtitle          [plan]     │ 3 progress rows             │
│ chart panel                          │ quota summary box           │
│ 7 day columns + legend               │                             │
└──────────────────────────────────────┴─────────────────────────────┘
[ Recent Activity (full width): header left/right + table ]
```

Vertical gap between major sections: 24 px. The page scrolls when content exceeds the
viewport.

---

## 4. Features

### 4.1 Data and lifecycle

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-01 | Aggregated load | One parallel fetch per activation; no duplicate requests on rerender | P0 |
| DB-02 | Re-fetch on return | Navigating away and back refreshes the data | P0 |
| DB-03 | No polling | No interval fires while the page is idle | P0 |
| DB-04 | No refresh button | The page has no manual refresh control | P0 |
| DB-05 | Optional failures | Profiles failure → `[]`; license failure → `null`; page still renders | P0 |
| DB-06 | Required failures | `/users/me` or `/stats/dashboard` failure → error banner and no success data | P0 |
| DB-07 | Stale data | After a later failure, keep the last good data and mark it "Stale" | P1 |

### 4.2 KPI row

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-08 | Five cards | Exactly five, equal width, one row on wide screens | P0 |
| DB-09 | Suno credit spent | `stats.credits_spent`, US grouping (`1,234`) | P0 |
| DB-10 | Songs generated | `stats.songs_generated` | P0 |
| DB-11 | Images generated | `stats.images_generated` | P0 |
| DB-12 | Videos generated | `stats.videos_generated` | P0 |
| DB-13 | YouTube uploaded | Uses `stats.videos_generated` (reference parity) | P0 |
| DB-14 | Loading placeholders | All five show `--` before data | P0 |
| DB-15 | Card anatomy | Label, large figure, one tinted icon box; no sparkline | P0 |
| DB-16 | Distinct tints | Violet, sky, emerald, amber, rose; icons are semantic | P1 |

### 4.3 Weekly usage

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-17 | Title/subtitle | "Weekly Usage" / "Songs, images, and videos generated over the recent 7-day window." | P0 |
| DB-18 | Plan badge | Current plan + expiry (`Expires …` or "Expiration not provided") | P0 |
| DB-19 | Three series | Songs, images, videos; each scaled independently by its series max | P0 |
| DB-20 | Chart geometry | 4 dashed grid lines; padding 20; `y = h − p − (v/max)·(h − 2p)` | P0 |
| DB-21 | Colors | `#8B7CF6` songs, `#38BDF8` images, `#4ADE80` videos; 3 px stroke | P0 |
| DB-22 | Seven day columns | Short date (`MMM d`) + `{songs+images+videos} items` | P0 |
| DB-23 | Legend | Three dots + labels below the day grid | P0 |
| DB-24 | Empty chart | "No usage data available yet." when `usage_by_day` is empty | P0 |
| DB-25 | Hover/readout | Hover shows a vertical guide and the three values for that day | P1 |
| DB-26 | Data table alternative | "View data" exposes a table for accessibility | P1 |

### 4.4 Remaining this month

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-27 | Credits row | `remaining / total`, clamped percent, violet bar | P0 |
| DB-28 | Songs row | License remaining/quota preferred, then stats, sky bar | P0 |
| DB-29 | Images row | `0 / 1`, emerald bar (reference parity) | P0 |
| DB-30 | Percent | `round(value/total*100)` clamped 0–100 | P0 |
| DB-31 | Quota summary | Credits balance, song quota ("Not provided" when absent), image quota `0` | P0 |
| DB-32 | Loading | Values `--`; bars at 0 | P0 |

### 4.5 Recent activity

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-33 | Header | Title/subtitle; plan + `Expires: …` on the right | P0 |
| DB-34 | Six columns | Time, Type, Batch, Channel, Stage, Detail | P0 |
| DB-35 | Fixed columns | Batch and Channel always `--` | P0 |
| DB-36 | Status pill | Stage uses a badge, not plain text | P0 |
| DB-37 | Time format | `MMM d, yyyy, hh:mm AM/PM` | P0 |
| DB-38 | Loading row | "Loading recent activity..." spanning all columns | P0 |
| DB-39 | Empty row | "No recent activity found." | P0 |
| DB-40 | Row count | Up to 20 events from the API, newest first | P0 |

### 4.6 Page-level

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| DB-41 | Error banner | Rose card with the exact copy from §6 | P0 |
| DB-42 | Responsive | Two columns ≥ 1200 px; stacked below | P1 |
| DB-43 | Keyboard | Cards and table are reachable; "View data" is focusable | P1 |
| DB-44 | Skeleton | Static skeleton blocks; no shimmer | P1 |

---

## 5. States

| State | KPIs | Banner | Chart | Activity |
|---|---|---|---|---|
| Loading | `--` | hidden | empty | "Loading recent activity..." |
| Success | numbers | hidden | data or empty message | rows or empty message |
| Error | `--` or stale | visible | empty | empty message |
| Empty account | `0` | hidden | "No usage data available yet." | "No recent activity found." |

---

## 6. Copy (verbatim)

- Error: "Unable to load dashboard statistics right now. The shell still works, but
  dashboard data needs the backend stats endpoint to respond successfully."
- Empty chart: "No usage data available yet."
- Loading activity: "Loading recent activity..."
- Empty activity: "No recent activity found."

---

## 7. Tests

| ID | Scenario | Assert |
|---|---|---|
| DB-T1 | Loading | Section titles visible; KPIs `--`; no refresh button |
| DB-T2 | Error | Banner copy present; no success data |
| DB-T3 | Success | Five KPI values match the payload |
| DB-T4 | Songs bar | `remaining / quota`, not "X remaining" |
| DB-T5 | Activity loading | Loading message before rows |
| DB-T6 | Activity empty | Empty message |
| DB-T7 | Return to page | A second fetch occurs |
| DB-T8 | Chart geometry | Points match the formula for known data |

---

## 8. Definition of Done

- [ ] DB-01 … DB-44 implemented; all `P0` verified against sandbox.
- [ ] Loading, error, empty and stale states verified.
- [ ] Chart is accessible with a data-table alternative.
- [ ] No refresh button and no polling.
- [ ] DB-T1 … DB-T8 pass.
- [ ] Visual baseline approved at 1440×900.
