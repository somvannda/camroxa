## Video Editor Enhancements

### Goals
1) Add a Spectrum ON/OFF toggle (applies to preview + export).
2) Add Logo CD spin effect (direction + speed, applies to preview + export).
3) Background should not stretch across resolution changes; support fit modes and allow drag/scale in preview, exporting exactly what preview shows.

### Scope
- Template-driven (saved in template JSON/DB).
- Applies to both live preview (`SpectrumPreview`) and export renderer (`gpu_render.py`).

### Tasks
- [ ] Add template fields:
  - `spectrumEnabled`
  - `logoSettings.spinEnabled`, `logoSettings.spinDirection`, `logoSettings.spinSpeed`
  - `backgroundSettings.fitMode`, `backgroundSettings.userScale`, `backgroundSettings.userOffsetX`, `backgroundSettings.userOffsetY`
- [ ] UI controls:
  - Spectrum tab: Enable Spectrum toggle
  - Logo tab: Enable Spin + Direction + Speed
  - Background tab: Fit mode + Scale + Reset + “Edit background in preview” mode
- [ ] Preview:
  - Skip spectrum drawing when disabled
  - Rotate logo in shader based on time + spin settings
  - Implement background fit (contain/cover/original) + apply drag/scale offsets
  - Dragging background updates template offsets; scaling updates template scale
- [ ] Export parity:
  - Same background mapping and logo rotation in GPU renderer
  - Same spectrum enabled behavior

### Validation
- [ ] Turning Spectrum OFF hides spectrum in preview and export output
- [ ] Logo spins CW/CCW at selected speed in preview and export output
- [ ] Background fit mode prevents stretching; drag/scale changes are reflected in export output

