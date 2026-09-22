# Camxora Studio (python_camxora)

A standalone, CapCut-style multi-track video editor desktop app, built with
Python + PySide6. Ported from a browser-based HTML/JS reference into a
native Qt application with a real ffmpeg export pipeline.

This app is fully independent from `camxora_python` (separate dependencies,
separate entry point, separate UI) — it lives in its own directory and
worktree/branch so it can evolve without touching the sibling desktop app.

## Features
- Multi-track timeline — unlimited Video, Audio, and Overlay (text/image) tracks
- Drag & drop media, text presets, and filters onto the timeline
- Clip editing — move, trim, split at playhead (`S`), duplicate, delete (`Del`)
- 8 built-in filters (Vivid, Noir, Warm, Cool, Faded, Dream, Cyberblue, Original)
- Text & titles — draggable position, color, size, fade in/out
- Music visualizer — Bars, Mirror Bars, Waveform, Radial, driven by precomputed audio spectra
- Transport — play/pause (`Space`), scrub bar, live timecode
- Export — renders the composited timeline + mixed audio via a single ffmpeg
  pass to MP4 (H.264/AAC), with a cancellable progress dialog. Reuses the
  exact same frame compositor as the live preview, so export is
  frame-accurate rather than a real-time screen recording.
- Project save/load — save the full timeline (tracks, clips, media
  references, filters, text, visualizer settings) to a `.camxora` JSON file
  and reopen it later
- Real undo/redo (`Ctrl+Z` / `Ctrl+Y` or `Ctrl+Shift+Z`), unlike the
  browser reference app which only stubs these out

## Keyboard shortcuts
| Shortcut | Action |
|---|---|
| `Space` | Play / pause |
| `S` | Split selected clip at playhead |
| `Delete` / `Backspace` | Delete selected clip |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo |
| `Ctrl+S` | Save project |
| `Ctrl+O` | Open project |

## Setup

```bash
cd python_camxora
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -e ".[dev]"
```

## Run

```bash
python -m app.main
```

## Test

```bash
pytest
```

## Structure

```
python_camxora/
  app/            # entry point, QSS theme
  core/           # data model, project state, undo/redo, time helpers,
                  # project save/load (.camxora JSON files)
  media/          # media import, video/audio decode, thumbnails, STFT
  render/         # compositor, filters, text renderer, visualizer draw routines
  audio/          # sounddevice-based playback mixer
  export/         # ffmpeg-based export pipeline
  ui/             # PySide6 widgets (topbar, library, preview, timeline, inspector)
  assets/         # icons
  tests/          # pytest suite
```
