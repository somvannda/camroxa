# Release 2.0.0 — Scope, Compatibility and Gates

> **Document ID:** CAMXORA-ED-08
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Release target:** **Camxora Desktop 2.0.0**
> **Owner:** Product + Delivery
> **Last updated:** 2026-11-19

---

## 1. What 2.0.0 is

Camxora Desktop 2.0.0 is the Electron rebuild of the desktop client with **Vizzy as the only
video engine**:

- the full Vizzy editor;
- pipeline template authoring;
- automatic video render, merge, reel and YouTube upload;
- the core desktop pages (Login, Dashboard, Profile, Progress, Music, Image, Marketplace,
  Settings, Shell).

The old Video and Merger pages are gone. Their capabilities live in Vizzy, Music, Progress,
Settings and the pipeline service.

---

## 2. Version policy

- The product version is **2.0.0**.
- Every phase in this pack ships into 2.0.0. Do not bump the version per phase.
- Internal build metadata may increment: `2.0.0+20261119.1`, `2.0.0+20261120.2`.
- Patch releases (2.0.x) are only for defects, security and platform compatibility; they are
  not part of this plan.
- There is no 2.1 deferral in this plan.

---

## 3. 2.0.0 scope

### 3.1 In scope

| Surface | Included |
|---|---|
| Login / auth / onboarding / update | Email/password, Google, remember me, recent accounts, gates, startup, mandatory update |
| Shell | Window chrome, sidebar, header, footer, command palette, notifications, background coordinators |
| Dashboard | KPIs, weekly chart, quotas, recent activity |
| Profile | Account, membership, channel profiles, activity |
| Progress | Filters, stats, operational table, live render/merge stages, manual upload, manual recovery, live download queue |
| Music | Composer, draft/polish, channel pairs, automation toggles, credits, generate, history, background downloads |
| Image | Queue, previews, retry, clear, prompt autosave |
| Vizzy | Full editor, project I/O, media, manual export, pipeline template authoring, Renders panel |
| Vizzy content | All built-in presets, spectrum catalogue, particle presets, Butterchurn presets, community/user presets and templates work as-is |
| Vizzy templates | All 91 templates are available to users, open/preview/save/reopen/export, and can be saved as video templates; staged in a reproducible library and currently bundled (installer-size decision pending) |
| Pipeline | Single-template and offscreen batch render/merge are live; reel, retry and Progress are wired. Manual YouTube upload is **not yet ported** and is a release blocker (Auto-Upload itself stays disabled) |
| Marketplace | Catalog, filters, search, pagination, install/reinstall, pipeline template kind/compatibility |
| Settings | Profiles, publication, preferences, descriptions, structures, moods, pools, Suno, template pickers |
| Packaging | Signed Windows installer, auto-update, uninstall |

### 3.2 Out of scope as separate pages

Workflow, Create, Video, Merger, Studio, raw Diagnostics console, admin portal, public
website, streaming portal, macOS/Linux release, UI localisation. The **capabilities** of the
Video and Merger pages are included through the pipeline, not as pages.

### 3.3 Deferred beyond 2.0.0 (not release blockers)

These are enhancements, not missing 1.7.1 capabilities:

- multi-GPU / worker count above 2 for 1080p;
- cloud project sync;
- collaborative editing;
- template marketplace ratings/comments;
- additional codecs/hardware encoders beyond the validated ladder;
- macOS/Linux installers.

---

## 4. Compatibility with 1.7.1

2.0.0 is a new desktop client. It keeps the backend contract and user data, and it replaces
the Video/Merger pages with the Vizzy pipeline.

| 1.7.1 capability | 2.0.0 behaviour | Notes |
|---|---|---|
| Email/password + Google login | Same | Session storage moves to the OS keystore; sign in once |
| Dashboard / Profile / Progress / Music / Image / Marketplace / Settings | Same feature set (see page docs) | Visual refresh; data contract unchanged |
| Video page | **Removed**; Vizzy is the editor and pipeline surface | No dead route |
| Merger page | **Removed**; merge is a pipeline stage | Progress shows it |
| Auto-Video / Auto-Merge / Auto-Reel | **Live** on the Vizzy renderer | Same toggles, now real |
| Auto-Upload | **Unchanged from 1.7.1** | Toggle stays disabled; the manual upload action still has to be ported |
| Converter/Merge/YouTube stages | **Render/merge live; upload pending** | Progress shows render/merge; manual upload port is a release blocker |
| Profile Video/Reel templates | **Live** Vizzy pipeline template pickers | Validated on save |
| Marketplace Video/Reel templates | **Live** for Vizzy templates; old Camxora templates are not selectable | Clear policy label |
| Manual video export | **Vizzy native export** | Same project and renderer; FFmpeg handles merge/reel |
| Local paths/settings | Migration wizard or documented manual setup | Back up before first run |
| Old Camxora video templates | **Not migrated in 2.0.0** | Users who need them stay on 1.7.x or re-author later |

### 4.1 Old Camxora video templates

The 1.7.1 Camxora video template schema is a parameter file for the Python visualizer, not a
Vizzy project. **2.0.0 does not migrate it.**

- Old templates are not selectable by the pipeline and are not shown as usable templates.
- There is no converter, re-author pass or Python sidecar in 2.0.0.
- A user who needs an old template stays on 1.7.x or re-authors it in Vizzy later.
- The UI and release notes state the policy; no dead picker or broken template is shown.

**Vizzy-native templates only.** The pipeline requires a Vizzy pipeline template
(`template.json` + `pipeline.json`). All existing Vizzy presets, catalogues, particle presets,
Butterchurn presets and templates must work as-is.

### 4.2 Release note copy (draft)

> Camxora Desktop 2.0.0 is a full rebuild. The Video and Merger pages are replaced by Vizzy
> and its render pipeline. Existing automation now runs on Vizzy: automatic video, merge,
> reel and YouTube upload, using Vizzy pipeline templates. Old Camxora video templates are
> **not migrated in 2.0.0**; users who depend on them should stay on 1.7.x or re-author them
> in Vizzy later. Back up your local settings before the first launch.

---

## 5. Release gates

A 2.0.0 candidate ships only when:

### 5.1 Current evidence (2026-11-19)

- 16 E2E suites pass, including login/gates, all pages, downloads, Vizzy host, export,
  save/preview/render, templates, library and batch.
- 249 unit tests pass; `api:check` and `npm audit --omit=dev` pass.
- All 91 templates import through the real editor (0 failures, 0 skipped) and one exports to a
  validated MP4.
- A real library template (`candy-wave`) completed save → render at 640×360/60 with a run track.
- Old Camxora templates are refused; Auto-Upload remains disabled and is E2E-pinned.
- Offscreen batch rendering runs without `/vizzy` open: two songs rendered in 4.8–5.9 s at
  320×180/2 s, merged to a 4.0 s/120-frame MP4; cancel left no partial file and retry reran only
  the cancelled row.
- Reel branch verified: a 1080×1920/30 reel template rendered a 1080×1920 H.264/AAC MP4
  (1.97 s) through the same offscreen queue.
- All eight Settings tabs are live and covered by the settings suite (prompt CRUD, pools pager,
  Suno bounds, deterministic save-all).
- The download coordinator writes exact-byte files to the device root: dedupe, 3-attempt retry,
  cancel with no `.part`, traversal rejection and completion sync are covered by the downloads E2E.

Still open for release: manual YouTube upload port, installer size and asset clearance, a
clean-VM gate, accessibility and signing.

### 5.2 Gate checklist

- [ ] Every page doc has all `P0` features `☑`.
- [ ] Page acceptance suites pass on a clean Windows VM against sandbox.
- [ ] Vizzy 10-project matrix and manual export matrix pass.
- [ ] Pipeline acceptance passes: long render, reel, merge, upload, determinism, resume,
      retry, partial batch.
- [ ] Vizzy content parity gate passes (built-in presets, catalogue, particle, Butterchurn,
      community/user presets, templates).
- [ ] All 91 templates are available, pass open/preview/save/reopen/export, and can be saved
      as video templates.
- [ ] Licensing/asset clearance for the 91-template pack is recorded before public release.
- [ ] Old Camxora video templates are not selectable; the policy is published.
- [ ] Manual vs pipeline parity passes on the same Vizzy template/inputs.
- [ ] Security review: no P0/P1 findings; tokens absent from logs/diagnostics.
- [ ] Accessibility: WCAG 2.2 AA on all pages.
- [ ] Performance budgets met or deviations approved.
- [ ] Installer signed; update and rollback verified.
- [ ] Diagnostics redaction verified.
- [ ] 1.7.1 → 2.0.0 compatibility statement published in-app and in the release notes.
- [ ] Product/design/security sign-off.

---

## 6. Rollout and rollback

1. Build a signed Windows NSIS installer with version `2.0.0`.
2. Publish to the beta channel first; collect crash/diagnostics data.
3. Keep Auto-Upload exactly as 1.7.1 (disabled toggle); verify the existing publication/manual
   upload flow instead.
4. Promote to stable after the gate and a 7-day beta window.
5. Keep 1.7.x available for users who hit a migration blocker.
6. If a P0 is found, withdraw the 2.0.0 manifest and restore the previous feed; the updater
   must not force the withdrawn build.
7. The local database migration is forward-only; the installer creates a backup before the
   first run.

---

## 7. Support notes

- **"Where is the Video page?"** → Replaced by Vizzy. The editor and the Renders panel are
  in the Vizzy route; per-run automation is in Music/Progress.
- **"Where are the 91 templates?"** → In the Vizzy template library (Templates → Library).
  All 91 are available. Open one, preview it, and save it as your video template. The current
  build bundles the staged library; a first-run pack remains a packaging option.
- **"Where is my old Camxora template?"** → Old templates are not migrated in 2.0.0. Use
  1.7.x if you need it, or re-author it in Vizzy. The pipeline uses Vizzy templates only.
- **"Auto-Upload is still disabled."** → That is unchanged from 1.7.1. Upload through the
  existing publication/manual flow; the render itself is unaffected.
- **"A render failed."** → Open Progress → row detail. Retry the failed stage; completed
  outputs are kept.
- **"Can I stay on 1.7.1?"** → Yes, until the migration blocker is resolved. 1.7.x remains
  available.

---

## 8. What comes after 2.0.0

2.0.0 closes the replacement. Future work is enhancement, not deferred capability:

- multi-GPU and higher worker counts;
- cloud project sync and collaboration;
- additional codecs/hardware encoders;
- macOS/Linux installers;
- template marketplace ratings, comments and richer metadata;
- an optional legacy Camxora template migration/re-authoring program, if product decides it
  is worth doing later;
- performance tuning from real batch telemetry.

Any 2.0.x release is a patch; any feature release is a new product decision.
