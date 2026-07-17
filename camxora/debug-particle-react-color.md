[OPEN] Debug Session: particle-react-color

## Symptom
- Particle `React Color` does not visibly change during music reaction.

## Expected
- Particles visibly blend from `Color` → `React Color` as audio drive increases (sustained energy and/or trigger peaks).

## Reproduction
- Enable particles.
- Set `Color` to a strong base (e.g. #0000ff) and `React Color` to a contrasting color (e.g. #ff0000).
- Set `React Strength` to 1.0.
- Play an mp3 with strong bass/kick.

## Hypotheses (Falsifiable)
- A) Reactive drive is effectively ~0 in preview (reactiveEnv/triggerEnv never rises), so color mix remains near base.
- B) The template draft values are not the ones reaching the GPU runtime (react color / react strength not propagated).
- C) Uniform packing mismatch (CPU writes base/react colors, but shader reads different offsets).
- D) The particle layer draws, but post-fx / blend makes hue shift imperceptible (color changes numerically but not visually).
- E) The shader path never uses the reactive mix due to a branch or a constant value (reactStrength or colorMix becomes 0).

## Evidence To Collect (pre-fix)
- Particle runtime snapshot: base/react colors, reactStrength, reactiveEnv, triggerEnv.
- WebGPU uniform snapshot for particle pass: packed offsets for params and colors.
- Preview snapshot: draft values for particlesColor/particlesReactColor/particlesReactStrength at runtime.

## Status
- Next: Start debug server, instrument A/B/C observation points, reproduce once, analyze `.dbg/trae-debug-log-particle-react-color.ndjson`.

