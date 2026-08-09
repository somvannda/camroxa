# Composition Studio follow-ups — metadata, schema bridge, export

**Branch:** `feature/studio-v1`  
**Date:** 2026-08-09

## Summary

Extends Studio v1 beyond the MVP shell:

- **Asset metadata** on composition catalogs (`visualizer/presets/metadata.py`) with mood/genre/tags/perf + Studio Asset Library search/apply.
- **Doc-09 schema bridge** (`features/studio/lib/schema_bridge.py`) — `camxora.project` projection; composition remains authoring authority.
- **Studio export** — Export JSON (project projection) and Export Video (reuses `VideoManualExportWorker` with Studio-built `ManualRenderSceneRequest`). Requires audio + background paths on disk.

Music→Video pipeline cutover, AI Designer, Timeline, and Plugin SDK remain out of scope.

## Verify

```text
cd camxora_python
python -m pytest tests/test_navigation.py tests/test_studio_v1.py -q
```
