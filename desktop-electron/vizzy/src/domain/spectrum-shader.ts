/**
 * Per-layer custom shaders for Spectrum (`colorType: "Shader"`).
 *
 * `shaderSrc` in the reference export is "raw GLSL" (see
 * `docs/REFERENCE-DATA-MODEL.md`); no concrete sample was available in the
 * exported project, so this module defines the contract we accept:
 *
 *   - The source is a **fragment body** and must define `void main()`.
 *   - Before it runs, the prelude below declares the standard uniforms, the
 *     `vUv` varying and the helpers the built-in renderer uses, so a layer
 *     shader can reuse `planar`, `ring`, `softCoverage`, `gradientColor`, etc.
 *   - The shader writes `gl_FragColor`. Its alpha is multiplied by the object
 *     opacity and the layer alpha, so layer-level opacity still applies.
 *
 * The uniform list here is deliberately a stable public surface: it does not
 * track additions to the built-in shader automatically, because exposing a new
 * uniform to user shaders is a contract change, not an implementation detail.
 *
 * Shader sources are data. They are never used to reach the filesystem, the
 * network or the DOM; they are only compiled by the GPU. A source that fails
 * to compile is rejected and the layer falls back to its solid colour.
 */

import * as THREE from "three";

/** Shared vertex stage; the fragment stage only ever reads `vUv`. */
export const SPECTRUM_VERTEX_SHADER = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

/**
 * Declarations and helpers available to a layer shader. Mirrors the built-in
 * renderer's uniforms so a custom shader can be a drop-in variant of it.
 */
const PRELUDE = /* glsl */ `
  precision highp float;
  uniform float uSpectrum[256];
  uniform float uWave[256];
  uniform float uBands;
  uniform float uType;      // 0 = bars, 1 = circle
  uniform float uDraw;      // 0 line, 1 curve, 2 plexus, 3 point
  uniform float uFill;      // 1 = fill, 0 = stroke
  uniform float uMirror;
  uniform float uColorShift;
  uniform float uGain;
  uniform float uOpacity;
  uniform float uAspect;
  uniform float uHeight;
  uniform float uDot;
  uniform float uFeather;
  uniform float uDownsample;
  uniform float uRotation;
  uniform float uScaleMul;
  uniform float uLayerScale;
  uniform float uLayerRotation;
  uniform float uLayerAlpha;
  uniform float uLayerGain;
  uniform float uColorType; // 0 = solid, 1 = gradient
  uniform vec3  uColorSolid;
  uniform float uColorMix;
  uniform vec3  uGrad0;
  uniform vec3  uGrad1;
  uniform vec3  uGrad2;
  uniform vec3  uGrad3;
  uniform float uGradCount;
  uniform float uBlur;
  uniform float uMean;
  uniform float uCeiling;
  uniform vec2  uTexPos;
  uniform vec2  uTexScale;
  uniform float uShadowOn;
  uniform float uShadowScale;
  uniform float uShadowAlpha;
  uniform vec3  uShadowColor;
  uniform vec2  uShadowOffset;
  uniform float uCircleSize;
  uniform vec3  uCircleColor;
  uniform float uFillCircle;
  uniform float uClipCircle;
  uniform float uConnect;
  uniform float uAA;
  uniform float uAspectFix;
  // Spectrum items measure their canvas in 1000-unit item space; the
  // reference's SkSL p is a point in that space, not a texture coordinate.
  uniform float u_itemSize;
  uniform sampler2D uImage;
  uniform float uHasImage;
  uniform float uImageSize;
  uniform float uCircularImage;
  uniform sampler2D uMask;
  varying vec2 vUv;

  float bandAt(float index) {
    return min(uSpectrum[int(clamp(index, 0.0, 255.0))], uCeiling);
  }

  float waveAt(float index) {
    return uWave[int(clamp(index, 0.0, 255.0))];
  }

  float rawBand(float i) {
    return bandAt(i * (256.0 / max(uBands, 2.0)));
  }

  float valueAt(float t) {
    float n = max(uBands / max(uDownsample, 1.0), 2.0);
    float idx = clamp(t, 0.0, 0.9999) * (n - 1.0);
    float i0 = floor(idx);
    float f = fract(idx);
    float a = rawBand(i0 * uDownsample);
    float b = rawBand(min(i0 + 1.0, n - 1.0) * uDownsample);
    return mix(a, b, f) * uGain * uLayerGain * uHeight;
  }

  float edge(float d) {
    float w = 0.004 + uFeather * 0.0009;
    return uAA > 0.5 ? smoothstep(w, 0.001, d) : step(d, w);
  }

  float planar(vec2 p) {
    float base = 0.08;
    float n = max(uBands / max(uDownsample, 1.0), 2.0);

    if (uDraw < 0.5) {
      float local = fract(clamp(p.x, 0.0, 0.9999) * n);
      float h = valueAt(p.x);
      return step(local, 0.68) * step(base, p.y) * step(p.y, base + h);
    }
    if (uDraw < 1.5) {
      float top = base + valueAt(p.x);
      return (uFill > 0.5)
        ? step(base, p.y) * step(p.y, top)
        : edge(abs(p.y - top));
    }
    if (uDraw < 2.5) {
      float idx = clamp(p.x, 0.0, 0.9999) * (n - 1.0);
      float i0 = floor(idx);
      float f = fract(idx);
      float y0 = base + rawBand(i0 * uDownsample) * uGain * uLayerGain * uHeight;
      float y1 = base + rawBand(min(i0 + 1.0, n - 1.0) * uDownsample) * uGain * uLayerGain * uHeight;
      return edge(abs(p.y - mix(y0, y1, f)));
    }

    float idx = clamp(p.x, 0.0, 0.9999) * n;
    float i0 = floor(idx);
    float local = fract(idx) - 0.5;
    float y = base + rawBand(i0 * uDownsample) * uGain * uLayerGain * uHeight;
    float af = mix(1.0, 2.25, uAspectFix);
    vec2 d = vec2(local * af / n, p.y - y);
    float bead = 1.0 - smoothstep(uDot, uDot + 0.006 + uFeather * 0.0009, length(d));

    if (uConnect < 0.5) return bead;
    float y1 = base + rawBand(min(i0 + 1.0, n - 1.0) * uDownsample) * uGain * uLayerGain * uHeight;
    return max(bead, edge(abs(p.y - mix(y, y1, fract(idx)))));
  }

  float ring(vec2 p) {
    float r = length(p);
    float a = atan(p.y, p.x) / 6.2831853 + 0.5;
    float n = max(uBands / max(uDownsample, 1.0), 2.0);
    // Image-filled circles read as filled discs in the reference.
    float inner = 0.16;
    float outer = inner + valueAt(a) * 0.45;

    // An image-backed circle is just the artwork disc.
    if (uHasImage > 0.5) {
      float radius = 0.5 * clamp(uImageSize, 0.05, 1.0) * (0.85 + 0.3 * uMean);
      return step(r, radius);
    }

    float bar;
    if (uDraw < 0.5) {
      float local = fract(a * n);
      bar = step(local, 0.68) * step(inner, r) * step(r, outer);
    } else if (uDraw < 1.5) {
      bar = (uFill > 0.5)
        ? step(inner, r) * step(r, outer)
        : edge(abs(r - outer));
    } else if (uDraw < 2.5) {
      bar = edge(abs(r - outer));
    } else {
      float idx = a * n;
      float i0 = floor(idx);
      float local = fract(idx) - 0.5;
      float rr = inner + rawBand(i0 * uDownsample) * uGain * uLayerGain * uHeight * 0.45;
      vec2 d = vec2(local * 6.2831853 * rr * 2.25 / n, r - rr);
      bar = 1.0 - smoothstep(uDot, uDot + 0.006 + uFeather * 0.0009, length(d));
    }

    // The image fills a fixed disc behind the bands.
    float imageDisc = (uHasImage > 0.5)
      ? step(r, 0.5 * clamp(uImageSize, 0.05, 1.0))
      : 0.0;
    float disc = (uFillCircle > 0.5) ? step(r, uCircleSize) : 0.0;
    float cov = max(max(bar, disc), imageDisc);
    if (uClipCircle > 0.5) cov *= step(r, uCircleSize);
    return cov;
  }

  vec3 hueShift(vec3 c, float h) {
    const vec3 k = vec3(0.57735);
    float cosA = cos(h);
    return c * cosA + cross(k, c) * sin(h) + k * dot(k, c) * (1.0 - cosA);
  }

  vec3 gradientColor(float t) {
    float shifted = clamp(t + (uColorMix - 0.5), 0.0, 1.0);
    if (uGradCount < 1.5) return uGrad0;
    float last = max(uGradCount - 1.0, 1.0);
    float s = shifted * last;
    if (s < 1.0) return mix(uGrad0, uGrad1, s);
    if (uGradCount < 2.5) return uGrad1;
    if (s < 2.0) return mix(uGrad1, uGrad2, s - 1.0);
    if (uGradCount < 3.5) return uGrad2;
    return mix(uGrad2, uGrad3, clamp(s - 2.0, 0.0, 1.0));
  }

  float shapeCoverage(vec2 q) {
    vec2 shape = q + 0.5;
    if (uMirror > 0.5 && uType < 0.5) {
      shape.x = abs(shape.x - 0.5) * 2.0;
    }
    return (uType < 0.5) ? planar(shape) : ring(vec2(q.x * uAspect, q.y));
  }

  float softCoverage(vec2 q) {
    if (uBlur <= 0.0001) return shapeCoverage(q);
    float radius = clamp(uBlur, 0.0, 1.0) * 0.08;
    float diagonal = radius * 0.70710678;
    float sum = shapeCoverage(q) * 2.0;
    sum += shapeCoverage(q + vec2(radius, 0.0));
    sum += shapeCoverage(q - vec2(radius, 0.0));
    sum += shapeCoverage(q + vec2(0.0, radius));
    sum += shapeCoverage(q - vec2(0.0, radius));
    sum += shapeCoverage(q + vec2(diagonal, diagonal));
    sum += shapeCoverage(q + vec2(-diagonal, diagonal));
    sum += shapeCoverage(q + vec2(diagonal, -diagonal));
    sum += shapeCoverage(q - vec2(diagonal, diagonal));
    return sum / 10.0;
  }

  // A custom layer shader colours the spectrum path, exactly like a Skia
  // Paint shader: the path coverage is applied outside the shader's own colour.
  float pathCoverage() {
    vec2 p = (vUv - 0.5) / max(uScaleMul * uLayerScale, 0.05);
    float c = cos(uRotation + uLayerRotation);
    float s = sin(uRotation + uLayerRotation);
    p = mat2(c, -s, s, c) * p;
    p = p / max(uTexScale, vec2(0.05)) + uTexPos;
    return softCoverage(p);
  }
`;

/**
 * Appended after the user body. Applies object opacity and layer alpha without
 * requiring the layer shader to know about them.
 */
const MAIN_WRAPPER = /* glsl */ `
  void main() {
    spectrumUserMain();
    gl_FragColor.a *= pathCoverage() * clamp(uOpacity * uLayerAlpha, 0.0, 1.0);
  }
`;

/** Same, for a `Shader` layer: the mask holds the decompiled path coverage. */
const MAIN_WRAPPER_MASKED = /* glsl */ `
  void main() {
    spectrumUserMain();
    gl_FragColor.a *= texture2D(uMask, vUv).a * clamp(uOpacity * uLayerAlpha, 0.0, 1.0);
  }
`;

/** Paint-only wrapper: the shader supplies colour, the caller supplies coverage. */
const MAIN_WRAPPER_PAINT = /* glsl */ `
  void main() {
    spectrumUserMain();
  }
`;

/** Matches the `void main()` entry point the layer shader must provide. */
const MAIN_PATTERN = /\bvoid\s+main\s*\(\s*(?:void\s*)?\)/;

/**
 * The reference stores SkSL (Skia runtime effects), not GLSL: its entry point is
 * `half4 main(float2 p)` and it uses `float2`/`half4` style type names. Detect
 * that dialect so it is translated instead of being rejected as broken GLSL.
 */
export function isSkSL(source: string): boolean {
  if (/\b(?:half|float)4\s+main\s*\(\s*(?:in\s+)?(?:half|float)2\s+\w+\s*\)/.test(source)) {
    return true;
  }
  return /\b(?:half|float)[234](?:x[234])?\b/.test(source);
}

/**
 * Translate the SkSL subset the reference uses into GLSL ES 1.00.
 *
 * Covers type aliases, the `half4 main(float2)` entry point (whose parameter is
 * the pixel coordinate, like `sk_FragCoord`) and its `return` into
 * `gl_FragColor`. Anything outside that subset is reported, not guessed at.
 */
export function skslToGlsl(
  source: string,
  masked = false,
  paint = false,
): { source: string; error: string | null } {
  let unsupported: string | null = null;
  source.replace(/\b(?:half|float)([234])x([234])\b/g, (match, columns, rows) => {
    if (columns !== rows) unsupported = `unsupported non-square matrix type ${match}`;
    return match;
  });
  if (unsupported) return { source: "", error: unsupported };

  // Matrices before vectors, so `float2x2` is not half-matched as `float2`.
  let translated = source
    .replace(/\b(?:half|float)([234])x\1\b/g, "mat$1")
    .replace(/\bhalf([234])\b/g, "vec$1")
    .replace(/\bfloat([234])\b/g, "vec$1")
    .replace(/\bint([234])\b/g, "ivec$1");

  // SkSL allows int literals in float arithmetic; GLSL ES does not. Promote
  // literals next to * or / so e.g. `M_PI*3*u_time` becomes `M_PI*3.0*u_time`
  // instead of failing to compile (rainbow-circle's Skia spectrum shader).
  translated = translated
    .replace(/(?<![A-Za-z0-9_.\]])(\d+)(?![A-Za-z0-9_.\]])(?=\s*[*\/])/g, "$1.0")
    .replace(/([*\/]\s*)(\d+)(?![A-Za-z0-9_.\]])(?!\s*\])/g, "$1$2.0");

  const main = /\bvec4\s+main\s*\(\s*(?:in\s+)?vec2\s+(\w+)\s*\)\s*\{/.exec(translated);  if (!main) {
    return { source: "", error: "SkSL shader must define half4 main(float2)" };
  }

  const start = main.index;
  const head = translated.slice(0, start);
  let body = translated.slice(start + main[0].length);

  // Main's `return` becomes the fragment colour; helper functions keep theirs.
  body = body.replace(/\breturn\s+([^;]+);/g, "gl_FragColor = $1;");
  const close = body.lastIndexOf("}");
  if (close < 0) return { source: "", error: "SkSL main() is not terminated" };

  const coverage = masked ? "texture2D(uMask, vUv).a" : "pathCoverage()";
  const withAlpha = paint
    ? body
    : `${body.slice(0, close)}  gl_FragColor.a *= ${coverage} * clamp(uOpacity * uLayerAlpha, 0.0, 1.0);\n` +
      body.slice(close);

  return {
    // The reference's SkSL `main(float2 p)` receives the local coordinate of
    // the path, i.e. the 1000-unit item canvas with (0,0) at the item centre.
    // `vUv` is the same point normalised; `gl_FragCoord` is surface pixels.
    source: `${head}void main() {\n  vec2 ${main[1]} = (vec2(vUv.x, 1.0 - vUv.y) - 0.5) * u_itemSize;\n${withAlpha}`,
    error: null,
  };
}


/**
 * The reference migrated spectrum shaders from `u_amt` to the two analyser
 * uniforms. `setShaderEffect` rewrites the declaration, then the first use,
 * only when the source has neither new uniform yet.
 */
function upgradeDeprecatedUniforms(source: string): string {
  if (source.includes("u_audio_cumulative") && source.includes("u_audio_current")) {
    return source;
  }
  return source
    .replace(
      "uniform float u_amt;",
      "uniform float u_audio_cumulative;\nuniform float u_audio_current;",
    )
    .replace("u_amt", "u_audio_cumulative");
}

/** Guards against absurd sources being compiled on the GPU. */
const MAX_SHADER_SOURCE = 64_000;

export interface SpectrumFragment {
  /** Complete fragment shader, or null when the layer must keep the built-in one. */
  source: string | null;
  /** Why the source was rejected, or null when it compiled or is still being checked. */
  error: string | null;
  /** True while the GPU check for a well-formed source is still in flight. */
  pending: boolean;
}

/**
 * Wrap `shaderSrc` in the layer-shader contract. Rejects sources that are empty,
 * oversized, carry their own `#version`, or never define `void main()`.
 */
export function wrapSpectrumFragment(
  shaderSrc: string,
  masked = false,
  paint = false,
): {
  source: string | null;
  error: string | null;
} {
  const trimmed = shaderSrc.trim();
  if (!trimmed) return { source: null, error: "shader source is empty" };
  if (trimmed.length > MAX_SHADER_SOURCE) {
    return { source: null, error: `shader source exceeds ${MAX_SHADER_SOURCE} characters` };
  }
  // Three supplies the #version directive; a second one is a compile error.
  if (/#version\b/.test(trimmed)) {
    return { source: null, error: "shader source must not contain #version" };
  }

  // Reference `setShaderEffect` migrates the deprecated `u_amt` uniform before
  // compiling: it rewrites the declaration and the first use.
  const upgraded = upgradeDeprecatedUniforms(trimmed);

  // The reference stores SkSL; translate it rather than treating it as GLSL.
  if (isSkSL(upgraded)) {
    const translated = skslToGlsl(upgraded, masked, paint);
    if (translated.error) return { source: null, error: translated.error };
    return { source: `${PRELUDE}\n${translated.source}`, error: null };
  }

  const renamed = upgraded.replace(MAIN_PATTERN, "void spectrumUserMain()");
  if (renamed === upgraded) {
    return { source: null, error: "shader source must define void main()" };
  }

  return {
    source: `${PRELUDE}\n${renamed}\n${
      paint ? MAIN_WRAPPER_PAINT : masked ? MAIN_WRAPPER_MASKED : MAIN_WRAPPER
    }`,
    error: null,
  };
}

/**
 * What a layer should render *this frame*. Compilation is asynchronous (three
 * links shaders through `KHR_parallel_shader_compile`), so a new source reports
 * `pending` until the GPU verdict is known; callers keep the built-in material
 * in the meantime and never hand an unverified shader to the renderer.
 */
export function buildSpectrumFragment(
  shaderSrc: string,
  masked = false,
  paint = false,
): SpectrumFragment {
  const wrapped = wrapSpectrumFragment(shaderSrc, masked, paint);
  if (!wrapped.source) return { source: null, error: wrapped.error, pending: false };

  const verdict = validationCache.get(wrapped.source);
  if (verdict === undefined) {
    void requestShaderValidation(wrapped.source);
    return { source: null, error: null, pending: true };
  }
  if (verdict === null) return { source: wrapped.source, error: null, pending: false };
  return { source: null, error: verdict, pending: false };
}

/** null = compiles, string = driver log, undefined = not checked yet. */
export function getShaderValidation(source: string): string | null | undefined {
  return validationCache.get(source);
}

/** Compiled sources only need checking once per session. */
const validationCache = new Map<string, string | null>();

const inFlight = new Set<string>();

let scratch: {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.OrthographicCamera;
} | null = null;

function scratchRenderer(): typeof scratch {
  if (scratch) return scratch;
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false });
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  scratch = { renderer, scene, camera };
  return scratch;
}

/**
 * Compile a candidate fragment shader with the renderer's own GLSL handling and
 * cache the verdict.
 *
 * The program must be rendered once, not just compiled: three waits for
 * `KHR_parallel_shader_compile`, and only checks link status when the program is
 * first used. Resolves with null when it compiles, otherwise the driver's log.
 */
export function requestShaderValidation(source: string): Promise<string | null> {
  const cached = validationCache.get(source);
  if (cached !== undefined) return Promise.resolve(cached);

  const context = scratchRenderer();
  if (!context) {
    const error = "shader validation is unavailable outside a browser";
    validationCache.set(source, error);
    return Promise.resolve(error);
  }

  if (inFlight.has(source)) {
    return new Promise((resolve) => {
      const poll = () => {
        const settled = validationCache.get(source);
        if (settled === undefined) setTimeout(poll, 16);
        else resolve(settled);
      };
      poll();
    });
  }
  inFlight.add(source);

  return (async () => {
    let log: string | null = null;
    const previous = context.renderer.debug.onShaderError;
    context.renderer.debug.onShaderError = (gl, program, vertexShader, fragmentShader) => {
      log = [
        gl.getProgramInfoLog(program),
        gl.getShaderInfoLog(fragmentShader),
        gl.getShaderInfoLog(vertexShader),
      ]
        .map((entry) => (entry ?? "").trim())
        .filter((entry) => entry.length > 0)
        .join("\n");
    };

    const material = new THREE.ShaderMaterial({
      vertexShader: SPECTRUM_VERTEX_SHADER,
      fragmentShader: source,
    });
    const geometry = new THREE.PlaneGeometry(2, 2);
    const mesh = new THREE.Mesh(geometry, material);
    context.scene.add(mesh);
    try {
      await context.renderer.compileAsync(context.scene, context.camera);
      context.renderer.render(context.scene, context.camera);
    } catch (failure) {
      log = `shader compile threw: ${(failure as Error).message}`;
    } finally {
      context.scene.remove(mesh);
      geometry.dispose();
      material.dispose();
      context.renderer.debug.onShaderError = previous;
      inFlight.delete(source);
    }

    validationCache.set(source, log ?? null);
    return log ?? null;
  })();
}

