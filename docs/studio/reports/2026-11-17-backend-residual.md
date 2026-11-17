# W1 — backend residual verification after the refresh-backoff change

**Date:** 2026-11-17
**Workstream:** W1 (plan: `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` §2)
**Agent:** W1, branch `qa/backend-residual`, worktree
`C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-backend`
**Base:** `origin/main` @ `e04e0ac3` (`docs(studio): close the QA ledger with two recorded absences`)
**Change under test:** `68a67e07` — *"…stop refresh re-arming the mirror"*
(`platform_api/services/web_music_service.py`, 13 lines in `refresh_studio_project`)

**Method:** tests only. No server was started, no port bound, no deploy, no push, no
provider call. `G:\Developments\Projects\Camxora` was not touched. Working tree was left
clean (`git status --short` empty at the end).

**Toolchain:** Python 3.11.9 · pytest 8.4.2 · Node v24.13.0 · npm 11.6.2 ·
ruff 0.15.20 · black 23.11.0.

---

## 1. Summary

| # | Check | Command | Result | Duration |
|---|---|---|---|---|
| 1 | Full platform suite | `python -m pytest platform_api/tests -q` | **3,479 passed, 1 failed**, 2 warnings | **225.79 s** |
| 2 | `musicapi` unit suite | `npm run test:unit` (after `npm ci`) | **198 / 198 passed**, 0 failed | 0.52 s (1.2 s wall) |
| 3a | `ruff check` (change files) | see §4 | 23 errors — **identical to parent**, pre-existing | — |
| 3b | `black --check` (change files) | see §4 | would reformat `web_music_service.py` — **identical to parent** | — |
| 3c | Byte-compile | `python -m compileall -q platform_api` | exit 0 | 2.8 s |
| 4 | Shipped behaviour | read `refresh_studio_project` / `sync_studio_project` | refresh does **not** enqueue; sync still pushes | — |
| 5 | Collateral damage | grep platform tests | **1 stale test**, encodes the old re-arm | — |

**Headline:** counts 1, 2 and 3c meet D1's numbers, but the suite is **not green**: exactly
one pre-existing test still asserts the old refresh→enqueue behaviour and fails against the
shipped code. The product change is correct; the test is the residual.

---

## 2. Full platform suite — 3,479 passed / 1 failed

```
python -m pytest platform_api/tests -q
1 failed, 3479 passed, 2 warnings in 225.79s (0:03:45)
```

Collected: **3,480**. Passed: **3,479** (D1's floor of 3,479 passed is met numerically).
Failed: **1**.

### The failing test

`platform_api/tests/test_web_music_studio_sync.py::test_refresh_rearms_a_mirror_that_never_reached_musicapi`
(lines 83–100)

```
>       assert result["status"] == "synced"
E       AssertionError: assert 'pending' == 'synced'
E
E         - synced
E         + pending

platform_api\tests\test_web_music_studio_sync.py:98: AssertionError
```

Line 98 is the first assertion, so pytest stops there; line 100
(`assert actions == ["refresh", "enqueue", "refresh"]`) would fail as well — the shipped
code emits `["refresh"]` only.

### Proof the failure is caused by the change, not flakiness

Ran the same test file twice in this worktree, swapping only the service module:

| Service module | Result |
|---|---|
| `68a67e07^` (parent, re-arm still present) | `2 passed, 19 deselected` |
| `e04e0ac3` (shipped) | `1 failed, 1 passed, 19 deselected` |

The test file was not modified between runs. The tree was restored with
`git checkout -- platform_api/services/web_music_service.py`; `git status --short` is empty.

**Classification:** stale test, not a product defect and not a data-dependent/flaky failure.
Per instructions, no code or test was fixed.

### Warnings (not failures)

- `platform_api/services/free_monthly_grant.py:38` — `RuntimeWarning: coroutine
  'AsyncMockMixin._execute_mock_call' was never awaited` (`test_auth_router.py`).
- `platform_api/routers/ws.py:174` — same `RuntimeWarning` (`test_ws_router.py`).

Both are mock-hygiene warnings predating this change and do not affect outcomes.

---

## 3. `musicapi` unit suite — 198 / 198

`node_modules` was absent, so `npm ci` was run first (3 moderate advisories reported, no
build step needed). Then:

```
cd musicapi && npm run test:unit    # tsx test/run.ts
ℹ tests 198
ℹ pass 198
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ duration_ms 520.7153
```

Matches D1's expected 198. Wall time incl. Node startup: 1.2 s.

---

## 4. Lint and compile

```
ruff  check platform_api/services/web_music_service.py platform_api/tests/test_web_music_studio_contracts.py
black --check platform_api/services/web_music_service.py platform_api/tests/test_web_music_studio_contracts.py
python -m compileall -q platform_api
```

**Compile:** exit 0, no output, 2.8 s.

**Ruff:** `Found 23 errors.` (2 fixable) — 20 × `E402` module-level import not at top of file
(lines 47–110), 2 × `F401` unused import (`StreamingResponse`, `billing_today`),
1 × `F841` unused `last_error` (line 8840). The test file is clean.

**Black:** `would reformat platform_api/services/web_music_service.py`,
`1 file would be left unchanged` (the test file).

### These are baseline, not caused by the change

The repo has **no ruff or black configuration** — no `[tool.ruff]`/`[tool.black]` in
`platform_api/pyproject.toml`, no `ruff.toml`/`.ruff.toml`/`setup.cfg`/`tox.ini` — so both
tools run their defaults against a tree that has never been formatted to them. Re-running
both tools against the **parent revision** of the same two files (extracted with
`git show 68a67e07^:<path>`) gives the **same 23 ruff errors and the same single black
reformat**. The changed hunk (lines 3589–3615) is entirely inside the docstring and the
deleted block; no finding lands in it.

So D1's "ruff/black clean" clause is **unachievable at `origin/main` before this change**,
not a regression introduced by it. Reported as pre-existing debt, file-scoped to the two
files the change touched.

---

## 5. Code evidence — the shipped behaviour is the new behaviour (task 4)

### 5.1 `refresh_studio_project` — no `enqueue`

`platform_api/services/web_music_service.py:3589-3615` (shipped):

```python
3589:    async def refresh_studio_project(self, user_id: UUID, project_id: UUID) -> dict[str, Any]:
3590:        """Ask Suno whether it moved ahead; never touches the local document.
3591:
3592:        An unlinked project used to re-arm its mirror here. The editor calls this on open
3593:        and every 15 s, and an enqueue may wait up to 90 s on a slow provider — with a
3594:        mirror that cannot link, every poll became a fresh 40 s push and the API drowned
3595:        in its own retries (QA follow-up). Healing now belongs to saves (which queue the
3596:        mirror) and to the explicit Send to Suno Sync action.
3597:        """
3598:        project = await self._pool.fetchrow(
...
3605:        view = await self._studio_sync_request(str(user_id), str(project_id), "refresh")
3606:        return view or {
```

The only mirror call is `action="refresh"` (`:3605`). The removed block (`68a67e07^`
lines 3604–3608) called `_studio_sync_document` and posted `"enqueue"` then re-read
`"refresh"`. Neither call exists on this path any more, and `"refresh"` carries no document,
so the receiver cannot insert into the outbox.

### 5.2 `sync_studio_project` — still pushes the document

`platform_api/services/web_music_service.py:3617-3640` (shipped):

```python
3617:    async def sync_studio_project(self, user_id: UUID, project_id: UUID) -> dict[str, Any]:
...
3625:        document = self._studio_sync_document(row)
3626:        if document is None:
3627:            raise ValidationError("This project cannot be mirrored.")
...
3634:        result = await self._studio_sync_request(str(user_id), str(project_id), "sync", document)
```

**Correction to the task wording:** `sync_studio_project` does not hit the outbox
`enqueue` route; it sends `action="sync"` **with the document**, i.e. a synchronous push.
The durable outbox enqueue lives on the save path (`queue_studio_mirror` →
`_studio_enqueue_with_retry` → `action="enqueue"`,
`platform_api/services/web_music_service.py:3149-3175`, called from the save/update paths at
lines 2929, 3062, 3801, 3867, 4036). Both healing routes named in the new docstring
therefore still exist.

Receiver side confirms the split — `musicapi/src/server.ts`:

- `:8912-8923` `POST /internal/studio/projects/:id/sync` → `studioSync.syncProject(doc)`
  (synchronous push, body document required).
- `:8926-8936` `POST /internal/studio/projects/:id/enqueue` → `studioSync.enqueue(doc)`
  then `runDue(1)`; returns `202 {status:"queued"}`.
- `:8958-8970` `POST /internal/studio/projects/:id/refresh` → `studioSync.refresh(id, userId)`
  only; body is `{user_id}`, no document, **no enqueue**.

and `musicapi/src/sunoStudio.ts:711-724` is the only writer of `studio_suno_outbox`
(`INSERT … ON CONFLICT (local_project_id) DO UPDATE …`), reached solely from `enqueue`.

**Conclusion:** the shipped `refresh` is read-only; refresh no longer arms the mirror, on
either side of the wire. Task 4 confirmed, with the wording of 5.2 corrected above.

### 5.3 The change itself (`git show 68a67e07 -- platform_api/services/web_music_service.py`)

5 insertions, 8 deletions: docstring rewrite plus removal of the
`if view is None or not view.get("suno_project_id"): … "enqueue" …` block. No other
production code changed.

---

## 6. Collateral damage in the test suite (task 5)

Grepped `platform_api/tests` for `refresh_studio_project|rearm|re-arm|refresh.*enqueue|enqueue.*refresh`.

| Test | File:line | Encodes | Status |
|---|---|---|---|
| `test_refresh_rearms_a_mirror_that_never_reached_musicapi` | `test_web_music_studio_sync.py:83-100` | **Old** behaviour: `["refresh","enqueue","refresh"]`, expects `synced` | **FAILS** |
| `test_refresh_proxies_the_read_only_check` | `test_web_music_studio_sync.py:66-79` | New/neutral: one call, `"refresh"` | passes |
| `test_refresh_does_not_enqueue_an_unlinked_project` | `test_web_music_studio_contracts.py:320-344` | **New** behaviour (added by `68a67e07`) | passes |

**Yes — one test still encodes the old behaviour**, and it is the sole failure in §2. The
change added a new contract test in `test_web_music_studio_contracts.py` but did not retire
the older assertion in `test_web_music_studio_sync.py`, so the suite now contains two
contradictory contracts. No other test, fixture or helper assumes refresh re-arms the mirror.
The stale test is the only residual; retiring it (delete or rewrite to assert a single
`"refresh"` call) is a one-test fix owned by whoever lands the follow-up — **not applied
here**, per W1's no-fix instruction.

---

## 7. Verdict

```
D1: FAIL
```

Reason: the full `platform_api/tests` run is not green — **1 failed, 3,479 passed**
(`test_refresh_rearms_a_mirror_that_never_reached_musicapi`, assertion text in §2). Every
other D1 number is met: 3,479 passed (≥ 3,479), `musicapi` 198/198, `compileall` clean.
The ruff/black findings are bit-identical at the parent revision and therefore pre-existing
repository debt, not a product regression.

Scope of the failure is narrow and known: the product change is correct in the shipped code
(§5), and exactly one stale test contradicts it (§6). Fixing that test — not the service —
turns D1 green; no production-code change is implied by any failure in this run.

**Timestamps:** full suite 2026-11-17 08:06–08:09 +07:00; units and lint 08:09–08:12 +07:00.
**Branch commit:** see `git log -1 --format=%H` on `qa/backend-residual` (report-only commit,
not pushed).
