# 3. Profile

> **Feature prefix:** `PR-`
> **Route:** `/app/profile`
> **Phase:** P2
> **Sources of truth:**
> - `camxora_python/features/profile/views/profile_view.py`
> - `camxora_python/.docs/pages/04_PROFILE_REQUIREMENTS.md`

---

## 1. Purpose

A read-only account overview: signed-in user, plan and quotas, channel profiles, and
lifetime counters. It shares the Dashboard's aggregated fetch.

Not a profile editor, not a settings page, no refresh button, no polling.

---

## 2. Data

Same aggregated payload as Dashboard:

| # | Method | Path | Required | Failure |
|---|---|---|---|---|
| 1 | GET | `/users/me` | Yes | Whole fetch fails |
| 2 | GET | `/stats/dashboard` | Yes | Whole fetch fails |
| 3 | GET | `/profiles` | No | `[]` |
| 4 | GET | `/licenses/validate` | No | `null` |

---

## 3. Layout

```
Row 1 (~1.2fr + 0.8fr):  [ Account ]            [ Membership ]
Row 2 (~1.55fr + 0.75fr): [ Channel Profiles ]  [ Activity ]
```

---

## 4. Features

### 4.1 Account card

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PR-01 | Section label | "Account" (sentence case in the new design) | P0 |
| PR-02 | Display name | `me.display_name`; "Loading account..." before data | P0 |
| PR-03 | Email | `me.email`; "Loading account email..." before data | P0 |
| PR-04 | Error copy | Email becomes "Unable to load account information."; name stays loading | P0 |
| PR-05 | Verification badge | Verified / Pending from `me.email_confirmed`, inset top-right | P0 |
| PR-06 | User ID | `me.id` or `--` | P0 |
| PR-07 | Session | "Active" on success; "Needs attention" on error | P0 |
| PR-08 | Copy user ID | A copy action with a confirmation toast | P2 |

### 4.2 Membership card

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PR-09 | Section label | "Membership" | P0 |
| PR-10 | Profile metric bar | Label left, value right, bar below (distinct from Dashboard style) | P0 |
| PR-11 | Profiles bar | `{channel_profile_count} / {profile_allowance}`, percent used | P0 |
| PR-12 | Songs bar | `{songs_remaining} remaining` or "Not provided"; percent used | P0 |
| PR-13 | Plan field | `me.plan_name` or "No active plan" | P0 |
| PR-14 | Credits balance | License wallet preferred, else `me.credit_balance`, locale format | P0 |
| PR-15 | Song quota | License `monthly_song_quota` or "Not provided" | P0 |
| PR-16 | Plan expiry | `formatOptional(expiration_date, "Not provided")` | P0 |
| PR-17 | Bar colors | Profiles emerald, songs sky | P0 |
| PR-18 | Loading | Bars at 0, values `--` | P0 |

### 4.3 Channel profiles card

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PR-19 | Section label | "Channel Profiles" | P0 |
| PR-20 | Subtitle | "Profiles available for generation and publication workflows." | P0 |
| PR-21 | Allowance text | Same formula as the profiles bar, top-right | P0 |
| PR-22 | Table columns | Name, Run Prefix, Output Resolution, Image Mode, Visibility | P0 |
| PR-23 | Image mode helper | `bg_thumb` → "BG + TH", `bg_only` → "BG Only", `thumb_only` → "TH Only" | P0 |
| PR-24 | Visibility helper | Public/Unlisted/Private/Scheduled with correct labels | P0 |
| PR-25 | Loading | "Loading profiles..." | P0 |
| PR-26 | Empty | "No channel profiles found yet." | P0 |
| PR-27 | Row action | "Open in Settings" selects the profile in Settings | P1 |
| PR-28 | Sort | Default by name; column sort is optional | P2 |

### 4.4 Activity card

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PR-29 | Section label | "Activity" | P0 |
| PR-30 | Four counters | Songs, Images, Videos generated; Credits spent | P0 |
| PR-31 | Formatting | Locale number; `--` when null/loading | P0 |
| PR-32 | Comparison | Optional "vs last month" when the API provides it | P2 |

---

## 5. States

| State | Account | Membership | Profiles | Activity |
|---|---|---|---|---|
| Loading | Loading copy | `--` | "Loading profiles..." | `--` |
| Success | Live | Bars + fields | Rows or empty | Counters |
| Error | Error email + Needs attention | `--` | Empty message | `--` |

---

## 6. Tests

| ID | Scenario | Assert |
|---|---|---|
| PR-T1 | Loading | Loading copy; profiles loading; activity `--` |
| PR-T2 | Error | Error email; session "Needs attention"; empty profiles |
| PR-T3 | Success | Song quota 120, "76 remaining", image mode, visibility public |
| PR-T4 | Empty profiles | Empty message |
| PR-T5 | Metric bar | Header row + percent from used/total |

---

## 7. Definition of Done

- [ ] PR-01 … PR-32 implemented; all `P0` verified against sandbox.
- [ ] Loading, error and empty states verified.
- [ ] Profile table readable at 1280×800.
- [ ] PR-T1 … PR-T5 pass.
- [ ] Visual baseline approved.
