# Video — Enterprise Architecture

> **Document ID:** CAMXORA-PAGE-09-VIDEO-ENTERPRISE  
> **Version:** 1.0.0  
> **Status:** Approved for planning (architecture contract)  
> **Parent:** [`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)  
> **Last updated:** 2026-07-08

---

# 1. Purpose

This document states **why the Video integration is designed for enterprise-grade delivery** — maintainable at scale, extensible for a marketplace, safe under load, and testable across Electron + Python without rework.

**Scope:** Desktop Camxora (single-tenant per machine today). “Enterprise” here means **production rigor**, not multi-tenant SaaS hosting.

---

# 2. Enterprise pillars (summary)

| Pillar | How Video achieves it |
|--------|-------------------------|
| **Separation of concerns** | 3 layers: product (Electron) · integration shell · GPU engine |
| **Contract-first integration** | Saved JSON schema, flat draft, renderer dict, golden fixtures |
| **Extensibility without rewrites** | Effect packs + catalog provider protocol (MP-1–MP-8) |
| **Fault isolation** | GPU export in subprocess; preview GL on dedicated widget thread rules |
| **Resource governance** | `ExportGate` global worker cap + spawn throttle (NVENC-safe) |
| **Data integrity** | Draft-before-save; domain-scoped merge; explicit save patch |
| **Versioning & compatibility** | Pack semver, `domainContractVersion`, `appVersionRange` |
| **Testability** | Golden JSON fixtures, skipped normalizer parity tests, domain unit tests |
| **Security boundaries** | Manifest validation before install; no UI → filesystem for packs |
| **Operational clarity** | `MG_EVENT` progress protocol; export queue state machine |

---

# 3. Layered architecture (bounded contexts)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PRODUCT CONTEXT (Electron parity)                                        │
│  UX · draft · inspectors · API · pipeline · effect pack product rules     │
│  Must not import ModernGL / spawn subprocesses directly from views        │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ typed contracts only
┌───────────────────────────────▼──────────────────────────────────────────┐
│  APPLICATION CONTEXT (camxora_python features/video)                      │
│  Coordinators orchestrate; services own rules; workers own side effects   │
│  TemplateNormalizer · EffectPackService · RenderSceneBuilder · ExportGate │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ DTOs: PreviewConfig, RenderRequest
┌───────────────────────────────▼──────────────────────────────────────────┐
│  RENDERING CONTEXT (visualizer/)                                          │
│  ModernGL · shaders · audio FFT · frame loop · CLI subprocess             │
│  No PySide6 imports · no PlatformApi · no draft store                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Enterprise rules for layers

| ID | Rule |
|----|------|
| **EA-1** | **Inward dependencies only** — `visualizer/` never imports `features/video/views/`. |
| **EA-2** | **Coordinators don’t render** — they call `PreviewBridge` / `ExportCoordinator`. |
| **EA-3** | **Services are stateless** — draft state lives in `DraftStore`; cache in `WorkspaceCache`. |
| **EA-4** | **Side effects at the edge** — disk, subprocess, and network only in services/workers. |
| **EA-5** | **Single schema authority** — Electron saved JSON; normalizer is the only Electron→GPU adapter. |

This matches how large desktop products split **UI**, **domain**, and **engine** so teams can evolve them independently.

---

# 4. Contract-first integration (enterprise integration pattern)

Cross-repo integration fails when teams share “tribal knowledge.” Video avoids that with **explicit contracts**:

| Contract | Artifact | Enforcement |
|----------|----------|---------------|
| Saved template shape | [`09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md) | Golden fixtures + round-trip with Electron |
| Draft ↔ saved mapping | Domain `*Settings.ts` ports | Unit tests per domain patch builder |
| Renderer input | `TemplateNormalizer.to_renderer_dict()` | 4 golden fixture sets + skipped parity tests |
| Export job | `RenderSceneRequest` | Port of `renderSceneRequest.ts` tests |
| Effect pack | `effectPackContracts` (Zod → Python) | Validate before install; reject unknown domains |
| Progress events | `MG_EVENT` JSON lines | Parser tests on worker |

**Enterprise benefit:** Electron, Python UI, and GPU teams can ship on different schedules if contracts + fixtures stay green.

---

# 5. Extensibility — marketplace-ready (not marketplace-implemented)

Phase 9 builds **interfaces**, not a storefront. That is the correct enterprise sequence: **stable core → pluggable extensions → remote catalog**.

```
                    ┌─────────────────────────┐
                    │ RemoteMarketplaceCatalog │  Phase N
                    │ Provider (future)        │
                    └───────────┬─────────────┘
                                │ implements
                    ┌───────────▼─────────────┐
                    │ EffectPackCatalogProvider│  Protocol (Phase 9c)
                    └───────────┬─────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
  LocalRegistryCatalog   EffectPackService      Domain inspectors
  (Phase 9c)             install/validate/apply  pack selectors
```

| Constraint | Enterprise rationale |
|------------|---------------------|
| **MP-1** Domain isolation | Third-party packs cannot corrupt unrelated template domains |
| **MP-2** Stable `packId` + semver | Auditable installs; rollback by version |
| **MP-3** Manifest validation | Fail closed — bad ZIP never enters registry |
| **MP-4** Registry abstraction | Swap storage (local → synced) without UI rewrite |
| **MP-5** Catalog provider protocol | Swap discovery (local → marketplace API) without UI rewrite |
| **MP-7** Draft-only apply | Users preview vendor content before persisting |
| **MP-8** Compatibility gates | Prevent broken packs across app upgrades |

---

# 6. Reliability & fault isolation

### 6.1 Subprocess export (crash containment)

| Property | Design |
|----------|--------|
| GPU work | Separate Python process (`visualizer/main.py`) |
| UI thread | Never blocked on encode; progress via async events |
| Failure mode | Subprocess exit → `RenderResult.error`; gate released in `finally` |
| Stop/cancel | Kill subprocess + drain queue; no zombie NVENC sessions |

**Enterprise benefit:** A shader bug or driver fault does not take down the main Camxora shell.

### 6.2 ExportGate (resource governance)

Ported from `python_app` after production incidents (NVENC session exhaustion, disk thrash on cold start):

| Control | Purpose |
|---------|---------|
| Global `acquire`/`release` | Honors `videoExportWorkers` across **all** pipeline channels |
| `throttle_spawn` | Staggers subprocess starts to warm OS file cache |
| Resizable limit | User preference changes without restart hazards |

### 6.3 Draft vs saved (consistency)

| Pattern | Enterprise rationale |
|---------|---------------------|
| Live draft for preview/export (manual) | User sees exactly what will render |
| Explicit Save | No accidental persistence of experiments |
| Domain-scoped dirty flags | Partial save UX; clear audit of what changed |
| Pipeline `draftSource: saved` | Batch automation uses stable template, not editor scratch |

---

# 7. Security & trust boundaries

Desktop enterprise still needs **supply-chain discipline** for installable effect packs:

| Boundary | Requirement |
|----------|-------------|
| Pack install | Validate manifest schema + domain + semver before extracting |
| Pack identity | `packId` regex + vendor field; no anonymous blobs |
| Filesystem | UI uses `EffectPackService`, not raw paths |
| Renderer | Consumes merged template JSON only — no arbitrary code execution from pack JSON |
| Future marketplace | Entitlement check in catalog provider; download URL from trusted API |

**Not in scope for Phase 9:** code-signed packs, sandboxed shader VMs. Manifest validation + domain isolation are the baseline enterprise controls.

---

# 8. Observability & operations

| Signal | Mechanism |
|--------|-----------|
| Export progress | `MG_EVENT` → export queue UI + workspace state |
| Export status | `VideoExportState` parity (running, branch, workers, merge) |
| Preview health | GL init failure → user-visible fallback message (no silent blank) |
| Diagnostics (9h) | Frame time, GPU memory hooks, recovery after context loss |

**Enterprise benefit:** Support can diagnose “export stuck at 0%” (historically NVENC/gate issues) from queue state + subprocess logs.

---

# 9. Test strategy (quality gates)

| Gate | When | Blocks merge if… |
|------|------|------------------|
| Fixture structure tests | Now | JSON fixtures malformed or missing aliases |
| TemplateNormalizer golden | Phase 9d | Output ≠ expected renderer dict |
| Draft merge tests | Phase 9a–9b | Domain patch clobbers other domains |
| Render scene builder | Phase 9f | Differs from Electron serializable request |
| Effect pack validation | Phase 9c | Invalid manifest installs |
| ExportGate stress | Phase 9f | Concurrency exceeds limit |
| Smoke: preview mount | Phase 9d | GL widget fails init |

Golden fixtures in [`tests/fixtures/video/`](../../tests/fixtures/video/) are the **long-lived contract** between product and engine teams.

---

# 10. Versioning & forward compatibility

| Layer | Strategy |
|-------|----------|
| Saved template JSON | Unknown keys preserved (normalizer N-2) |
| Effect packs | `domainContractVersion` + `appVersionRange` |
| Renderer | Reads subset of keys; normalizer fills defaults |
| Cross-app | Same `{userData}/video/` files open in Electron and Python |

**Enterprise benefit:** Upgrade app without mass-migrating user templates; packs declare compatibility explicitly.

---

# 11. Anti-patterns explicitly rejected

| Anti-pattern | Why rejected | Our approach |
|--------------|--------------|--------------|
| Monolithic video view calling GPU directly | Untestable, unreleasable | `PreviewBridge` + `visualizer/` |
| Hard-coded presets only | No marketplace path | Effect packs + registry |
| Per-channel export workers | Broke NVENC in production | Global `ExportGate` |
| Two template schemas on disk | Data loss between apps | Electron canonical JSON |
| WebGPU port to Python | High cost, duplicate engine | ModernGL from `python_app` |
| Silent pack overwrite on apply | User trust / support burden | Draft-only apply (MP-7) |
| `videoPy` duplicate route | Product confusion | Single `/app/video` |

---

# 12. Enterprise readiness checklist (Phase 9 sign-off)

Add to Definition of Done — architecture gates:

- [ ] **EA-1–EA-5** layer rules verified (no forbidden imports across boundaries)
- [ ] `TemplateNormalizer` passes all 4 golden fixture sets
- [ ] `EffectPackService` validates manifests fail-closed
- [ ] `EffectPackCatalogProvider` protocol documented; local provider implemented
- [ ] `ExportGate` enforces global worker limit under multi-channel pipeline test
- [ ] Export subprocess crash releases gate and surfaces error to UI
- [ ] Saved template round-trips Electron ↔ camxora_python without migration
- [ ] Domain merge tests prove MP-1 (pack apply does not clobber unrelated keys)
- [ ] Preview GL failure shows actionable error (not blank screen)
- [ ] No direct filesystem access from pack UI components

---

# 13. How this fits the wider Camxora Python app

Video follows the same enterprise patterns already used elsewhere in `camxora_python`:

| Pattern | Existing precedent | Video usage |
|---------|-------------------|-------------|
| Page = coordinator + view + workers | Music, Image, Progress | `VideoWorkspaceCoordinator` |
| Platform API parity | Dashboard, Settings | Video workspace routes |
| Workspace cache (TTL) | Dashboard, Settings | Template list, prefs |
| Shell background coordinators | Planned Phase 7 | `DesktopVideoPipelineCoordinator` |
| deep_blue QSS, native widgets | All shell pages | Video inspectors |

Video is the **most complex** page because it adds a **third-party-grade rendering engine** — the enterprise architecture is what keeps that complexity contained.

---

# 14. Related documents

- [`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md) — integration flows & module layout
- [`09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md) — field-level contracts
- [`09_VIDEO_REQUIREMENTS.md`](09_VIDEO_REQUIREMENTS.md) — UX, MP-1–MP-8, phased plan
- [`../../tests/fixtures/video/`](../../tests/fixtures/video/) — golden fixtures
