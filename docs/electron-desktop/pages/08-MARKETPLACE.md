# 8. Marketplace

> **Feature prefix:** `MK-`
> **Route:** `/app/marketplace`
> **Phase:** P6
> **Sources of truth:**
> - `camxora_python/features/marketplace/views/marketplace_view.py`
> - `camxora_python/features/marketplace/views/marketplace_page_controller.py`
> - `camxora_python/features/marketplace/coordinator.py`
> - `camxora_python/features/marketplace/preview_loader.py`
> - `platform_api/routers/marketplace.py`

---

## 1. Purpose

Browse the curated template catalog, inspect a preview, and install a template locally so it
appears in the template picker without restarting the app.

Not a template editor and not the admin catalog manager. Template save/delete/protection
flows belong to the template-management surface (Vizzy / Settings), not this browse page.

**2.0.0 scope:** Video/Reel catalog items must be **Vizzy pipeline templates** to be usable.
The card and detail state the schema (`vizzy` / `legacy`). Old Camxora (`legacy`) templates
are **not supported in 2.0.0**: they may be visible for reference, but cannot be selected by
the pipeline, and the card says so. There is no converter in 2.0.0.

---

## 2. Data

| # | Method | Path | Purpose |
|---|---|---|---|
| 1 | GET | `/marketplace/catalog?page=&page_size=20&kind=&search=` | Catalog page |
| 2 | GET | `/marketplace/items/{id}/download` | Template ZIP (`template.json` + `manifest.json` + assets) |
| 3 | Local | `templates` store | Installed state and records |

The catalog item shape: `id, name, description, version, author, kind, tags, status, price,
preview_url, created_at`.

Page size: 20.

---

## 3. Layout

```
[ header: Marketplace + description ]
[ filter bar: All | Video | Reel    [search..............] ]
[ error banner / empty state / loading skeleton ]

┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ preview  │ │ preview  │ │ preview  │ │ preview  │
│ name     │ │ name     │ │ name     │ │ name     │
│ author   │ │ author   │ │ author   │ │ author   │
│ kind price│ │ ...     │ │ ...      │ │ ...      │
│ [Install]│ │ [Install]│ │ [Install]│ │ [Install]│
└──────────┘ └──────────┘ └──────────┘ └──────────┘

[ Previous ]  Page 1 of N  [ Next ]
```

Responsive columns: 4 at ≥ 1600, 3 at ≥ 1200, 2 at ≥ 900, 1 below.

---

## 4. Features

### 4.1 Catalog

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MK-01 | Initial load | Fetches page 1, kind = all, no search | P0 |
| MK-02 | Pagination | Page size 20; Previous/Next disabled at bounds | P0 |
| MK-03 | Page label | "Page {n} of {totalPages}" | P0 |
| MK-04 | Kind filter | All / Video / Reel; resets to page 1 | P0 |
| MK-05 | Search | Debounced 300 ms; resets to page 1; trims whitespace | P0 |
| MK-06 | Combined filters | Kind + search + page produce one request | P0 |
| MK-07 | Refresh | Re-fetch the current query without losing filters | P1 |
| MK-08 | Total count | Shows the total when the API provides it | P1 |

### 4.2 Cards

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MK-09 | Preview | 16:9 image, lazy-loaded, placeholder while loading | P0 |
| MK-10 | Preview failure | Neutral placeholder, no broken-image icon | P0 |
| MK-11 | Name | Truncated to two lines with a tooltip | P0 |
| MK-12 | Author | Displayed as a secondary line | P0 |
| MK-13 | Kind badge | Video / Reel, quiet text + dot, not a loud pill | P0 |
| MK-14 | Price | `Free` or formatted price | P0 |
| MK-15 | Description | One line with a tooltip for the full text | P1 |
| MK-16 | Version | Shown in the detail tooltip | P2 |
| MK-17 | Installed state | "Installed" label + check; button becomes Reinstall | P0 |
| MK-18 | Card click | Opens a detail panel/dialog with the full preview and metadata | P1 |

### 4.3 Install / reinstall

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MK-19 | Install | Downloads the ZIP, validates `template.json` + `manifest.json`, extracts to `templates/<uid>` | P0 |
| MK-20 | Progress | Card button shows "Installing…"; no duplicate install | P0 |
| MK-21 | Already installed | Prompts "This template is already installed. Do you want to reinstall it?" | P0 |
| MK-22 | Reinstall | Replaces content while preserving the local identity; no duplicate records | P0 |
| MK-23 | Success | Toast "Template installed"; card flips to Installed; template picker refreshes | P0 |
| MK-24 | Failure | Toast with a specific reason (network, corrupt zip, missing JSON, disk permission) | P0 |
| MK-25 | Corrupt zip | Rejects safely; no partial template left behind | P0 |
| MK-26 | Disk full | Readable error; no half-extracted directory | P0 |
| MK-27 | Post-install invalidation | Invalidates the template cache and refreshes Settings/Video/Vizzy pickers | P0 |
| MK-28 | Offline | Install disabled or fails with a clear offline message | P1 |
| MK-29 | Cancel | No cancel after download starts; the operation is short; document it | P2 |
| MK-30 | Licence/schema | Shows the licence and schema; `legacy` (old Camxora) is labelled **not supported in 2.0.0** | P0 |

### 4.4 States

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| MK-31 | Loading | Skeleton cards, not a blank grid | P0 |
| MK-32 | Empty | "No templates match this filter." + clear filters | P0 |
| MK-33 | Error | Error banner with retry; distinguish from empty | P0 |
| MK-34 | Offline | Offline banner; last catalog remains visible if cached | P1 |
| MK-35 | Image loading | Previews load in parallel with a concurrency cap (4) | P1 |

---

## 5. Tests

| ID | Scenario | Assert |
|---|---|---|
| MK-T1 | Initial catalog | One request, 20 items, page 1 |
| MK-T2 | Kind filter | `kind` param sent; page resets |
| MK-T3 | Search | Debounced; trimmed; page resets |
| MK-T4 | Pagination | Next/Previous boundaries |
| MK-T5 | Install | ZIP downloaded, files extracted, record stored |
| MK-T6 | Reinstall | Confirmation; record updated, not duplicated |
| MK-T7 | Corrupt zip | Error, no partial folder |
| MK-T8 | Post-install | Template picker refreshes without restart |
| MK-T9 | Empty vs error | Distinct UI |
| MK-T10 | Card state | Installed label persists after navigation |

---

## 6. Dependencies

- Template store in main (`templates` table + filesystem).
- Template manifest validation.
- Cache invalidation hooks for Settings, Vizzy and any template picker.
- Preview proxy/cache (no direct remote image loading in the renderer).

---

## 7. Definition of Done

- [ ] MK-01 … MK-35 implemented; all `P0` verified against sandbox.
- [ ] Installed Vizzy templates are immediately selectable.
- [ ] Install/reinstall verified with a real catalog item.
- [ ] A `legacy` template cannot be selected by the pipeline and shows the 2.0.0 policy.
- [ ] Corrupt/partial ZIP cannot leave a broken template.
- [ ] Picker refresh verified across pages.
- [ ] MK-T1 … MK-T10 pass.
- [ ] Visual baseline approved.
