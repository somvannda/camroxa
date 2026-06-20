# Requirements Document

## Introduction

This feature adds two new automation toggles to the Music page's Automation card: **Auto Merge** and **Auto Reel**. Auto Merge gates the post-export merge step that currently runs unconditionally in the auto-video pipeline. Auto Reel produces additional 9:16 portrait (reel) videos using a separate reel template system, reusing the same background image generated for the batch.

## Glossary

- **Automation_Card**: The horizontal card in the Music page containing automation toggle buttons (Auto-Gen Image, Auto-GSuno, Auto-Video, Auto-Upload)
- **Auto_Video_Pipeline**: The automated workflow that exports MP4 videos from MP3 tracks after a Suno batch completes
- **Merge_Worker**: The component that concatenates multiple MP4 files into a single combined video using FFmpeg
- **Reel_Video**: A video rendered in 9:16 portrait format (1080×1920) intended for short-form platforms
- **Reel_Template**: A video template configured for 9:16 portrait rendering, stored in the same table as video templates but distinguished by a kind field
- **Video_Template**: A JSON configuration defining visual layout for video rendering (stored in video_templates table)
- **Profile**: A named configuration set containing template mappings, logo paths, and output settings
- **Music_Settings**: The persisted key-value settings store for the Music page
- **Channel_Plan**: The resolved set of inputs (template, background, MP3 list, output directory) for one auto-video export run

## Requirements

### Requirement 1: Auto Merge Toggle in Automation Card

**User Story:** As a music producer, I want to control whether exported MP4 files are automatically merged after the auto-video pipeline completes, so that I can choose between individual track videos or a single combined video.

#### Acceptance Criteria

1. THE Automation_Card SHALL display an "Auto Merge" toggle button positioned after the "Auto-Video" toggle and before the "Auto-Upload" toggle
2. WHEN the Auto Merge toggle is clicked, THE Music_Settings SHALL persist the `autoMergeAfterVideo` boolean value immediately
3. WHEN the Music page loads, THE Automation_Card SHALL restore the Auto Merge toggle state from the persisted `autoMergeAfterVideo` setting, defaulting to false when no persisted value exists
4. IF the `autoMergeAfterVideo` setting cannot be read from persistence, THEN THE Automation_Card SHALL display the Auto Merge toggle in the off (false) state

### Requirement 2: Auto Merge Gating of Post-Export Merge

**User Story:** As a music producer, I want the auto-video pipeline to skip the merge step when Auto Merge is off, so that I only get individual track MP4 files without the time-consuming concatenation.

#### Acceptance Criteria

1. WHILE `autoMergeAfterVideo` is true, THE Auto_Video_Pipeline SHALL invoke the Merge_Worker to concatenate all exported MP4 files for the channel into a single merged video after all individual MP4 exports for that channel have completed successfully
2. WHILE `autoMergeAfterVideo` is false, THE Auto_Video_Pipeline SHALL skip the merge step and emit the `auto_video_done` event with the `output` field set to an empty string
3. THE Auto_Video_Pipeline SHALL read only the `autoMergeAfterVideo` setting to decide whether to merge, and SHALL NOT read or be affected by the `videoAutoMergeMp4` setting used by the manual Video Export section
4. IF `autoMergeAfterVideo` is true AND the Merge_Worker fails during concatenation, THEN THE Auto_Video_Pipeline SHALL emit the `auto_video_done` event with the `output` field set to an empty string and SHALL emit a status message indicating the merge failure reason

### Requirement 3: Auto Reel Toggle in Automation Card

**User Story:** As a music producer, I want to automatically generate 9:16 portrait reel videos alongside the standard 16:9 landscape videos, so that I can produce short-form content without manual re-exports.

#### Acceptance Criteria

1. THE Automation_Card SHALL display an "Auto Reel" toggle button positioned after the "Auto Merge" toggle
2. WHEN the Auto Reel toggle is clicked, THE Music_Settings SHALL persist the `autoReelAfterVideo` boolean value
3. WHEN the Music page loads, THE Automation_Card SHALL restore the Auto Reel toggle state from the persisted `autoReelAfterVideo` setting

### Requirement 4: Reel Video Export in Auto-Video Pipeline

**User Story:** As a music producer, I want the auto-video pipeline to produce a 9:16 reel MP4 for each track when Auto Reel is enabled, so that I get portrait-format videos without additional manual steps.

#### Acceptance Criteria

1. WHILE `autoReelAfterVideo` is true, WHEN the standard 16:9 export completes for all tracks in the batch, THE Auto_Video_Pipeline SHALL render one 9:16 MP4 for each MP3 track before proceeding to the merge stage
2. THE Auto_Video_Pipeline SHALL render reel videos at a fixed resolution of 1080 pixels wide by 1920 pixels tall
3. THE Auto_Video_Pipeline SHALL use the same background image from the batch image_jobs table for reel rendering as used for the standard video
4. THE Auto_Video_Pipeline SHALL resolve the reel template from the Profile's `reelTemplateId` field
5. IF the Profile has no `reelTemplateId` configured, THEN THE Auto_Video_Pipeline SHALL skip reel generation for that channel and emit a warning status message indicating the missing reel template
6. WHILE `autoReelAfterVideo` is false, THE Auto_Video_Pipeline SHALL skip reel video generation entirely
7. IF a reel render fails for an individual track, THEN THE Auto_Video_Pipeline SHALL log the failure, skip that track's reel output, and continue rendering reels for the remaining tracks

### Requirement 5: Reel Merge When Both Toggles Active

**User Story:** As a music producer, I want reel videos to be merged into a single combined reel when both Auto Merge and Auto Reel are enabled, so that I get a full-length portrait video alongside the merged landscape video.

#### Acceptance Criteria

1. WHILE `autoMergeAfterVideo` is true AND `autoReelAfterVideo` is true AND 2 or more reel MP4 files exist, THE Merge_Worker SHALL concatenate all reel MP4 files in the same track order used for the standard 16:9 merge into a separate merged reel video named `MERGED_REEL_{role}_{suffix}.mp4`
2. WHILE `autoMergeAfterVideo` is true AND `autoReelAfterVideo` is true AND fewer than 2 reel MP4 files exist, THE Merge_Worker SHALL skip the reel merge step and retain the single reel file as-is without producing a `MERGED_REEL_` output
3. WHILE `autoMergeAfterVideo` is false AND `autoReelAfterVideo` is true, THE Auto_Video_Pipeline SHALL produce individual reel MP4 files without merging them
4. THE Merge_Worker SHALL execute the reel merge as a separate operation from the standard 16:9 merge such that failure of one does not prevent completion of the other
5. IF the reel merge operation fails, THEN THE Merge_Worker SHALL emit a warning status message indicating the reel merge failure and SHALL preserve all individual reel MP4 files

### Requirement 6: Reel Template Kind Field in Video Templates

**User Story:** As a music producer, I want reel templates to coexist with video templates in the same storage system, so that I can manage both template types through a unified interface.

#### Acceptance Criteria

1. THE video_templates table SHALL include a `kind` column with values "video" or "reel" and a default value of "video"
2. WHEN listing templates for the Profile video template selector, THE system SHALL filter to templates where kind equals "video"
3. WHEN listing templates for the Profile reel template selector, THE system SHALL filter to templates where kind equals "reel"
4. THE system SHALL preserve backward compatibility by defaulting existing templates without a kind value to "video"

### Requirement 7: Reel Template Selector in Profile Editor

**User Story:** As a music producer, I want to select a reel template for each profile, so that the auto-reel pipeline knows which visual layout to use for portrait videos.

#### Acceptance Criteria

1. THE Profile editor SHALL display a "Reel template" combo box positioned adjacent to the existing "Video template" combo box
2. THE "Reel template" combo box SHALL list templates from the video_templates table where kind equals "reel"
3. WHEN a reel template is selected, THE Profile SHALL persist the selection as the `reelTemplateId` field
4. WHEN a Profile is loaded, THE "Reel template" combo box SHALL restore the previously selected reel template

### Requirement 8: Reel Template CRUD Operations

**User Story:** As a music producer, I want to create, read, update, and delete reel templates using the same management interface as video templates, so that I have a consistent experience managing both template types.

#### Acceptance Criteria

1. THE system SHALL support creating reel templates with kind set to "reel" using the same CRUD operations as video templates
2. THE system SHALL support updating reel templates without affecting video templates
3. THE system SHALL support deleting reel templates without affecting video templates
4. WHEN a reel template is created, THE system SHALL store the template with uid, name, source, template JSON, kind, and timestamp fields

### Requirement 9: Profile reelTemplateId Field

**User Story:** As a music producer, I want each profile to store a reel template mapping, so that the auto-reel pipeline resolves the correct template per profile.

#### Acceptance Criteria

1. THE profiles table SHALL include a `reel_template_id` column of type text
2. THE Profile data model SHALL include a `reelTemplateId` field that maps to the reel_template_id column
3. WHEN a Profile is saved, THE system SHALL persist the `reelTemplateId` value to the database
4. WHEN a Profile is loaded, THE system SHALL read the `reelTemplateId` value from the database

### Requirement 10: Progress Page Stage Awareness for Reel Videos

**User Story:** As a music producer, I want the progress page to reflect the reel export and merge status alongside the standard video progress, so that I can monitor the full pipeline completion.

#### Acceptance Criteria

1. WHILE `autoReelAfterVideo` is true, THE Progress_Page SHALL include reel MP4 counts in the converter column display (e.g., "MP4 5/5 · Reel 5/5")
2. WHILE `autoReelAfterVideo` is true AND `autoMergeAfterVideo` is true, THE Progress_Page SHALL display the merged reel filename in the merge column alongside the standard merged filename
3. THE Progress_Page stage detection SHALL consider the reel export incomplete until all reel MP4 files are produced when Auto Reel is enabled
4. THE Progress_Page stage detection SHALL consider the merge stage incomplete until the reel merge completes when both Auto Merge and Auto Reel are enabled
5. THE `_scan_progress_output_dir` method SHALL detect reel MP4 files (identifiable by naming convention) separately from standard MP4 files

### Requirement 11: Auto-Video Done Event Propagation for Reel Outputs

**User Story:** As a music producer, I want the auto-video completion event to carry reel output information, so that downstream consumers (progress refresh, future Facebook upload) can react appropriately while keeping reel videos excluded from YouTube.

#### Acceptance Criteria

1. WHEN auto-video export completes with Auto Reel enabled, THE Auto_Video_Pipeline SHALL emit the done event with both the standard merged path and the reel merged path
2. THE Auto_Video_Pipeline SHALL exclude all reel video outputs (individual and merged) from the YouTube auto-upload flow regardless of the `autoUploadYouTube` setting (reel videos are intended for Facebook Reel upload via future browser automation)
3. THE done event SHALL include a `reelOutput` field containing the reel merged path or empty string
4. THE YouTube upload handler SHALL ignore the `reelOutput` field and only process the standard `output` path

### Requirement 12: Reel MP4 Output Naming Convention and Location

**User Story:** As a music producer, I want reel video files to be stored in the same output directory as standard videos with a clear naming convention, so that all outputs for a batch channel are co-located and distinguishable.

#### Acceptance Criteria

1. THE Auto_Video_Pipeline SHALL write reel MP4 files to the same output directory as the standard 16:9 MP4 files (no separate subdirectory)
2. THE Auto_Video_Pipeline SHALL name individual reel MP4 files with a `_REEL` suffix before the file extension (e.g., `trackname_REEL.mp4`)
3. THE Auto_Video_Pipeline SHALL name merged reel files with the pattern `MERGED_REEL_{role}_{suffix}.mp4`
4. THE Progress_Page output directory scan SHALL identify reel files by the `_REEL.mp4` suffix and merged reels by the `MERGED_REEL_` prefix
