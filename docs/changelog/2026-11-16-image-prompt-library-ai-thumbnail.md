# Admin image prompt library and AI thumbnail text

**Date:** 2026-11-16
**Branch:** `feature/image-prompt-library`
**Migration:** `205_image_prompt_library`

## What

Admins can now curate a reusable library of background and thumbnail prompt
styles. The desktop can use that library instead of a single personal prompt:

- `imageBackgroundPromptSource` / `imageThumbnailPromptSource` = `custom` or
  `admin_library`.
- The server selects a style per channel at image-job creation.
- Within one batch, a second channel excludes styles already used by the first.
- Selection uses `image_random_history` least-used rotation and records
  `last_batch_id` so the next batch avoids the previous one where possible.
- Thumbnail styles can carry a `text_template` with `{title}`, `{album}`, or
  `{channel}`.

Thumbnail generation also gains `thumbnailReferenceMode=background_text`:

- The generated background is sent to the image model as the reference image.
- The prompt asks the model to preserve the background and render the exact
  thumbnail text.
- The old black-canvas chroma-key composite stays available as
  `thumbnailReferenceMode=composite`.
- `background_text` is the new default; composite remains the explicit legacy
  mode. Migration `205` updates an existing `thumbnailReferenceMode=composite`
  system setting to `background_text`.
- Migration `206` seeds `fal/flux-dev-image-to-image` thumbnail pricing:
  FAL list price $0.03/MP, 1920x1080 = $0.062208 cost, 100% markup = $0.124416,
  rounded to 25 credits (250,000 micro-units).
- Migration `207` adds image-job hold recovery fields (`hold_units`,
  `hold_state`, `provider_invoked`). The worker now sweeps stale `RUNNING`
  image jobs and stale dependent thumbnails, refunding the exact hold by
  `job.id` before requeueing/failing them.

## Data

Migration `205` adds:

- `image_prompt_styles` (`kind`, `name`, `prompt_text`, `text_template`,
  `is_active`, `sort_order`, `notes`).
- `image_jobs.prompt_style_id`, `source_mode`, `thumbnail_mode`.
- `image_random_history.last_batch_id`.

Per-job fields make retries and setting changes deterministic. A normal retry
keeps the stored prompt; force regenerate re-picks a style and bills as before.

## API

- `GET/POST/PATCH/DELETE /api/v3/admin/image-prompts`
- `GET /api/v3/image-prompts/summary`
- `GET /api/v3/image-prompts` (active names/templates for the desktop)

## Admin portal

New **Content → Image Prompts** page with background/thumbnail tabs, prompt
editor, text template, active/sort controls, and usage-friendly empty states.
Settings → Image Generation adds the `AI text on background` mode and marks it
recommended.

## Desktop

- Settings and the Image page gain **Prompt source** per kind: My prompt or
  Admin prompt library.
- Local prompt boxes become read-only when the library is active.
- The page shows active style counts and blocks generation when the library is
  empty.
- Thumbnail mode is selectable; `background_text` is the default.

## Credits

No new billing operation and no extra image job:

- Two-channel batch: 2 background + 2 thumbnail jobs (4 total).
- `background_text` replaces the existing thumbnail AI call, not adds one.
- Empty library, unsupported provider, and overlong prompt are rejected before
  wallet hold. Normal retry does not charge for a new prompt pick.

## Verification

```bash
python -m pytest platform_api/tests -q
# 3485 passed

python -m pytest camxora_python/tests/test_image_view.py \
  camxora_python/tests/test_image_workspace.py \
  camxora_python/tests/test_settings_workspace.py \
  camxora_python/tests/test_settings_view.py -q
# 43 passed

cd admin_portal && npm run build
```
