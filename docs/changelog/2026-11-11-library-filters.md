# Library filters: enable what the corpus backs, explain what it does not

**Date:** 2026-11-11
**Branch:** `feat/library-filters` (stacked on `feat/studio-rebuild`, because the test harness and e2e fixture live there)
**Surfaces:** camxora.com (Library)
**Status:** implemented, gates green, not deployed

## Summary

The Library filter menu advertised twelve filters, but five were dead entries with no
explanation and one ("Voice") was disabled although the data existed. This change makes
the menu tell the truth: filters the corpus backs are live, filters it cannot back stay
visible with a written reason, and an active selection can be cleared in one click.

The reference lists ten clip filters (`filterCovers`, `filterUploadedClips`,
`filterPrivateClips`, `filterPublicClips`, `filterRemasterClips`, …). Our `suno_tasks`
corpus carries only `instrumental`, playable state and duration, so most of that set is
not expressible yet — recorded below rather than faked.

## Product impact

- **New: Vocals / Instrumental** — both live, driven by the generation's `instrumental`
  flag (the old "Voice" entry was disabled even though the data existed).
- **Renamed: "Downloads" → "Ready to play"** — the filter has always meant "the clip has
  playable audio", not "the user downloaded it"; the label now says so.
- **Blocked filters explain themselves** — `Public`, `Private`, `Uploads`, `Cover` and
  `Hide stems` are disabled with a `title`: songs stay private (publishing is not built),
  imported audio lives in Studio, covers are not attributed in the corpus, and the
  library lists songs rather than stems.
- **Clear filters** — appears once anything is selected, above a separator.
- Filtering behaviour is unchanged where it already worked (Liked, Disliked, Full song,
  Hide disliked): with nothing selected, every row still shows.

## Technical impact

- New `lib/library-filters.ts` is the single source of truth: `LIBRARY_FILTERS`
  (id, label, optional reason), `matchesLibraryFilters(row, active)`.
- `LibraryView` now derives its menu from that list and delegates row matching to the
  helper instead of five inline `filters.includes(...)` checks, so the menu and the
  matching cannot drift.
- Reasons render as the menu item's `title`; the disabled state comes from the same
  field, so a filter cannot be disabled without an explanation.

## Files touched

- `camxora.com/lib/library-filters.ts` (new)
- `camxora.com/components/LibraryView.tsx`
- `camxora.com/tests/library-filters.test.ts` (new, 8 unit tests)
- `camxora.com/tests/e2e/library-filters.spec.ts` (new)

## Migration/deploy

None. No schema, API or document change; the filters are evaluated client-side over the
already-fetched page of generations.

## Tests

| Layer | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run check:ui` | compliant |
| Vitest | **263 passed** (27 files; 8 new) |
| Playwright `library-filters.spec.ts` | **1 passed** — live filters enabled, `Public` disabled with its reason, selecting `Vocals` shows `Filters (1)`, clearing returns to `Filters (0)` |

The unit tests pin the semantics directly: preview-length clips fail "Full song",
unknown duration does not, instrumentals fail "Vocals", every active filter must pass, and
the blocked set must match exactly.

## Follow-ups

- **Public / Private** need a visibility field on `suno_tasks` plus a publish flow.
- **Covers / Remasters / Extensions** need origin attribution — `studio_operations` knows
  the operation type and source task, so a join that tags derived generations is the
  likely path.
- **Uploaded clips** need the Studio uploads listing inside the web Library (the backend
  endpoint already exists).
- **Hide stems** stays meaningless until stems appear in this library rather than Studio.
- This branch is stacked on `feat/studio-rebuild` only because the vitest config and the
  Playwright fixture live there; once the studio branch merges, the feature is
  independent.
