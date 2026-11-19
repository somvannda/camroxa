# QA and Acceptance — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-04
> **Version:** 1.0.0
> **Status:** Draft
> **Release target:** Camxora Desktop **2.0.0**
> **Owner:** QA lead
> **Last updated:** 2026-11-19

---

## 1. Test strategy

```
                 ┌─────────────────────────────┐
                 │ Release acceptance (manual) │
                 ├─────────────────────────────┤
                 │ E2E (Playwright + Electron) │
                 ├─────────────────────────────┤
                 │ Integration (IPC + API mock)│
                 ├─────────────────────────────┤
                 │ Unit (Vitest, pure logic)   │
                 └─────────────────────────────┘
```

| Layer | Tool | What it proves |
|---|---|---|
| Unit | Vitest | Formatters, cost math, filters, grouping, reducers, schemas |
| Integration | Vitest + mocked IPC/API | Page data flow, state transitions, error handling |
| E2E | Playwright + Electron | Real window, real IPC, sandbox API, downloads/exports |
| Visual | Playwright screenshots + pixel diff | Layout and renderer parity |
| Manual | Checklist | Destructive actions, OS integration, installer, update |

---

## 2. Environments

| Environment | API | Data | Use |
|---|---|---|---|
| Unit | none | fixtures | CI on every commit |
| Integration | mocked | fixtures | CI on every commit |
| Sandbox | `api.sandbox.camxora.com/api/v3` | seeded sandbox account | E2E nightly + release |
| Local | `127.0.0.1:8000/api/v1` | local DB | development |
| Clean VM | sandbox | fresh user | installer/update/manual |

Rules:

- Never run destructive tests against production.
- Use a dedicated sandbox account and channel per test run.
- Clean up runs, jobs and downloaded files after the suite.
- Do not reuse another agent's Chrome/Electron profile.

---

## 3. CI gates

| Gate | Command | Blocks merge |
|---|---|---|
| Typecheck | `npm run typecheck` | Yes |
| Lint | `npm run lint` | Yes |
| Unit | `npm run test:unit` | Yes |
| OpenAPI drift | `npm run api:check` | Yes |
| Build | `npm run build` | Yes |
| E2E smoke | `npm run test:e2e:smoke` | Yes |
| Full E2E | `npm run test:e2e` | Nightly / release |
| Visual | `npm run test:visual` | Nightly / release |
| Audit | `npm audit --omit=dev` | Yes (allowlist) |
| License | `npm run license:check` | Yes |

---

## 4. Cross-cutting acceptance

### 4.1 States

Every page must prove:

- [ ] Loading
- [ ] Success with data
- [ ] Empty
- [ ] Error (required endpoint fails)
- [ ] Partial failure (optional endpoint fails)
- [ ] Stale data after a later failure
- [ ] Offline
- [ ] Retry/recovery

### 4.2 Forms

- [ ] Required fields block submit with inline errors.
- [ ] Server errors map to the right field or a page banner.
- [ ] Double submit is blocked.
- [ ] Unsaved changes prompt before navigation.
- [ ] Keyboard-only completion.

### 4.3 Tables

- [ ] Header, hover, selected, focus, disabled are distinct.
- [ ] Empty/loading rows preserve column widths.
- [ ] 200 rows without layout jank.
- [ ] Sort/filter stable across refresh.

### 4.4 Dialogs

- [ ] Focus trap and restore.
- [ ] Escape closes; destructive confirm defaults to cancel.
- [ ] Background scroll locked.
- [ ] Screen-reader labels.

---

## 5. Page acceptance suites

Each suite is a Playwright spec plus a manual checklist. The must-pass IDs are in the page
doc.

| Suite | Covers | Must pass |
|---|---|---|
| `auth.spec` | Login, register, Google, gates, session, update | LG-T1 … LG-T10 |
| `dashboard.spec` | KPIs, chart, quotas, activity, states | DB-T1 … DB-T8 |
| `profile.spec` | Account, membership, profiles, activity | PR-T1 … PR-T5 |
| `progress.spec` | Filters, stats, table, runtime, manual, downloads | PG-T1 … PG-T8 |
| `music.spec` | Strip, editor, draft, polish, pairs, costs, generate, history, downloads, automation hand-off | MU-T1 … MU-T14 |
| `image.spec` | Filters, grouping, retry, clear, previews, prompts | IM-T1 … IM-T10 |
| `marketplace.spec` | Catalog, filters, install, reinstall, errors | MK-T1 … MK-T10 |
| `settings.spec` | 8 tabs, CRUD, dirty, YouTube, diagnostics | ST-T1 … ST-T15 |
| `shell.spec` | Window, nav, session, IPC, coordinators, files, updates | SH-T1 … SH-T10 |
| `vizzy.spec` | Boot, project, media, export, crash, visual | VZ-T1 … VZ-T12, VZ-H1 … VZ-H12 |
| `pipeline.spec` | Template binding, headless render, merge, reel, upload, resume/retry | PL-T1 … PL-T10 |
| `vizzy-content.spec` | Every built-in pass/catalogue/particle/Butterchurn/template | VZ-T15, PL-41 … PL-45 |
| `vizzy-corpus.spec` | All 91 templates: open, preview, save, reopen, export, save as video template | VZ-T17/T18, PL-T11/T12 |

### 5.1 Pipeline acceptance suite

These tests protect the full-replacement decision (ADR-007). They are release blockers.

- [ ] A pipeline template validates and exposes the binding inspector.
- [ ] A run binds audio, background, logo, title/artist/album, palette and duration.
- [ ] Long-form 1080p renders a playable MP4 with audio.
- [ ] Reel 1080×1920 renders with the same bindings.
- [ ] Multiple songs merge into one validated MP4.
- [ ] Upload uses the profile publication fields and can be retried without re-rendering.
- [ ] Repeat renders match at the accepted tolerance.
- [ ] Restart resumes a queued job; cancel removes partial output.
- [ ] One failed song does not cancel the rest of the batch.
- [ ] Every Vizzy preset/catalogue/particle/Butterchurn/template applies, renders, saves and reloads.
- [ ] All 91 templates are available, open/preview/save/reopen/export, and can be saved as video templates.
- [ ] The pipeline output matches the saved preview.
- [ ] Auto-Upload remains disabled exactly as 1.7.1.
- [ ] The 91-template delivery pack and licensing record are complete.
- [ ] Old Camxora video templates are not selectable and show the no-migration policy.
- [ ] Music, Progress, Settings, Marketplace and Vizzy expose live controls with no dead ends.

### 5.2 Vizzy content parity suite

This protects “everything we have in Vizzy works as is.” It is a release blocker.

- [ ] 5 built-in spectrum presets apply and save.
- [ ] 32 spectrum catalogue presets load, render and apply.
- [ ] 18 particle presets apply; Default restores the shipped node; movement/reaction differs.
- [ ] 6 Butterchurn presets load and render.
- [ ] Community presets load (empty array is valid).
- [ ] User presets create/save/update/delete/import/export survive restart.
- [ ] Template modal/panel lists and applies templates.
- [ ] Preset thumbnails/images resolve (no broken images).
- [ ] Every node kind and effect used by the presets renders without console errors.
- [ ] Import/export preserves presets, template bindings and project settings.

---

## 6. API contract testing

1. Generate types from `openapi.json`.
2. Validate every response in development with a Zod schema derived from the same types.
3. Contract tests assert:
   - required fields exist;
   - enums match;
   - nullability is honoured;
   - error envelopes parse.
4. A schema change that breaks the client fails CI before a release.
5. Unknown fields are ignored; missing required fields are an error.

---

## 7. Vizzy acceptance

See [`vizzy/03-PARITY-HARNESS.md`](vizzy/03-PARITY-HARNESS.md). Minimum release set:

- 10 projects open, save, reopen;
- 5 render frames compared to the Rea baseline;
- image export at 1080p;
- video export at 720p and 1080p with audio;
- cancel export leaves no partial file;
- a forced view crash recovers;
- `crossOriginIsolated` and the threaded FFT tier;
- **pipeline**: long render, reel render, merge, upload hand-off, determinism, resume, retry
  and partial-batch behavior (PL-T1 … PL-T10).

---

## 8. Visual regression

| Surface | Size | Baseline |
|---|---|---|
| Shell + each page | 1440×900, 1920×1080 | 1 per page per size |
| Vizzy shell | 1440×900 | 1 |
| Vizzy stage | project-specific | 1 per fixture frame |
| Login | 1280×800, 1440×900 | 1 each |

Rules:

- Mask dynamic regions (timestamps, live values) with stable fixtures.
- Fonts must be loaded before capture.
- Disable animations for the capture.
- A diff above 0.1 % of pixels requires review; above 0.5 % fails unless approved.
- Store the diff image and the run id with the failure.

---

## 9. Performance testing

| Test | Method | Budget |
|---|---|---|
| Cold start | Timed to interactive | ≤ 6 s cold, ≤ 3.5 s warm |
| Route switch | Timed from click to first paint | ≤ 150 ms cached |
| Memory | 5 routes + 1 Vizzy project | ≤ 450 MB |
| Progress poll | 200 rows, 4 s interval | ≤ 50 ms reconcile |
| Music history | 500 rows filter | ≤ 100 ms |
| Image preview | 2 MP decode | ≤ 100 ms off-main |
| Vizzy stage | 1080p, mid GPU | 60 fps; 30 fps floor |
| Export | 120 frames 1080p | No regression > 20 % vs current baseline |
| Idle CPU | Shell, no page polling | ≤ 3 % |

Use Electron's `performance` APIs and a release build, not dev.

---

## 10. Security testing

- [ ] `contextIsolation`, `sandbox`, `nodeIntegration` verified at runtime.
- [ ] IPC fuzz: invalid types, oversized payloads, path traversal, null bytes.
- [ ] Navigation blocked to remote origins.
- [ ] `setWindowOpenHandler` opens external URLs in the browser.
- [ ] CSP has no violations in a normal session.
- [ ] Tokens absent from renderer memory dumps, logs, diagnostics and crash reports.
- [ ] Media protocol rejects outside-root paths and symlinks.
- [ ] FFmpeg args cannot inject shell commands.
- [ ] Update signature verification fails closed.
- [ ] Dependency audit has no unmitigated high/critical.
- [ ] Diagnostics redaction test with seeded secrets.
- [ ] Marketplace ZIP cannot write outside the template folder (`zip-slip`).

---

## 11. Accessibility testing

- [ ] axe scan on every page: 0 serious/critical.
- [ ] Keyboard-only: login, dashboard, music generate, image retry, settings save, Vizzy open/export.
- [ ] Focus visible on all interactive elements.
- [ ] Dialog focus trap/restore.
- [ ] Charts have a text/table alternative.
- [ ] Color is not the only status signal.
- [ ] Reduced motion honoured.
- [ ] Screen-reader smoke on Windows Narrator.

---

## 12. Release gates

A build is a release candidate only when:

- [ ] CI is green on the candidate commit.
- [ ] All page suites pass against sandbox.
- [ ] Vizzy 10-project matrix passes.
- [ ] Visual baselines approved.
- [ ] Security checklist complete; no P0/P1 findings.
- [ ] Accessibility checklist complete.
- [ ] Installer/update/uninstall verified on a clean VM.
- [ ] Diagnostics redaction verified.
- [ ] Pipeline acceptance suite passes (long, reel, merge, upload, determinism, resume, retry, partial batch).
- [ ] Vizzy content parity gate passes.
- [ ] All-91-template library gate passes, including save-as-video-template and preview parity.
- [ ] Auto-Upload behavior is unchanged from 1.7.1.
- [ ] Release notes, known limitations and the 1.7.1 → 2.0.0 compatibility statement published.
- [ ] Product/design/security sign-off recorded.

---

## 13. Defect severity

| Severity | Definition | Action |
|---|---|---|
| **P0** | Data loss, security breach, cannot start/login, corrupt export | Stop the release; fix immediately |
| **P1** | Core flow broken, wrong credits, run cannot complete | Fix before release |
| **P2** | Workaround exists, cosmetic in a primary flow | Fix in the next patch |
| **P3** | Minor polish, rare edge | Backlog |

Every bug report includes: build, page, steps, expected/actual, request id, screenshot, log
excerpt (redacted) and whether it reproduces on a clean profile.

---

## 14. Evidence format

For each phase sign-off, attach:

```
phase: P4
build: 1.0.0-beta.3 (sha)
api: sandbox
date: 2026-…
tester: …
suites: music.spec 13/13, visual 4/4
screenshots: artifacts/…
notes: …
```

No sign-off without a reproducible command and a log.
