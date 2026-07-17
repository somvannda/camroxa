# Video template golden fixtures

Golden JSON fixtures for `TemplateNormalizer` and draft merge tests.

Each numbered set has:

| File | Role |
|------|------|
| `NN_saved_template.json` | Electron saved template (`currentTemplate` / disk shape). Set **03** uses `03_legacy_sensitivity_template.json`. |
| `NN_draft_flat.json` | Flat `VideoTemplateDraft` fields (in-memory editor) |
| `NN_layers.json` | Editable spectrum layers (may match or override saved `layers`) |
| `NN_workspace.json` | `{ "logoPath": "..." }` for draft hydration |
| `NN_expected_renderer_dict.json` | Expected output of `TemplateNormalizer.to_renderer_dict()` |

## Normalizer contract (all sets)

1. Deep-merge saved template with `buildVideoWorkspaceTemplateSavePatch` equivalent.
2. Set `audioSettings.sensitivity = audioSettings.inputGain` when `inputGain` is present.
3. If only legacy `sensitivity` exists, set `inputGain = sensitivity` in merged output.
4. Text overlays use `sizePx` (not `fontSize`) in renderer output.
5. Preserve unknown keys from saved template (forward compatibility).

## Usage (Phase 9d+)

```python
from features.video.services.template_normalizer import TemplateNormalizer

def test_fixture_01():
    normalizer = TemplateNormalizer()
    result = normalizer.to_renderer_dict(
        base=load_json("01_saved_template.json"),
        draft=load_json("01_draft_flat.json"),
        layers=load_json("01_layers.json"),
        workspace=load_json("01_workspace.json"),
    )
    assert result == load_json("01_expected_renderer_dict.json")
```

## Source provenance

- **01** — Synthetic minimal case aligned with Electron `buildVideoTemplateDraft({}, { logoPath: "" })` defaults.
- **02** — Trimmed from `python_app/video_templates_local.json` entry **Bass Drive** (real production template).
- **03** — Legacy `audioSettings.sensitivity` only (pre-`inputGain` migration). Base file: `03_legacy_sensitivity_template.json`.
- **04** — Live edit scenario: style change, text overlay, effect pack ref, particles disabled.
