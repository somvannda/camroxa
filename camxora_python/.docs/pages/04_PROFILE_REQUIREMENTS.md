# Profile Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-04-PROFILE  
> **Version:** 1.0.0  
> **Status:** Approved for implementation  
> **Phase:** 4  
> **Source of truth:** `camxora/src/renderer/src/features/shell/ProfilePage.tsx`  
> **Target:** `camxora_python/features/profile/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

This is the **complete requirements document** for the Profile page. Implementation must match **100% functional parity** with the Electron Camxora app. UI is rebuilt with **native PySide6 widgets** and **`shared/themes/deep_blue.py`** QSS — not a pixel-perfect CSS clone.

**Build rule:** Do not mark Profile complete until every item in **§14 Definition of Done** is checked.

---

# 2. Overview

## 2.1 What the Profile page is

The Profile page (`/app/profile`) is a **read-only account overview**: signed-in user details, plan/membership quotas, channel profiles table, and lifetime activity counters.

## 2.2 What the Profile is not

- Not a profile editor — no create/update/delete actions
- Not a settings page — no API URL or theme controls
- No manual refresh button
- No auto-polling timer
- No page-level error banner (errors surface inline in Account card)

## 2.3 User goals

| User need | Profile answer |
|-----------|----------------|
| Who am I signed in as? | Account card: name, email, user ID, verification |
| What's my plan and quota? | Membership card: metric bars + plan/credits/expiry |
| What channel profiles exist? | Channel Profiles table |
| What have I generated? | Activity card: songs, images, videos, credits spent |

---

# 3. Entry points & navigation

## 3.1 Route

| Property | Value |
|----------|-------|
| Path | `/app/profile` |
| Sidebar key | `profile` |
| Sidebar label | Profile |
| Page title | Profile |
| Eyebrow | Account |
| Description | Signed-in account, plan, credits, allowance, and created channel profiles. |

**PySide6:** Metadata from `shared/constants/navigation.py`. Page header visible (same as Electron shell).

## 3.2 Data refresh trigger

| Event | Fetch profile data? |
|-------|---------------------|
| First navigate to Profile | **Yes** |
| Navigate away and back | **Yes** |
| Timer / polling | **No** |
| User clicks Refresh | **No** (no button exists) |

---

# 4. Data requirements

## 4.1 Aggregated payload

Profile uses the **same aggregated object as Dashboard** (Electron: `useDashboardOverviewQuery`; Python: `DashboardOverview`):

```text
{
  me: UserMeResponse,
  profiles: ProfileResponse[],
  license: ValidateLicenseResponse | null,
  stats: DashboardStatsResponse
}
```

## 4.2 API calls (parallel)

| # | Method | Path | Required | On failure |
|---|--------|------|----------|------------|
| 1 | GET | `/api/v1/users/me` | **Yes** | Entire fetch fails → error state |
| 2 | GET | `/api/v1/stats/dashboard` | **Yes** | Entire fetch fails → error state |
| 3 | GET | `/api/v1/profiles` | No | Use `[]` |
| 4 | GET | `/api/v1/licenses/validate` | No | Use `null` (404 = no license) |

**Python:** `DashboardOverviewWorker` + `PlatformApi.get_dashboard_overview()` (reuse from Dashboard).

---

# 5. Layout structure

Two-row grid matching Electron `ProfilePage.tsx`:

```text
Row 1 (≈ 1.2fr + 0.8fr):
  [ Account card ]  [ Membership card ]

Row 2 (≈ 1.55fr + 0.75fr):
  [ Channel Profiles card ]  [ Activity card ]
```

---

# 6. Functional requirements

## FR-1 — Account card

| ID | Requirement |
|----|-------------|
| FR-1.1 | Section label: **ACCOUNT** |
| FR-1.2 | Display name: `me.display_name` or fallback **"Loading account..."** |
| FR-1.3 | Email: `me.email` or **"Loading account email..."** while loading |
| FR-1.4 | On error: email **"Unable to load account information."**; display name stays **"Loading account..."** |
| FR-1.5 | **Verification badge** top-right (inset card, not full-width field): Verified / Pending from `me.email_confirmed` |
| FR-1.6 | SummaryField **User ID**: `me.id` or `--` |
| FR-1.7 | SummaryField **Session**: **Active** on success; **Needs attention** on error |

## FR-2 — Membership card

| ID | Requirement |
|----|-------------|
| FR-2.1 | Section label: **MEMBERSHIP** |
| FR-2.2 | **Profile MetricBar** (distinct from Dashboard `ProgressSummaryRow`): label left, **value text right**, bar below |
| FR-2.3 | Monthly profiles bar: value = `{channel_profile_count} / {profile_allowance}` or profile count; percent = `profileUsed / profileAllowance` |
| FR-2.4 | Monthly songs bar: value = `{songs_remaining} remaining` when license has `songs_remaining`; else **"Not provided"**; percent = `songsUsed / songQuota` |
| FR-2.5 | SummaryField **Plan**: `me.plan_name` or **"No active plan"** |
| FR-2.6 | SummaryField **Credits balance**: license `wallet_balance` if set, else `me.credit_balance`; locale-formatted |
| FR-2.7 | SummaryField **Song quota**: license `monthly_song_quota` as string or **"Not provided"** |
| FR-2.8 | SummaryField **Plan expiry**: `formatOptional(license.expiration_date, 'Not provided')` |

**Bar colors:** profiles = emerald (`#34d399`), songs = sky (`#38bdf8`).

## FR-3 — Channel Profiles card

| ID | Requirement |
|----|-------------|
| FR-3.1 | Section label: **CHANNEL PROFILES** |
| FR-3.2 | Subtitle: **"Profiles available for generation and publication workflows."** |
| FR-3.3 | Allowance text top-right (same formula as membership profiles bar) |
| FR-3.4 | Table columns: Name, Run Prefix, Output resolution, Image mode, Visibility |
| FR-3.5 | Image mode from `profile_image_mode()` helper |
| FR-3.6 | Visibility from `profile_visibility()` helper |
| FR-3.7 | Loading + empty profiles: **"Loading profiles..."** / **"No channel profiles found yet."** |

## FR-4 — Activity card

| ID | Requirement |
|----|-------------|
| FR-4.1 | Section label: **ACTIVITY** |
| FR-4.2 | Songs generated, Images generated, Videos generated, Credits spent |
| FR-4.3 | Values use `formatCount` parity: locale number or **`--`** when null/loading |

---

# 7. State matrix

| State | Account | Membership | Profiles table | Activity |
|-------|---------|------------|----------------|----------|
| **Loading** | Loading copy | bars `--` | "Loading profiles..." | `--` |
| **Success** | Live data | Live bars + fields | Rows or empty message | Formatted counts |
| **Error** | Error email + Needs attention | `--` placeholders | "No channel profiles found yet." | `--` |

---

# 8. Test requirements

Port Electron `ProfilePage.test.tsx`:

| Test ID | Scenario | Assert |
|---------|----------|--------|
| T-1 | Loading | Account loading copy; profiles table "Loading profiles..."; activity `--` |
| T-2 | Error | Email error message; session "Needs attention"; empty profiles message |
| T-3 | Success | Song quota 120, "76 remaining", image mode, visibility public |
| T-4 | Empty profiles | "No channel profiles found yet." |
| T-5 | MetricBar | Label + value header row; bar percent from used/total |

---

# 9. Implementation structure

```text
features/profile/
  views/
    profile_view.py
  widgets/
    membership_metric_bar.py   ← Profile MetricBar (not Dashboard MetricBar)
    profile_cards.py           ← Account, Membership, ChannelProfiles, Activity

shared/
  workers/data_workers.py      ← DashboardOverviewWorker (reuse)
  widgets/metric_bar.py        ← SummaryField (reuse)
```

---

# 10. Electron source reference map

| Requirement area | Electron file |
|------------------|---------------|
| Full UI | `camxora/src/renderer/src/features/shell/ProfilePage.tsx` |
| Data hook | `camxora/src/renderer/src/features/shell/useDashboardOverviewQuery.ts` |
| Tests | `camxora/src/renderer/src/features/shell/ProfilePage.test.tsx` |
| Route meta | `camxora/src/renderer/src/features/shell/shellNavigation.ts` |

---

# 11. Definition of Done (100% checklist)

### Data & lifecycle
- [ ] **P-1** Reuse parallel fetch via `DashboardOverviewWorker`
- [ ] **P-2** Fetch on `activate_page()`; re-fetch on return; no polling
- [ ] **P-3** No Refresh button

### Account (FR-1)
- [ ] **P-4** Loading copy for name and email
- [ ] **P-5** Verification badge top-right inset
- [ ] **P-6** Error: unable to load email + Needs attention session

### Membership (FR-2)
- [ ] **P-7** Profile-style MetricBar (value right, bar below)
- [ ] **P-8** Songs bar shows "X remaining" / "Not provided" (not `remaining / quota`)
- [ ] **P-9** Plan, credits, song quota, plan expiry fields

### Channel Profiles (FR-3)
- [ ] **P-10** Subtitle copy exact
- [ ] **P-11** Five-column table with helpers
- [ ] **P-12** Loading and empty messages

### Activity (FR-4)
- [ ] **P-13** Four summary fields with `--` during load

### Quality
- [ ] **P-14** Tests T-1 through T-5 passing
- [ ] **P-15** Manual verify with live `platform_api` while logged in
- [x] **P-16** `02_IMPLEMENTATION_STATUS.md` updated: Profile ✅

---

# 12. Revision history

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-07-07 | AI + user | Initial complete requirements from Electron ProfilePage |
