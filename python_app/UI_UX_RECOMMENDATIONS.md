# Python App UI/UX Recommendations

## Purpose

This document captures a detailed UI/UX recommendation set for the standalone Python spectrum app in `python_app/`.

The goal is not just to "make it prettier". The goal is to make the app:

- easier to scan,
- easier to click,
- less visually fatiguing,
- more stable-feeling while adjusting controls,
- more aligned with how creators actually work during preview and export.

This document is intended for future implementation planning.

## Current-State Update (2026-05-24)

This section supersedes parts of the older recommendation set wherever the app has already evolved.

## Boss Compact UI Preferences (2026-05-24)

These preferences should override earlier recommendations where they conflict.

### Core Preference Direction

Boss prefers a more compact, denser creator-tool layout rather than a roomy touch-style layout.

- Inputs should be compact.
- Controls should be compact.
- Fonts should stay readable, but should not be oversized if that causes sidebar scrolling.
- The goal is to fit more useful controls inside the fixed `1670 x 1080` window without making the sidebars feel bloated.

### Explicit Preferences

#### 1. Compact Controls

- Prefer compact controls over oversized controls.
- Reduce unnecessary vertical padding.
- Keep sliders, dropdowns, and input rows tighter so more content fits within the sidebar width and height.
- Compact does not mean tiny; it means efficient and space-aware.

#### 2. Reduce Sidebar Scrolling

- The left sidebar should not feel offset or overgrown because controls, fonts, and spacing became too large.
- The right sidebar has the same issue and should follow the same compact-density rules.
- Excessive scrolling in the sidebars should be treated as a layout failure, not as a normal expectation.
- The UI should aim to fit primary controls in the visible sidebar area first, with scrolling reserved for advanced or expanded controls.

#### 3. Reduce Frames And Borders

- Too many frames, card outlines, and borders create visual clutter.
- Borders should be lighter, fewer, and more purposeful.
- Use grouping primarily through spacing, titles, and subtle background tone shifts instead of drawing a heavy box around everything.
- Avoid stacking border-inside-border-inside-border patterns.

#### 4. Compact Sidebar Tabs

- The left sidebar should move toward a compact tabbed navigation model for the main groups:
  - `Spectrum`
  - `Background`
  - `Logo`
  - `Particles`
- Tabs should be small, compact, and creator-tool-like rather than large segmented blocks.
- The main purpose is to reduce vertical stacking and make the sidebar faster to scan.
- Template and global project controls can stay above the tabs if needed, but the heavy control groups should be tabbed.

### Design Interpretation

The correct UX direction is now:

- compact professional desktop-tool layout,
- reduced chrome,
- reduced border density,
- more information per visible screen area,
- fewer always-visible control blocks,
- more use of tabs or compact section switching.

This is intentionally different from a “large comfortable touch-first” UI approach.

### Why this update exists

The Python app now contains significantly more controls and workflow steps than the earlier version of this document covered.

- The UI now supports real multi-layer spectrum editing.
- The right panel now includes layer management and real per-layer render controls.
- Export now includes output-folder prompting and per-song progress reporting.
- The MP3 folder workflow was improved so the folder picker can show `.mp3` files while browsing.
- Template management now includes deletion and more reliable current-template handling.

### Current implemented controls

#### Template / project controls

- Template name input
- `Save`
- `Delete`
- template load dropdown
- template persistence / restore

#### Preview / assets / playback

- live preview
- pop-out live preview
- `Set BG`
- `Set Logo`
- playback buttons
- seek bar
- MP3 folder picker
- selected MP3 dropdown

#### Export controls

- `Start Batch Export`
- output-folder prompt on export start
- output-folder status label
- per-song progress bar
- stage text
- exported-count text

#### Left panel controls

- style preset dropdown
- stacked preset dropdown + apply
- spectrum sensitivity / smoothing
- anchor
- X / Y offset
- background brightness / reactivity / smoothing
- logo shape / size / opacity / reactivity / smoothing
- particles enable / density / motion / visual controls

#### Right panel controls

- layer selector
- `Add`
- `Duplicate`
- `Remove`
- layer rename
- gravity / anchor direction
- curve / mirror / fill
- bar width
- spike height
- layer radius / gap
- opacity
- blend mode
- glow strength
- glow softness
- color mode
- solid color input + picker
- gradient direction
- preset gradients

### New UX problems caused by feature growth

The app is stronger functionally, but the visual and interaction model has not kept up.

- The right panel is no longer just a simple style area; it is now a full layer-editing workflow and needs stronger grouping.
- The left panel mixes presets, motion, positioning, background, logo, and particles in one long stack.
- The export area works much better than before, but it still visually feels like a toolbar instead of a dedicated export card.
- Multi-button action rows such as template actions and layer actions feel cramped because all actions have similar sizing and weight.
- Recent enlargement of controls and card frames improved click comfort, but it also increased sidebar scrolling and made the side panels feel too bulky for Boss's preferred compact workflow.
- There are now too many visible frame boundaries and bordered regions, which adds visual noise instead of clarity.
- The older recommendation text assumed some controls that were later removed or simplified:
  - no separate `Fill Color`
  - no output-folder button in the bottom bar
  - no Python preview/export engine selector in the bottom bar

### Updated recommendations for the current app

#### Left panel

The left panel should now be thought of as `Project + Motion`, not just `settings`.

Recommended grouping:

1. Template
2. Presets
3. Audio Reactivity
4. Positioning
5. Background
6. Logo
7. Particles

Updated compact preference:

- Move the heavy control groups into compact tabs:
  - `Spectrum`
  - `Background`
  - `Logo`
  - `Particles`
- Keep only compact template / asset / playback essentials always visible above the tab content.
- Avoid making the entire left sidebar a permanently expanded long-form panel.

#### Right panel

The right panel should now be thought of as `Layer Workflow + Style Inspector`.

Recommended grouping:

1. Layer Management
2. Geometry
3. Blend / Glow
4. Color Engine

Updated compact preference:

- Use a denser inspector layout.
- Reduce vertical spacing between controls.
- Reduce border count and nested framed regions.
- Consider compact sub-tabs or segmented selectors inside the inspector if that helps keep the layer panel visible without deep scrolling.

#### Export area

The export area should focus on what Boss actually needs during long renders:

- selected MP3 source
- output target
- current-song percentage
- current stage
- frame count when available
- completed batch count

The document's older export-area guidance that referenced an engine selector should be considered outdated.

### Updated immediate implementation priorities

Given the current real control set, the most valuable implementation order is:

1. compact the sidebars so primary controls fit with less scrolling
2. add compact tabs for `Spectrum / Background / Logo / Particles` in the left sidebar
3. reduce frame and border density across both sidebars
4. make the right inspector denser and more space-efficient
5. keep readability while reducing oversized padding, spacing, and font usage
6. debounce heavier preview updates without inflating the UI footprint

## Current UX Problems

Based on review of the current UI in `python_app/main.py` and the provided screenshot, the main issues are:

### 1. Controls Are Too Small

- Buttons are visually small for repeated use.
- Slider grooves and handles are too thin, which makes them feel imprecise.
- Text is often too small for a dense dark interface.
- Checkboxes and form elements do not have enough comfortable hit area.

### 2. Panels Are Too Dense

- The left panel contains too many stacked controls with nearly identical presentation.
- The right panel has low visual hierarchy, so the eye cannot quickly identify primary vs secondary controls.
- The user has to read line by line instead of scanning by chunk.

### 3. The UI Feels "Buggy" Even When Logic Works

- Many controls are likely triggering live updates too aggressively.
- Sliders appear to behave like low-level dev controls instead of polished creative-tool controls.
- Realtime preview updates can make the interface feel unstable or sticky while dragging.

### 4. Visual Fatigue Is Too High

- The preview is already visually intense.
- The side panels also use hard contrast, thin borders, small text, and many repeated blue accents.
- This creates eye strain because both the content and the chrome are loud.

### 5. Inputs Lack Appropriate Form

- Not every parameter should be slider-only.
- Technical values such as counts, lifetime, thickness, and offsets are often easier with number input + stepper.
- Binary options such as `Fill Circle`, `Curve`, and `Mirror` should feel like mode switches, not generic form controls.

### 6. Workflow Is Not Clearly Organized

- The layout feels like a list of settings, not a creator workflow.
- There is not enough separation between:
  - asset setup,
  - spectrum styling,
  - audio response,
  - playback,
  - export.

## UX Goals

The recommended UX direction should optimize for these goals:

### Goal A: Fast Scanning

Users should be able to glance at the panel and immediately know:

- where to load assets,
- where to style the spectrum,
- where to tune motion,
- where to control playback,
- where to export.

### Goal B: Comfortable Interaction

Users should be able to:

- click controls easily,
- drag sliders without frustration,
- input precise values without wrestling with sliders,
- adjust settings for long periods without eye fatigue.

### Goal C: Stable-Feeling Feedback

The app should feel responsive and calm:

- labels update instantly,
- preview updates feel smooth,
- dragging does not feel jittery or over-sensitive,
- the UI should never feel like it is fighting the user.

### Goal D: Clear Creator Workflow

The app should guide the user through a natural order:

1. Choose assets
2. Play preview
3. Style spectrum
4. Tune reactivity and motion
5. Save template
6. Export

## Recommended Information Architecture

## Overall Layout

Keep the three-column structure, but change the role of each area:

### Left Panel: Project + Motion Controls

This panel should contain:

- Template
- Assets
- Playback / preview sync
- Audio response
- Background
- Logo
- Particles

This is the "project control" side.

### Center: Large Preview First

The preview should remain the focal point.

The control bar above and below the preview should be simplified so the preview remains dominant.

### Right Panel: Spectrum Style Inspector

This panel should contain:

- Layer selection
- Shape / anchor mode
- Fill / mirror / curve
- Spike height
- Stroke width
- Color engine

This is the "visual styling" side.

## Section Model

Each sidebar should use collapsible section cards instead of one long uninterrupted stack.

Recommended section pattern:

- section title,
- short helper subtitle,
- 4 to 8 controls max visible by default,
- optional advanced subsection,
- per-section reset button.

Recommended initial expanded sections:

- `Assets`
- `Audio Response`
- `Spectrum Style`

All other sections can start collapsed.

## Recommended Visual System

## Color Strategy

The preview is already loud and vibrant. The surrounding UI should be calmer.

Recommended palette direction:

- App background: very dark neutral, not pure black
- Panel background: slightly lifted dark surface
- Borders: soft low-contrast separators
- Primary accent: one clear accent color for active states
- Secondary text: muted gray-blue
- Destructive / warning: reserved and rare

Avoid using the same bright accent color on every control.

## Typography

Recommended typography hierarchy:

- Window / section title: `16–18px`, semibold
- Subsection label: `13–14px`, semibold
- Body control label: `13–14px`
- Secondary helper / value label: `12–13px`

The current `11px` usage is too small for this density.

## Spacing

Recommended spacing system:

- Control row vertical gap: `10–12px`
- Group gap: `18–24px`
- Section padding: `16–20px`
- Card spacing: `12–16px`

The current panel rhythm feels cramped and repetitive.

## Recommended Control Design

## Buttons

### Problems

- Primary and secondary actions do not feel sufficiently distinct.
- Buttons are too short for comfortable repeated use.

### Recommendation

- Standard control height: `40–44px`
- Primary actions:
  - `Save`
  - `Start Batch Export`
  - `Set BG`
  - `Set Logo`
- Secondary actions:
  - `Reset Center`
  - `Pick`
  - `Pop Out Live Preview`

### Visual rules

- Primary button: solid fill
- Secondary button: subtle surface + border
- Tertiary button: minimal text-style or ghost button

## Sliders

### Problems

- Too many settings are slider-only.
- Small handles are hard to target.
- Value comprehension is weak.

### Recommendation

For every slider row:

- left: clear label,
- right: current formatted value,
- below: slider,
- optional far-right: numeric input / stepper.

Recommended slider specs:

- height target area: `28–32px`
- handle size: `20–24px`
- groove thickness: `8px`

### Behavior recommendations

- Drag should update the value label immediately.
- Heavy preview updates should be:
  - debounced, or
  - applied on `sliderReleased` for expensive controls.
- Double-click should reset to default.
- Right-click should offer "Reset to default".

### Use sliders only when the value is naturally continuous

Good slider candidates:

- opacity
- smoothing
- reactivity
- brightness
- logo size

Better as number input + stepper:

- max count
- birth rate
- lifetime
- thickness
- bar width
- x/y offset

Best as segmented control:

- shape
- curve on/off
- mirror on/off
- gravity

## Toggles

Replace checkbox-like behaviors with clearer toggle switches for:

- Enable Particles
- Fill Circle
- Curve
- Mirror
- Circle Crop

Toggles feel more intentional and are easier to scan.

## Dropdowns

The following controls should be reconsidered:

- `Style Preset`
- `Anchor`
- `Gravity / Anchor`
- `Shape`

### Better options

- `Style Preset`: visual preset picker with thumbnail or mini icon preview
- `Anchor`: 3x3 position grid selector
- `Gravity`: icon or segmented direction control
- `Shape`: segmented control for `Circle` / `Original`

## Text Inputs

Template name and color fields should be more deliberate:

- Template name should have stronger visual importance
- Color input should include:
  - swatch preview,
  - color button,
  - optional hex field

The current `#ffffff + Pick` row is functional but not polished.

## Recommended Section-by-Section Improvements

## 1. Template Header

### Current issue

The template controls are visually too small and not clearly positioned as project-level actions.

### Recommendation

Use a dedicated template card at the top left:

- Template name input
- `Save`
- `Save As`
- `Load`
- `Reset`

Optional metadata:

- current template id,
- last saved time,
- unsaved changes indicator.

## 2. Assets Section

Group these together:

- Background image
- Logo image
- MP3 source / folder
- Selected MP3

Each asset row should show:

- label,
- current file name,
- change button,
- clear button.

This is more understandable than scattering asset actions between top bar and bottom bar.

## 3. Audio Response Section

This section should explain the difference between global spectrum behavior and per-element behavior.

Suggested content:

- Spectrum sensitivity
- Spectrum smoothing
- Background reactivity
- Background smoothing
- Logo reactivity
- Logo smoothing
- Particle reactivity
- Particle smoothing

Each control should have one-line help text.

Example:

- `Reaction Smoothness`
  - higher = more fluid but slower response
  - lower = more immediate but twitchier

## 4. Background Section

Background settings should feel like image treatment controls:

- Brightness
- Audio Reactivity
- Reaction Smoothness

Optional future additions:

- blur
- scale
- vignette

These should visually read as a media-treatment block, not generic sliders.

## 5. Logo Section

Recommended controls:

- Shape
- Size
- Opacity
- Audio Reactivity
- Reaction Smoothness

Optional future improvements:

- edge softness
- shadow
- glow

Also consider showing a tiny live scale indicator near the preview so users understand the logo is audio-reactive.

## 6. Particles Section

This section currently contains too many controls with similar visual weight.

Recommended grouping:

### Enable

- master toggle

### Motion

- Base Speed
- Audio Reactivity
- Reaction Smoothness
- Lifetime

### Density

- Max Count
- Birth Rate

### Visual

- Particle Size
- Opacity
- Color

This grouping reduces cognitive load.

## 7. Spectrum Style Inspector

The right sidebar should feel like a style panel, not a backup settings dump.

Recommended structure:

### Geometry

- Curve
- Mirror
- Gravity
- Spike Height
- Stroke Width
- Fill Circle

### Color

- Solid / Gradient mode
- Color / Gradient preset
- Gradient direction
- Opacity

### Future Advanced

- glow
- blur
- thickness modulation
- visual preset thumbnails

## Playback And Export UX

## Playback Bar

The playback bar should be easier to understand and easier to hit.

Recommended improvements:

- larger play / pause / stop controls
- clearer active state
- larger seek handle
- current time and duration more visible
- selected track name visually separated from export status

### Specific recommendation

Separate playback status from export status.

Right now these roles compete in the same bottom area.

## Export Area

Recommended export card:

- engine selector
- output target
- queue summary
- export button
- progress
- status / error summary

This should feel like a final action area, not just another row in the bottom toolbar.

## Recommended Interaction Behavior Changes

## 1. Debounce Heavy Updates

This is the single highest-impact behavioral improvement.

When the user drags a slider:

- update the numeric label immediately,
- debounce the expensive preview update by `60–120ms`,
- or commit on release for the heaviest controls.

This will dramatically reduce the "buggy" feeling.

## 2. Add Reset Behavior

Each major section should support:

- reset section,
- reset control,
- restore recommended defaults.

## 3. Add Hover Help

For advanced controls, short tooltips should explain:

- what the control does,
- what higher/lower values mean,
- any important side effects.

## 4. Mark Basic vs Advanced

Not every user needs every control immediately.

Recommended:

- show a "Basic" set by default,
- move technical controls into an expandable "Advanced" area.

## Accessibility Recommendations

Even for a desktop creative tool, accessibility matters.

### Must improve

- larger text
- larger hit targets
- stronger focus states
- keyboard navigation visibility
- better contrast balance on labels and values

### Suggested minimums

- no important text below `12px`
- focus ring on all interactive controls
- active slider handle visibly larger than inactive

## Recommended Implementation Phases

## Phase 1: Ergonomics And Stability

Focus on:

- larger controls,
- better typography,
- better spacing,
- improved slider hit area,
- debounced preview updates,
- stronger section separation.

This phase will likely deliver the biggest usability gain.

## Phase 2: Layout And Workflow

Focus on:

- reorganized left/right panels,
- grouped sections,
- better asset handling area,
- better playback/export grouping.

## Phase 3: Visual Polish

Focus on:

- calmer theme,
- cleaner accent usage,
- better icons,
- visual preset selection,
- subtle shadows/surfaces,
- better state feedback.

## Phase 4: Advanced Creator UX

Focus on:

- preset thumbnails,
- searchable settings,
- live tooltips,
- envelope meters,
- more discoverable advanced controls.

## Acceptance Criteria For Future UI Refactor

The UI refactor should be considered successful only if:

- the user can identify major control groups without reading every label,
- sliders are comfortable to drag and easy to hit,
- live preview adjustments feel smooth rather than jittery,
- panels no longer feel visually exhausting after several minutes of use,
- asset, playback, style, and export workflows feel clearly separated,
- binary controls feel like intentional switches, not generic forms,
- the app looks like a creator tool, not an internal debug panel.

## Recommended First Implementation Priorities

If implementation begins later, start in this order:

1. enlarge controls and text
2. debounce slider-driven preview updates
3. reorganize panel sections into cards or collapsibles
4. replace checkbox/dropdown patterns where better interaction models exist
5. refine theme and contrast

## Notes

- This document is intentionally detailed so future implementation can happen in planned phases.
- The recommendations target `python_app/main.py` first, because that file currently defines most of the UI structure and widget styling.
- The best result will come from combining visual cleanup with interaction-behavior cleanup.
