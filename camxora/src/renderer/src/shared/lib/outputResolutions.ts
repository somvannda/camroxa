export type OutputResolutionOption = {
  value: string
  label: string
}

export const OUTPUT_RESOLUTION_OPTIONS: ReadonlyArray<OutputResolutionOption> = [
  { label: 'Landscape 720p (16:9) — 1280×720', value: '1280x720' },
  { label: 'Landscape 1080p (16:9) — 1920×1080', value: '1920x1080' },
  { label: 'Shorts/Reels (9:16) — 1080×1920', value: '1080x1920' },
  { label: 'Square (1:1) — 1080×1080', value: '1080x1080' },
  { label: 'Instagram Feed (4:5) — 1080×1350', value: '1080x1350' },
  { label: 'QHD (16:9) — 2560×1440', value: '2560x1440' },
  { label: '4K UHD (16:9) — 3840×2160', value: '3840x2160' },
]

