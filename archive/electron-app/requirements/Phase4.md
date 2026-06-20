# Phase 4 Requirements — Professional Editor, Node System & Visual Composer

&#x20;

Phase 1 built:

- core renderer
- FFT
- spectrum
- export system

Phase 2 built:

- effects
- particles
- automations
- compositing

Phase 3 built:

- GPU renderer
- shaders
- realtime preview
- advanced rendering pipeline

***

# Phase 4 transforms the engine into:

# Full Professional Visual Composer Platform

This is where the system becomes:

- Vizzy.io-like
- TouchDesigner-like
- Unreal Blueprint-like
- Node-based motion graphics software

This phase introduces:

- visual editor
- node graph
- timeline
- live editing
- reusable presets
- drag/drop workflow
- professional composition tools

***

# PHASE 4 GOAL

By the end of Phase 4:

The app should support:

✅ Visual node editor\
✅ Drag/drop objects\
✅ Live preview editing\
✅ Timeline system\
✅ Automation graph editor\
✅ Layer stack UI\
✅ Preset system\
✅ Realtime parameter editing\
✅ Save/load projects\
✅ Template browser\
✅ Professional editor workflow\
✅ Multi-scene projects

***

# PHASE 4 SCOPE

## INCLUDED

✅ Desktop editor UI\
✅ Node graph system\
✅ Timeline editor\
✅ Property inspector\
✅ Layer hierarchy\
✅ Live editing\
✅ Scene serialization\
✅ Preset browser\
✅ Keyframe system\
✅ Project system\
✅ Asset browser\
✅ Editor camera controls

***

## EXCLUDED (Later Phases)

❌ Cloud collaboration\
❌ Marketplace backend\
❌ Browser SaaS version\
❌ AI generation systems\
❌ Distributed rendering farm\
❌ Mobile version

***

# 1. EDITOR ARCHITECTURE

Phase 1–3:

- headless rendering engine

Phase 4:

- professional editor application

***

# Required Separation

System

Responsibility

Engine Core

rendering/audio

Editor UI

editing workflow

Runtime

playback

Serialization

save/load

STRICT separation required.

***

# 2. DESKTOP APPLICATION FRAMEWORK

Recommended:

Purpose

Technology

UI Framework

PySide6 / Qt

GPU Viewport

OpenGL widget

Backend

existing engine

State Management

editor controller

***

# Requirements

Editor must support:

- dockable panels
- resizable windows
- GPU viewport
- realtime interaction

***

# 3. NODE GRAPH SYSTEM

MOST IMPORTANT Phase 4 feature.

***

# Goal

Create:

- visual automation/effect graph

Similar to:

- Unreal Blueprints
- Blender nodes
- TouchDesigner
- Notch

***

# Requirements

Node graph must support:

✅ Drag/drop nodes\
✅ Connectable ports\
✅ Value propagation\
✅ Dependency ordering\
✅ Realtime updates

***

# Required Node Types

Node Type

Purpose

Audio Node

FFT data

Spectrum Node

geometry

Effect Node

bloom/RGB

Automation Node

property binding

Math Node

calculations

Camera Node

movement

Particle Node

particles

Output Node

final render

***

# Node Structure

```
```

```
class Node:
    inputs = []
    outputs = []

    def evaluate(self):
        pass
```

***

# 4. NODE CONNECTION SYSTEM

Requirements:

- &#x20;connect outputs → inputs&#x20;
- &#x20;type validation&#x20;
- &#x20;cycle prevention&#x20;
- &#x20;execution ordering&#x20;

***

# Example

```
```

```
Bass Analyzer
↓
Multiply Node
↓
Bloom Intensity
```

***

# 5. REALTIME PROPERTY INSPECTOR

Requirements:

- &#x20;live property editing&#x20;
- &#x20;instant viewport updates&#x20;
- &#x20;grouped properties&#x20;
- &#x20;searchable controls&#x20;

***

# Editable Properties

Property

Editable

color

YES

opacity

YES

blend mode

YES

particle count

YES

bloom intensity

YES

***

# 6. TIMELINE SYSTEM

Professional timeline editor.

***

# Requirements

Timeline must support:

✅ Keyframes\
&#x20;✅ Scrubbing\
&#x20;✅ Playback controls\
&#x20;✅ Zooming\
&#x20;✅ Track organization\
&#x20;✅ Multi-layer animation

***

# Timeline Features

Feature

Required

play

YES

pause

YES

stop

YES

frame stepping

YES

timeline zoom

YES

***

# 7. KEYFRAME ANIMATION SYSTEM

Requirements:

- &#x20;property animation&#x20;
- &#x20;interpolation&#x20;
- &#x20;easing curves&#x20;
- &#x20;bezier curves&#x20;

***

# Example

```
```

```
Frame 0 → bloom 0.2
Frame 120 → bloom 1.5
```

***

# 8. LAYER STACK UI

Requirements:

- &#x20;Photoshop-style layer panel&#x20;
- &#x20;visibility toggle&#x20;
- &#x20;reordering&#x20;
- &#x20;lock/unlock&#x20;
- &#x20;grouping&#x20;

***

# Layer Properties

Property

Required

visible

YES

opacity

YES

blend mode

YES

locked

YES

***

# 9. SCENE SYSTEM

Phase 4 introduces:

- &#x20;multiple scenes/compositions&#x20;

***

# Requirements

Scene system must support:

- &#x20;multiple compositions&#x20;
- &#x20;scene switching&#x20;
- &#x20;scene serialization&#x20;

***

# Example

```
```

```
Project
├── Intro Scene
├── Main Drop Scene
└── Outro Scene
```

***

# 10. PROJECT SAVE/LOAD SYSTEM

Requirements:

- &#x20;save complete projects&#x20;
- &#x20;restore editor state&#x20;
- &#x20;restore node graph&#x20;
- &#x20;restore timeline&#x20;

***

# Project Format

Recommended:

```
```

```
.project
```

JSON-based serialization.

***

# 11. ASSET MANAGEMENT SYSTEM

Requirements:

- &#x20;import assets&#x20;
- &#x20;organize assets&#x20;
- &#x20;thumbnail previews&#x20;
- &#x20;asset caching&#x20;

***

# Supported Assets

Asset

Support

PNG

YES

JPG

YES

MP3

YES

WAV

YES

Video

FUTURE

***

# 12. TEMPLATE/PRESET BROWSER

Requirements:

- &#x20;browse templates&#x20;
- &#x20;preview thumbnails&#x20;
- &#x20;duplicate presets&#x20;
- &#x20;save custom presets&#x20;

***

# Preset Categories

Category

Examples

EDM

neon/bass

Trap

dark

Phonk

car visuals

Anime

glow

Techno

minimal

***

# 13. LIVE VIEWPORT SYSTEM

Requirements:

- &#x20;realtime GPU preview&#x20;
- &#x20;editor overlays&#x20;
- &#x20;gizmos&#x20;
- &#x20;object selection&#x20;

***

# Viewport Features

Feature

Required

zoom

YES

pan

YES

selection

YES

transform handles

YES

***

# 14. GIZMO SYSTEM

Requirements:

- &#x20;move tool&#x20;
- &#x20;scale tool&#x20;
- &#x20;rotate tool&#x20;

Similar to:

- &#x20;Blender&#x20;
- &#x20;Unity&#x20;
- &#x20;Unreal&#x20;

***

# 15. EDITOR CAMERA SYSTEM

Requirements:

- &#x20;smooth movement&#x20;
- &#x20;zoom&#x20;
- &#x20;panning&#x20;
- &#x20;cinematic preview&#x20;

***

# 16. UNDO/REDO SYSTEM

CRITICAL feature.

***

# Requirements

Support:

- &#x20;property changes&#x20;
- &#x20;node edits&#x20;
- &#x20;layer edits&#x20;
- &#x20;timeline edits&#x20;

***

# 17. COMMAND SYSTEM

Requirements:

- &#x20;centralized editor commands&#x20;
- &#x20;undoable actions&#x20;
- &#x20;command history&#x20;

***

# Example

```
```

```
class Command:
    def execute(self):
        pass

    def undo(self):
        pass
```

***

# 18. AUDIO SCRUB SYSTEM

Requirements:

- &#x20;scrub timeline with audio&#x20;
- &#x20;realtime FFT update&#x20;
- &#x20;responsive seeking&#x20;

***

# 19. RENDER PREVIEW MODES

Requirements:

- &#x20;draft preview&#x20;
- &#x20;full quality preview&#x20;
- &#x20;low-resolution preview&#x20;

***

# 20. EXPORT UI

Requirements:

- &#x20;export dialog&#x20;
- &#x20;render settings&#x20;
- &#x20;FPS selection&#x20;
- &#x20;resolution selection&#x20;
- &#x20;codec selection&#x20;

***

# Export Targets

Output

Required

1080p

YES

4K

YES

60 FPS

YES

H264

YES

***

# 21. PLUGIN ARCHITECTURE

VERY important for scalability.

***

# Requirements

Support:

- &#x20;custom effects&#x20;
- &#x20;custom nodes&#x20;
- &#x20;external scripts&#x20;

***

# Plugin Structure

```
```

```
class Plugin:
    def register(self):
        pass
```

***

# 22. MULTI-THREADING REQUIREMENTS

Editor must:

- &#x20;separate UI thread&#x20;
- &#x20;render thread&#x20;
- &#x20;audio thread&#x20;

Prevent editor freezing.

***

# 23. STATE MANAGEMENT SYSTEM

Requirements:

- &#x20;centralized editor state&#x20;
- &#x20;selection state&#x20;
- &#x20;playback state&#x20;
- &#x20;project state&#x20;

***

# 24. AUTO-SAVE SYSTEM

Requirements:

- &#x20;periodic autosave&#x20;
- &#x20;crash recovery&#x20;
- &#x20;backup restoration&#x20;

***

# 25. PERFORMANCE REQUIREMENTS

Phase 4 targets:

Feature

Target

viewport FPS

60

realtime editing

smooth

node updates

realtime

timeline scrubbing

responsive

***

# 26. PHASE 4 SUCCESS CRITERIA

Phase 4 is COMPLETE when:

✅ Drag/drop editor works\
&#x20;✅ Node graph functions\
&#x20;✅ Timeline edits work\
&#x20;✅ Keyframes animate correctly\
&#x20;✅ Realtime viewport updates\
&#x20;✅ Save/load projects works\
&#x20;✅ Layer system works\
&#x20;✅ Presets/templates manageable\
&#x20;✅ Editor workflow feels professional

***

# 27. PHASE 4 NON-GOALS

DO NOT implement yet:

❌ Cloud collaboration\
&#x20;❌ Browser editor\
&#x20;❌ Marketplace backend\
&#x20;❌ AI generation\
&#x20;❌ Online accounts\
&#x20;❌ Distributed render farm

Those belong later.

***

# FINAL EXPECTED RESULT OF PHASE 4

The application should now behave like:

## Professional Motion Graphics Software

Similar to:

- &#x20;TouchDesigner&#x20;
- &#x20;Vizzy.io&#x20;
- &#x20;Notch&#x20;
- &#x20;Unreal Blueprint editor&#x20;
- &#x20;Blender compositor&#x20;

***

# FINAL USER WORKFLOW

```
```

```
Import MP3
↓
Choose template
↓
Edit nodes/effects live
↓
Adjust timeline
↓
Preview in realtime
↓
Export cinematic MP4
```

***

# FINAL EXPECTED UI
