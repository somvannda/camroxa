# Preview P2 — interactive scrub performance

**Date:** 2026-08-04  
**Status:** implemented (desktop; restart required)  
**Branch:** `bugfix/preview-p2-interactive-perf` (on top of P0+P1)  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) P2

## REQ-P2.1 baseline (code-path profile)

Method: static path tracing of one spectrum Glow / particle Opacity drag
(no GPU timing harness in CI). Hot path before this change:

1. Inspector emit → `_patch_selected_spectrum_layer` / `_patch_template_draft`
2. `_update_inspectors` **always** called `_schedule_preview_update` (48ms)
3. `_update_preview` → `TemplateNormalizer.to_renderer_dict` (full draft merge)
4. `stage.set_renderer_preview` → `json.dumps` whole template
5. `preview.set_template` → another `json.dumps` + **`normalize_renderer_template`**
   + **`_spectrum_peak_cache.clear()`**
6. 60 FPS `paintGL` continues on the main thread

**Top 2 cost centers identified:**

1. Full `to_renderer_dict` + `normalize_renderer_template` on every scrub tick  
2. Peak-cache clear + fingerprint `json.dumps` forcing extra CPU work before paint

## Changes (P2.2–P2.5)

| REQ | Delivery |
|-----|----------|
| P2.2 | Allowlisted live `apply_preview_patch` — no normalize on scrub ticks |
| P2.3 | `set_template(..., generation=)` skips full `json.dumps` when generation matches; scrub bumps generation without dumps |
| P2.4 | Opacity/glow/size patches **do not** clear `_spectrum_peak_cache` |
| P2.5 | While scrubbing: preview timer **20 FPS**; idle 180ms → full flush + **60 FPS** |
| P2.6 | Skipped (baseline showed normalize/push dominated; paint reduced via P2.5) |

### Allowlisted draft / layer keys

- Layer: `glow`, `opacity`, `barWidth`
- Draft: `particlesOpacity`, `particlesSize`

Unknown keys still use the full template push (safe default). After scrub idle,
a Full_Template_Push runs so draft/workspace stay canonical.

## Files

- `camxora_python/features/video/lib/preview_scrub_patch.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_preview_scrub_patch.py`
- `camxora_python/tests/test_preview_apply_scrub_patch.py`
- `docs/changelog/2026-08-04-preview-p2-interactive-perf.md`
- `CHANGELOG.md`

## Tests

```bash
pytest camxora_python/tests/test_preview_scrub_patch.py \
       camxora_python/tests/test_preview_apply_scrub_patch.py -q
```
