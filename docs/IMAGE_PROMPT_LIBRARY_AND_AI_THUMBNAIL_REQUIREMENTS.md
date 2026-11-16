# Image Prompt Library & AI Thumbnail Text — Requirements

**Date:** 2026-11-16
**Status:** implementation in progress
**Product scope:** `platform_api`, `admin_portal`, `camxora_python`
**Related docs:**
- [`IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md`](./IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md) — earlier prompt-only / categories / personal-reference work. This document supersedes its §14 #1 ("prompt-only thumbnail = composite") for the new `background_text` mode.
- [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — which surfaces receive new work.

---

## 0. Why this document exists

Boss wants image generation to be driven by a **server-side prompt library** that admins curate, instead of every user retyping one prompt:

1. Admin stores as many background and thumbnail prompt styles as needed.
2. The desktop user can choose to use the admin library instead of a personal prompt.
3. Each channel in a batch must draw a **different** prompt from the library, even when both channels belong to the same batch.
4. Rotation must not give every batch the same prompt; least-used rotation is the default, with an attempt to avoid the immediately previous batch.
5. Thumbnail text must not be generated as a separate black-background layer and pasted onto the background. The image model must receive the generated background and add the exact text itself (`image-to-image` / image edit).
6. The thumbnail text itself must be stored in admin, with tokens resolved per channel.
7. Credit charging must not change: the feature must not add extra image jobs or silently bill extra generations.

---

## 1. Locked product decisions

| # | Decision |
|---|---|
| 1 | **One preset row** = one prompt style. For thumbnails the same row also carries an optional `text_template`. Separate style/text pools are out of v1. |
| 2 | **Prompt source is orthogonal to reference source.** New per-kind settings: `imageBackgroundPromptSource` / `imageThumbnailPromptSource` = `custom` \| `admin_library`. They can be combined with `Category` or `Prompt only` reference modes. |
| 3 | Selection happens **server-side** at image-job creation. The desktop never picks the prompt itself; it only selects the prompt source. This also covers batches created by automation. |
| 4 | Within one batch, a kind never reuses the same prompt style for two channels while another active style exists. If the library is too small, reuse with a warning instead of failing the batch. |
| 5 | Across batches, selection uses the existing `image_random_history` least-used rotation. `last_batch_id` is stored so the service can avoid the immediately previous batch when alternatives exist. |
| 6 | New thumbnail reference mode `background_text`: the generated background is sent to the image provider as the reference/base image and the prompt asks the model to add the exact text without changing the background. |
| 7 | `background_text` is the **new default** thumbnail mode. `composite` remains available as the explicit legacy/fallback mode. |
| 8 | If the routed provider cannot accept a reference image, the job fails with a clear validation error before wallet hold. It does **not** silently fall back to text-to-image or to composite. |
| 9 | Thumbnail text tokens: `{title}`, `{album}`, `{channel}`. Resolution is per channel. Empty resolved text falls back to the song title, then to `NEW MUSIC`. |
| 10 | Admin style prompts are capped at **3,000 characters**; the composed prompt must stay within the existing **5,000-character** image gate. |
| 11 | Per-job persistence: `prompt_style_id`, `source_mode`, and `thumbnail_mode` are stored on `image_jobs` so retries and setting changes do not alter an already-created job. |
| 12 | Normal retry preserves the stored prompt. Only **force regenerate** re-picks a library style and bills a new image job as today. |
| 13 | No new billing operation. Background jobs stay `background_image`; thumbnails stay `thumbnail_image`. A two-channel batch still creates four image jobs. |

---

## 2. Current behavior (baseline)

- A batch has Primary (`OK`) and Secondary (`ALT`) profiles. `BatchService.create_image_jobs_for_batch()` creates one background and one thumbnail job per profile, so a normal two-channel batch produces **4 image jobs**.
- `_create_jobs_for_profile()` composes `profile_prompt + user_prompt` for each kind. Both channels receive the **same** user prompt. Only sample images are excluded per batch via `used_samples`.
- `_get_user_image_prompt()` reads `imageBackgroundPrompt` / `imageThumbnailPrompt` from user settings.
- Thumbnail generation goes through `_generate_thumbnail_composite()`: AI renders typography on black, then `compose_thumbnail_onto_background()` chroma-keys black and pastes it onto the background.
- `normalize_thumbnail_reference_mode()` only knows `composite` and `dual_reference`.
- Credits are held per image job in `ImageJobService._run_one_job()`.

---

## 3. Data model

### 3.1 `image_prompt_styles`

```sql
CREATE TABLE image_prompt_styles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL CHECK (kind IN ('background', 'thumbnail')),
    name TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    text_template TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_image_prompt_styles_kind_name
    ON image_prompt_styles(kind, lower(name));
CREATE INDEX idx_image_prompt_styles_kind_active
    ON image_prompt_styles(kind, is_active, sort_order);
```

Rules:

- `kind` is `background` or `thumbnail`.
- `prompt_text` is the art-direction/typography prompt. It must not be empty.
- `text_template` is only meaningful for `kind='thumbnail'`. It may contain `{title}`, `{album}`, `{channel}`. Empty means “use the song title”.
- Deactivate instead of delete when possible. Deleting is allowed; jobs keep the literal prompt.

### 3.2 `image_jobs` additions

```sql
ALTER TABLE image_jobs
    ADD COLUMN prompt_style_id UUID REFERENCES image_prompt_styles(id) ON DELETE SET NULL,
    ADD COLUMN source_mode TEXT,
    ADD COLUMN thumbnail_mode TEXT;
```

- `prompt_style_id` records which admin style produced the job.
- `source_mode` records `prompt_only` / `category` / `personal_reference` at creation time.
- `thumbnail_mode` records `composite` / `background_text` at creation time.
- The final prompt is still stored in `image_jobs.prompt`; it is the source of truth for retries.

### 3.3 `image_random_history` addition

```sql
ALTER TABLE image_random_history
    ADD COLUMN last_batch_id UUID;
```

History keys:

- `bg_prompt_style` — background prompt style ids.
- `thumb_prompt_style` — thumbnail prompt style ids.

---

## 4. Selection behavior

### 4.1 Service

New `ImagePromptLibraryService`:

```python
async def pick_style(
    *,
    kind: ImageKind,
    batch_id: UUID,
    exclude_ids: list[str] | None = None,
    previous_batch_id: UUID | None = None,
) -> ImagePromptStyleRecord | None
```

Algorithm:

1. Load active styles for `kind`.
2. Remove ids in `exclude_ids` (already selected for this batch).
3. If `previous_batch_id` is provided, remove styles whose `last_batch_id` equals it, **only if** at least one candidate remains.
4. Order candidates by `used_count ASC, used_at ASC NULLS FIRST, random()`.
5. Increment the chosen style’s `used_count`, set `used_at = NOW()` and `last_batch_id = batch_id`.
6. Return the style.
7. If no active styles exist at all, raise `ValidationError` with a clear message. If exclusion emptied the list, reuse the full active list and log a warning.

Use a short transaction/advisory lock per kind to keep concurrent batch creation from picking the same style twice.

### 4.2 Per-batch uniqueness

`create_image_jobs_for_batch()` loads `used_prompt_ids` for the batch (from existing image jobs), passes them through the profile loop, and appends each selection. This mirrors the existing `used_samples` mechanism.

### 4.3 Preflight

`preflight_music_plan()` and `create_batch()` validate before Suno/draft work:

- If a kind uses `admin_library`, at least one active style must exist.
- If `background_text` is active, at least one reference-capable provider must be available in the routing chain.
- A composed prompt over 5,000 characters is rejected at job creation; the admin editor prevents most of it at 3,000.

Failures return a user-facing reason and must not charge music or image credits.

---

## 5. Prompt composition

One helper, used by every path:

- normal batch creation (`_create_jobs_for_profile`)
- manual generation (`create_manual_image_generation`)
- manual image source (`_build_manual_jobs_for_profile`)
- retry refresh (`refresh_image_job_prompts_for_retry`)

The helper returns `(prompt, prompt_style_id, source_mode, thumbnail_mode)`.

Composition order:

1. profile prompt (`{title}` / `{album}` resolved)
2. prompt source:
   - `custom`: user setting `imageBackgroundPrompt` / `imageThumbnailPrompt`
   - `admin_library`: selected `prompt_text`
3. for thumbnail, exact text instruction when `text_template` resolves non-empty:
   `Render exactly this text: "<text>"` with no extra words/logos/watermarks.
4. mode instruction:
   - background: `BACKGROUND_NO_TEXT_INSTRUCTION`
   - thumbnail `background_text`: `THUMBNAIL_BACKGROUND_TEXT_INSTRUCTION`
   - thumbnail `composite`: `enrich_thumbnail_prompt(...)`
5. length check against 5,000.

Resolve tokens with `{title}`, `{album}` and the new `{channel}` (profile name where available).

---

## 6. Thumbnail `background_text` mode

### 6.1 Prompt instruction

The model receives the generated background plus an instruction shaped like:

> Use the supplied image as the exact background. Keep its composition, colors, lighting, objects, and framing unchanged. Do not redraw, recolor, crop, or move anything. Add only the following text, exactly as written and spelled correctly:
> "<<TEXT>>"
> Typography style: <<style prompt>>
> The text block should be about 38–42% of the frame width, centered horizontally, slightly above the vertical middle. No extra words, letters, logos, watermarks, captions, or signage.

### 6.2 Pipeline

`ImageJobService`:

1. Wait for the source background job.
2. Read the background bytes. If unreadable, fail clearly; do not silently generate a fresh image.
3. Submit one `ImageRequest` with `base_image=background_bytes`, `operation="thumbnail_image"`, and the composed prompt.
4. Run `to_cover_png_bytes()` on the result.
5. Do **not** call `chroma_key_black_overlay()` or `compose_thumbnail_onto_background()`.

### 6.3 Provider capability

Add `supports_reference_image` to image model specs:

- SLAI image models: true.
- CALA: true.
- FAL: true only for endpoints verified to accept image-to-image.
- OpenAI image models: false until `/v1/images/edits` is implemented.
- Kie: false (text-to-image only).

For `background_text`, filter the routing chain to reference-capable providers. If none remain, fail before wallet hold with a clear message.

### 6.4 Persistence

`thumbnail_mode` is stored on the job. The worker uses `job.thumbnail_mode` first, then falls back to the setting for legacy rows.

---

## 7. Admin portal

New page: **Content → Image Prompts** (`/image-prompts`).

- Tabs: **Background styles** and **Thumbnail styles**.
- Table columns: name, prompt preview, text template, active, sort, usage.
- Create/edit dialog fields: kind, name, prompt text (3,000-character counter), text template (thumbnail only), active, sort order, notes.
- Bulk paste: one prompt per line creates multiple styles.
- Empty states explain that the desktop library mode requires at least two active styles per kind for two-channel batches.
- Settings → Image Generation gains the `background_text` option and marks it recommended.
- Existing Image Packs page remains for sample images.

API:

- `GET /api/v3/admin/image-prompts?kind=...`
- `POST /api/v3/admin/image-prompts`
- `PATCH /api/v3/admin/image-prompts/{id}`
- `DELETE /api/v3/admin/image-prompts/{id}`
- `GET /api/v3/image-prompts/summary` (authenticated; active counts per kind)

---

## 8. Desktop

### 8.1 Settings / Image page

Per kind:

- Reference source: existing Category / Prompt only.
- Prompt source: **My prompt** (`custom`) / **Admin prompt library** (`admin_library`).
- Thumbnail only: text source is the selected admin style’s `text_template` when library is active; custom mode keeps the existing prompt-token behavior.

Thumbnail generation:

- **AI text on background** (`background_text`, recommended/default)
- **Composite (legacy)** (`composite`)

Behavior:

- When `admin_library` is active, the local prompt box is disabled and shows “Using admin prompt library — a different style is chosen per channel.”
- Show active style counts from the summary endpoint.
- If zero active styles, block generation with a clear inline error.
- If fewer than two active styles for a kind, warn that both channels may reuse one style.
- Include the new settings in `_current_settings_patch()` and `build_system_settings_patch()`.

### 8.2 Image queue

- Job detail shows the actual selected prompt (already returned by the API).
- Manual Generation uses the same prompt-source logic. If no song title is available and a text template resolves empty, fall back to `NEW MUSIC`.
- Normal Retry does not re-pick a style. Force Regenerate does.

---

## 9. Credits

- Two-channel batch with both kinds: **4 image jobs** (2 background, 2 thumbnail).
- Example list price: 2×6 + 2×8 = **28 credits**; plan allowance still applies.
- Prompt library selection costs nothing.
- `background_text` replaces the existing thumbnail AI call; it does not add a call.
- No second AI pass over the background.
- Validation failures (empty library, unsupported provider, overlong prompt) happen before wallet hold.
- Force regenerate bills like today. Normal retry preserves the prompt and bills only when a provider call actually runs.
- If routing is filtered to a reference-capable provider, use that filtered chain for the credit hold so the hold matches the executed model.

---

## 10. Acceptance criteria

- [ ] Admin can create, edit, deactivate, and delete background/thumbnail prompt styles.
- [ ] Admin can store a thumbnail text template with `{title}`, `{album}`, `{channel}`.
- [ ] With `admin_library` on and at least two active styles, two channels in one batch receive different `prompt_style_id` values.
- [ ] A second batch uses least-used rotation and avoids the previous batch where possible.
- [ ] With only one active style, both channels reuse it with a warning, and the batch still completes.
- [ ] Empty library rejects the batch at preflight with a clear message; no music or image credits are charged.
- [ ] `background_text` sends the background bytes as `base_image` and never calls the composite helpers.
- [ ] `background_text` output is cropped to the job resolution and saved as `thumbnail-16x9.png`.
- [ ] A provider without reference-image support is rejected before wallet hold.
- [ ] Normal retry keeps the original prompt; force regenerate re-picks and bills a new image job.
- [ ] `prompt_style_id`, `source_mode`, and `thumbnail_mode` are persisted on image jobs.
- [ ] Covered prompt > 5,000 characters fails clearly before the provider call.
- [ ] Manual generation with no song title uses `NEW MUSIC` or the configured fallback.
- [ ] Defaults preserve behavior for rows without the new fields; the new `background_text` default is documented and tested.
- [ ] Credit estimate remains four image jobs per two-channel batch.

---

## 11. Phased implementation

| Phase | Scope |
|---|---|
| **P1** | Migration, prompt style repo/service, admin CRUD + API |
| **P2** | Prompt-source settings, per-batch selection, preflight, desktop controls, tests |
| **P3** | `background_text` thumbnail mode, provider capability gate, admin toggle, tests |
| **P4** | Bulk import/usage UI, docs/changelog, sandbox verification |

Suggested branch: `feature/image-prompt-library` (this worktree).

---

## 12. Out of scope

- Personal/user-owned prompt libraries.
- Per-theme prompt categories beyond the existing `kind`.
- Automatic OCR validation of generated text.
- AI-generated 9:16 thumbnails; this work covers the 16:9 image job only.
- Changing Suno, draft, streaming, or video billing.
- Electron / `python_app` parity.
