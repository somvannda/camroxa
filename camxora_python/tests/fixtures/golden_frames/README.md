# Golden frame parity fixtures (REQ-2.7)

Low-motion templates for preview vs export PNG comparison.

| Case | Description |
|------|-------------|
| `minimal/` | Straight bars, shake/particles/bloom off |

Assets:

- `template.json` — renderer template (background path patched at runtime)
- `bg.png` — auto-generated gradient if missing
- `test_tone.wav` — 45 s 440 Hz tone if `.dbg/export_e2e_test` MP3 absent
- `baselines/` — optional reference PNGs (`CAMXORA_GOLDEN_UPDATE=1`)

Run tests:

```powershell
pytest camxora_python/tests/test_export_golden_frames.py -v
```

Update baselines:

```powershell
$env:CAMXORA_GOLDEN_UPDATE = "1"
pytest camxora_python/tests/test_export_golden_frames.py -v
```
