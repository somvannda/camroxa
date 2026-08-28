# 2026-08-27 — Create form controls match the studio screenshot

Local desktop only. Sandbox and production were not deployed.

## Summary

Dropdowns, date fields, radios, checkboxes, and Simple/Advanced tabs on the native Create page now use the same chrome as the design screenshot instead of generic Qt Fusion controls.

## Product impact

- Language and template dropdowns show a down-arrow and open below the field
- From / To fields show a calendar icon and open a dark calendar popup
- Vocal Gender radios are a purple ring with an inner dot
- Download options use a square checkbox with a check mark
- Simple / Advanced are boxed tabs; the active tab has a purple fill, with no underline row
- Count spinner arrows and slider thumbs match the same set
- From / To / Primary / Secondary / Count stay left-aligned instead of stretching across the bar
- Create workspace fill matches the form/Files panels so leftover navy gutters no longer show around the cards
- Simple / Advanced boxed tabs are 36px tall
- LYRICS, STYLES, song title, negative tags, Files table, and player track use **Khmer OS Siemreap**
- The Advanced form fills the panel height; extra space goes to LYRICS / STYLES
- Create form / Files split is 60 / 40 and stays that way on large windows
- Create form is 60% width, Files is 40%
- Simple / Advanced tabs are taller boxed pills
- Lyrics, styles, song title, file names, and the player track use Khmer OS Siemreap so Khmer renders
- Workspace background matches the panels so leftover navy gutters do not show; lyrics/styles grow to fill height
- Lyrics/Styles sit in the input only (no extra dark block), checkbox info icons are gone, the files table is 15px, Ready is a solid green pill, and Generate Music is taller
- Date fields open a calendar popup from the icon, Choose a Save to folder sits on the save row, and the files refresh icon has no button chrome
- Create header, planning bar, form, and files cards have 10px gaps so the frames are not flush
- Simple tab keeps lyrics and styles, and hides negative tags, vocal gender, and the three sliders
- Song title sits on its own row above the options columns; Advanced wrappers no longer paint a darker block

## Technical impact

- New `StudioComboBox`, `StudioDateEdit`, `StudioRadioButton`, `StudioCheckBox`, and `ModeTab` in `features/create/widgets/studio_controls.py`
- Native combo/date arrows are hidden so the painted icons are the only affordance

## Files touched

- `camxora_python/features/create/widgets/studio_controls.py`
- `camxora_python/features/create/widgets/create_form.py`
- `camxora_python/features/create/widgets/planning_bar.py`
- `camxora_python/features/create/create_styles.py`
- `camxora_python/features/create/views/create_view.py`
- `camxora_python/shared/icons/lucide_icons.py`
- `camxora_python/tests/test_create_view.py`
