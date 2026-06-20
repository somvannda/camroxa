## Video After Suno — Design

### Profile → Template Mapping
- Location: Settings → Profiles (profile details form).
- Add field: Video Template (dropdown).
- Dropdown item label format: `<template_name> · <template_id>`
- Dropdown value stored: `<template_id>` (persisted in profile as `videoTemplateId`).

### States
- No DB configured: field is disabled and shows “(Database not configured)”.
- No templates: field is enabled but list contains only “(No templates)”.
- Profile has `videoTemplateId` that no longer exists: show `Missing · <id>` as selected.

### Interaction
- Selecting a dropdown item updates an internal pending value (not persisted until Save Profile).
- Clicking Save Profile persists `videoTemplateId` along with existing fields (name, folder, prefix, logo).
