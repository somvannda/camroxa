# YouTube publishing — end-to-end gap analysis (2026-11-07)

Written after the first real publishes (aoy5uK3dbOM, b9xjiqrKROM) and the failures found in
production. Each row is a defect or gap observed in the live flow, with its state.

## Defects found and fixed

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Upload never reached YouTube; jobs `UPLOAD_EXPIRED` | `CreatePublishJobRequest` had no `media_url` field, so the hosted URL was dropped and the server asked for a second upload | commit `eee78995` |
| 2 | `invalidTags` 400 | Publication keyword list sent verbatim; one invalid keyword fails the whole upload | tags not sent (`9ffd0492`) |
| 3 | Scheduled uploads 400 `Invalid value … "scheduled"` | YouTube accepts only public/unlisted/private; scheduling is `publishAt` | `e649522a` |
| 4 | Settings Connect did nothing | `_set_publish_waiting_ui` referenced a legacy button that may not exist | `e649522a` |
| 5 | Playlist dropdown empty | editable combo + permanent auth-failure flag + polling that re-bound the tab and cleared the list | `243df74e`, `81391d0f`, `2f9f4bb9` |
| 6 | Row showed `Publishing 38h` | elapsed measured from the oldest job, not the newest | `a98a4e95` |
| 7 | Row flipped to `Failed` right after "Video published" | aggregate counted every job for the slot; an older failure kept winning | `a98a4e95` |
| 8 | Retry refused with "already uploading" forever | a provider job stuck in `processing` blocked the slot | `810e103f`, `37556a60` (45 min) |
| 9 | Uploads silently used the legacy provider | native lookup exception or unconnected profile fell back to the provider, charging credits | `810e103f` (no fallback on error), `24a63ef0` (refuse when disconnected) |
| 10 | Credits charged for videos that never published | retirement marked the job failed without refunding | `d405ca27` |
| 11 | Same upload free on native, 5 credits on provider | native report path bypassed billing | `native_charge` (this change) |
| 12 | 6 uploads/day cap hit as raw provider errors | no quota accounting | `0becb20b` |

## Gaps still open

| # | Gap | Impact | Suggested fix |
|---|---|---|---|
| G1 | Refund requires the billing service; it cannot be invoked from a standalone script (dependency graph needs app state) | historical refunds are manual | add `POST /admin/publish/jobs/{id}/refund` using the existing service, plus a button in the admin console |
| G2 | Two historical jobs (`a653b2dc`, `c193659e`) were charged 80,000 units each and never published | 2 × refund owed | admin action once G1 exists |
| G3 | Native upload charges only on report; if the report call fails after a successful upload, the charge is skipped | lost revenue | charge server-side when the video id is recorded, retry on next report |
| G4 | No automatic retry for native uploads after a network drop | user must click again (resume works, so cheap) | reuse `publish_retry` policy in `YouTubeDirectUploadWorker` |
| G5 | Upload UI allows one transfer per profile; parallel merges queue but there is no visible queue | user may think nothing happened | show "1 queued" chip on the row |
| G6 | Thumbnail/playlist failures are logged as status text but not surfaced on the row | silent partial success | record warnings in `error_message` and show an ⚠ on the row |
| G7 | Installer requires UAC; automated installs fail silently | version drift between `dist` and `Program Files` | code-sign the installer, or ship portable zip + updater |
| G8 | `/download` still serves 1.4.9 | customers get an old build | publish 1.6.0 in Admin → Software updates |
| G9 | Release version churn (11 builds of 1.6.0) made "which binary is installed?" ambiguous | wasted debugging | include the commit sha in the shell footer |

## Missing end-to-end tests

The unit suites cover pieces, but nothing exercises the contract end to end. Recommended:

1. **Service-level E2E (fast, CI)**
   - connect → token → create upload session (mocked Google) → report → row shows `Published`
   - report twice → only one charge
   - stalled job retired → refund issued once
   - quota exhausted → token minting returns `YOUTUBE_QUOTA_REACHED` and no credit is taken
2. **Contract test against a fake Google server** (resumable protocol: 308 with `Range`, 200 with id, 400 mapping)
3. **Progress aggregation tests** for the matrix: failed→success, success→failed, pending→success, multiple jobs per slot
4. **Manual smoke script** the team runs before a release (documented checklist):
   - connect a fresh channel, disconnect, reconnect
   - playlist dropdown populated
   - upload 1 video, scheduled upload, cancel mid-transfer
   - quota limit lowered to see the refusal
   - refund visible in the wallet after a simulated stall

## Process gaps

- Every fix shipped as a rebuild of 1.6.0 with a new hash, so the version number stopped identifying
  the binary. Next: one build per release, sha in the footer, and a changelog entry per build.
- Provider and native paths coexisted too long; the provider caused three of the twelve defects above.
  Remove it once native is verified for every connected channel.
