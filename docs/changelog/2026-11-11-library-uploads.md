# Library ▸ Uploads: imported audio is no longer Studio-only

**Date:** 2026-11-11
**Branch:** `feat/library-uploads`
**Surfaces:** camxora.com (Library)
**Status:** implemented, gates green, not deployed

## Summary

Audio imported into Studio was only visible inside the Studio library. The web Library now
has an **Uploads** tab that lists it, plays it through the shared player, and explains the
empty state when nothing has been imported. The backend listing
(`GET /api/v3/web-music/studio/uploads`) already existed; this is the missing surface.

The filter menu's disabled `Uploads` entry now says *"Uploaded audio has its own tab"*
instead of pointing at Studio, and the toolbar's `Uploads` quick pill navigates to the tab
(selecting the tab hides the song-only Filters/Sort controls so they cannot look inert).

## Product impact

- **Uploads tab** — filename, duration and a Play affordance per imported file; a search
  box filters by filename; the tab loads on first open rather than on page load.
- **Empty state** — "No uploads yet" with an `Open Studio` action, which is the real next
  step because importing happens there.
- **Errors are visible** — a failed listing shows the backend message in an alert rather
  than an empty list, matching how the rest of the Library reports failures.
- **Player integration** — playing an upload hands the signed URL to the same player used
  by songs, with the filename (minus extension) as the title and "Upload" as the artist.

## Technical impact

- `LibraryView` gains an `uploads` tab, a lazy fetch effect keyed on the tab, and
  `playUpload`, which maps `StudioUpload` onto the player's `Track`.
- The song toolbar's Filters/Sort/Liked/Public pills are wrapped out on this tab; only
  the search field remains, and it filters uploads locally.
- No API, schema or document change: `listStudioUploads` and the signed URL come from the
  existing Studio upload service.

## Files touched

- `camxora.com/components/LibraryView.tsx`
- `camxora.com/lib/library-filters.ts` (reason copy for the disabled Uploads filter)
- `camxora.com/tests/e2e/library-uploads.spec.ts` (new, 2 tests)

## Migration/deploy

None. Uploads are read-only here; nothing is written. The listing is empty until an
API with configured storage records an import (B-006/B-007), which is why the browser
tests mock the response.

## Tests

| Layer | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run check:ui` | compliant |
| Vitest | **263 passed** (28 files) |
| Playwright | **121 passed / 2 skipped** (the new spec covers listing + play, and the empty state with its `Open Studio` action) |

## Add to project (same day)

The tab's cards carry **Add to project**: a picker lists the user's Studio projects
(lazily, when the dialog opens), and choosing one appends the upload to the project's
first track at the end of that track's clips — or to a new `Uploads` track when the
project is empty. The write goes through the normal project PATCH with
`expected_updated_at`, so a project edited elsewhere surfaces as an error in the dialog
instead of being overwritten. `lib/studio-upload-place.ts` holds the pure placement
logic; the e2e proves a real document change (the clip lands at 4 s after the fixture
clip with its source URL).

## Follow-ups

- **Delete / rename uploads** — the upload service has no mutation endpoint yet.
- Once storage is configured, drop the mock and let the spec read a real imported file.
