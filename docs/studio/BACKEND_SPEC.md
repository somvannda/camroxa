# BACKEND SPEC — five work items

Design-only. No code until approved. Each item lists: what the reference proves, our
target shape, schema, routes, states, and acceptance.

Reference evidence: `reference/endpoint-inventory.json` (81 studio endpoints),
spec §31 (clip menu), §33 (edit chain), §25 (versions), §36 (`CTRL S` save).

---

## B1. Normalized operation record

**Problem.** Each verb (stems, extend, cover, remaster, mashup, replace-section,
add-vocals, add-instrumental, cover-image, upload-extend, upload-cover, persona,
render) has its own route, its own result shape, and its own frontend plumbing.

**Target.**
```
op = {
  id, user_id, project_id?, kind, target: {type: "clip"|"upload"|"project", id},
  params: jsonb,            // verb-specific, validated per kind
  state: queued|running|succeeded|failed|cancelled,
  progress: 0..100?, error_code?, error_message?,
  result: jsonb?,           // clips[], artifact ids, persona id, render id
  credits_charged int, credits_refunded int,
  provider_job_id?, attempts int,
  created_at, started_at, finished_at
}
```

**State machine**
```
queued → running → succeeded
   │        │
   │        ├→ failed (refund if credits_charged > refunded)
   └────────┴→ cancelled (refund)
```

**Routes**
| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/studio/ops` | create `{kind, target, params, project_id?}` → `{op_id}` |
| GET | `/internal/studio/ops/:id` | `{state, progress, result?, error?}` |
| POST | `/internal/studio/ops/:id/cancel` | cancel if not terminal |
| GET | `/internal/studio/ops?project_id=` | op history for the project |

Legacy per-verb routes stay as thin wrappers that create an `op`, so no frontend
breaks during migration.

**Acceptance**
- one poll shape for every verb;
- refund on failure is provable from `credits_charged − credits_refunded`;
- killing the worker mid-job leaves `running` reconcilable to `failed` after timeout.

---

## B2. Clip edit chain (server-side, healable)

**Problem.** We bake crop/fade/speed/reverse into the audio in the browser. The
reference keeps an ordered chain and offers `Heal Edits`.

**Target.** Edits live on the clip inside the project document, and are applied by the
server when rendering:

```
clip.edits = [
  { id, type: "crop",    params: { start_s, end_s, remove }, created_at },
  { id, type: "fade",    params: { in_s, out_s },            created_at },
  { id, type: "speed",   params: { multiplier, keep_pitch }, created_at },
  { id, type: "reverse", params: {},                         created_at },
]
```

Rules
1. Edits are **non-destructive and ordered**; render applies them left to right.
2. `Heal Edits` removes the whole chain (not one entry) and returns the clip to source.
3. Removing a single edit is allowed only if the chain stays renderable (e.g. no fade
   referencing a trimmed range).
4. Edits are part of the versioned document, so undo/versions restore them too.

**Routes**
| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/studio/clips/:id/edits` | append `{type, params}` → `{edit}` |
| DELETE | `/internal/studio/clips/:id/edits/:editId` | remove one |
| DELETE | `/internal/studio/clips/:id/edits` | `Heal Edits` (clear chain) |
| GET | `/internal/studio/clips/:id/edits` | read chain |

**Acceptance**
- crop → fade → reverse produces the same audio as applying them in order offline;
- heal restores byte-identical output to the untouched source;
- a version restore restores the chain, not just the audio.

---

## B3. Analysis endpoints

**Problem.** Our waveforms are synthetic/approximate and lyric timing is ours, not the
provider's. The reference reads analysis from the server.

| Endpoint (reference) | Returns | Our use |
|---|---|---|
| `/api/gen/{clip_id}/downbeats` | downbeat timestamps | bar/beat grid, metronome accent, quantize |
| `/api/gen/{clip_id}/waveform-aggregates` | peak bins | timeline + clip waveforms |
| `/api/gen/{clip_id}/aligned_lyrics/v3` | words with start/end | lyric view, karaoke, section edits |
| `/api/gen/{clip_id}/novelty-sections` | section boundaries | markers (verse/chorus) |

**Target (ours)**
| Method | Path | Cache |
|---|---|---|
| GET | `/internal/studio/clips/:id/downbeats` | per clip+source hash, immutable |
| GET | `/internal/studio/clips/:id/waveform?bins=512` | immutable, keyed by bins |
| GET | `/internal/studio/clips/:id/lyrics?variant=` | short TTL, revalidated on replace |
| GET | `/internal/studio/clips/:id/sections` | immutable |

Storage: `clip_analysis(clip_id, kind, payload jsonb, source_hash, created_at)` with a
unique `(clip_id, kind, source_hash)`. Serve from the table; refresh on new source.

**Acceptance**
- waveform renders from server peaks without downloading the full audio;
- downbeats drive the metronome accent (fixes the known mid-song signature bug);
- lyric timings match provider output, not estimates.

---

## B4. Social layer on clips

**Problem.** A share link currently behaves like a static export. The reference has
permissions, comments, and remix toggles.

**Reference surface**
`/api/clip/{id}/permissions` · `/grants` · `/visibility` · `/api/gen/{id}/comments` ·
`/comments/count` · `/comment` · `/toggle_comments` · `/toggle_remixes` ·
`/toggle_show_remixes`

**Target tables**
```sql
clip_permissions(clip_id, owner_id, visibility enum(private|unlisted|public), can_remix bool)
clip_permission_grants(clip_id, grantee_id, capabilities jsonb, created_at)
clip_comments(id, clip_id, parent_id, author_id, body, created_at, deleted_at)
clip_comment_flags(clip_id, user_id, hidden bool)      -- per-user "hide comments"
project_shares(...)                                    -- already exists
```

**Routes (public, v3)**
`GET/PATCH /api/v3/web-music/clips/:id/permissions` ·
`POST /api/v3/web-music/clips/:id/grants` · `DELETE …/grants/:uid` ·
`GET/POST /api/v3/web-music/clips/:id/comments` · `DELETE …/comments/:cid` ·
`POST …/toggle-comments` · `POST …/toggle-remixes`

**Rules**
- Comment visibility inherits clip visibility; private clips never expose comments.
- `toggle_comments` off hides the thread but keeps the data.
- A share link grants **view + fork** (measured, spec §24) — never live co-editing.

**Acceptance**
- commenting on a shared clip works for a signed-in viewer;
- turning comments off hides them everywhere without deletion;
- forking a shared project copies clips but not comments.

---

## B5. Render artifacts

**Problem.** Our export returns a blob to the browser; nothing is stored, so a failed
or interrupted export cannot resume, and multitrack/stem exports are single-shot.

**Target tables**
```sql
render_jobs(id, user_id, project_id, scope enum(full|range|multitrack|stems|clip),
            state, params jsonb, error_code?, created_at, finished_at)
render_artifacts(id, render_job_id, kind enum(mix|stem|clip|archive),
                 format, bytes, duration_s, storage_key, checksum, created_at)
```

**Routes**
| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/studio/render-state` | create job → `{render_id}` |
| GET | `/internal/studio/renders/:id` | `{state, progress, artifacts[]}` |
| GET | `/internal/studio/renders/:id/artifacts/:aid` | stable download URL (signed, expiring) |
| POST | `/internal/studio/renders/:id/cancel` | cancel, keep completed artifacts |

**Rules**
- artifacts are immutable once written; retries create a new job;
- URLs are short-lived but re-mintable from the artifact id;
- multitrack renders one artifact per track plus a manifest, so a partial failure
  still leaves usable output;
- checksum recorded so a resumed client can verify.

**Acceptance**
- killing the client mid-render resumes from the artifact list;
- a 17-track multitrack export yields 17 artifacts + manifest;
- re-downloading an artifact does not re-render.

---

## Ordering and dependency

```
B1 (op record)  ──►  B2 (edit chain)  ──►  B5 (render artifacts use ops)
      │
      ├──►  B3 (analysis; independent, cache-only)
      └──►  B4 (social; independent of ops)
```

1. **B1 first** — everything else reports through it.
2. **B3 next** — independent, improves the UI immediately, no migration risk.
3. **B2 before more editing features** — otherwise every new clip feature inherits the
   baked-edit model.
4. **B4** — independently shippable.
5. **B5 last** — depends on B1 for job states.

## Out of scope for these five

- Canvas-vs-DOM rendering decision.
- Take-lane merge/comping logic.
- Plugin designer (Wavetable / IR) storage.
