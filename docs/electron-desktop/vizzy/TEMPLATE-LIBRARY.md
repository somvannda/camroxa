# Vizzy Template Library — All 91 Templates

> **Document ID:** CAMXORA-ED-VZ-LIB
> **Status:** Planning / port required
> **Source:** `G:\Developments\Rea\editor\public\creations\templates` (91 ported projects, local `/creations/assets` paths)
> **Raw exports:** `G:\Developments\Rea\docs\reference-exports\creations\templates` (pre-port, remote Firebase URLs)
> **Inventory:** [`library-inventory.csv`](library-inventory.csv) (91 rows)
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

Use the **editor tree**, not the raw reference exports: the editor copies have already been
rewritten to local `/creations/assets/templates/<slug>/…` paths.

| Measure | Value |
|---|---|
| Template projects | **91** — 90 slugs + `moai-money` |
| Template JSON | **14.4 MB** |
| Ported media/assets | **249.4 MB** |
| Templates with asset folders | **88** |
| Templates without an asset folder | **3** — `1735`, `code-286`, `nebula-staff` |
| Missing local asset references | **0** |
| Thumbnails | **91 / 91** |
| Remote audio references | 89 templates, 114 URLs (expected; licensed audio is not shipped) |
| Remote font references | **35 templates, 78 URLs** — must be vendored or mapped to a bundled fallback |
| Remote image references | **3 templates, 4 URLs** — must be vendored |
| Non-asset URL | `retro` keeps a GLSL-sandbox provenance string; not a fetch |

The per-template table is in [`library-inventory.csv`](library-inventory.csv):
`slug, json_kb, assets_mb, asset_folder, local_refs, missing_local, remote_audio, remote_font,
remote_image, remote_other, thumbnail`.

### 2.1 Asset gaps

- `1735` — no asset folder; references two remote custom fonts.
- `code-286` — no asset folder; references one remote custom font.
- `nebula-staff` — no asset folder; procedural/text only, safe.
- 35 templates reference Firebase/Google-hosted fonts. Offline render needs each font vendored
  into `assets/templates/<slug>/` (or a deliberate local substitute recorded in metadata).
- 3 templates reference remote images. Vendor them the same way.
- Audio stays out of the package unless its licence is cleared. The manifest names the original
  track; the pipeline binds the user's run audio.

Before porting:

- [ ] Vendor or substitute the 78 remote font URLs and 4 remote images.
- [ ] Re-run `npm run vizzy:audit` and require `remote_font = 0`, `remote_image = 0`,
      `missing_local = 0`.
- [ ] Keep `remote_audio` as metadata, not a render dependency.
- [ ] Add a regression project for `1735`, `code-286`, `nebula-staff`.

The audit script is `desktop-electron/scripts/audit-vizzy-library.mjs`. It reads
`CAMXORA_VIZZY_SOURCE` (or `G:/Developments/Rea/editor`) and rewrites the CSV:
`npm run vizzy:audit` reports status and `npm run vizzy:audit:strict` fails on remote
fonts/images, missing local files or missing thumbnails.

---

## 3. Delivery

The library is staged on disk before packaging:

```powershell
cd desktop-electron
npm run vizzy:library          # copy from CAMXORA_VIZZY_SOURCE (default G:/Developments/Rea/editor)
npm run vizzy:library:check    # manifest + file presence gate
```

- Output: `desktop-electron/vizzy-library/` (git-ignored), **263.9 MB**:
  91 project JSON files, 88 asset folders, 91 thumbnails and `manifest.json`.
- `manifest.json` rows: `slug, name, project, thumbnail, hasAssets, jsonBytes, assetBytes`.
- `electron-builder.yml` ships it as `extraResources/vizzy-library`; the app reads it from
  `process.resourcesPath` (packaged) or `desktop-electron/vizzy-library` (dev).
- The release build requires the staged library; `package:win` runs the check first.

| Option | Behaviour | Trade-off |
|---|---|---|
| **Bundle** (current staging) | All 91 ship inside the installer | Simple, fully offline; adds ~264 MB plus the 45 MB editor bundle |
| **First-run pack** | Lean installer; the app installs all 91 on first run | Needs hosting, a signed pack, resume/repair |
| **Lazy download** | Fetch each template on first open | Most complex; weakest offline story |

All three present **all 91 as available**. The current build bundles them; the installer size
budget in `02-MODULE-MAP.md` (≤220 MB) is exceeded and needs an explicit product decision
before release.

- [x] Stage the pack locally with a manifest.
- [x] Verify every manifest row resolves to a file.
- [ ] Decide bundle vs first-run pack before the 2.0.0 installer.
- [ ] Add a library repair/verify action in Settings.
- [ ] Add licence metadata per template (see §4).

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
