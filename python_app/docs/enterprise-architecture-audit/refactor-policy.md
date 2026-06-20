# Non-Breaking Refactor Policy

## Purpose
Define the rules all extraction work must follow so that decomposing `MainWindow` and reshaping the architecture never breaks existing user-facing behavior.

---

## Golden Rules

### Rule 1 — Visible behavior is immutable
Every extraction slice must preserve:
- what the user sees on screen
- what the user clicks and what happens next
- all current error messages, status text, and loading states
- keyboard shortcuts and mouse interactions
- page navigation order and transitions

If behavior changes, it is a regression, not a refactor.

### Rule 2 — Small validated slices only
- Extract one coherent cluster per slice
- Validate the slice before starting the next
- Never accumulate multiple untested moves
- Each slice should be reviewable in under 5 minutes

### Rule 3 — Delegate before deleting
- First: add the coordinator method
- Second: make the host method delegate to it
- Third: validate everything still works
- Only then: consider removing the old `*_impl` body if it is fully covered

### Rule 4 — Preserve public entrypoints
If a method is referenced by:
- a signal/slot connection
- a timer callback
- a view mixin host call
- an external module

Keep the public name stable. Delegate internally. Do not rename or remove until all callers are migrated.

### Rule 5 — No simultaneous behavior + structure changes
- One slice = either move logic OR change behavior, never both
- If you need to fix a bug, do it in a separate slice with its own validation
- If you need to improve UX, do it after the extraction is stable

---

## What Is Allowed in an Extraction Slice

### Safe operations
- Moving a coherent block of logic into a coordinator method
- Adding a thin delegator wrapper in `MainWindow`
- Adding new imports to support the coordinator
- Renaming internal/local variables within the moved block
- Adding logging/debug points if they do not change flow
- Extracting a helper function that is called from the moved block

### Unsafe operations (require separate slice)
- Changing the order of operations in a workflow
- Replacing a DB call with a different query
- Changing error message text or status text
- Removing a signal/slot connection
- Changing timer intervals or polling frequency
- Replacing one service call with another
- Modifying UI layout or widget structure
- Changing event payload shapes

---

## Pre-Slice Checklist

Before starting any extraction slice:

- [ ] Identify the exact code block to move (line numbers or method names)
- [ ] Confirm the block has a clear responsibility boundary
- [ ] List all callers of the code (signals, timers, view mixins, other hosts)
- [ ] Verify no other method outside the block depends on its internal variables
- [ ] Confirm the target coordinator/facade is the right home
- [ ] Write down the expected visible behavior that must not change

---

## During Slice Execution

- [ ] Create the coordinator method with the same logic
- [ ] Keep variable names consistent to reduce cognitive load
- [ ] Preserve all existing error handling and fallback paths
- [ ] Add the thin delegator in `MainWindow` that calls the coordinator
- [ ] Do not delete the old implementation yet — rename it to `*_impl` if needed
- [ ] Run `py_compile` on all changed files

---

## Post-Slice Validation

Immediately after each slice, verify:

### Compile check
- [ ] `python -m py_compile` passes on all changed files

### Smoke test (see `smoke-checklist.md` for full list)
- [ ] App launches without errors
- [ ] Page navigation works
- [ ] Feature-specific actions for the extracted area still work
- [ ] No new import errors or attribute errors in the console

### Code review
- [ ] The delegator in `MainWindow` is thin (1-3 lines)
- [ ] The coordinator method is self-contained
- [ ] No new forbidden dependency was introduced
- [ ] The old `*_impl` body is preserved and marked as transitional

---

## Transitional Code Policy

### When `*_impl` methods are acceptable
During extraction, keeping `*_impl` methods in `MainWindow` is acceptable when:
- They are called by view mixins that still reference `self`
- They contain logic not yet ready to move
- They serve as a fallback during migration

### When `*_impl` methods must be removed
`*_impl` methods should be cleaned up when:
- All callers have been migrated to the coordinator
- The coordinator fully covers the behavior
- A follow-up slice is planned specifically for cleanup

### Maximum transition window
No transitional method should survive more than 5 slices without a cleanup plan.

---

## Rollback Policy

If a slice causes a regression:

1. **Stop** — do not build on top of broken behavior
2. **Identify** — was it the move itself, or a missed caller?
3. **Revert** — restore the `*_impl` body to the delegator
4. **Diagnose** — understand what was missed
5. **Retry** — only after the root cause is understood

Never "fix forward" on top of a broken extraction.

---

## Architecture Drift Prevention

### After each slice, ask:
- Did this move reduce `MainWindow` responsibility, or just shuffle it?
- Did this add new dependencies that violate `dependency-rules.md`?
- Is the coordinator now a better home for this logic than the host?
- Would a new engineer find this logic in the right place?

### Red flags (stop and reconsider):
- The coordinator grew to 500+ lines in one slice
- You needed to pass `MainWindow` itself into the coordinator
- The slice touched 5+ unrelated files
- You changed event payload shapes or signal signatures
- You mixed two different feature responsibilities in one move

---

## Slice Ordering Principles

1. **Pure computation first** — helpers with zero UI/DB dependencies
2. **Read-only DB queries next** — methods that only read data
3. **Write operations after** — methods that persist state
4. **Workflow orchestration last** — methods that coordinate multiple steps
5. **Timer/thread ownership last** — lifecycle management is highest risk

This ordering minimizes the chance of breaking behavior at each step.
