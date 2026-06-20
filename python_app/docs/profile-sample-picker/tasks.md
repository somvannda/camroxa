## Profile Sample Picker UI

### Goal
- In Profile settings, allow Boss to pick sample images from the selected Samples Dir using a selectable list UI.
- Random mode remains a simple checkbox; Manual mode is selecting from the list.
- Remove the “one path per line” text boxes to reduce confusion.

### Tasks
- [ ] Replace profile sample text boxes with QListWidget pickers (BG + Thumbnail)
- [ ] Load list items from selected samples dir; support Reload button
- [ ] Manual mode: allow selecting up to 5 images; persist to profile `imageConfig.backgroundSamples` / `thumbnailSamples`
- [ ] Random mode: disables manual list selection (selection cleared on enable)
- [ ] Update load/save logic for profiles to match new widgets

### Validation
- [ ] Selecting a directory loads images into the list
- [ ] Manual selection persists after Save + reselect profile
- [ ] Random ON disables selection and does not persist manual list into new jobs

