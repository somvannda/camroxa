## Background Motion — Design

### Product Goal
Give the background image a more “alive” feel synced to music, without making the whole scene hard to read.

### User Goal
Boss can enable:
- Vibrate (shake) when the beat hits
- Zoom in/out when music reacts
and control the strength.

---

## UI/UX

### Location
- Python app → Video → Template Settings → Background tab.

### Controls
- Motion Mode:
  - None
  - Zoom
  - Vibrate
  - Both
- Zoom Strength (only when mode includes Zoom)
  - Range: 0.00 → 2.00
- Vibrate Strength (only when mode includes Vibrate)
  - Range: 0.00 → 2.00

### Behavioral Rules
- Motion affects **background only**.
- Uses the same audio envelope that background brightness reacts to (bass + a bit of kick), smoothed by Background Smoothness.
- Default is **None** so existing templates won’t suddenly change.

### States
- Mode = None: no motion.
- Mode = Zoom: only zoom.
- Mode = Vibrate: only shake.
- Mode = Both: both effects enabled.
