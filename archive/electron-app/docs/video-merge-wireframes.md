# Video Merge — Visual Design (Wireframes)

These wireframes target the existing **Background** card (see [ThumbnailPanel.tsx](file:///d:/Development/Projects/Electron/MusicGenerator/src/components/dashboard/ThumbnailPanel.tsx)). The new feature uses the unused bottom space under the background image section.

## Screen 1 — Main (Background panel with Video Merge section)

```
┌──────────────────────────────────────────────────────────────┐
│ Background                                      [Res ▼] [↻]  │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │                   Background preview                      │ │
│ │                 (existing image area)                     │ │
│ └──────────────────────────────────────────────────────────┘ │
│  status text...                               [Generate Thumb]│
│  Sample: ... (optional)                                     │
│  Car: ...                                                   │
│  Template: ...                                              │
│                                                              │
│  Video Merge                                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Export settings                                         │  │
│  │ Resolution [1920×1080 ▼]   FPS [30 ▼]                   │  │
│  │ Codec [H.264 ▼]  Preset [fast ▼]  Quality (CRF) [20]    │  │
│  │ Audio [AAC ▼] Bitrate [192k ▼]                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Selected directories                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ D:\clips\set01                                 [Remove] │  │
│  │ D:\clips\set02                                 [Remove] │  │
│  │ D:\clips\set03                                 [Remove] │  │
│  │ ... (scrollable list)                                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [Select directories]                      [Merge Videos]     │
│                                                              │
│  Progress                                                    │
│  Merged 2 / 5 directories                                    │
│  [██████████░░░░░░░░░░░░░░░░░░]                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ set01  ✓ done     saved: ...\merged\merged_...mp4       │  │
│  │ set02  ✓ done     saved: ...\merged\merged_...mp4       │  │
│  │ set03  ▶ running  encoding...                            │  │
│  │ set04  • pending                                        │  │
│  │ set05  • pending                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Notes
- The “Video Merge” area can scroll internally if the panel height is constrained.
- Export settings are shown above the directory list so users set settings once and then merge.

## Screen 2 — Select directories flow (OS folder picker)

V1 uses the OS directory picker:
- Clicking **Select directories** opens folder picker
- User selects a folder
- App adds it to the list
- User can click **Select directories** again to add more folders

Optional v1 improvement:
- If platform supports multi-select folder picking in one dialog, we use it; otherwise repeated selection is OK.

## Screen 3 — Merge running (disabled controls)

```
Video Merge
Export settings (disabled while merging)
Selected directories (disabled remove while merging, or allow remove only for pending)

[Select directories] (disabled)   [Merge Videos] (disabled, shows "Merging...")
Progress updates live
```

## Screen 4 — Merge complete (summary)

```
Progress
Merged 5 / 5 directories
Completed with 1 error

Rows show ✓ done or ✗ failed with message.
[Merge Videos] becomes enabled again.
```

