## Video After Suno — Tasks

### Goal
- Add per-profile `videoTemplateId` mapping in Settings → Profiles.
- UI shows both template name and template id; stores template id.

### Tasks
- [ ] DB: add `profiles.video_template_id` column (migration).
- [ ] DB: extend profile read/write to include `videoTemplateId`.
- [ ] Model: include `videoTemplateId` in normalized profile shape.
- [ ] UI: add a Video Template dropdown in Profiles settings; show `Name · <id>` and store `<id>`.
- [ ] UI: load selected profile’s template value; persist on Save.
- [ ] Validation: ensure profile list loads with/without DB; ensure templates list loads with/without DB.
- [ ] Verification: `py -m py_compile` for touched modules.
- [ ] Documentation: update `DEVELOPMENT_LOG.md`.

### Acceptance Checklist
- [ ] Selecting a template updates profile `videoTemplateId` and persists to DB.
- [ ] Dropdown shows both template name and template id.
- [ ] If template is deleted, profile still loads (dropdown shows “(missing)” but id preserved).
- [ ] Works for both OK and ALT profiles.
