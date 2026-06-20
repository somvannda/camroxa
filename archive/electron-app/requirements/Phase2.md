# Phase 2 Requirements — Advanced Visual System & Effects Engine

&#x20;

Phase 1 built:

- core renderer
- FFT analyzer
- circular spectrum
- MP4 export

Phase 2 transforms the engine from:

```
```

```
basic audio visualizer
```

into:

# cinematic music visualizer engine

This phase introduces:

- &#x20;layered rendering&#x20;
- &#x20;blending&#x20;
- &#x20;effects&#x20;
- &#x20;particles&#x20;
- &#x20;automations&#x20;
- &#x20;professional motion graphics architecture&#x20;

***

# PHASE 2 GOAL

By end of Phase 2:

The engine should support:

✅ Multi-layer spectrums\
&#x20;✅ Glow/Bloom\
&#x20;✅ RGB split\
&#x20;✅ Particles\
&#x20;✅ Blend modes\
&#x20;✅ Opacity\
&#x20;✅ Audio-reactive effects\
&#x20;✅ Automation bindings\
&#x20;✅ Reusable templates\
&#x20;✅ Cinematic visuals

***

# PHASE 2 SCOPE

## INCLUDED

✅ Layer system\
&#x20;✅ Blend modes\
&#x20;✅ Opacity system\
&#x20;✅ Post-processing\
&#x20;✅ Bloom\
&#x20;✅ RGB split\
&#x20;✅ Particle engine\
&#x20;✅ Audio-reactive particles\
&#x20;✅ Camera shake\
&#x20;✅ Automation system\
&#x20;✅ Multi-layer spectrum\
&#x20;✅ Better template system

***

## EXCLUDED (Later Phases)

❌ Web UI\
&#x20;❌ Live editor\
&#x20;❌ Drag/drop node editor\
&#x20;❌ Multiplayer/cloud rendering\
&#x20;❌ Marketplace\
&#x20;❌ GPU shaders (Phase 3)\
&#x20;❌ WebGL migration

***

# 1. OBJECT LAYER SYSTEM

This is the MOST important Phase 2 feature.

***

# Requirements

All renderable objects must support layers.

Each layer must support:

Property

Type

opacity

float

blend\_mode

string

enabled

bool

z\_index

int

***

# Layer Render Order

Renderer must sort layers by:

zlower→zhigherz\_{lower} \rightarrow z\_{higher}zlower​→zhigher​

before rendering.

***

# Example

```
```

```
{
  "layers": [
    {
      "type": "background",
      "z_index": 0
    },

    {
      "type": "spectrum",
      "z_index": 10
    }
  ]
}
```

***

# 2. BLEND MODE SYSTEM

Renderer must support professional compositing.

***

# Required Blend Modes

Mode

Purpose

normal

standard rendering

additive

glow/light

alpha

transparency

screen

neon effects

multiply

shadows

overlay

contrast

***

# Blend Formula Examples

## Additive

Cfinal=Cbg+Clayer⋅opacityC\_{final}=C\_{bg}+C\_{layer}\cdot opacityCfinal​=Cbg​+Clayer​⋅opacity

***

## Alpha Blend

Cfinal=(1−α)Cbg+αClayerC\_{final}=(1-\alpha)C\_{bg}+\alpha C\_{layer}Cfinal​=(1−α)Cbg​+αClayer​

***

# Requirements

Every render object must support:

- &#x20;opacity&#x20;
- &#x20;blend mode&#x20;
- &#x20;independent transparency&#x20;

***

# 3. MULTI-LAYER SPECTRUM SYSTEM

Phase 1 had:

- &#x20;single spectrum&#x20;

Phase 2 adds:

- &#x20;stacked visual passes&#x20;

***

# Required Spectrum Layers

Layer

Purpose

main

base spectrum

glow

blurred light

RGB offset

chromatic edges

shadow

dark depth

outline

outer highlight

***

# Requirements

Each spectrum layer must support:

Property

Type

color

RGB

opacity

float

thickness

float

blur

float

radius\_offset

float

blend\_mode

string

***

# Example

```
```

```
{
  "spectrum_layers": [
    {
      "type": "main",
      "color": "#ffffff"
    },

    {
      "type": "glow",
      "color": "#00ffff",
      "opacity": 0.5,
      "blend_mode": "additive"
    }
  ]
}
```

***

# 4. SPECTRUM MOTION IMPROVEMENTS

Spectrum motion must feel:

- &#x20;elastic&#x20;
- &#x20;fluid&#x20;
- &#x20;organic&#x20;

NOT jittery.

***

# Requirements

Add:

- &#x20;interpolation&#x20;
- &#x20;spring smoothing&#x20;
- &#x20;damping&#x20;
- &#x20;inertia&#x20;

***

# Suggested Formula

vcurrent=vcurrent+(vtarget−vcurrent)⋅smoothingv\_{current}=v\_{current}+(v\_{target}-v\_{current})\cdot smoothingvcurrent​=vcurrent​+(vtarget​−vcurrent​)⋅smoothing

***

# 5. POST-PROCESSING PIPELINE

Renderer must support:

- &#x20;full-screen effects&#x20;
- &#x20;multi-pass compositing&#x20;

***

# Render Pipeline

```
```

```
Render Scene
↓
Apply Bloom
↓
Apply RGB Split
↓
Apply Blur
↓
Final Composite
```

***

# Requirements

Effects must:

- &#x20;operate on framebuffer/surface&#x20;
- &#x20;support enable/disable&#x20;
- &#x20;support opacity/intensity&#x20;

***

# 6. BLOOM EFFECT

Bloom creates:

- &#x20;glow&#x20;
- &#x20;neon light&#x20;
- &#x20;cinematic energy&#x20;

***

# Requirements

Bloom pipeline:

```
```

```
Extract bright pixels
↓
Blur
↓
Additive blend back
```

***

# Configurable Settings

Property

Type

strength

float

blur\_radius

int

threshold

float

opacity

float

***

# 7. RGB SPLIT / CHROMATIC ABERRATION

Requirements:

- &#x20;separate RGB channels&#x20;
- &#x20;offset independently&#x20;
- &#x20;subtle cinematic distortion&#x20;

***

# Configurable Properties

Property

Type

red\_offset

vec2

green\_offset

vec2

blue\_offset

vec2

opacity

float

***

# 8. PARTICLE ENGINE

Particles create:

- &#x20;motion&#x20;
- &#x20;depth&#x20;
- &#x20;energy&#x20;

***

# Requirements

Particle system must support:

- &#x20;configurable count&#x20;
- &#x20;velocity&#x20;
- &#x20;acceleration&#x20;
- &#x20;lifetime&#x20;
- &#x20;fade out&#x20;
- &#x20;spawn rate&#x20;

***

# Particle Properties

Property

Type

position

vec2

velocity

vec2

size

float

opacity

float

color

RGB

lifetime

float

***

# 9. AUDIO-REACTIVE PARTICLES

Particles must react to audio.

***

# Requirements

Audio Source

Reaction

bass

velocity

mids

rotation

treble

brightness

beat

spawn burst

***

# 10. CAMERA SHAKE SYSTEM

Requirements:

- &#x20;subtle cinematic motion&#x20;
- &#x20;bass-reactive shake&#x20;
- &#x20;smooth interpolation&#x20;

***

# Configurable Properties

Property

Type

intensity

float

smoothing

float

frequency

float

***

# 11. AUTOMATION SYSTEM

MOST IMPORTANT Phase 2 system.

This creates:

- &#x20;reactive visuals&#x20;

***

# Requirements

Bind audio → property.

***

# Examples

Source

Target

bass

scale

beat

shake

treble

glow

mids

rotation

***

# Automation Structure

```
```

```
{
  "source": "bass",
  "target": "spectrum.scale",
  "multiplier": 1.4
}
```

***

# Requirements

Automation must support:

- &#x20;multiplier&#x20;
- &#x20;offset&#x20;
- &#x20;smoothing&#x20;
- &#x20;clamping&#x20;

***

# 12. PROPERTY ANIMATION SYSTEM

Properties should animate smoothly.

***

# Requirements

Support:

- &#x20;interpolation&#x20;
- &#x20;easing&#x20;
- &#x20;damping&#x20;
- &#x20;animation curves&#x20;

***

# 13. TEMPLATE SYSTEM EXPANSION

Phase 1 template:

- &#x20;basic settings only&#x20;

Phase 2:

- &#x20;full visual definitions&#x20;

***

# Requirements

Templates must support:

✅ Layers\
&#x20;✅ Effects\
&#x20;✅ Particles\
&#x20;✅ Automations\
&#x20;✅ Blend modes\
&#x20;✅ Opacity\
&#x20;✅ Camera settings

***

# Example

```
```

```
{
  "effects": {
    "bloom": {
      "enabled": true,
      "strength": 1.2
    }
  }
}
```

***

# 14. EFFECT ENABLE/DISABLE SYSTEM

Every effect/object must support:

```
```

```
{
  "enabled": true
}
```

Renderer skips disabled systems.

***

# 15. PERFORMANCE REQUIREMENTS

Phase 2 becomes heavier.

Requirements:

- &#x20;stable 60 FPS rendering&#x20;
- &#x20;memory-safe frame processing&#x20;
- &#x20;avoid unnecessary redraws&#x20;
- &#x20;support 5–10 minute songs&#x20;

***

# 16. RENDER PASSES

Renderer must support:

- &#x20;independent render passes&#x20;
- &#x20;compositing pipeline&#x20;

***

# Required Passes

Pass

Purpose

background

image

spectrum

geometry

particles

particles

effects

post-processing

final

export

***

# 17. OBJECT INHERITANCE SYSTEM

All visual objects must inherit from:

```
```

```
class VisualObject:
    def update(self, dt):
        pass

    def render(self, surface):
        pass
```

***

# 18. EFFECT BASE CLASS

All effects must inherit from:

```
```

```
class Effect:
    def apply(self, surface):
        pass
```

***

# 19. PHASE 2 SUCCESS CRITERIA

Phase 2 is COMPLETE when:

✅ Multiple spectrum layers render\
&#x20;✅ Blend modes work correctly\
&#x20;✅ Bloom creates glow\
&#x20;✅ RGB split works\
&#x20;✅ Particles react to music\
&#x20;✅ Camera shake works\
&#x20;✅ Automations bind correctly\
&#x20;✅ Templates fully configure visuals\
&#x20;✅ Visuals look cinematic

***

# 20. PHASE 2 NON-GOALS

DO NOT implement yet:

❌ Web UI\
&#x20;❌ Node editor\
&#x20;❌ Real-time editing\
&#x20;❌ Multiplayer/cloud\
&#x20;❌ GPU shaders\
&#x20;❌ WebGL\
&#x20;❌ Live preview editor

Those belong later.

***

# FINAL EXPECTED RESULT OF PHASE 2

Input:

```
```

```
song.mp3
template.json
background.jpg
```

***

Command:

```
```

```
python main.py song.mp3 template.json
```

***

Output:

With:

✅ glow\
&#x20;✅ particles\
&#x20;✅ layered spectrum\
&#x20;✅ bloom\
&#x20;✅ RGB split\
&#x20;✅ cinematic compositing\
&#x20;✅ audio-reactive motion
