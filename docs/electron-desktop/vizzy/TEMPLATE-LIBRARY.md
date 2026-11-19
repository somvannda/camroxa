# Vizzy Template Library — All 91 Templates

> **Document ID:** CAMXORA-ED-VZ-LIB
> **Status:** Planning / port required
> **Source:** `G:\Developments\Rea\docs\reference-exports\creations\templates` + `moai-money.json`
> **Inventory:** [`library-inventory.csv`](library-inventory.csv) (90 rows + Moai Money)
> **Updated:** 2026-11-19

---

## 1. Scope

- **90 project exports + the Moai Money creation = 91 templates.**
- All 91 are part of the **product library**; none are hidden.
- Every template must:
  1. open in Vizzy,
  2. preview and render,
  3. save and reopen,
  4. export,
  5. be saveable as a **user video template** for the pipeline.
- A “featured” row may help discovery; it must not remove anything.

---

## 2. Inventory

| Measure | Value |
|---|---|
| Template JSON | 90 files, **14.2 MB** |
| Moai Money creation | 1 file, 29.9 KB |
| Ported media/assets | **244.8 MB** |
| Templates with asset folders | **87** |
| Templates missing an asset folder | **3** — `1735`, `code-286`, `nebula-staff` |
| Licensed audio | **Not copied**; the manifest names the track. The user supplies the run audio. |
| Largest asset sets | `rebecca-resonator` 36.5 MB, `retro` 25.3 MB, `killer-amv` 23.3 MB, `leafy-spectrum` 17.7 MB |
| Largest JSON | `asphalt` 390.4 KB, `nebula-staff` 183.4 KB, `blobs-cubiq` 179.6 KB |

The per-template table is in [`library-inventory.csv`](library-inventory.csv):
`Slug, JsonKB, AssetsMB, AssetFolder`.

### 2.1 Missing asset folders

`1735`, `code-286`, `nebula-staff` have no `public/creations/assets/templates/<slug>/`
folder in the Rea tree. Before porting:

- [ ] Confirm whether the project uses no local media (safe) or references an external asset
      that was not captured (blocked).
- [ ] If external, capture/replace the asset or mark the template `needs assets` in the
      library metadata.
- [ ] Add a regression project for each after resolution.

---

## 3. Delivery

| Option | Behaviour | Recommendation |
|---|---|---|
| **First-run pack** | Base installer is lean; the app installs all 91 into the library on first run | **Recommended** |
| **Bundle** | All 91 ship inside the installer | Acceptable if product accepts the size |
| **Lazy download** | Templates fetch on first open | Only if the pack becomes too large |

All three present **all 91 as available**. The difference is only when the bytes land on disk.

- [ ] Choose the delivery mode (default: first-run pack).
- [ ] Include a manifest with slug, display name, kind, thumbnail, asset list and licence.
- [ ] Verify the pack installs atomically and resumes on interruption.
- [ ] Keep a cache/repair action in Settings.

---

## 4. Licensing and provenance

The 91 are Vizzy editor exports (10 curated + 80 staff picks, retrieved 2026-10-27). They are
evidence/fixtures in Rea, not a redistribution licence.

Before public distribution:

- [ ] Record the licence/provenance for each template and its media.
- [ ] Exclude or replace any asset that cannot be cleared.
- [ ] Keep licensed audio out of the package; the user supplies their run audio.
- [ ] Publish a `NOTICE`/credits file for cleared templates.
- [ ] Do not ship the Rea `.shots` reference corpus.

---

## 5. Port acceptance per template

| ID | Check | Pass condition |
|---|---|---|
| LIB-01 | Open | Project loads with no console errors |
| LIB-02 | Preview | Canvas renders at the project resolution; no black frame |
| LIB-03 | Assets | All images/videos/fonts resolve locally |
| LIB-04 | Save/reopen | Semantically identical project JSON |
| LIB-05 | Export | Image export succeeds at 1080p |
| LIB-06 | Video template | “Save as video template” succeeds; bindings are detected/confirmable |
| LIB-07 | Pipeline | A fixture run renders the saved template; output matches the preview at tolerance |
| LIB-08 | Thumbnail | A real thumbnail exists and resolves |
| LIB-09 | Metadata | Name, slug, kind, compatibility and licence are present |

A template that fails a check is listed in the library report with the failing ID; it is not
silently hidden.

---

## 6. Test matrix

- **Per PR:** open/preview/save/reopen/export a rotating sample of 10 templates.
- **Nightly:** all 91 templates through LIB-01 … LIB-09.
- **Release:** all 91 + the saved-video-template path for every template that has bindable
  audio/background/logo/text.
- **Performance:** time-to-first-frame and memory for the four largest asset sets.
- **Determinism:** repeat preview/render for a subset; no wall-clock dependence.

---

## 7. Pipeline use

Every template can be opened, previewed and saved as a **user video template**:

1. open the template,
2. adjust it,
3. **Save as video template** — captures the exact project,
4. auto-detect bindings (audio, background, logo, title/artist/album, palette),
5. confirm or override,
6. select it in the profile Video/Reel picker.

The pipeline renders the saved project, not a re-creation. Templates without a suitable
placeholder still render as previewed with the run audio; bindings can be added later.

See [`../09-PIPELINE-AUTOMATION.md`](../09-PIPELINE-AUTOMATION.md) §3–§4 and
[`../PIPELINE-TEMPLATE-CONTRACT.md`](PIPELINE-TEMPLATE-CONTRACT.md).

---

## 8. Definition of Done

- [ ] All 91 templates have a resolved asset status.
- [ ] All 91 pass LIB-01 … LIB-09 or have a published failure reason.
- [ ] The delivery pack installs all 91 atomically.
- [ ] Licensing/asset clearance is recorded.
- [ ] The library shows all 91 with real thumbnails.
- [ ] At least the templates with suitable placeholders are proven as video templates.
- [ ] The CSV inventory and this document are updated with the final counts.
