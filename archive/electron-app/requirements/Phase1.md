# Phase 1 Requirements — Foundation & Core Architecture

&#x20;

This document defines ONLY Phase 1 of the project.

Goal of Phase 1:

# Build the foundation of the visualizer engine

NOT:

- advanced effects
- particles
- bloom
- web app
- GPU shaders
- batch rendering

Those come later.

***

# PHASE 1 GOAL

By the end of Phase 1, the app should:

```
```

```
Load MP3
↓
Analyze FFT audio
↓
Render simple circular spectrum
↓
Display background image
↓
Export MP4
```

That is the ONLY goal.

***

# PHASE 1 SCOPE

## INCLUDED

✅ Project structure\
&#x20;✅ Audio analyzer\
&#x20;✅ FFT processing\
&#x20;✅ Render loop\
&#x20;✅ Circular spectrum\
&#x20;✅ Background image\
&#x20;✅ PNG frame export\
&#x20;✅ MP4 export\
&#x20;✅ JSON template loading

***

## EXCLUDED (Later Phases)

❌ Bloom\
&#x20;❌ Particles\
&#x20;❌ RGB split\
&#x20;❌ Camera shake\
&#x20;❌ GPU shaders\
&#x20;❌ Web UI\
&#x20;❌ Drag/drop editor\
&#x20;❌ Batch rendering\
&#x20;❌ Multiprocessing\
&#x20;❌ Automation graph

***

# 1. PROJECT OVERVIEW

## Project Name

```
```

```
Python Audio Visualizer Engine
```

***

# 2. CORE OBJECTIVE

Create a:

# Headless Visualizer Renderer

The system should:

- &#x20;load audio&#x20;
- &#x20;analyze music frequencies&#x20;
- &#x20;generate audio-reactive visuals&#x20;
- &#x20;render video frames&#x20;
- &#x20;export final MP4&#x20;

WITHOUT requiring:

- &#x20;live editor&#x20;
- &#x20;GUI tools&#x20;
- &#x20;browser rendering&#x20;

***

# 3. TECH STACK

## Required Technologies

Purpose

Technology

Language

Python 3.11+

Audio analysis

librosa

Math

numpy

Rendering

pygame

Image loading

pillow

Video encoding

FFmpeg

Templates

JSON

***

# 4. PROJECT STRUCTURE

Required folder structure:

```
```

```
visualizer/
│
├── main.py
├── renderer.py
├── audio.py
├── config.py
│
├── objects/
│   └── spectrum.py
│
├── templates/
│   └── default.json
│
├── assets/
│   ├── music/
│   ├── backgrounds/
│   └── logos/
│
├── output/
│
└── frames/
```

***

# 5. DEPENDENCY REQUIREMENTS

Required Python packages:

```
```

```
pygame
librosa
numpy
pillow
opencv-python
```

***

# 6. AUDIO SYSTEM REQUIREMENTS

File:

```
```

```
audio.py
```

***

## Functional Requirements

The audio system must:

### 6.1 Load MP3 Files

Requirements:

- &#x20;support MP3 input&#x20;
- &#x20;load audio into memory&#x20;
- &#x20;extract sample rate&#x20;

***

### 6.2 FFT Analysis

Requirements:

- &#x20;perform Short-Time Fourier Transform (STFT)&#x20;
- &#x20;expose FFT frequency bins&#x20;
- &#x20;expose amplitude values&#x20;

***

### 6.3 Frequency Ranges

System must expose:

Range

Purpose

Bass

low frequencies

Mid

vocals/synth

Treble

highs

***

### 6.4 FFT Smoothing

Requirements:

- &#x20;reduce jitter&#x20;
- &#x20;smooth transitions&#x20;
- &#x20;stable animation&#x20;

Suggested smoothing:

vt=vt−1⋅s+vnew⋅(1−s)v\_t = v\_{t-1} \cdot s + v\_{new} \cdot (1-s)vt​=vt−1​⋅s+vnew​⋅(1−s)

Where:

- sss = smoothing factor&#x20;

***

### 6.5 Normalization

Requirements:

- &#x20;normalize FFT values between 0 and 1&#x20;
- &#x20;prevent clipping&#x20;
- &#x20;stable sensitivity&#x20;

***

# 7. RENDERER REQUIREMENTS

File:

```
```

```
renderer.py
```

***

## Functional Requirements

Renderer must:

### 7.1 Create Render Window

Requirements:

- &#x20;resolution: 1920x1080&#x20;
- &#x20;support 60 FPS&#x20;
- &#x20;support alpha transparency&#x20;

***

### 7.2 Render Loop

Must support:

```
```

```
update()
render()
save_frame()
```

executed every frame.

***

### 7.3 Frame Timing

Requirements:

- &#x20;stable frame progression&#x20;
- &#x20;sync visual timing with audio timing&#x20;

***

### 7.4 PNG Frame Export

Requirements:

- &#x20;save every frame as PNG&#x20;
- &#x20;sequential naming&#x20;

Example:

```
```

```
frame_00001.png
frame_00002.png
```

***

# 8. BACKGROUND SYSTEM REQUIREMENTS

Requirements:

- &#x20;load background image&#x20;
- &#x20;scale image to 1920x1080&#x20;
- &#x20;render behind spectrum&#x20;

Supported:

- &#x20;JPG&#x20;
- &#x20;PNG&#x20;

***

# 9. SPECTRUM SYSTEM REQUIREMENTS

File:

```
```

```
objects/spectrum.py
```

***

# Functional Requirements

***

## 9.1 Circular Spectrum

System must:

- &#x20;create radial spectrum&#x20;
- &#x20;use FFT amplitudes to deform circle&#x20;

***

## 9.2 Point-Based Geometry

Requirements:

- &#x20;generate configurable point count&#x20;
- &#x20;default: 256 points&#x20;

***

## 9.3 Radius Deformation

Spectrum deformation formula:

ri=rbase+ffti⋅strengthr\_i = r\_{base} + fft\_i \cdot strengthri​=rbase​+ffti​⋅strength

Where:

- rir\_iri​ = point radius&#x20;
- fftifft\_iffti​ = frequency amplitude&#x20;

***

## 9.4 Polar Conversion

Convert polar coordinates:

x=rcos⁡(θ),y=rsin⁡(θ)x = r\cos(\theta),\quad y = r\sin(\theta)x=rcos(θ),y=rsin(θ)

***

## 9.5 Smooth Shape Rendering

Requirements:

- &#x20;connected smooth outline&#x20;
- &#x20;avoid jagged spikes&#x20;
- &#x20;fluid motion&#x20;

***

## 9.6 Configurable Settings

Spectrum must support:

Property

Type

radius

float

thickness

float

color

RGB

strength

float

smoothing

float

point\_count

int

***

# 10. TEMPLATE SYSTEM REQUIREMENTS

File:

```
```

```
config.py
```

***

# Functional Requirements

***

## 10.1 JSON Template Loading

Load settings from:

```
```

```
templates/default.json
```

***

## 10.2 Template Settings

Template must support:

```
```

```
{
  "background": "background.jpg",

  "spectrum": {
    "radius": 240,
    "strength": 120,
    "color": [255,255,255],
    "thickness": 4,
    "point_count": 256
  }
}
```

***

## 10.3 Default Fallbacks

Requirements:

- &#x20;fallback defaults if values missing&#x20;
- &#x20;prevent crashes&#x20;

***

# 11. MAIN APPLICATION REQUIREMENTS

File:

```
```

```
main.py
```

***

# Functional Requirements

***

## 11.1 App Flow

Required execution flow:

```
```

```
Load template
↓
Load audio
↓
Initialize renderer
↓
Process FFT frames
↓
Render spectrum
↓
Export PNG frames
↓
Combine into MP4
```

***

## 11.2 Command Line Usage

Application must support:

```
```

```
python main.py song.mp3 template.json
```

***

# 12. VIDEO EXPORT REQUIREMENTS

***

## 12.1 FFmpeg Integration

Use FFmpeg to combine:

- &#x20;PNG frames&#x20;
- &#x20;MP3 audio&#x20;

into:

- &#x20;H264 MP4&#x20;

***

## 12.2 Export Settings

Required output:

- &#x20;1920x1080&#x20;
- &#x20;60 FPS&#x20;
- &#x20;yuv420p pixel format&#x20;

***

## 12.3 Output File

Example:

```
```

```
output/song_name.mp4
```

***

# 13. PERFORMANCE REQUIREMENTS

Requirements:

- &#x20;stable rendering&#x20;
- &#x20;no frame skipping&#x20;
- &#x20;support 3–5 minute songs&#x20;
- &#x20;manageable RAM usage&#x20;

***

# 14. CODE ARCHITECTURE REQUIREMENTS

System must be:

Requirement

Description

Modular

separate systems

Reusable

future templates

Expandable

future effects

Config-driven

JSON templates

Maintainable

clean architecture

***

# 15. PHASE 1 SUCCESS CRITERIA

Phase 1 is COMPLETE when:

✅ MP3 loads successfully\
&#x20;✅ FFT reacts correctly\
&#x20;✅ Circular spectrum animates smoothly\
&#x20;✅ Background image displays\
&#x20;✅ Frames export correctly\
&#x20;✅ MP4 exports successfully\
&#x20;✅ Template JSON controls appearance

***

# 16. IMPORTANT LIMITATIONS

Phase 1 intentionally DOES NOT include:

Feature

Reason

Bloom

later

Particles

later

GPU rendering

later

Automation system

later

Blend modes

later

Web interface

later

Keep Phase 1 SMALL and stable.

***

# 17. FINAL DELIVERABLE

Expected final result for Phase 1:

## Input

```
```

```
song.mp3
background.jpg
template.json
```

***

## Command

```
```

```
python main.py song.mp3 template.json
```

***

## Output

```
```

```
output/song.mp4
```

Containing:

- &#x20;background image&#x20;
- &#x20;smooth circular audio spectrum&#x20;
- &#x20;synchronized audio reaction&#x20;
- &#x20;exported HD video

