## Video Workspace Resolution Selector + Expanded Presets

### Goal
- Boss can change output resolution directly inside the Video workspace.
- Preview aspect ratio updates immediately to match the selected resolution.
- The selected resolution drives the same end-to-end pipeline behavior as today (images + export use the chosen width×height).

### Scope
- Add an Output Resolution dropdown to the Video workspace header.
- Expand the global/per-profile resolution preset list (shared source of truth).
- Persist selection to settings key `outputResolution`.

### Tasks
- [ ] Centralize output resolution presets so Settings + Profiles + Video workspace use the same list
- [ ] Add Output Resolution dropdown to Video workspace
- [ ] On change: persist `outputResolution`, update preview aspect ratio
- [ ] Update existing preset docs to include the new preset options

### Validation
- [ ] Changing resolution in Video workspace updates preview aspect ratio immediately
- [ ] New presets appear in Settings → Image and Settings → Profiles
- [ ] Export uses the selected resolution (width×height)
- [ ] Image generation uses the selected resolution (width×height)

