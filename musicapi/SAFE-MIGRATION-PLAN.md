# SAFE PROJECT MIGRATION PLAN — musicgenerator + SUNOAPI

> **Status**: DRAFT — awaiting user `PROCEED` confirmation.  
> **Operator rules**: INSPECT → REPORT → BACKUP/COPY → VERIFY → MIGRATE SUNOAPI → VERIFY → AUDIT PATHS → TEST → REPORT.  
> **STOP on any unexpected condition**: explain → wait for user decision.

---

## TABLE OF CONTENTS

1. [Operating Commitments (Non-Negotiable)](#1-operating-commitments-non-negotiable)
2. [Source, Destination, and Final Structure](#2-source-destination-and-final-structure)
3. [Phase 1 — Discovery (Read-Only)](#phase-1--discovery-read-only)
4. [Phase 2 — Safety Check](#phase-2--safety-check)
5. [Phase 3 — Create New musicgenerator Copy (robocopy)](#phase-3--create-new-musicgenerator-copy-robocopy)
6. [Phase 4 — Verify Git (Before Adding SUNOAPI)](#phase-4--verify-git-before-adding-sunoapi)
7. [Phase 5 — Add SUNOAPI](#phase-5--add-sunoapi)
8. [Phase 6 — Check Git Impact](#phase-6--check-git-impact)
9. [Phase 7 — Path and Configuration Audit](#phase-7--path-and-configuration-audit)
10. [Phase 8 — Project Dependency Audit](#phase-8--project-dependency-audit)
11. [Phase 9 — No-Refactoring Guard (Self-Audit)](#phase-9--no-refactoring-guard-self-audit)
12. [Phase 10 — Validation](#phase-10--validation)
13. [Phase 11 — Final Report Template](#phase-11--final-report-template)
14. [Alignment / Go Command](#14-alignment--go-command)

---

## 1. OPERATING COMMITMENTS (Non-Negotiable)

| # | Rule | Commitment |
|---|---|---|
| 1 | **Never delete first** | `D:\Development\Projects\Electron\musicgenerator` and `E:\Development\SunoAPI` remain as rollback backups for the entire session. No remove/delete command is issued against either unless and until the user explicitly approves after final verification. |
| 2 | **Never discard git changes** | Forbidden during this session: `git reset --hard`, `git clean -fd`, `git checkout -- .`, `git restore .`, or any operation (stash with drop, checkout with overwrite, etc.) that would discard uncommitted modifications or untracked files. |
| 3 | **Do not commit work** | No `git add .`, no `git commit`, no `git push`. Uncommitted work on `feature/desktop-studio-page` must remain uncommitted at migration end. |
| 4 | **Do not modify source** | `D:\Development\Projects\Electron\musicgenerator` is a PROTECTED backup. All operations are COPY to `E:`; never MOVE. |
| 5 | **Preserve Git exactly** | `.git` directory copied bit-for-bit. Branches, commits, remotes, tags, config, HEAD, index, reflogs, work-tree uncommitted state, untracked files all preserved. |
| 6 | **No nested git in SUNOAPI** | Before copy of SUNOAPI: if `E:\Development\SunoAPI\.git` exists → STOP + report. Final tree: one and only one `.git` at `E:\...\musicgenerator\.git`. |
| 7 | **Inspect before modify** | Before robocopy: enumerate sizes, large directories, symlinks/junctions, venvs, node_modules, build dirs, .env. Proposed exclusions (if any) are shown to user for explicit approval — never silently dropped. |
| 8 | **Verify every stage** | After each major operation: `git status`, `git branch --show-current`, `git rev-parse HEAD`, `git remote -v`, `git diff --stat`, `git ls-files --others --exclude-standard`. File/size counts where appropriate. Discrepancy → STOP. |
| 9 | **Secrets redacted** | `.env` / credential files: report filenames only, never contents. |
| 10 | **STOP protocol** | Pre-existing filled destination, nested `.git` found, disk insufficient, HEAD mismatch after copy, diff mismatch after copy, any locked/unreadable file, unexpected exit code → STOP + explain + wait. |
| 11 | **No refactoring** | Only changes required for the new location to function are made. No dependency upgrades, no renames, no import rewrites, no bug fixes, no architecture reorg, no UI changes. |

---

## 2. SOURCE, DESTINATION, AND FINAL STRUCTURE

### Source (Protected — read-only)

```
D:\Development\Projects\Electron\musicgenerator
  ├── .git\                  (full repo — MUST be preserved)
  └── ... existing project files, uncommitted mods, untracked files

E:\Development\SunoAPI
  └── ... SUNOAPI project files (currently NOT a git repo; verify)
```

### Destination (New primary)

```
E:\Development\Projects\Electron\musicgenerator
  ├── .git\                  (copied from D:)
  ├── existing musicgenerator project files (copied from D:)
  │   └── uncommitted changes + untracked files INTACT
  └── SUNOAPI\               (copied from E:\Development\SunoAPI)
      └── NO .git\ here
```

### Rollback backups (remain untouched)

```
D:\Development\Projects\Electron\musicgenerator   ← ORIGINAL, KEPT
E:\Development\SunoAPI                            ← ORIGINAL, KEPT
```

---

## PHASE 1 — DISCOVERY (Read-Only)

> **NO MODIFICATIONS.** All commands are read-only.

Inspect these three roots:

```
D:\Development\Projects\Electron\musicgenerator
E:\Development\SunoAPI
E:\Development\Projects\Electron
```

### Checklist

| # | Check | Method / Command |
|---|---|---|
| 1 | Path existence | `Test-Path` each |
| 2 | Destination pre-existence | `Test-Path E:\Development\Projects\Electron\musicgenerator`; if true → list contents recursively (top-level names + count) |
| 3 | SUNOAPI nested `.git` check | `Test-Path E:\Development\SunoAPI\.git` → if true: HARD STOP |
| 4 | Project sizes (including ignored) | PowerShell: `Get-ChildItem -Recurse -Force -ErrorAction SilentlyContinue \| Measure-Object -Property Length -Sum` for each source |
| 5 | Approximate file counts | `(Get-ChildItem -Recurse -Force -ErrorAction SilentlyContinue).Count` |
| 6 | Large generated directories (candidates for exclusion review) | Enumerate top-level `node_modules`, `.next`, `dist`, `build`, `out`, `coverage`, `.turbo`, `.cache`, `.parcel-cache`, `__pycache__`, `.venv`, `venv`, `.tox` + sizes. PROPOSE exclusions to user; do not act without approval. |
| 7 | Symlinks / NTFS junctions | `Get-ChildItem -Recurse -Force \| Where-Object { $_.Attributes -match "ReparsePoint" } \| Select-Object FullName, LinkType, Target` |
| 8 | Git branch | `git -C <src> branch --show-current` (expect: `feature/desktop-studio-page`) |
| 9 | Git HEAD SHA | `git -C <src> rev-parse HEAD` |
| 10 | Git remotes | `git -C <src> remote -v` |
| 11 | Git status (porcelain) | `git -C <src> status --porcelain`; count modified + untracked |
| 12 | Git submodules | `git -C <src> submodule status`; check for `.gitmodules` |
| 13 | Git LFS | Check for `.gitattributes` with `filter=lfs` lines; `git -C <src> lfs env` if binary present |
| 14 | Uncommitted diff stats | `git -C <src> diff --stat`; `git -C <src> diff --cached --stat` |
| 15 | Untracked files list | `git -C <src> ls-files --others --exclude-standard` (filenames) |
| 16 | Package manager signals | Presence of `package.json`, `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `bun.lockb`, `pnpm-workspace.yaml`, `turbo.json`, `lerna.json`, `vite.config.*`, `electron-builder.*` |
| 17 | Python signals | Presence of `.venv/`, `venv/`, `requirements.txt`, `pyproject.toml`, `poetry.lock`, `uv.lock`, `Pipfile` |
| 18 | Environment files (names only) | `Get-ChildItem -Recurse -Force -Filter .env* -ErrorAction SilentlyContinue \| Select -Expand FullName` (and similarly: `*.local`, `.pem`, `*.key`, `secrets.*`, `credentials.*`) — report names only |
| 19 | Hardcoded D: path refs | `Select-String -Path *.* -Pattern "D:\\\\Development\\\\Projects\\\\Electron\\\\musicgenerator" -Recurse -CaseSensitive:$false` (truncated preview; filenames + line counts) |
| 20 | Hardcoded old SUNOAPI path refs | `Select-String ... "E:\\\\Development\\\\SunoAPI"` |
| 21 | `.gitignore` contents | Read top-level `.gitignore` and any nested ones for patterns that might accidentally ignore `SUNOAPI/` |

### Deliverable at end of Phase 1

A concise report containing:

- Existence / non-existence of each path + destination pre-state
- Sizes and file counts (with and without candidate exclusion dirs)
- Git: branch, HEAD, remotes, submodules, LFS, modified count, untracked count
- Package manager + Python + env summary
- Symlink/junction inventory
- Proposed exclusion list (default: NONE — copy everything) with size impact, for user approval
- Absolute-path reference hit list (files only, no secrets)
- Any red/yellow flags

---

## PHASE 2 — SAFETY CHECK

### A. Destination pre-collision check

```
If (Test-Path E:\Development\Projects\Electron\musicgenerator):
  if (directory has children):
    → LIST CHILDREN (names + sizes)
    → STOP. DO NOT OVERWRITE. Report to user. Await explicit approval and strategy.
  else (empty dir):
    → Proceed, noting it pre-existed empty.
Else:
  → Parent check: ensure E:\Development\Projects\Electron exists; mkdir -p only up to that parent (not the project dir itself).
```

### B. Disk space check

```powershell
Get-PSDrive E | Select Name, Free, Used
```

```
Required = 1.3 × ( musicgenerator_size + sunoapi_size )
Available = Free bytes on E:

If Available < Required → STOP, report shortfall.
```

### C. Source sanity

- Both source paths still `Test-Path $true`.
- On musicgenerator source, re-run the 4 key git commands (branch, head, remote, status) to confirm source wasn't altered between phases.

### Output

GO / NO-GO decision with numbers. If GO, proceed to Phase 3.

---

## PHASE 3 — CREATE NEW MUSICGENERATOR COPY (robocopy)

```
Source : D:\Development\Projects\Electron\musicgenerator
Dest   : E:\Development\Projects\Electron\musicgenerator
```

### Base robocopy command (Windows-native, preserves metadata)

```powershell
robocopy `
  "D:\Development\Projects\Electron\musicgenerator" `
  "E:\Development\Projects\Electron\musicgenerator" `
  /E /COPYALL /DCOPY:DAT /R:2 /W:2 /ETA /XJ /NP `
  [ /XD node_modules .next dist build .turbo .cache .venv venv ... ]  ← ONLY IF APPROVED
```

- `/E` — include empty directories
- `/COPYALL` — copy all file info: Data, Attributes, Timestamps, Security (NTFS ACLs), Owner info, Auditing info
- `/DCOPY:DAT` — preserve directory Data, Attributes, Timestamps
- `/R:2 /W:2` — retry 2×, wait 2s between retries; any file still locked after that → STOP and report
- `/ETA` — show ETA
- `/XJ` — exclude junctions (prevents infinite recursion across reparse points)
- `/NP` — no progress percentage in log (cleaner)

### Optional exclusions (disabled by default — require user approval)

Proposed only if they exist AND their size makes copy prohibitively expensive or redundant. Reinstall post-migration:

| Dir | Reason | Alternative post-migration step |
|---|---|---|
| `node_modules/` | Generated by package manager | `pnpm install` or `npm install` |
| `.next/` | Next build cache | Rebuilt on `next dev/build` |
| `dist/`, `build/`, `out/` | Build output | Re-run build |
| `.turbo/`, `.cache/`, `.parcel-cache/` | Caches | Regenerated |
| `.venv/`, `venv/` | Python venv (rarely portable across drives anyway) | Recreate venv + reinstall deps |
| `coverage/` | Test coverage output | Regenerate from test run |

**DEFAULT STRATEGY**: copy all of the above. User must explicitly approve any `/XD` entries.

### Post-copy verification

1. **Robocopy exit code interpretation**
   - 0 — no files copied, no error (ok if we'd copied already; not ok first run)
   - 1 — files copied successfully → OK
   - 2 — extra files/dirs present in dest → review
   - ≥ 8 — errors occurred → STOP, review robocopy log

2. **Size + count match**

   ```powershell
   function Measure-Tree($p) {
     $items = Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
     [pscustomobject]@{
       Path  = $p
       Files = ($items | Where-Object { -not $_.PSIsContainer }).Count
       Dirs  = ($items | Where-Object {       $_.PSIsContainer }).Count
       Bytes = ($items | Measure-Object -Property Length -Sum).Sum
     }
   }
   Measure-Tree "D:\Development\Projects\Electron\musicgenerator"
   Measure-Tree "E:\Development\Projects\Electron\musicgenerator"
   ```

   Compare: Files count ± small tolerance due to junctions excluded; Bytes within ~0.1% or investigate.

3. **Critical artifacts present in dest**
   - `Test-Path E:\...\musicgenerator\.git` → true
   - `git -C E:\...\musicgenerator rev-parse --git-dir` → returns `.git`
   - Sample hidden: `.gitignore`, `.env*` if present in src → present in dest

4. **Log of copy retained** — capture robocopy output to `E:\Development\Projects\Electron\_robocopy-musicgenerator.log` (outside the repo, for reference).

---

## PHASE 4 — VERIFY GIT (BEFORE ADDING SUNOAPI)

All commands run with `-C` against new E: repo and D: source repo; results compared side by side.

```powershell
$src = "D:\Development\Projects\Electron\musicgenerator"
$dst = "E:\Development\Projects\Electron\musicgenerator"

function g($arg) { git -C $src $arg }
function G($arg) { git -C $dst $arg }
```

| # | Check (src vs dst) | Expected | If mismatch → |
|---|---|---|---|
| 1 | `git branch --show-current` | Exact match (default expectation: `feature/desktop-studio-page`) | STOP |
| 2 | `git rev-parse HEAD` | Exact 40-char SHA match | STOP |
| 3 | `git rev-parse --abbrev-ref HEAD` | Same as #1 | STOP |
| 4 | `git remote -v` | Line-by-line equality (order irrelevant) | STOP |
| 5 | `git diff --stat` | Same file names + hunks counts (order irrelevant) | STOP, inspect with `git diff --name-only` |
| 6 | `git diff --cached --stat` | Same on both (often empty) | STOP |
| 7 | `git ls-files --others --exclude-standard \| Sort-Object` | Byte-identical lists (after sort) | STOP, diff them |
| 8 | `git submodule status` | Same output or both empty | Investigate submodule .git dir resolution after drive move |
| 9 | `git status --porcelain` | Same status per tracked file; extra untracked lines only in dst if dest had some (shouldn't) | STOP if tracked-file status differs |
| 10 | `.git/config` file checksum | Core `[remote]`, `[branch]`, `[core]` sections logically same (file-level checksum may differ due to line endings — compare parsed `git config -l`) | STOP if remotes/branch configs differ |

Only after all 10 PASS → proceed to Phase 5.

---

## PHASE 5 — ADD SUNOAPI

### Pre-copy re-check (defense in depth)

```powershell
if (Test-Path "E:\Development\SunoAPI\.git") {
  Write-Error "HARD STOP: SUNOAPI source contains .git. Nested repo detected. Not copying. Await user decision."
  exit 99
}
```

If present: STOP. Report. Options for user will be:
- (a) delete SUNOAPI `.git` from source first,
- (b) copy with explicit `/XD .git`,
- (c) keep SUNOAPI separate (abort nesting).

### Copy

```
Source : E:\Development\SunoAPI
Dest   : E:\Development\Projects\Electron\musicgenerator\SUNOAPI
```

```powershell
robocopy `
  "E:\Development\SunoAPI" `
  "E:\Development\Projects\Electron\musicgenerator\SUNOAPI" `
  /E /COPYALL /DCOPY:DAT /R:2 /W:2 /ETA /XJ /NP /XD .git
```

Note: even though Phase 5 pre-check found no `.git`, we pass `/XD .git` defensively.

### Post-copy verification

1. Robocopy exit code ≤ 2 and no errors in log.
2. No nested `.git`:
   ```powershell
   -not (Test-Path "E:\...\musicgenerator\SUNOAPI\.git")   # MUST be True
   ```
3. Size/count compare:
   ```powershell
   Measure-Tree "E:\Development\SunoAPI"
   Measure-Tree "E:\Development\Projects\Electron\musicgenerator\SUNOAPI"
   ```
   (src count may be larger by 1 `.git` dir if it existed and was excluded; review accordingly.)
4. Sample known files present in dest SUNOAPI (names taken from Phase 1 inventory).

---

## PHASE 6 — CHECK GIT IMPACT

Run in new E: musicgenerator root:

```powershell
git -C "E:\...\musicgenerator" status --porcelain
```

Expectations:

- Every file under `SUNOAPI/` should be shown as `??` (untracked) OR not shown at all if already matched by an existing top-level `.gitignore` pattern.
- If NOT shown at all → investigate. Likely a too-broad rule (e.g., `**/SUNOAPI`, `*` with un ignore, etc.).

### Inspect ignore files

1. Read `E:\...\musicgenerator\.gitignore` top-level.
2. If exists, read `E:\...\musicgenerator\SUNOAPI\.gitignore` (note: it is inert for git tracking because SUNOAPI isn't a repo; but document it for inner tooling).
3. Run diagnostic to confirm which rules hit:
   ```powershell
   git -C "E:\...\musicgenerator" check-ignore -v SUNOAPI/package.json        (or any known SUNOAPI file)
   ```
   - If output blank → correctly untracked, not ignored.
   - If output names a pattern → decide whether pattern was intended or accidental.
     - *Accidental*: report and ask if `.gitignore` should be tuned (e.g., negation rule `!SUNOAPI/`). We do NOT edit `.gitignore` without your call because `.gitignore` is often committed and changing it creates a modification.

### Inventory env/credential files under SUNOAPI (names only)

```powershell
Get-ChildItem -LiteralPath "E:\...\musicgenerator\SUNOAPI" -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object Name -match "^(\.env|.*\.env\..*|secrets?|credentials?|\.pem|\.key|id_rsa)$" |
  Select-Object -Expand FullName
```

Report names only. Never paste contents.

---

## PHASE 7 — PATH AND CONFIGURATION AUDIT

### Greps run in `E:\...\musicgenerator` (exclude `.git/` from search)

```powershell
$patterns = @(
  "D:\\Development\\Projects\\Electron\\musicgenerator",
  "D:\\Development\\Projects\\Electron",
  "D:\\Development",
  "E:\\Development\\SunoAPI",
  "E:\\Development\\Projects\\Electron\\musicgenerator"   # catch premature self-reference expectations
)

foreach ($p in $patterns) {
  $esc = [regex]::Escape($p)
  $r   = [regex]::new($esc, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  Get-ChildItem -LiteralPath "E:\...\musicgenerator" -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object FullName -NotMatch "\\\.git(\b|\\)" |
    Select-String -Pattern $r |
    Select-Object Path, LineNumber, Line |
    Format-Table -Wrap -AutoSize
}
```

### For every hit, produce a row in the audit table:

| File (link) | Line | Match snippet (truncated, no secrets) | Purpose guess | Verdict |
|---|---|---|---|---|
| `electron-builder.yml:12` | 12 | `D:\Development\...\output` | Hardcoded build output dir | **CHANGE** → relative `dist/` or param |
| `.env:3` | 3 | `D:\...\db.sqlite` | Absolute DB path | **REVIEW** — env var; user may want to keep pointing D: or copy DB |
| `README.md:40` | 40 | `cd D:\...` | Docs-only instruction | **KEEP** — docs, not runtime |

Verdicts:
- **CHANGE** — required for new location to function correctly. I will edit, one file at a time, minimal relative/environment-variable-based change.
- **KEEP** — docs, comments, historical references, already parameterized elsewhere.
- **REVIEW** — unclear or user preference (e.g., pointer to data outside repo). I will flag and await.

**Blind search-and-replace across the repo is FORBIDDEN.**

---

## PHASE 8 — PROJECT DEPENDENCY AUDIT

### Read (not modify unless Phase 7 verdict = CHANGE)

#### musicgenerator root
- `package.json` → scripts, workspaces, `main`, `build.directories`, paths.
- `pnpm-workspace.yaml`, `turbo.json` → workspace roots. If SUNOAPI has its own `package.json`, consider: is it referenced by workspace? Default: KEEP as-is; workspace plumbing is out of scope unless required for paths.
- `vite.config.*`, `electron-builder.*`, `tsconfig*.json` → absolute `paths` / `include` / `exclude`.
- Dockerfile(s), docker-compose, CI configs (`.github/`, `.gitlab-ci.yml`, etc.) → mount points / absolute paths.

#### SUNOAPI nested
- `package.json` → scripts referencing absolute `E:\Development\SunoAPI` → candidate relative paths only if they break under new location; otherwise KEEP.
- `tsconfig`, Python configs, env files.

### Output

Summary: "SUNOAPI [was / was not] independently runnable (based on presence of scripts + config). N scripts referenced the old absolute path; M of them were adjusted per Phase 7 rules; the rest are docs/comments and were kept."

---

## PHASE 9 — NO-REFACTORING GUARD (Self-Audit)

Before proceeding to Validation, operator signs off on:

- [ ] No files/dirs renamed outside Phase 7 edits (if any).
- [ ] No dependency version changes (`package.json` diff limited to Phase 7 path strings only — and even that is unlikely).
- [ ] No `npm install` / `pnpm up` / `yarn` executed yet (will be user-call in Validation report at earliest).
- [ ] No application logic / UI / API changes.
- [ ] No import-path rewrites (only filesystem-path edits for runtime-location issues).
- [ ] Diff of entire tracked tree (src D: vs dst E:) limited to exactly Phase 7 edits + expected file-add of SUNOAPI directory tree as untracked.

If any violated: revert those changes before Phase 10.

---

## PHASE 10 — VALIDATION

### A. Git integrity (E: copy)

```powershell
$dst = "E:\Development\Projects\Electron\musicgenerator"

git -C $dst status --short
git -C $dst branch --show-current
git -C $dst rev-parse HEAD
git -C $dst remote -v
git -C $dst diff --stat
git -C $dst ls-files --others --exclude-standard | Measure-Object -Line
```

### B. Structural checklist

| # | Check | Tool | Pass? |
|---|---|---|---|
| 1 | musicgenerator exists at E: target, non-empty | `Test-Path + (dir).count` | ☐ |
| 2 | Branch matches expected (default: `feature/desktop-studio-page`) | `git branch --show-current` | ☐ |
| 3 | HEAD SHA byte-identical to D:-src | compare `rev-parse HEAD` | ☐ |
| 4 | `git diff --stat` file count == D:-src tracked-modified count | compare counts | ☐ |
| 5 | Untracked files = D-src untracked + SUNOAPI files (modulo .gitignore) | compute delta | ☐ |
| 6 | `SUNOAPI\` dir present in dest tree | `Test-Path` | ☐ |
| 7 | `SUNOAPI\.git` ABSENT | `-not (Test-Path ...\.git)` | ☐ |
| 8 | Parent `.git` present and `git` commands succeed | `git rev-parse --git-dir` | ☐ |
| 9 | No destructive git commands issued during session | Audit plan steps (self) | ☐ |
| 10 | D: source still fully intact | `Test-Path`, key file spot-check | ☐ |
| 11 | SUNOAPI source still fully intact | `Test-Path`, key file spot-check | ☐ |
| 12 | No remaining required-path TODOs still pointing to wrong drive (Phase 7 done) | re-grep patterns flagged CHANGE | ☐ |

### C. Lightweight validation (choose minimum-risk option)

Options (proposed to user; default = Option 1):

- **Option 1 — NO runtime validation (safe, no installs, no build artifacts).**  
  Confirm via checklist A + B only. This is the default for maximum preservation.
- **Option 2 — Static analysis only (no installs; only if tooling is already installed and cached).**  
  E.g., `tsc --noEmit -p` (only if `tsconfig` + global tsc or already-installed local).
- **Option 3 — Package install + smoke test (generates node_modules; only if excluded in Phase 3 or if user explicitly wants).**  
  Run only in E: copy; never touch D: source. User must approve.

---

## PHASE 11 — FINAL REPORT TEMPLATE

```
# Migration Result (FILLED VALUES — ACTUAL NUMBERS TBD)

OLD (kept as rollback backup):  D:\Development\Projects\Electron\musicgenerator
NEW (primary now):              E:\Development\Projects\Electron\musicgenerator
SUNOAPI nested at:              E:\Development\Projects\Electron\musicgenerator\SUNOAPI

Status: SUCCESS / PARTIAL / FAILED

## Git
- Branch:         feature/desktop-studio-page
- HEAD  (D-src):  <sha>
- HEAD  (E-new):  <sha>      (match: ✔ / ⚠)
- Remotes:
    origin  <url> (fetch)
    origin  <url> (push)

## Worktree (E-new vs D-src)
- Tracked modified  : <N_new>  vs  <N_src>   (match ✔ / diff ⚠)
- Untracked files   : <M_new>  vs  <M_src>   (expected increase by SUNOAPI tree)

## SUNOAPI
- Copied cleanly:         YES / NO
- Nested .git present:    NO          (REQUIRED)
- Visible as untracked:   YES / PARTIAL (reason: ___)
- Interaction with .gitignore:  none / ___
- .env/credential files (names only): .env, ___

## Path Audit — Action Taken
(Phase 7 CHANGE rows enumerated; REVIEW rows deferred to user)

## Path Audit — REMAINING TODOs (if any)
- [file:line] D:\... ref kept intentionally (docs/comments)
- [file:line] E:\Development\SunoAPI ref kept intentionally in ___
- [file:line] User decision pending on external-data pointer

## Warnings
- Robocopy locked-file list (if any, skipped + reported)
- Submodule .git dir path resolution after drive move (verify with `git submodule status`)
- LFS objects: if used, confirm `git lfs fsck` passes (optional, user-call)
- Symlinks/junctions skipped by /XJ (inventory recap)
- Node_modules / venvs: [ copied ][ excluded, user must reinstall ]

## Recommended Next Commands (RUN BY USER — I WILL NOT EXECUTE THESE)

1. cd E:\Development\Projects\Electron\musicgenerator
2. # (if excluded in Phase 3) reinstall deps:
3. #    pnpm install     # or npm install / yarn / bun install
4. git status
5. # <run your normal dev command here — choose for your project>
6. # Smoke-test that the app runs from E:.

ONLY AFTER YOU EXPLICITLY TELL ME the E: project is fully working end-to-end
will I provide safe-removal instructions for the D: backup and the original
E:\Development\SunoAPI directory.

## ROLLBACK OPTION (Always open)

If anything is wrong in E:, simply stop using it. The following are untouched:
  D:\Development\Projects\Electron\musicgenerator      (FULL ORIGINAL)
  E:\Development\SunoAPI                               (FULL ORIGINAL)
No commits, no pushes, no resets were performed during the entire migration.
Returning to D: restores prior state exactly.
```

---

## 14. ALIGNMENT / GO COMMAND

### To start

User replies with one of:

- **`PROCEED`** → execute **Phase 1 DISCOVERY** (read-only), then I report back before any mutation.
- **`PROCEED, EXCLUDE node_modules|.next|dist|build|.turbo|.cache|.venv|venv`** → same, with those exclusions applied to Phase 3 robocopy (and post-migration reinstall instructions will be added). Exclusion list must be explicitly approved — no implied defaults.
- **`AMEND: <specific change to plan>`** → plan updated, re-aligned, then re-confirm.

### What I will NOT do before explicit GO

- No robocopy / mkdir / file edits.
- No git commands that mutate trees (only read-only queries allowed in Phase 1).
- No deletions, ever, during this session regardless.

---

*Plan version: 1.0 — generated 2026-09-09 — bound by rules of master prompt.*
