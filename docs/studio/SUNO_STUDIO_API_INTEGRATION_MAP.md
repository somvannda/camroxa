# SUNO STUDIO API INTEGRATION MAP

Our Studio never calls the reference platform. The chain is:

```
Studio UI (camxora.com)
  → lib/studio-api.ts                (browser, relative /api/v3/*)
  → platform_api (FastAPI)           (auth, credits, ownership, shaping)
  → musicapi (Fastify)               (studio domain, provider adapter, storage)
  → MusicAPI provider adapter        (authorised generation provider)
```

Rule from `AGENTS.md`: browser code uses `lib/*-api.ts` helpers and the relative
`/api/v3/*` rewrite; the backend origin never appears in the browser.

## 1. Browser → platform API

All helpers live in `camxora.com/lib/studio-api.ts` and go through
`musicAuthFetch` (session cookie + refresh).

| Helper | Method + path | Returns |
|---|---|---|
| `listStudioProjects` | `GET /api/v3/web-music/studio/projects` | `{items,total}` |
| `getStudioProject` | `GET /api/v3/web-music/studio/projects/{id}` | project + `data` |
| `createStudioProject` | `POST /api/v3/web-music/studio/projects` | project |
| `updateStudioProject` | `PATCH /api/v3/web-music/studio/projects/{id}` | project |
| `deleteStudioProject` | `DELETE /api/v3/web-music/studio/projects/{id}` | 204 |
| `forkStudioProject` | `POST /api/v3/web-music/studio/projects/{id}/fork` | project |
| `listStudioProjectVersions` | `GET .../{id}/versions` | `{items,total}` |
| `createStudioProjectVersion` | `POST .../{id}/versions` | version |
| `restoreStudioProjectVersion` | `POST .../{id}/versions/{vid}/restore` | project |
| `createStudioProjectShare` | `POST .../{id}/shares` | share (token, path) |
| `listStudioProjectShares` | `GET .../{id}/shares` | `{items}` |
| `revokeStudioProjectShare` | `DELETE .../{id}/shares/{sid}` | 204 |
| `listStudioProjectComments` | `GET .../{id}/comments` | `{items}` |
| `getStudioSharedProject` | `GET /api/v3/web-music/studio/shares/{token}` | project + permission |
| `updateStudioSharedProject` | `PATCH /api/v3/web-music/studio/shares/{token}` | project (optimistic `expected_updated_at`) |
| `forkStudioSharedProject` | `POST .../shares/{token}/fork` | project |
| `waitStudioShareUpdate` | `GET .../shares/{token}/updates` | long-poll `{changed}` |
| `listStudioShareComments` / `addStudioShareComment` | `.../shares/{token}/comments` | comments |
| `touchStudioPresence` | `POST .../shares/{token}/presence` | `{items:presence}` |
| `uploadStudioAudio` | `POST /api/v3/web-music/studio/uploads` (multipart) | upload |
| `getStudioUploadUrl` | `GET .../uploads/{id}` | short-lived URL |
| `requestStudioStems` | `POST .../generations/{taskId}/stems` | operation |
| `requestStudioExtend` | `POST .../generations/{taskId}/extend` | operation |
| `requestStudioCover` | `POST .../generations/{taskId}/cover` | operation |
| `requestStudioAddVocals` | `POST .../generations/{taskId}/add-vocals` | operation |
| `requestStudioAddInstrumental` | `POST .../generations/{taskId}/add-instrumental` | operation |
| `requestStudioReplaceSection` | `POST .../generations/{taskId}/replace-section` | operation |
| `requestStudioRemaster` | `POST .../generations/{taskId}/remaster` | operation |
| `requestStudioCoverImage` | `POST .../generations/{taskId}/cover-image` | operation |
| `requestStudioMashup` | `POST /api/v3/web-music/studio/mashup` | operation |
| `requestStudioUploadExtend` / `…Cover` | `POST .../uploads/{id}/extend|c over` | operation |
| `getStudioOperation` | `GET .../studio/operations/{id}` | status + result clips |
| `getStudioLyrics` | `GET .../generations/{taskId}/lyrics?variant=` | lyrics + aligned words |
| `createStudioPersona` / `listStudioPersonas` | `.../personas` | persona |
| `getStudioPricing` | `GET .../studio/pricing` | `{edit,stems_2,stems_12}` |

## 2. Platform API → core API

`platform_api/routers/web_music.py` owns `/studio/*` (CRUD, versions, shares,
comments). It resolves the user, checks ownership, enforces plan limits and
credits, then calls musicapi. Musicapi's `/internal/studio/*` routes are service-only
(no public exposure) and are the only place that talks to a generation provider.

## 3. Core API (musicapi) studio surface

Owned by `musicapi/src/server.ts`:

| Route | Responsibility |
|---|---|
| `GET/POST /v1/studio/projects`, `PATCH/DELETE /v1/studio/projects/:id` | persistence |
| `POST /v1/studio/projects/:id/fork` | duplication |
| `POST /internal/studio/stems` | 2- or multi-stem separation job |
| `/internal/studio/extend`, `/cover`, `/add-vocals`, `/add-instrumental` | clip transforms |
| `/internal/studio/replace-section`, `/remaster`, `/mashup`, `/cover-image` | advanced transforms |
| `/internal/studio/upload-extend`, `/upload-cover` | upload transforms |
| `/internal/studio/render-state`, `/render-state-multitrack` | server-side render (paid) |
| `/internal/studio/projects/:id/save`, `.../version/:vid` | versioned document writes |
| `/internal/studio/lyrics/:clip_id` | lyric alignment proxy |
| `/internal/studio/persona` | persona creation |
| `/internal/studio/voice/*` | voice phrase / sample / verify |
| `/internal/studio/jobs/:id` | job polling |

## 4. Persistence model

`musicapi/migrations/0041_studio_projects.sql`:

```sql
studio_projects(id uuid pk, user_id uuid, title, major_version int,
                bpm int check 20..300, time_signature text,
                data jsonb, created_at, updated_at)
```

- `data` is the arrangement document (tracks, clips, automation, markers, mixer).
  It is versioned rather than normalised so the schema can evolve without breaking
  project ids or ownership. Normalisation is a later, internal change.
- Versions add immutable snapshots; restore rewrites `data` from a snapshot.
- Shares are separate rows keyed by an opaque token with permission + expiry.

## 5. Credits and cost

- Cost is read from the `pricing` table via the admin console, never hardcoded
  (`AGENTS.md`). `getStudioPricing` surfaces the current numbers to the UI before
  a paid action so the dialog can show the real charge.
- Every paid Studio action creates an operation row with `credits_charged`, so an
  audit can reconcile provider spend against user charges
  (`docs/suno-studio-operations-charge-report.md` in this repo predates the
  independent stack and is reference-only).

## 6. Failure contracts the UI must honour

| Status | Meaning | UI behaviour |
|---|---|---|
| 401 | Session expired | Redirect to login, preserve `next` |
| 403 | Not your project / link revoked | Terminal state, no retry loop |
| 404 | Unknown project/token | Terminal state with a route back |
| 409 | Version conflict (shared edit) | Offer reload / re-apply |
| 422 | Validation (bad range, empty lyrics) | Inline field error |
| 429 | Rate limited | Back off, show retry-after |
| 5xx | Upstream/provider failure | Error state + retry, never a silent no-op |

`readError()` in `lib/studio-api.ts` normalises `{error:{message}}` and `{detail}`
into one string; new endpoints must keep that envelope.

## 7. What we deliberately do not integrate

- The reference platform's Studio endpoints. They are documented in
  `docs/studio-1to1.md` purely as behavioural evidence (decision D-002). No code in
  the product path may call them.
- Any UI automation of the reference site.
