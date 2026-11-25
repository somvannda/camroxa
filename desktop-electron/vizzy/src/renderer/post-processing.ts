/**
 * Post-processing composer.
 *
 * Ported from the reference's manager: effects are an ordered list, each pass
 * renders into a ping-pong buffer, and the last pass writes to the screen (or to
 * a buffer when the caller wants to keep compositing). A pass is skipped when no
 * effect is active.
 */

import * as THREE from "three";
import { BLEND_MODES, type EffectInstance } from "../domain/effects";
import { CameraShakeTransform } from "../domain/camera-shake";

const VERTEX_SHADER = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const PRELUDE = /* glsl */ `
  precision highp float;
  uniform sampler2D tDiffuse;
  uniform vec2 uResolution;
  varying vec2 vUv;

  // Scene buffers hold premultiplied colour, and the reference composites with
  // ONE / ONE_MINUS_SRC_ALPHA, so effects reason about straight colour and
  // premultiply again on output. Without this a pass that brightens a
  // transparent pixel adds its colour to the frame beneath it.
  vec4 straight(vec2 uv) {
    vec4 colour = texture2D(tDiffuse, uv);
    return colour.a > 0.0001
      ? vec4(colour.rgb / colour.a, colour.a)
      : vec4(0.0, 0.0, 0.0, colour.a);
  }
`;

interface TimeStopHistory {
  width: number;
  height: number;
  targets: THREE.WebGLRenderTarget[];
  writeIndex: number;
  framesCaptured: number;
  lastTime: number | null;
}

interface JfaResources {
  width: number;
  height: number;
  targets: [THREE.WebGLRenderTarget, THREE.WebGLRenderTarget];
}

interface BloomResources {
  sourceWidth: number;
  sourceHeight: number;
  bright: THREE.WebGLRenderTarget;
  horizontal: THREE.WebGLRenderTarget[];
  vertical: THREE.WebGLRenderTarget[];
}

const TRANSFORM_BLEND_EQUATIONS: Record<string, THREE.BlendingEquation> = {
  Add: THREE.AddEquation,
  Subtract: THREE.SubtractEquation,
  "Reverse subtract": THREE.ReverseSubtractEquation,
  Min: THREE.MinEquation,
  Max: THREE.MaxEquation,
};

const TRANSFORM_BLEND_FACTORS: Record<string, THREE.BlendingDstFactor> = {
  Zero: THREE.ZeroFactor,
  One: THREE.OneFactor,
  // The reference maps SrcColor and OneMinusDstAlpha to these factors.
  SrcColor: THREE.SrcAlphaFactor,
  OneMinusSrcColor: THREE.OneMinusSrcColorFactor,
  SrcAlpha: THREE.SrcAlphaFactor,
  OneMinusSrcAlpha: THREE.OneMinusSrcAlphaFactor,
  DstAlpha: THREE.DstAlphaFactor,
  OneMinusDstAlpha: THREE.OneMinusSrcAlphaFactor,
  DstColor: THREE.DstColorFactor,
  OneMinusDstColor: THREE.OneMinusDstColorFactor,
};

const SHADERS: Record<string, string> = {
  "color-tint": /* glsl */ `
    uniform float uAmount;
    uniform float uWeight;
    uniform float uInvert;
    uniform vec3 uMapBlack;
    uniform vec3 uMapWhite;
    void main() {
      vec4 src = straight(vUv);
      float lum = clamp(dot(src.rgb, vec3(0.2126, 0.7152, 0.0722)) * uWeight, 0.0, 1.0);
      if (uInvert > 0.5) lum = 1.0 - lum;
      vec3 mapped = mix(uMapBlack, uMapWhite, lum);
      vec3 result = mix(src.rgb, mapped, clamp(uAmount, 0.0, 1.0));
      gl_FragColor = vec4(result * src.a, src.a);
    }
  `,
  invert: /* glsl */ `
    uniform float uAmount;
    void main() {
      vec4 src = straight(vUv);
      vec3 result = mix(src.rgb, 1.0 - src.rgb, clamp(uAmount, 0.0, 1.0));
      gl_FragColor = vec4(result * src.a, src.a);
    }
  `,
  pixelate: /* glsl */ `
    uniform float uAmount;
    void main() {
      vec2 blocks = max(vec2(uAmount), vec2(1.0));
      vec2 uv = (floor(vUv * blocks) + 0.5) / blocks;
      vec4 src = straight(uv);
      gl_FragColor = vec4(src.rgb * src.a, src.a);
    }
  `,
  "chromatic-aberration": /* glsl */ `
    // Reference main~56930160.81d4160c.chunk.js @36283 (the shipped
    // chromatic-aberration shader). The displacement is *radial* Ã¢â‚¬â€ it scales with
    // 0.7 * length(dir) from the centre Ã¢â‚¬â€ and the two channels divide by
    // different resolution components, so the fringe grows towards the edges and
    // the centre of the frame keeps a clean white.
    uniform float uX;
    uniform float uY;

    #define delta vec2(uX * 10.0, uY * 10.0)

    void main() {
      vec2 uv = gl_FragCoord.xy / uResolution;
      vec2 dir = vUv - vec2(0.5);
      float d = 0.7 * length(dir);
      vec2 value = d * dir * delta;

      vec4 c1 = texture2D(tDiffuse, uv - value / uResolution.x);
      vec4 c2 = texture2D(tDiffuse, uv);
      vec4 c3 = texture2D(tDiffuse, uv + value / uResolution.y);

      gl_FragColor = vec4(c1.r, c2.g, c3.b, c1.a + c2.a + c3.b);
    }
  `,
  "box-blur": /* glsl */ `
    uniform float uRadius;
    uniform float uPasses;
    void main() {
      // One 3x3 tap per fragment; repeated reference passes widen the kernel.
      vec2 texel = (uRadius * sqrt(max(uPasses, 1.0))) / uResolution;
      float alpha = texture2D(tDiffuse, vUv).a;
      vec3 sum = vec3(0.0);
      for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
          sum += straight(vUv + vec2(float(x), float(y)) * texel).rgb;
        }
      }
      gl_FragColor = vec4(sum / 9.0 * alpha, alpha);
    }
  `,
  // Shipped BoxBlur (module 1289) horizontal/vertical modules 492/493. Each
  // pass averages nine taps spread `radius * 0.0005` across the frame (the
  // horizontal span is divided by the frame aspect), and the raw premultiplied
  // RGBA goes through unweighted.
  "box-blur-horizontal": /* glsl */ `
    uniform float uRadius;
    void main() {
      float hh = uRadius * 0.002 / 4.0;
      float hx = hh / (uResolution.x / uResolution.y);
      vec4 sum = vec4(0.0);
      sum += texture2D(tDiffuse, vec2(vUv.x - 4.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x - 3.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x - 2.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x - 1.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vUv);
      sum += texture2D(tDiffuse, vec2(vUv.x + 1.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x + 2.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x + 3.0 * hx, vUv.y));
      sum += texture2D(tDiffuse, vec2(vUv.x + 4.0 * hx, vUv.y));
      gl_FragColor = sum / 9.0;
    }
  `,
  "box-blur-vertical": /* glsl */ `
    uniform float uRadius;
    void main() {
      float hh = uRadius * 0.002 / 4.0;
      vec4 sum = vec4(0.0);
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 4.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 3.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 2.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 1.0 * hh));
      sum += texture2D(tDiffuse, vUv);
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 1.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 2.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 3.0 * hh));
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 4.0 * hh));
      gl_FragColor = sum / 9.0;
    }
  `,
  bloom: /* glsl */ `
    uniform float uThreshold;
    uniform float uIntensity;
    void main() {
      vec4 src = straight(vUv);
      float lum = dot(src.rgb, vec3(0.2126, 0.7152, 0.0722));
      vec3 added = vec3(0.0);
      if (lum > uThreshold) {
        // Wide enough to read as a glow rather than an edge fringe; the
        // reference's item shadow is a sigma-20 blur.
        vec2 texel = 16.0 / uResolution;
        vec3 glow = vec3(0.0);
        for (int y = -1; y <= 1; y++) {
          for (int x = -1; x <= 1; x++) {
            glow += straight(vUv + vec2(float(x), float(y)) * texel).rgb;
          }
        }
        added = (glow / 9.0) * (lum - uThreshold) * uIntensity;
      }
      // The halo may extend past the layer's silhouette, where it only adds
      // light because the destination is attenuated by a zero alpha.
      gl_FragColor = vec4(src.rgb * src.a + added, src.a);
    }
  `,
  alpha: /* glsl */ `
    uniform float uAlpha;
    void main() {
      // Shipped module 1293: the texel is scaled as a whole, so colour and alpha
      // stay in step and a pass whose alpha already reached 0 keeps its colour.
      gl_FragColor = texture2D(tDiffuse, vUv) * uAlpha;
    }
  `,
  "gray-scale": /* glsl */ `
    uniform float uAmount;
    void main() {
      vec4 src = straight(vUv);
      float amount = clamp(uAmount / 100.0, 0.0, 1.0);
      float sum = (src.r + src.g + src.b) / 3.0;
      vec3 result = mix(src.rgb, vec3(sum), amount);
      gl_FragColor = vec4(result * src.a, src.a);
    }
  `,
  sepia: /* glsl */ `
    uniform float uAmount;
    void main() {
      vec4 src = straight(vUv);
      float scaled = uAmount / 20.0;
      vec3 c = src.rgb;
      vec3 result;
      result.r = dot(c, vec3(1.0 - 0.607 * scaled, 0.769 * scaled, 0.189 * scaled));
      result.g = dot(c, vec3(0.349 * scaled, 1.0 - 0.314 * scaled, 0.168 * scaled));
      result.b = dot(c, vec3(0.272 * scaled, 0.534 * scaled, 1.0 - 0.869 * scaled));
      gl_FragColor = vec4(min(vec3(1.0), result) * src.a, src.a);
    }
  `,
  flicker: /* glsl */ `
    uniform float uTime;
    uniform float uAmplitudeBrightness;
    uniform float uFrequencyBrightness;
    uniform float uAmplitudeColor;
    uniform float uFrequencyColor;
    uniform float uSeedColor;
    uniform float uBrightness;
    uniform float uContrast;
    uniform bool uDarken;

    float rand(float seed) {
      return mod(fract(sin(seed * 6.7892397856)) + 0.5, 1.0);
    }
    float smoothNoise(float seed) {
      float a = rand(floor(seed));
      float b = rand(ceil(seed));
      return mix(a, b, fract(seed));
    }
    vec4 hueShift(vec3 c, float s) {
      vec3 k = vec3(0.55735);
      vec3 p = k * dot(k, c);
      vec3 u = c - p;
      vec3 v = cross(k, u);
      return vec4(u * cos(s * 6.2832) + v * sin(s * 6.2832) + p, 1.0);
    }
    void main() {
      vec4 src = straight(vUv);
      src.rgb *= max(uContrast, 0.0);
      float brightnessNoise = smoothNoise(uTime * uFrequencyBrightness);
      float colorNoise = smoothNoise(uTime * uFrequencyColor + uSeedColor);
      if (uDarken) {
        src.rgb *= brightnessNoise * uAmplitudeBrightness + uBrightness;
      } else {
        src.rgb *= abs(brightnessNoise * uAmplitudeBrightness) + uBrightness;
      }
      vec4 shifted = hueShift(src.rgb, colorNoise * uAmplitudeColor);
      vec3 result = ((shifted.rgb - vec3(0.5)) * uContrast) + vec3(0.5);
      gl_FragColor = vec4(clamp(result, 0.0, 1.0) * src.a, src.a);
    }
  `,
  "color-correction": /* glsl */ `
    uniform float uHueAmount;
    uniform float uBrightness;
    uniform float uContrast;
    uniform float uVibrance;
    uniform float uSaturation;
    uniform float uShadows;
    uniform float uHighlights;
    uniform bool uInvert;
    uniform float uAddR;
    uniform float uAddG;
    uniform float uAddB;
    uniform float uMulR;
    uniform float uMulG;
    uniform float uMulB;

    vec4 hueShift(vec3 c, float s, float a) {
      float product = 1.0 / sqrt(3.0);
      vec3 p = vec3(product) * dot(vec3(product), c);
      vec3 u = c - p;
      vec3 v = cross(vec3(product), u);
      return vec4(u * cos(s * 6.28318530718) + v * sin(s * 6.28318530718) + p, a);
    }
    float invLerp(float a, float b, float v) { return (v - a) / (b - a); }
    vec4 saturateColor(vec4 col, float adjustment) {
      const vec3 w = vec3(0.2125, 0.7154, 0.0721);
      vec3 intensity = vec3(dot(col.rgb, w));
      return mix(vec4(intensity, col.a), col, adjustment);
    }
    void main() {
      // The shipped shader samples the layer directly (no un-premultiply) and
      // returns straight colour; only the invert branch scales by alpha.
      vec4 pixel = texture2D(tDiffuse, vUv);
      float average = (pixel.r + pixel.g + pixel.b) / 3.0;
      float maxColor = max(pixel.r, max(pixel.g, pixel.b));
      float luminance = dot(pixel.rgb, vec3(0.2125, 0.7154, 0.0721));
      pixel.r = pixel.r * uMulR + uAddR;
      pixel.g = pixel.g * uMulG + uAddG;
      pixel.b = pixel.b * uMulB + uAddB;
      pixel.rgb *= max(uContrast, 0.0);
      pixel.rgb += uBrightness - 1.0;
      pixel.rgb = ((pixel.rgb - vec3(0.5)) * uContrast) + vec3(0.5);
      pixel = hueShift(pixel.rgb, invLerp(360.0, 0.0, uHueAmount), pixel.a);
      float vibrance = (maxColor - average) * (-3.0 * uVibrance);
      pixel.rgb = mix(pixel.rgb, vec3(maxColor), vibrance);
      pixel = saturateColor(pixel, uSaturation);
      float shadow = clamp(
        (pow(luminance, 1.0 / (uShadows + 1.0)) + (-0.76) * pow(luminance, 2.0 / (uShadows + 1.0))) - luminance,
        0.0, 1.0);
      float highlight = clamp(
        (1.0 - (pow(1.0 - luminance, 1.0 / (2.0 - uHighlights)) +
          (-0.8) * pow(1.0 - luminance, 2.0 / (2.0 - uHighlights)))) - luminance,
        -1.0, 0.0);
      pixel.rgb = (luminance + shadow + highlight) * (pixel.rgb / max(vec3(luminance), vec3(0.0001)));
      if (uInvert) {
        vec3 unpacked = pixel.rgb / max(pixel.a, 0.0001);
        pixel = vec4((vec3(1.0) - unpacked) * pixel.a, pixel.a);
      }
      gl_FragColor = clamp(pixel, 0.0, 1.0);
    }
  `,
  "directional-blur": /* glsl */ `
    uniform float uAmount;
    uniform float uAngle;
    uniform int uSamples;
    void main() {
      float angleRad = uAngle * 0.0174533;
      vec2 direction = vec2(cos(angleRad), sin(angleRad));
      vec4 color = vec4(0.0);
      float total = 0.0;
      float normalizedAmount = uAmount * 0.001;
      for (int i = 0; i < 64; i++) {
        if (i >= uSamples) break;
        float percent = (float(i) - float(uSamples) * 0.5) / float(uSamples);
        vec2 offset = direction * percent * normalizedAmount;
        offset.x *= uResolution.y / uResolution.x;
        float weight = exp(-percent * percent * 2.0);
        color += texture2D(tDiffuse, vUv + offset) * weight;
        total += weight;
      }
      gl_FragColor = color / max(total, 1e-5);
    }
  `,
  "radial-blur": /* glsl */ `
    uniform float uAmount;
    uniform vec2 uCenter;
    uniform int uSamples;
    void main() {
      vec4 color = vec4(0.0);
      float total = 0.0;
      float angleStep = uAmount * 0.01;
      float aspect = uResolution.x / uResolution.y;
      vec2 offset = vec2((vUv.x - uCenter.x) * aspect, vUv.y - uCenter.y);
      for (int i = 0; i < 64; i++) {
        if (i >= uSamples) break;
        float fSamples = float(uSamples);
        float percent = (float(i) - fSamples * 0.5) / fSamples;
        float angle = percent * angleStep;
        float c = cos(angle);
        float s = sin(angle);
        vec2 rotated = vec2(offset.x * c - offset.y * s, offset.x * s + offset.y * c);
        vec2 samplePos = vec2(uCenter.x + rotated.x / aspect, uCenter.y + rotated.y);
        float weight = exp(-percent * percent * 2.0);
        color += texture2D(tDiffuse, samplePos) * weight;
        total += weight;
      }
      gl_FragColor = color / max(total, 1e-5);
    }
  `,
  "horizontal-blur": /* glsl */ `
    uniform float uAmount;
    void main() {
      float hh = uAmount / 25000.0 / (uResolution.x / uResolution.y);
      vec4 sum = vec4(0.0);
      sum += texture2D(tDiffuse, vec2(vUv.x - 7.0 * hh, vUv.y)) * 0.000489;
      sum += texture2D(tDiffuse, vec2(vUv.x - 6.0 * hh, vUv.y)) * 0.002403;
      sum += texture2D(tDiffuse, vec2(vUv.x - 5.0 * hh, vUv.y)) * 0.009246;
      sum += texture2D(tDiffuse, vec2(vUv.x - 4.0 * hh, vUv.y)) * 0.02784;
      sum += texture2D(tDiffuse, vec2(vUv.x - 3.0 * hh, vUv.y)) * 0.065602;
      sum += texture2D(tDiffuse, vec2(vUv.x - 2.0 * hh, vUv.y)) * 0.120999;
      sum += texture2D(tDiffuse, vec2(vUv.x - 1.0 * hh, vUv.y)) * 0.174697;
      sum += texture2D(tDiffuse, vUv) * 0.197448;
      sum += texture2D(tDiffuse, vec2(vUv.x + 1.0 * hh, vUv.y)) * 0.174697;
      sum += texture2D(tDiffuse, vec2(vUv.x + 2.0 * hh, vUv.y)) * 0.120999;
      sum += texture2D(tDiffuse, vec2(vUv.x + 3.0 * hh, vUv.y)) * 0.065602;
      sum += texture2D(tDiffuse, vec2(vUv.x + 4.0 * hh, vUv.y)) * 0.02784;
      sum += texture2D(tDiffuse, vec2(vUv.x + 5.0 * hh, vUv.y)) * 0.009246;
      sum += texture2D(tDiffuse, vec2(vUv.x + 6.0 * hh, vUv.y)) * 0.002403;
      sum += texture2D(tDiffuse, vec2(vUv.x + 7.0 * hh, vUv.y)) * 0.000489;
      gl_FragColor = sum;
    }
  `,
  "vertical-blur": /* glsl */ `
    uniform float uAmount;
    void main() {
      float vv = uAmount / 25000.0;
      vec4 sum = vec4(0.0);
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 4.0 * vv)) * 0.051;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 3.0 * vv)) * 0.0918;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 2.0 * vv)) * 0.12245;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y - 1.0 * vv)) * 0.1531;
      sum += texture2D(tDiffuse, vUv) * 0.1633;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 1.0 * vv)) * 0.1531;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 2.0 * vv)) * 0.12245;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 3.0 * vv)) * 0.0918;
      sum += texture2D(tDiffuse, vec2(vUv.x, vUv.y + 4.0 * vv)) * 0.051;
      gl_FragColor = sum;
    }
  `,
  glow: /* glsl */ `
    uniform vec3 uGlowColor;
    uniform float uDistance;
    uniform float uOuterStrength;
    uniform float uInnerStrength;
    uniform float uXSpread;
    uniform float uYSpread;
    const float PI = 3.14159265358979323846264;
    const float quality = 0.1;
    void main() {
      vec2 px = vec2(1.0 / uXSpread, 1.0 / uYSpread * uResolution.y / uResolution.x);
      float qualityDist = 1.0 / quality / max(uDistance, 0.001);
      vec4 ownColor = straight(vUv);
      vec4 curColor;
      float totalAlpha = 0.0;
      float maxTotalAlpha = 0.0;
      for (float angle = 0.0; angle <= PI * 2.0; angle += qualityDist) {
        float cosAngle = cos(angle);
        float sinAngle = sin(angle);
        for (float curDistance = 1.0; curDistance <= uDistance; curDistance += 1.0) {
          vec2 displaced = vUv + vec2(cosAngle, sinAngle) * curDistance * px;
          curColor = straight(displaced);
          totalAlpha += (uDistance - curDistance) * curColor.a;
          maxTotalAlpha += (uDistance - curDistance);
        }
      }
      maxTotalAlpha = max(maxTotalAlpha, 0.0001);
      ownColor.a = max(ownColor.a, 0.0001);
      ownColor.rgb /= ownColor.a;
      float outerGlowAlpha = (totalAlpha / maxTotalAlpha) * uOuterStrength * (1.0 - ownColor.a);
      float innerGlowAlpha = ((maxTotalAlpha - totalAlpha) / maxTotalAlpha) * uInnerStrength * ownColor.a;
      float resultAlpha = ownColor.a + outerGlowAlpha;
      gl_FragColor = vec4(
        mix(mix(ownColor.rgb, uGlowColor, innerGlowAlpha / ownColor.a), uGlowColor, outerGlowAlpha / max(resultAlpha, 1e-5)) * resultAlpha,
        resultAlpha);
    }
  `,
  vignette: /* glsl */ `
    uniform vec3 uVignetteColor;
    uniform float uTime;
    uniform float uSize;
    uniform float uSmoothness;
    uniform float uRoundness;
    uniform float uCenterX;
    uniform float uCenterY;
    uniform float uOpacity;
    uniform float uDither;
    uniform bool uUseAlpha;
    uniform bool uMoveNoise;
    uniform bool uUseScreenAspect;

    float random(vec2 st, float seed) {
      vec3 p3 = fract(vec3(st.xyx) * 0.1031);
      p3 += dot(p3, p3.yzx + 33.33 + fract(seed));
      return fract((p3.x + p3.y) * p3.z);
    }
    void main() {
      vec4 color = straight(vUv);
      vec2 center = vec2(uCenterX, uCenterY);
      vec2 distVec = vUv - center;
      if (!uUseScreenAspect) distVec.x *= uResolution.x / uResolution.y;
      float r = max(0.01, uRoundness * 2.0);
      float d = pow(pow(abs(distVec.x), r) + pow(abs(distVec.y), r), 1.0 / r);
      float clearArea = 1.0 - uSize;
      float vigMask = smoothstep(clearArea, clearArea + max(0.001, uSmoothness), d);
      if (uDither > 0.0) {
        float noise = (random(gl_FragCoord.xy, uMoveNoise ? uTime : 0.0) - 0.5) * uDither;
        float transitionMask = vigMask * (1.0 - vigMask) * 4.0;
        vigMask += noise * transitionMask;
      }
      vigMask = clamp(vigMask, 0.0, 1.0) * uOpacity;
      vec4 finalColor = mix(color, vec4(uVignetteColor, 1.0), vigMask);
      if (uUseAlpha) finalColor.a = color.a * (1.0 - vigMask);
      gl_FragColor = vec4(finalColor.rgb * finalColor.a, finalColor.a);
    }
  `,
  transform: /* glsl */ `
    uniform vec4 uTransformData[3];
    uniform int uUseMotionBlur;
    uniform float uMotionBlurLength;
    uniform int uMotionBlurIterations;
    uniform int uRepeatType;
    uniform float uAspect;

    vec2 rotate(vec2 v, float a) {
      float s = sin(a);
      float c = cos(a);
      mat2 m = mat2(c, -s, s, c);
      return m * v;
    }
    vec4 getColor(vec2 p, float r, vec2 s) {
      // Shipped module 77 builds the Transform's full-screen quad with the
      // composition aspect as its camera half-width
      // (new OrthographicCamera(-1*t, 1*t, 1, -1, 0, 50)) and module 361
      // renderEffect scales that mesh with setScaling(w, h, (1,1,1)), which
      // overfills a portrait frame by 1/aspect. The visible part of its vUv is
      // therefore 0.5 +/- aspect/2, not the whole 0..1 range. Our quad maps
      // vUv onto the frame exactly, so shrink it here for the same input space;
      // without this a portrait composition is inset by aspect times the
      // scale (orbital @45: the frame occupies 0.171..0.829 of both axes).
      vec2 uv = vUv;
      if (uAspect < 1.0) uv = vec2(0.5) + (vUv - 0.5) * uAspect;
      vec2 transformedUv;
      if (uAspect < 1.0) {
        transformedUv = vec2(uv.x - 0.5, (uv.y - 0.5) / uAspect) * 2.0 + p.xy;
      } else {
        transformedUv = vec2((uv.x - 0.5) * uAspect, uv.y - 0.5) * 2.0 + p.xy;
      }
      transformedUv = rotate(transformedUv, r);
      transformedUv.x *= 1.0 / uAspect;
      transformedUv /= s;
      transformedUv = (transformedUv + 1.0) / 2.0;
      vec2 pos = transformedUv;
      int wrapping = int(uTransformData[2].w);
      vec4 col = vec4(0.0);
      if (wrapping == 0) {
        col = texture2D(tDiffuse, pos);
      } else if (wrapping == 1) {
        col = texture2D(tDiffuse, mod(pos, 1.0));
        if (uRepeatType == 1 && (pos.x > 1.0 || pos.x < 0.0)) col = texture2D(tDiffuse, mod(vec2(1.0 - pos.x, pos.y), 1.0));
        if (uRepeatType == 2 && (pos.y > 1.0 || pos.y < 0.0)) col = texture2D(tDiffuse, mod(vec2(pos.x, 1.0 - pos.y), 1.0));
        if (uRepeatType == 3 && (pos.x > 1.0 || pos.x < 0.0 || pos.y > 1.0 || pos.y < 0.0)) col = texture2D(tDiffuse, mod(1.0 - pos, 1.0));
        if (uRepeatType == 4) {
          vec2 flip = mod(pos, 2.0);
          if (flip.y > 1.0) pos.y = 1.0 - pos.y;
          if (flip.x > 1.0) pos.x = 1.0 - pos.x;
          col = texture2D(tDiffuse, mod(pos, 1.0));
        }
      } else if (wrapping == 2) {
        if (pos.x > 1.0 || pos.y > 1.0 || pos.x < 0.0 || pos.y < 0.0) return vec4(0.0);
        col = texture2D(tDiffuse, pos);
      }
      return col;
    }
    void main() {
      vec2 currPos = uTransformData[0].xy;
      vec2 currScale = uTransformData[1].xy;
      float currRotation = uTransformData[2].y;
      float prevRotation = uTransformData[2].x;
      vec4 col = vec4(0.0);
      if (uUseMotionBlur == 0) {
        col = getColor(currPos, currRotation, currScale);
      } else {
        vec2 prevPos = uTransformData[0].zw;
        vec2 prevScale = uTransformData[1].zw;
        for (int i = 0; i < 100; i += 1) {
          if (i >= uMotionBlurIterations) break;
          // Shipped module 1291 computes float(i) / motionBlurLength with no
          // clamp, so a shutter longer than one sample step (iterations >
          // length) walks past the current pose instead of stopping at it. The
          // epsilon only guards length 0, which would divide by zero.
          float t = float(i) / max(uMotionBlurLength, 0.001);
          col += getColor(mix(prevPos, currPos, t), mix(prevRotation, currRotation, t), mix(prevScale, currScale, t));
        }
        col /= float(max(uMotionBlurIterations, 1));
      }
      gl_FragColor = col;
      gl_FragColor.a *= uTransformData[2].z;
    }
  `,
  "jfa-uv": /* glsl */ `
    void main() {
      vec2 pixel = gl_FragCoord.xy;
      float a00 = texture2D(tDiffuse, clamp(pixel + vec2(-1.0, -1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a01 = texture2D(tDiffuse, clamp(pixel + vec2(0.0, -1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a02 = texture2D(tDiffuse, clamp(pixel + vec2(1.0, -1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a10 = texture2D(tDiffuse, clamp(pixel + vec2(-1.0, 0.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a11 = texture2D(tDiffuse, clamp(pixel, vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a12 = texture2D(tDiffuse, clamp(pixel + vec2(1.0, 0.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a20 = texture2D(tDiffuse, clamp(pixel + vec2(-1.0, 1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a21 = texture2D(tDiffuse, clamp(pixel + vec2(0.0, 1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;
      float a22 = texture2D(tDiffuse, clamp(pixel + vec2(1.0, 1.0), vec2(0.0), uResolution - 1.0) / uResolution).a;

      vec4 outColor = vec4(pixel, 0.0, 0.0);
      if (a11 > 0.99) {
        gl_FragColor = outColor;
        return;
      }
      if (a11 < 0.01) {
        gl_FragColor = vec4(1.0, 1.0, 1.0, 1.0);
        return;
      }
      vec2 dir = -vec2(
        a00 + a01 * 2.0 + a02 - a20 - a21 * 2.0 - a22,
        a00 + a10 * 2.0 + a20 - a02 - a12 * 2.0 - a22
      );
      if (abs(dir.x) <= 0.005 && abs(dir.y) <= 0.005) {
        gl_FragColor = outColor;
        return;
      }
      dir = normalize(dir);
      gl_FragColor = vec4(pixel + dir * (1.0 - a11), 0.0, 0.0);
    }
  `,
  "jfa-jump": /* glsl */ `
    uniform float uJumpOffset;

    void main() {
      float minDistance = 99999.0;
      vec4 closest = vec4(1.0);
      vec2 pixel = gl_FragCoord.xy;
      for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
          vec2 sampleCoord = pixel + vec2(float(x), float(y)) * uJumpOffset;
          vec4 rgba = texture2D(tDiffuse, clamp(sampleCoord / uResolution, 0.0, 1.0));
          if (rgba.a < 1.0) {
            float dist = distance(pixel, rgba.xy);
            if (dist < minDistance) {
              minDistance = dist;
              closest = rgba;
            }
          }
        }
      }
      gl_FragColor = closest;
    }
  `,
  "fidelityfx-cas": /* glsl */ `

// Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
//
// FidelityFX FSR v1.0.2 by AMD
// ported to mpv by agyild - https://gist.github.com/agyild/82219c545228d70c5604f865ce0b0ce5
// ported to WebGL by goingdigital - https://www.shadertoy.com/view/stXSWB
// using glea.js by learosema - https://github.com/learosema/glea for webGL functions
// using colorspace functions from tobspr - https://github.com/tobspr/GLSL-Color-Spaces/blob/master/ColorSpaces.inc.glsl
// modified for https://vizzy.io

uniform float sharpeningAmt;
uniform float contrastAmt;
#define DISABLE false

#define SHARPENING sharpeningAmt // Sharpening intensity: Adjusts sharpening intensity by averaging the original pixels to the sharpened result. 1.0 is the unmodified default. 0.0 to 1.0.
#define CONTRAST contrastAmt // Adjusts the range the shader adapts to high contrast (0 is not all the way off). Higher values = more high contrast sharpening. 0.0 to 1.0.
#define PERFORMANCE 0 // Whether to use optimizations for performance with loss of quality

// precision highp float;

// uniform float width;
// uniform float height;
// uniform float texWidth;
// uniform float texHeight;

#define width uResolution.x
#define height uResolution.y

#define texWidth uResolution.x
#define texHeight uResolution.y

// Used to convert from linear RGB to XYZ space
const mat3 RGB_2_XYZ = (mat3(
    0.4124564, 0.2126729, 0.0193339,
    0.3575761, 0.7151522, 0.1191920,
    0.1804375, 0.0721750, 0.9503041
));

// Used to convert from XYZ to linear RGB space
const mat3 XYZ_2_RGB = (mat3(
     3.2404542,-0.9692660, 0.0556434,
    -1.5371385, 1.8760108,-0.2040259,
    -0.4985314, 0.0415560, 1.0572252
));
// Converts a color from linear RGB to XYZ space
vec3 rgb_to_xyz(vec3 rgb) {
    return RGB_2_XYZ * rgb;
}

// Converts a color from XYZ to linear RGB space
vec3 xyz_to_rgb(vec3 xyz) {
    return XYZ_2_RGB * xyz;
}

/* EASU stage
*
* This takes a reduced resolution source, and scales it up while preserving detail.
*
* Updates:
*   stretch definition fixed. Thanks nehon for the bug report!
*/

vec3 FsrEasuCF(vec2 p) {
	vec2 uv = (p + .5) / vec2(texWidth, texHeight);
	vec4 color = texture2D(tDiffuse, uv);
    return rgb_to_xyz(color.rgb);
}

/**** EASU ****/
void FsrEasuCon(
    out vec4 con0,
    out vec4 con1,
    out vec4 con2,
    out vec4 con3,
    // This the rendered image resolution being upscaled
    vec2 inputViewportInPixels,
    // This is the resolution of the resource containing the input image (useful for dynamic resolution)
    vec2 inputSizeInPixels,
    // This is the display resolution which the input image gets upscaled to
    vec2 outputSizeInPixels
)
{
    // Output integer position to a pixel position in viewport.
    con0 = vec4(
        inputViewportInPixels.x/outputSizeInPixels.x,
        inputViewportInPixels.y/outputSizeInPixels.y,
        .5*inputViewportInPixels.x/outputSizeInPixels.x-.5,
        .5*inputViewportInPixels.y/outputSizeInPixels.y-.5
    );
    // Viewport pixel position to normalized image space.
    // This is used to get upper-left of 'F' tap.
    con1 = vec4(1,1,1,-1)/inputSizeInPixels.xyxy;
    // Centers of gather4, first offset from upper-left of 'F'.
    //      +---+---+
    //      |   |   |
    //      +--(0)--+
    //      | b | c |
    //  +---F---+---+---+
    //  | e | f | g | h |
    //  +--(1)--+--(2)--+
    //  | i | j | k | l |
    //  +---+---+---+---+
    //      | n | o |
    //      +--(3)--+
    //      |   |   |
    //      +---+---+
    // These are from (0) instead of 'F'.
    con2 = vec4(-1,2,1,2)/inputSizeInPixels.xyxy;
    con3 = vec4(0,4,0,0)/inputSizeInPixels.xyxy;
}

// Filtering for a given tap for the scalar.
void FsrEasuTapF(
    inout vec3 aC, // Accumulated color, with negative lobe.
    inout float aW, // Accumulated weight.
    vec2 off, // Pixel offset from resolve position to tap.
    vec2 dir, // Gradient direction.
    vec2 len, // Length.
    float lob, // Negative lobe strength.
    float clp, // Clipping point.
    vec3 c
)
{
    // Tap color.
    // Rotate offset by direction.
    vec2 v = vec2(dot(off, dir), dot(off,vec2(-dir.y,dir.x)));
    // Anisotropy.
    v *= len;
    // Compute distance^2.
    float d2 = min(dot(v,v),clp);
    // Limit to the window as at corner, 2 taps can easily be outside.
    // Approximation of lancos2 without sin() or rcp(), or sqrt() to get x.
    //  (25/16 * (2/5 * x^2 - 1)^2 - (25/16 - 1)) * (1/4 * x^2 - 1)^2
    //  |_______________________________________|   |_______________|
    //                   base                             window
    // The general form of the 'base' is,
    //  (a*(b*x^2-1)^2-(a-1))
    // Where 'a=1/(2*b-b^2)' and 'b' moves around the negative lobe.
    float wB = .4 * d2 - 1.;
    float wA = lob * d2 -1.;
    wB *= wB;
    wA *= wA;
    wB = 1.5625*wB-.5625;
    float w=  wB * wA;
    // Do weighted average.
    aC += c*w;
    aW += w;
}

//------------------------------------------------------------------------------------------------------------------------------
// Accumulate direction and length.
void FsrEasuSetF(
    inout vec2 dir,
    inout float len,
    float w,
    float lA,float lB,float lC,float lD,float lE
)
{
    // Direction is the '+' diff.
    //    a
    //  b c d
    //    e
    // Then takes magnitude from abs average of both sides of 'c'.
    // Length converts gradient reversal to 0, smoothly to non-reversal at 1, shaped, then adding horz and vert terms.
    float lenX = max(abs(lD - lC), abs(lC - lB));
    float dirX = lD - lB;
    dir.x += dirX * w;
    lenX = clamp(abs(dirX)/lenX,0.,1.);
    lenX *= lenX;
    len += lenX * w;
    // Repeat for the y axis.
    float lenY = max(abs(lE - lC), abs(lC - lA));
    float dirY = lE - lA;
    dir.y += dirY * w;
    lenY = clamp(abs(dirY) / lenY,0.,1.);
    lenY *= lenY;
    len += lenY * w;
}

//------------------------------------------------------------------------------------------------------------------------------
void FsrEasuF(
    out vec3 pix,
    vec2 ip, // Integer pixel position in output.
    // Constants generated by FsrEasuCon().
    vec4 con0, // xy = output to input scale, zw = first pixel offset correction
    vec4 con1,
    vec4 con2,
    vec4 con3
)
{
    //------------------------------------------------------------------------------------------------------------------------------
    // Get position of 'f'.
    vec2 pp = ip * con0.xy + con0.zw; // Corresponding input pixel/subpixel
    vec2 fp = floor(pp);// fp = source nearest pixel
    pp -= fp; // pp = source subpixel

    //------------------------------------------------------------------------------------------------------------------------------
    // 12-tap kernel.
    //    b c
    //  e f g h
    //  i j k l
    //    n o
    // Gather 4 ordering.
    //  a b
    //  r g
    vec2 p0 = fp * con1.xy + con1.zw;
    
    // These are from p0 to avoid pulling two constants on pre-Navi hardware.
    vec2 p1 = p0 + con2.xy;
    vec2 p2 = p0 + con2.zw;
    vec2 p3 = p0 + con3.xy;

    // TextureGather is not available on WebGL2
    vec4 off = vec4(-.5,.5,-.5,.5)*con1.xxyy;
    // textureGather to texture offsets
    // x=west y=east z=north w=south
    vec3 bC = FsrEasuCF(p0 + off.xw); float bL = bC.g + 0.5 *(bC.r + bC.b);
    vec3 cC = FsrEasuCF(p0 + off.yw); float cL = cC.g + 0.5 *(cC.r + cC.b);
    vec3 iC = FsrEasuCF(p1 + off.xw); float iL = iC.g + 0.5 *(iC.r + iC.b);
    vec3 jC = FsrEasuCF(p1 + off.yw); float jL = jC.g + 0.5 *(jC.r + jC.b);
    vec3 fC = FsrEasuCF(p1 + off.yz); float fL = fC.g + 0.5 *(fC.r + fC.b);
    vec3 eC = FsrEasuCF(p1 + off.xz); float eL = eC.g + 0.5 *(eC.r + eC.b);
    vec3 kC = FsrEasuCF(p2 + off.xw); float kL = kC.g + 0.5 *(kC.r + kC.b);
    vec3 lC = FsrEasuCF(p2 + off.yw); float lL = lC.g + 0.5 *(lC.r + lC.b);
    vec3 hC = FsrEasuCF(p2 + off.yz); float hL = hC.g + 0.5 *(hC.r + hC.b);
    vec3 gC = FsrEasuCF(p2 + off.xz); float gL = gC.g + 0.5 *(gC.r + gC.b);
    vec3 oC = FsrEasuCF(p3 + off.yz); float oL = oC.g + 0.5 *(oC.r + oC.b);
    vec3 nC = FsrEasuCF(p3 + off.xz); float nL = nC.g + 0.5 *(nC.r + nC.b);
   
    //------------------------------------------------------------------------------------------------------------------------------
    // Simplest multi-channel approximate luma possible (luma times 2, in 2 FMA/MAD).
    // Accumulate for bilinear interpolation.
    vec2 dir = vec2(0);
    float len = 0.;

    FsrEasuSetF(dir, len, (1.-pp.x)*(1.-pp.y), bL, eL, fL, gL, jL);
    FsrEasuSetF(dir, len,    pp.x  *(1.-pp.y), cL, fL, gL, hL, kL);
    FsrEasuSetF(dir, len, (1.-pp.x)*  pp.y  , fL, iL, jL, kL, nL);
    FsrEasuSetF(dir, len,    pp.x  *  pp.y  , gL, jL, kL, lL, oL);

    //------------------------------------------------------------------------------------------------------------------------------
    // Normalize with approximation, and cleanup close to zero.
    vec2 dir2 = dir * dir;
    float dirR = dir2.x + dir2.y;
    bool zro = dirR < (1.0/32768.0);
    dirR = inversesqrt(dirR);
#if (PERFORMANCE == 1)
	if (zro) {
		vec4 w = vec4(0.0);
		w.x = (1.0 - pp.x) * (1.0 - pp.y);
		w.y =        pp.x  * (1.0 - pp.y);
		w.z = (1.0 - pp.x) *        pp.y;
		w.w =        pp.x  *        pp.y;
		pix.r = clamp(dot(w, vec4(fL, gL, jL, kL)), 0.0, 1.0);
		return;
	}
#elif (PERFORMANCE == 0)
    dirR = zro ? 1.0 : dirR;
    dir.x = zro ? 1.0 : dir.x;
#endif
    dir *= vec2(dirR);
    // Transform from {0 to 2} to {0 to 1} range, and shape with square.
    len = len * 0.5;
    len *= len;
    // Stretch kernel {1.0 vert|horz, to sqrt(2.0) on diagonal}.
    float stretch = dot(dir,dir) / (max(abs(dir.x), abs(dir.y)));
    // Anisotropic length after rotation,
    //  x := 1.0 lerp to 'stretch' on edges
    //  y := 1.0 lerp to 2x on edges
    vec2 len2 = vec2(1. +(stretch-1.0)*len, 1. -.5 * len);
    // Based on the amount of 'edge',
    // the window shifts from +/-{sqrt(2.0) to slightly beyond 2.0}.
    float lob = .5 - .29 * len;
    // Set distance^2 clipping point to the end of the adjustable window.
    float clp = 1./lob;

    //------------------------------------------------------------------------------------------------------------------------------
    // Accumulation mixed with min/max of 4 nearest.
    //    b c
    //  e f g h
    //  i j k l
    //    n o
    // Accumulation.
    vec3 aC = vec3(0);
    float aW = 0.;
    FsrEasuTapF(aC, aW, vec2( 0,-1)-pp, dir, len2, lob, clp, bC);
    FsrEasuTapF(aC, aW, vec2( 1,-1)-pp, dir, len2, lob, clp, cC);
    FsrEasuTapF(aC, aW, vec2(-1, 1)-pp, dir, len2, lob, clp, iC);
    FsrEasuTapF(aC, aW, vec2( 0, 1)-pp, dir, len2, lob, clp, jC);
    FsrEasuTapF(aC, aW, vec2( 0, 0)-pp, dir, len2, lob, clp, fC);
    FsrEasuTapF(aC, aW, vec2(-1, 0)-pp, dir, len2, lob, clp, eC);
    FsrEasuTapF(aC, aW, vec2( 1, 1)-pp, dir, len2, lob, clp, kC);
    FsrEasuTapF(aC, aW, vec2( 2, 1)-pp, dir, len2, lob, clp, lC);
    FsrEasuTapF(aC, aW, vec2( 2, 0)-pp, dir, len2, lob, clp, hC);
    FsrEasuTapF(aC, aW, vec2( 1, 0)-pp, dir, len2, lob, clp, gC);
    FsrEasuTapF(aC, aW, vec2( 1, 2)-pp, dir, len2, lob, clp, oC);
    FsrEasuTapF(aC, aW, vec2( 0, 2)-pp, dir, len2, lob, clp, nC);
    //------------------------------------------------------------------------------------------------------------------------------
    // Normalize and dering.
#if (PERFORMANCE == 1)
	pix = aC/aW;
#elif (PERFORMANCE == 0)
    vec3 min4 = min(min(fC,gC),min(jC,kC));
    vec3 max4 = max(max(fC,gC),max(jC,kC));
    pix=min(max4,max(min4,aC/aW));
#endif
}

void EASU( out vec4 fragColor, in vec2 fragCoord )
{
    vec3 c;
    vec4 con0,con1,con2,con3;
    
    // "rendersize" refers to size of source image before upscaling.
    vec2 rendersize = vec2(texWidth, texHeight);
    FsrEasuCon(
        con0, con1, con2, con3, rendersize, rendersize, vec2(width, height)
    );
    FsrEasuF(c, fragCoord, con0, con1, con2, con3);
    
    fragColor = vec4(xyz_to_rgb(c.xyz), 1);
}

vec4 getPixel(vec2 pos) {
	vec2 coord = (pos + .5) / vec2(width, height);
	//coord.y = 1.0 - coord.y;
	return texture2D(tDiffuse, coord);
}

void main() {
	vec4 e = getPixel(gl_FragCoord.xy);
		
    vec4 e_xyz = vec4(rgb_to_xyz(e.rgb), 1);
    EASU(e_xyz, (gl_FragCoord.xy + 0.5) / vec2(width, height));  
    
    // fetch a 3x3 neighborhood around the pixel 'e',
    //  a b c
    //  d(e)f
    //  g h i	
    vec3 a = getPixel(gl_FragCoord.xy + vec2(-1.0,-1.0)).rgb;
    vec3 b = getPixel(gl_FragCoord.xy + vec2( 0.0,-1.0)).rgb;
    vec3 c = getPixel(gl_FragCoord.xy + vec2( 1.0,-1.0)).rgb;
    vec3 f = getPixel(gl_FragCoord.xy + vec2( 1.0, 0.0)).rgb;
    vec3 g = getPixel(gl_FragCoord.xy + vec2(-1.0, 1.0)).rgb;
    vec3 h = getPixel(gl_FragCoord.xy + vec2( 0.0, 1.0)).rgb;
    vec3 d = getPixel(gl_FragCoord.xy + vec2(-1.0, 0.0)).rgb;
    vec3 i = getPixel(gl_FragCoord.xy + vec2( 1.0, 1.0)).rgb;;
    // Soft min and max.
    //  a b c			b
    //  d e f * 0.5	+ d e f * 0.5
    //  g h i			h
    // These are 2.0x bigger (factored out the extra multiply).

    vec3 mnRGB = min(min(min(d, e.rgb), min(f, b)), h);
    vec3 mnRGB2 = min(mnRGB, min(min(a, c), min(g, i)));
    mnRGB += mnRGB2;

    vec3 mxRGB = max(max(max(d, e.rgb), max(f, b)), h);
    vec3 mxRGB2 = max(mxRGB, max(max(a, c), max(g, i)));
    mxRGB += mxRGB2;

    // Smooth minimum distance to signal limit divided by smooth max.
    vec3 rcpMRGB = 1.0 / mxRGB;
    vec3 ampRGB = clamp(min(mnRGB, 2.0 - mxRGB) * rcpMRGB, 0.0, 1.0);

    // Shaping amount of sharpening.
    ampRGB = inversesqrt(ampRGB);

    float peak = -3.0 * clamp(CONTRAST, 0.0, 1.0) + 8.0;
    vec3 wRGB = -(1.0 / (ampRGB * peak));

    vec3 rcpWeightRGB = 1.0 / (4.0 * wRGB + 1.0);

    //					0 w 0
    //  Filter shape:	w 1 w
    //					0 w 0
    vec3 window = (b + d) + (f + h);
    vec3 outColor = clamp((window * wRGB + e.rgb) * rcpWeightRGB, 0.0, 1.0);

    gl_FragColor = vec4(mix(e.rgb, outColor, SHARPENING), e.a);
}

  `,
  liquify: /* glsl */ `
    uniform float uIntensity;
    uniform float uControl;
    uniform float uZoom;
    uniform float uComplexity;
    uniform float uScalDiv;
    uniform float uBlobs;

    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

    float snoise(vec3 v) {
      const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
      vec3 i = floor(v + dot(v, C.yyy));
      vec3 x0 = v - i + dot(i, C.xxx);
      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min(g.xyz, l.zxy);
      vec3 i2 = max(g.xyz, l.zxy);
      vec3 x1 = x0 - i1 + C.xxx;
      vec3 x2 = x0 - i2 + C.yyy;
      vec3 x3 = x0 - D.yyy;
      i = mod289(i);
      vec4 p = permute(permute(permute(
        i.z + vec4(0.0, i1.z, i2.z, 1.0)) +
        i.y + vec4(0.0, i1.y, i2.y, 1.0)) +
        i.x + vec4(0.0, i1.x, i2.x, 1.0));
      float n_ = 0.142857142857;
      vec3 ns = n_ * D.wyz - D.xzx;
      vec4 j = p - (49.0 + uBlobs) * floor(p * ns.z * ns.z);
      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_);
      vec4 x = x_ * ns.x + ns.yyyy;
      vec4 y = y_ * ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);
      vec4 b0 = vec4(x.xy, y.xy);
      vec4 b1 = vec4(x.zw, y.zw);
      vec4 s0 = floor(b0) * 2.0 + 1.0;
      vec4 s1 = floor(b1) * 2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));
      vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
      vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
      vec3 p0 = vec3(a0.xy, h.x);
      vec3 p1 = vec3(a0.zw, h.y);
      vec3 p2 = vec3(a1.xy, h.z);
      vec3 p3 = vec3(a1.zw, h.w);
      vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
      p0 *= norm.x;
      p1 *= norm.y;
      p2 *= norm.z;
      p3 *= norm.w;
      vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
      m = m * m;
      return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
    }

    #define scalDivt 2.1
    float FBM(vec3 v) {
      float sc1 = 1.0 / max(uScalDiv, 0.01) * 10.0;
      float sc2 = sc1 / max(uScalDiv, 0.01) * 10.0;
      float sc3 = sc2 / max(uScalDiv, 0.01) * 10.0;
      float sc1t = 1.0 / scalDivt;
      float sc2t = sc1t / scalDivt;
      float sc3t = sc2t / scalDivt;
      return 1.0 * 0.5 * snoise(v * vec3(sc3, sc3, sc3t)) +
        0.4 * 0.25 * snoise(v * vec3(sc2, sc2, sc2t)) +
        0.15 * 0.125 * snoise(v * vec3(sc1, sc1, sc1t));
    }

    void main() {
      vec2 uv = vUv * (1.0 - 0.02 * uZoom) + (vec2(uZoom) * 0.01);
      float noise1 = FBM(vec3(uComplexity * 10.0 * uv, 0.04 * 60.0 * (uControl / 1000.0)));
      float noise2 = FBM(vec3(
        uComplexity * 10.0 * uv,
        0.04 * 62.0 * (uControl / 1000.0) + 300.0
      ));
      gl_FragColor = texture2D(
        tDiffuse,
        uv + vec2(uIntensity * 0.01 * noise1, uIntensity * 0.0105 * noise2)
      );
    }
  `,
  "gradient-map": /* glsl */ `
    uniform sampler2D uLayTexture;
    uniform float uStrength;
    uniform float uInvert;

    void main() {
      vec4 color = texture2D(tDiffuse, vUv);
      float luminance = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
      if (uInvert > 0.5) luminance = 1.0 - luminance;
      vec3 mapped = texture2D(uLayTexture, vec2(luminance, 0.5)).rgb;
      color.rgb = mix(color.rgb, mapped, uStrength);
      color.rgb *= color.a;
      gl_FragColor = color;
    }
  `,
  "chroma-shift": /* glsl */ `
    uniform float uTime;
    uniform float uIntensity;
    uniform float uTimeSpeed;
    uniform float uTimeOffset;
    uniform float uColorFrequency;
    uniform float uPosterizationLevels;
    uniform float uColorPalette;

    vec3 rgb2hsv(vec3 c) {
      vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
      vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
      vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
      float d = q.x - min(q.w, q.y);
      float e = 1.0e-10;
      return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
    }
    vec3 hsv2rgb(vec3 c) {
      vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
      vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
      return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }
    vec3 getColorPalette(float t, float palette) {
      vec3 a;
      vec3 b;
      vec3 c;
      vec3 d;
      int index = int(palette);
      if (index == 1) {
        a = vec3(0.5); b = vec3(0.5); c = vec3(1.0); d = vec3(0.263, 0.416, 0.557);
      } else if (index == 2) {
        a = vec3(0.5); b = vec3(0.5); c = vec3(1.0); d = vec3(0.8, 0.2, 0.1);
      } else if (index == 3) {
        a = vec3(0.5); b = vec3(0.5); c = vec3(1.0); d = vec3(0.1, 0.4, 0.7);
      } else if (index == 4) {
        a = vec3(0.5); b = vec3(0.5); c = vec3(1.0); d = vec3(0.1, 0.8, 0.8);
      } else if (index == 5) {
        a = vec3(0.8, 0.5, 0.4);
        b = vec3(0.2, 0.4, 0.2);
        c = vec3(2.0, 1.0, 1.0);
        d = vec3(0.0, 0.25, 0.25);
      } else {
        return hsv2rgb(vec3(t, 1.0, 1.0));
      }
      return a + b * cos(6.28318 * (c * t + d));
    }

    void main() {
      vec4 modulator = texture2D(tDiffuse, vUv);
      float t = mod(
        (modulator.x + modulator.y + modulator.z) * uColorFrequency +
        (uTime * uTimeSpeed) + uTimeOffset,
        1.0
      );
      vec3 color = getColorPalette(t, uColorPalette);
      color = floor(color * uPosterizationLevels) / max(uPosterizationLevels, 1.0);
      color = mix(modulator.rgb, color, uIntensity);
      color *= modulator.a;
      gl_FragColor = vec4(color, modulator.a);
    }
  `,
  "premultiply-alpha": /* glsl */ `
    uniform float uDemultiply;

    void main() {
      vec4 col = texture2D(tDiffuse, vUv);
      if (uDemultiply > 0.5 && col.a > 0.0) {
        col = vec4(col.rgb / col.a, col.a);
      }
      gl_FragColor = vec4(col.rgb * col.a, col.a);
    }
  `,
  "distance-field": /* glsl */ `
    uniform sampler2D uDistanceField;
    uniform float uMaxDistance;
    uniform float uInvertField;
    uniform float uNormalizeField;
    uniform float uFieldOpacity;
    uniform int uVisualizationMode;

    vec3 hsv2rgb(vec3 c) {
      vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
      vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
      return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

    void main() {
      vec4 original = texture2D(tDiffuse, vUv);
      vec4 rgba = texture2D(uDistanceField, vUv);
      vec2 coord = rgba.xy;
      float dist = 0.0;
      if (rgba.a < 1.0) {
        dist = distance(coord, gl_FragCoord.xy);
      } else {
        dist = uMaxDistance;
      }
      float normalized = dist;
      if (uNormalizeField > 0.5) {
        normalized = clamp(dist / max(uMaxDistance, 0.0001), 0.0, 1.0);
      }
      if (uInvertField > 0.5) {
        normalized = 1.0 - normalized;
      }
      vec3 visualized;
      if (uVisualizationMode == 0) {
        visualized = vec3(normalized);
      } else if (uVisualizationMode == 1) {
        if (normalized < 0.33) {
          float t = normalized / 0.33;
          visualized = mix(vec3(0.0), vec3(1.0, 0.0, 0.0), t);
        } else if (normalized < 0.66) {
          float t = (normalized - 0.33) / 0.33;
          visualized = mix(vec3(1.0, 0.0, 0.0), vec3(1.0, 1.0, 0.0), t);
        } else {
          float t = (normalized - 0.66) / 0.34;
          visualized = mix(vec3(1.0, 1.0, 0.0), vec3(1.0), t);
        }
      } else if (uVisualizationMode == 2) {
        visualized = hsv2rgb(vec3(normalized, 1.0, 1.0));
      } else {
        visualized = vec3(normalized);
      }
      vec4 color = vec4(visualized, uFieldOpacity);
      color.rgb *= color.a;
      gl_FragColor = mix(original, color, color.a);
    }
  `,
  "advanced-outline": /* glsl */ `
    uniform sampler2D uDistanceField;
    uniform vec3 uOutlineColor;
    uniform float uThreshLow;
    uniform float uThreshHigh;
    uniform float uOutlineOpacity;
    uniform float uOutlineOnly;

    void main() {
      vec4 original = texture2D(tDiffuse, vUv);
      vec4 rgba = texture2D(uDistanceField, vUv);
      vec2 coord = rgba.xy;
      vec4 color = vec4(0.0);
      if (rgba.a < 1.0) {
        float dist = distance(coord, gl_FragCoord.xy);
        if (dist >= uThreshLow && dist <= uThreshHigh) {
          color = vec4(
            uOutlineColor,
            uOutlineOpacity * clamp(uThreshHigh - dist, 0.0, 1.0)
          );
        }
      }
      if (uOutlineOnly > 0.5) {
        gl_FragColor = color;
      } else {
        gl_FragColor = original + (1.0 - original.a) * color;
      }
    }
  `,
  "advanced-shadow": /* glsl */ `
    uniform sampler2D uDistanceField;
    uniform vec3 uShadowColor;
    uniform float uShadowOpacity;
    uniform vec2 uShadowOffset;
    uniform float uShadowSize;
    uniform float uShadowSpread;
    uniform float uShadowOnly;

    void main() {
      vec4 original = texture2D(tDiffuse, vUv);
      vec2 shadowUv = vUv + (uShadowOffset / uResolution);
      vec4 dfSample = texture2D(uDistanceField, shadowUv);
      vec4 shadow = vec4(uShadowColor, 0.0);
      if (dfSample.a < 1.0) {
        vec2 edgePos = dfSample.xy;
        vec2 adjustedPos = gl_FragCoord.xy + uShadowOffset;
        float dist = distance(adjustedPos, edgePos);
        float outerThreshold = uShadowSize;
        float spreadFactor = uShadowSpread / 100.0;
        float innerThreshold = outerThreshold * spreadFactor;
        if (dist <= outerThreshold) {
          if (spreadFactor >= 0.99) {
            shadow.a = uShadowOpacity;
          } else {
            shadow.a = uShadowOpacity *
              (1.0 - smoothstep(innerThreshold, outerThreshold, dist));
          }
        }
      }
      if (uShadowOnly > 0.5) {
        shadow.rgb *= shadow.a;
        gl_FragColor = shadow;
      } else {
        gl_FragColor = vec4(
          original.rgb + shadow.rgb * shadow.a * (1.0 - original.a),
          max(original.a, shadow.a * (1.0 - original.a))
        );
      }
    }
  `,
  glitch: /* glsl */ `
    uniform int uByp;
    uniform float uSnowAmount;
    uniform float uDisplacementAmount;
    uniform sampler2D tDisp;
    uniform float uAmount;
    uniform float uAngle;
    uniform float uSeed;
    uniform float uSeedX;
    uniform float uSeedY;
    uniform float uDistortionX;
    uniform float uDistortionY;
    uniform float uColS;

    float glitchRand(vec2 co) {
      return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
    }

    void main() {
      if (uByp < 1) {
        vec2 p = vUv;
        float xs = floor(gl_FragCoord.x / 0.5);
        float ys = floor(gl_FragCoord.y / 0.5);
        vec4 normal = texture2D(tDisp, p * uSeed * uSeed);
        if (p.y < uDistortionX + uColS && p.y > uDistortionX - uColS * uSeed) {
          if (uSeedX > 0.0) p.y = 1.0 - (p.y + uDistortionY);
          else p.y = uDistortionY;
        }
        if (p.x < uDistortionY + uColS && p.x > uDistortionY - uColS * uSeed) {
          if (uSeedY > 0.0) p.x = uDistortionX;
          else p.x = 1.0 - (p.x + uDistortionX);
        }
        p.x += normal.x * uSeedX * (uSeed / 5.0);
        p.y += normal.y * uSeedY * (uSeed / 5.0);
        vec2 offset = uAmount * vec2(cos(uAngle), sin(uAngle)) * uDisplacementAmount;
        vec4 cr = texture2D(tDiffuse, p + offset);
        vec4 cga = texture2D(tDiffuse, p);
        vec4 cb = texture2D(tDiffuse, p - offset);
        gl_FragColor = vec4(cr.r, cga.g, cb.b, cga.a);
        vec4 snow = 200.0 * uAmount *
          vec4(glitchRand(vec2(xs * uSeed, ys * uSeed * 50.0)) * 0.2);
        gl_FragColor = gl_FragColor + uSnowAmount * snow;
      } else {
        gl_FragColor = texture2D(tDiffuse, vUv);
      }
    }
  `,
  render: /* glsl */ `
    uniform float uOpa;

    void main() {
      vec4 color = texture2D(tDiffuse, vUv);
      color.a *= uOpa;
      gl_FragColor = color;
    }
  `,
  "blur-triangle": /* glsl */ `
    #define ITERATIONS 10.0
    uniform float uAmount;

    float triangleRand(vec2 n) {
      return fract(sin(dot(n, vec2(12.9898, 4.1414))) * 43758.5453);
    }

    void main() {
      float scaledAmount = uAmount / 5000.0;
      vec4 color = vec4(0.0);
      float total = 0.0;
      float offset = triangleRand(vUv);
      for (float t = -ITERATIONS; t <= ITERATIONS; t += 1.0) {
        float percent = (t + offset - 0.5) / ITERATIONS;
        float weight = 1.0 - abs(percent);
        color += texture2D(tDiffuse, vUv + vec2(scaledAmount) * percent) * weight;
        total += weight;
      }
      gl_FragColor = color / max(total, 0.0001);
    }
  `,
  vhs: /* glsl */ `
    uniform sampler2D uNoise;
    uniform float uTime;

    float ramp(float y, float start, float end) {
      float inside = step(start, y) - step(end, y);
      float fact = (y - start) / (end - start) * inside;
      return (1.0 - fact) * inside;
    }
    float onOff(float a, float b, float c, float t) {
      return step(c, sin(t + a * cos(t * b)));
    }
    vec2 coverScreen(vec2 fragCoord, vec2 res, float aspect) {
      vec2 uv = 0.5 * (2.0 * fragCoord - res);
      if (res.x / res.y > aspect) {
        uv = 0.5 - uv / vec2(res.x, -res.x / aspect);
      } else {
        uv = 0.5 - uv / vec2(res.y * aspect, -res.y);
      }
      return uv;
    }
    vec2 screenDistort(vec2 uv) {
      uv -= vec2(0.5, 0.5);
      uv = uv * 1.2 * (1.0 / 1.2 + 2.0 * uv.x * uv.x * uv.y * uv.y);
      uv += vec2(0.5, 0.5);
      return uv;
    }
    vec2 scanWarp(vec2 uv, float t) {
      float window = 1.0 / (1.0 + 20.0 * (uv.y - mod(t / 4.0, 1.0)) *
        (uv.y - mod(t / 4.0, 1.0)));
      uv.x = uv.x + sin(uv.y * 10.0 + t) / 50.0 * onOff(4.0, 4.0, 0.3, t) *
        (1.0 + cos(t * 80.0)) * window;
      float vShift = 0.4 * onOff(2.0, 3.0, 0.9, t) *
        (sin(t) * sin(t * 20.0) + (0.5 + 0.1 * sin(t * 200.0) * cos(t)));
      uv.y = mod(uv.y + vShift, 1.0);
      return uv;
    }
    float vignette(vec2 uv, float t) {
      float vigAmt = 3.0 + 0.3 * sin(t + 5.0 * cos(t * 5.0));
      return (1.0 - vigAmt * (uv.y - 0.5) * (uv.y - 0.5)) *
        (1.0 - vigAmt * (uv.x - 0.5) * (uv.x - 0.5));
    }
    float crtLines(vec2 uv, float t) {
      return (12.0 + mod(uv.y * 30.0 + t, 1.0)) / 13.0;
    }
    float getNoise(vec2 p, float t) {
      float s = texture2D(uNoise, vec2(1.0, 2.0 * cos(t)) * t * 8.0 + p * 1.0).x;
      s *= s;
      return s;
    }
    float getStripes(vec2 uv, float t) {
      float noi = getNoise(uv * vec2(0.5, 1.0) + vec2(1.0, 3.0), t);
      return ramp(
        mod(uv.y * 4.0 + t / 2.0 + sin(t + sin(t * 0.63)), 1.0),
        0.5,
        0.6
      ) * noi;
    }

    void main() {
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 uv = coverScreen(gl_FragCoord.xy, uResolution, aspect);
      uv = screenDistort(uv);
      uv = scanWarp(uv, uTime);
      vec4 video = texture2D(tDiffuse, uv);
      video.rgb += getStripes(uv, uTime);
      video.rgb += getNoise(uv * 3.0, uTime) / 3.0;
      video.rgb *= vignette(uv, uTime);
      video.rgb *= crtLines(uv, uTime);
      gl_FragColor = video;
    }
  `,
  vhs2: /* glsl */ `
    uniform float uTime;
    uniform float uScanlineStrength;
    uniform float uNoiseStrength;
    uniform float uNoiseSpeed;
    uniform float uBloomStrength;
    uniform float uDistortionStrength;
    uniform float uClarity;
    #define NotchHalfWidth -uClarity * 2.0

    vec4 safe_sinc(vec4 x) {
      vec4 res;
      res.x = x.x == 0.0 ? 1.0 : sin(x.x) / x.x;
      res.y = x.y == 0.0 ? 1.0 : sin(x.y) / x.y;
      res.z = x.z == 0.0 ? 1.0 : sin(x.z) / x.z;
      res.w = x.w == 0.0 ? 1.0 : sin(x.w) / x.w;
      return res;
    }
    float scanline(vec2 noise) {
      return fract(sin(dot(noise.xy, vec2(0.0001, 98.233))) * 925895933.14159265359);
    }
    float noisefloat(vec2 noise) {
      return fract(sin(dot(noise.xy, vec2(10.998, 98.233))) * 12433.14159265359);
    }

    const vec4 Zero = vec4(0.0);
    const vec4 Half = vec4(0.5);
    const vec4 One = vec4(1.0);
    const vec4 Two = vec4(2.0);
    const float Pi = 3.1415926535;
    const float Pi2 = 6.283185307;
    const vec4 A = vec4(0.5);
    const vec4 B = vec4(0.5);
    const float P = 0.5;
    const float CCFrequency = 3.59754545;
    const float YFrequency = 6.0;
    const float IFrequency = 1.2;
    const float QFrequency = 0.6;
    const float ScanTime = 52.6;
    const float MaxC = 2.1183;
    const vec4 MinC = vec4(-1.1183);
    const vec4 CRange = vec4(3.2366);

    vec4 CompositeSample(vec2 uv) {
      vec2 inverseRes = 1.0 / uResolution.xy;
      vec2 inverseP = vec2(P, 0.0) * inverseRes;
      vec2 c0 = uv;
      vec2 c1 = uv + inverseP * 0.25;
      vec2 c2 = uv + inverseP * 0.50;
      vec2 c3 = uv + inverseP * 0.75;
      vec4 cx = vec4(c0.x, c1.x, c2.x, c3.x);
      vec4 cy = vec4(c0.y, c1.y, c2.y, c3.y);
      vec3 texel0 = texture2D(tDiffuse, c0).rgb;
      vec3 texel1 = texture2D(tDiffuse, c1).rgb;
      vec3 texel2 = texture2D(tDiffuse, c2).rgb;
      vec3 texel3 = texture2D(tDiffuse, c3).rgb;
      vec4 t = A * cy * vec4(uResolution.x) * Two + B + cx;
      const vec3 yTransform = vec3(0.299, 0.587, 0.114);
      const vec3 iTransform = vec3(0.595716, -0.274453, -0.321263);
      const vec3 qTransform = vec3(0.211456, -0.522591, 0.311135);
      vec4 y = vec4(
        dot(texel0, yTransform), dot(texel1, yTransform),
        dot(texel2, yTransform), dot(texel3, yTransform)
      );
      vec4 i = vec4(
        dot(texel0, iTransform), dot(texel1, iTransform),
        dot(texel2, iTransform), dot(texel3, iTransform)
      );
      vec4 q = vec4(
        dot(texel0, qTransform), dot(texel1, qTransform),
        dot(texel2, qTransform), dot(texel3, qTransform)
      );
      vec4 phase = (CCFrequency * ScanTime) * t;
      vec4 encoded = y + i * cos(Pi2 * fract(phase)) + q * sin(Pi2 * fract(phase));
      return (encoded - MinC) / CRange;
    }

    vec3 NTSCCodec(vec2 uv) {
      vec2 inverseRes = 1.0 / uResolution.xy;
      vec4 yAccum = Zero;
      vec4 iAccum = Zero;
      vec4 qAccum = Zero;
      float quadXSize = uResolution.x * 4.0;
      float timePerSample = ScanTime / quadXSize;
      float fcY1 = (CCFrequency - NotchHalfWidth) * timePerSample;
      float fcY2 = (CCFrequency + NotchHalfWidth) * timePerSample;
      float fcY3 = YFrequency * timePerSample;
      float fcI = IFrequency * timePerSample;
      float fcQ = QFrequency * timePerSample;
      float pi2Length = Pi2 / 82.0;
      vec4 notchOffset = vec4(0.0, 1.0, 2.0, 3.0);
      for (float n = -41.0; n < 42.0; n += 4.0) {
        vec4 n4 = n + notchOffset;
        vec4 coordX = uv.x + inverseRes.x * n4 * 0.25;
        vec4 coordY = vec4(uv.y);
        vec2 texCoord = vec2(coordX.r, coordY.r);
        vec4 c = CompositeSample(texCoord) * CRange + MinC;
        vec4 phase = (CCFrequency * ScanTime) *
          (coordX + A * coordY * Two * uResolution.x + B);
        vec4 cosWt = cos(Pi2 * fract(phase));
        vec4 sinWt = sin(Pi2 * fract(phase));
        vec4 sincY1 = safe_sinc(Pi2 * fcY1 * n4);
        vec4 sincY2 = safe_sinc(Pi2 * fcY2 * n4);
        vec4 sincY3 = safe_sinc(Pi2 * fcY3 * n4);
        vec4 idealY = (2.0 * fcY1 * sincY1 - 2.0 * fcY2 * sincY2) + 2.0 * fcY3 * sincY3;
        vec4 filterY = (0.54 + 0.46 * cos(pi2Length * n4)) * idealY;
        vec4 sincI = safe_sinc(Pi2 * fcI * n4);
        vec4 idealI = 2.0 * fcI * sincI;
        vec4 filterI = (0.54 + 0.46 * cos(pi2Length * n4)) * idealI;
        vec4 sincQ = safe_sinc(Pi2 * fcQ * n4);
        vec4 idealQ = 2.0 * fcQ * sincQ;
        vec4 filterQ = (0.54 + 0.46 * cos(pi2Length * n4)) * idealQ;
        yAccum += c * filterY;
        iAccum += c * cosWt * filterI;
        qAccum += c * sinWt * filterQ;
      }
      float y = yAccum.r + yAccum.g + yAccum.b + yAccum.a;
      float i = (iAccum.r + iAccum.g + iAccum.b + iAccum.a) * 2.0;
      float q = (qAccum.r + qAccum.g + qAccum.b + qAccum.a) * 2.0;
      vec3 yiq = vec3(y, i, q);
      return vec3(
        dot(yiq, vec3(1.0, 0.956, 0.621)),
        dot(yiq, vec3(1.0, -0.272, -0.647)),
        dot(yiq, vec3(1.0, -1.106, 1.703))
      );
    }

    vec3 tex2D(sampler2D tex, vec2 p) {
      vec3 color = texture2D(tex, p).xyz;
      if (0.5 < abs(p.x - 0.5)) color = vec3(0.1);
      return color;
    }
    float hash(vec2 v) {
      return fract(sin(dot(v, vec2(89.44, 19.36))) * 22189.22);
    }
    float iHash(vec2 v, vec2 r) {
      float h00 = hash(vec2(floor(v * r + vec2(0.0, 0.0)) / r));
      float h10 = hash(vec2(floor(v * r + vec2(1.0, 0.0)) / r));
      float h01 = hash(vec2(floor(v * r + vec2(0.0, 1.0)) / r));
      float h11 = hash(vec2(floor(v * r + vec2(1.0, 1.0)) / r));
      vec2 ip = vec2(smoothstep(vec2(0.0), vec2(1.0), mod(v * r, 1.0)));
      return (h00 * (1.0 - ip.x) + h10 * ip.x) * (1.0 - ip.y) +
        (h01 * (1.0 - ip.x) + h11 * ip.x) * ip.y;
    }
    float tapeNoise(vec2 v) {
      float sum = 0.0;
      for (int i = 1; i < 9; i++) {
        sum += iHash(v + vec2(float(i)), vec2(2.0 * pow(2.0, float(i)))) /
          pow(2.0, float(i));
      }
      return sum;
    }

    void main() {
      vec2 normUv = gl_FragCoord.xy / uResolution.xy;
      vec2 invUv = gl_FragCoord.xy * (1.0 / uResolution.xy);
      normUv += (tapeNoise(vec2(normUv.y * 100.0, uTime * 10.0)) - 0.5) *
        (uDistortionStrength / 1000.0);
      invUv += (tapeNoise(vec2(normUv.y * 100.0, uTime * 10.0)) - 0.5) *
        (uDistortionStrength / 1000.0);
      vec2 noiseUv = fract(normUv * fract(sin(uTime * uNoiseSpeed)));
      vec3 scanlineColor = vec3(scanline(noiseUv.xy)) * uScanlineStrength;
      vec3 noiseColor = vec3(noisefloat(noiseUv.xy)) * uNoiseStrength;
      vec3 mixedNoise = mix(scanlineColor, noiseColor, 0.5);
      vec3 ntscColor = NTSCCodec(invUv);
      vec2 bloomUv = normUv;
      vec3 bloomColor = vec3(0.0);
      for (int i = 0; i < 13; i++) {
        float x = -uBloomStrength + float(i);
        if (x >= 2.5) break;
        bloomColor += vec3(
          tex2D(tDiffuse, bloomUv + vec2(x - 0.0, 0.0) * 7e-3).x,
          tex2D(tDiffuse, bloomUv + vec2(x - 2.0, 0.0) * 7e-3).y,
          tex2D(tDiffuse, bloomUv + vec2(x - 4.0, 0.0) * 7e-3).z
        ) * 0.1;
      }
      bloomColor -= uBloomStrength / 100.0;
      gl_FragColor = vec4(ntscColor + bloomColor + mixedNoise, 1.0);
    }
  `,
  outline: /* glsl */ `
    uniform vec3 uOutlineColor;
    uniform float uOutlineThickness;
    uniform float uOutlineOpacity;
    uniform float uOutlineOnly;

    void main() {
      vec2 texelSize = 1.0 / uResolution;
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      if (aspect != 1.0) {
        if (aspect > 1.0) texelSize *= vec2(1.0, 1.0 / aspect);
        else texelSize *= vec2(aspect, 1.0);
        texelSize.x *= 1.0 / aspect;
      }
      vec4 original = texture2D(tDiffuse, vUv);
      vec4 outline = vec4(0.0);
      int thickness = int(clamp(uOutlineThickness, 0.0, 50.0));
      for (int x = -50; x <= 50; x++) {
        if (x < -thickness || x > thickness) continue;
        for (int y = -50; y <= 50; y++) {
          if (y < -thickness || y > thickness) continue;
          vec2 sampleOffset = vec2(float(x), float(y)) * texelSize;
          vec4 sampleTexel = texture2D(tDiffuse, vUv + sampleOffset);
          if (sampleTexel.a > 0.0 && original.a == 0.0) {
            outline = vec4(uOutlineColor, 1.0);
          }
        }
      }
      outline.a *= uOutlineOpacity;
      if (uOutlineOnly > 0.5) {
        gl_FragColor = outline;
      } else {
        gl_FragColor = mix(original, outline, outline.a);
      }
    }
  `,
  "drop-shadow": /* glsl */ `
    uniform vec2 uOffset;
    uniform vec3 uColor;
    uniform float uOpacity;
    uniform float uSpread;
    uniform float uSize;
    uniform int uSteps;
    uniform float uIsInner;
    uniform float uShadowOnly;

    float sdCircle(vec2 p, float r) {
      return length(p) - r;
    }

    void main() {
      vec2 texelSize = 1.0 / uResolution;
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      if (aspect != 1.0) {
        if (aspect > 1.0) texelSize *= vec2(1.0, 1.0 / aspect);
        else texelSize *= vec2(aspect, 1.0);
        texelSize.x *= 1.0 / aspect;
      }
      vec4 texel = texture2D(tDiffuse, vUv);
      vec4 shadow = vec4(0.0);
      float totalWeight = 0.0;
      float spreadScale = 1.0 + uSpread * 10.0;
      int steps = clamp(uSteps, 1, 50);
      vec2 offsetUv = uOffset * texelSize;
      bool inner = uIsInner > 0.5;

      if (steps == 0) {
        vec2 shadowUv = vUv + (inner ? -offsetUv : offsetUv);
        vec4 sampleTexel = texture2D(tDiffuse, shadowUv);
        shadow.a = inner ? 1.0 - sampleTexel.a : sampleTexel.a;
        shadow.rgb = uColor;
        shadow.a *= uOpacity;
      } else {
        for (int x = -25; x <= 25; x++) {
          if (x < -steps || x > steps) continue;
          for (int y = -25; y <= 25; y++) {
            if (y < -steps || y > steps) continue;
            vec2 sampleOffset = vec2(float(x), float(y)) * texelSize * uSize;
            vec2 shadowUv = vUv + (inner ? -sampleOffset - offsetUv : sampleOffset + offsetUv);
            vec4 sampleTexel = texture2D(tDiffuse, shadowUv);
            float sdf = sdCircle(vec2(float(x), float(y)) / 4.0, spreadScale);
            float weight = 1.0 - smoothstep(0.0, 1.0, sdf);
            if (inner) shadow.a += (1.0 - sampleTexel.a) * weight;
            else shadow.a += sampleTexel.a * weight;
            totalWeight += weight;
          }
        }
        shadow.a /= max(totalWeight, 0.0001);
        shadow.rgb = uColor;
        shadow.a *= uOpacity;
      }

      vec4 finalColor;
      if (uShadowOnly > 0.5 && !inner) {
        finalColor = vec4(shadow.rgb * shadow.a, shadow.a);
      } else if (inner) {
        vec3 shadowColor = mix(texel.rgb, uColor, shadow.a);
        finalColor = vec4(mix(texel.rgb, shadowColor, texel.a * shadow.a), texel.a);
      } else {
        finalColor = vec4(
          texel.rgb + shadow.rgb * shadow.a * (1.0 - texel.a),
          texel.a + shadow.a * (1.0 - texel.a)
        );
      }
      gl_FragColor = finalColor;
    }
  `,
  "streak-glow": /* glsl */ `
    uniform float uRange;
    uniform float uSteps;
    uniform float uThreshold;
    uniform float uBrightness;
    uniform float uNumRays;
    uniform float uAngleOffset;
    uniform float uRenderInputOnTop;
    uniform sampler2D uCoverageMap;
    uniform float uHasCoverage;

    void main() {
      vec2 uv = vUv;
      vec4 color = texture2D(tDiffuse, uv);
      float steps = uSteps < 0.0001 ? 0.0001 : uSteps;
      float rayContribution = uBrightness * 2.0 / max(uNumRays, 1.0);
      for (float i = -uRange; i < uRange; i += steps) {
        float falloff = 1.0 - abs(i / max(uRange, 0.0001));
        for (float j = 0.0; j < uNumRays; j += 1.0) {
          float angle = uAngleOffset + j * (3.14159265359 * 2.0 / max(uNumRays, 1.0));
          vec2 offset = vec2(cos(angle), sin(angle)) * i;
          vec4 blur = texture2D(tDiffuse, uv + offset);
          if (blur.r + blur.g + blur.b > uThreshold * 3.0) {
            color += blur * falloff * steps * rayContribution;
          }
        }
      }
      if (uRenderInputOnTop > 0.5) {
        vec4 inputColor = texture2D(tDiffuse, vUv);
        // Same coverage rule as God rays (module 1313/1334).
        float coverage = uHasCoverage > 0.5
          ? texture2D(uCoverageMap, vUv).a
          : inputColor.a;
        color.rgb *= vec3(1.0 - coverage);
        color.rgb += inputColor.rgb;
      }
      gl_FragColor = color;
    }
  `,
  "morphing-fractal": /* glsl */ `
    uniform float uTime;
    uniform float uTimeOffset;
    uniform float uBaseTimeRate;
    uniform float uX;
    uniform float uY;
    uniform vec3 uColMult;
    uniform float uTwirl;
    uniform float uFriction;
    uniform int uIterations;
    #define ITERS 100

    vec2 rotate(vec2 p, float a) {
      return vec2(
        p.x * cos(a) + p.y * sin(a),
        -p.x * sin(a) + p.y * cos(a)
      );
    }

    float julia(vec2 c, vec2 c1, float maximum) {
      float xx = c.x * c.x;
      float yy = c.y * c.y;
      float xy = c.x * c.y;
      float s = xx + yy;
      for (int i = ITERS; i > 0; i--) {
        if (i > uIterations) break;
        c = vec2(xx - yy, xy + xy) + c1;
        xx = c.x * c.x;
        yy = c.y * c.y;
        xy = c.x * c.y;
        s = xx + yy;
        if (s >= maximum || i == 1) return float(ITERS - i) / float(ITERS);
      }
      return 0.0;
    }

    void main() {
      float t = uTime * uBaseTimeRate + uTimeOffset;
      vec4 col = texture2D(tDiffuse, vUv);
      vec2 c0 = (gl_FragCoord.xy / uResolution) - vec2(uX, uY);
      vec2 c = rotate(c0, t * uTwirl);
      float j = julia(c + cos(t / 2.0) / 4.0, c + sin(t / max(uFriction, 0.0001)) * 0.7, 16.0);
      float r = j * sin(c.x + t * uColMult.r) * col.r;
      float g = j * sin(c.y + t * uColMult.g) * col.g;
      float z = sqrt(max(
        pow(c.x, 2.0) + pow(c.y, 2.0) - 2.0 * c.x * c.y * cos(c.y),
        0.0
      ));
      float b = j * sin(z + t * uColMult.b) * col.b;
      gl_FragColor = vec4(r, g, b, 1.0);
    }
  `,
  displacement: /* glsl */ `
    uniform sampler2D uLayTexture;
    uniform float uHasMap;
    uniform float uDisplacementX;
    uniform float uDisplacementY;
    uniform float uTexScale;
    uniform float uNormalsMode;

    void main() {
      vec4 inputColor = texture2D(tDiffuse, vUv);
      if (uHasMap < 0.5) {
        gl_FragColor = inputColor;
        return;
      }
      vec2 displacementUv = (vUv - 0.5) * vec2(uTexScale) + 0.5;
      if (
        displacementUv.x < 0.0 || displacementUv.x > 1.0 ||
        displacementUv.y < 0.0 || displacementUv.y > 1.0
      ) {
        displacementUv = vec2(0.0);
      }
      vec3 mapColor = texture2D(uLayTexture, displacementUv).xyz;
      float dx;
      float dy;
      if (uNormalsMode > 0.5) {
        dx = (mapColor.r - 0.5) * uDisplacementX;
        dy = (mapColor.g - 0.5) * uDisplacementY;
      } else {
        dx = (mapColor.r - 0.5) * uDisplacementX;
        dy = (mapColor.r - 0.5) * uDisplacementY;
      }
      gl_FragColor = texture2D(tDiffuse, vec2(vUv.x - dx, vUv.y - dy));
    }
  `,
  "image-mask": /* glsl */ `
    uniform sampler2D uLayTexture;
    uniform float uHasMap;

    void main() {
      vec4 color = texture2D(tDiffuse, vUv);
      if (uHasMap < 0.5) {
        gl_FragColor = color;
        return;
      }
      vec4 mask = texture2D(uLayTexture, vUv);
      gl_FragColor = mix(color, vec4(0.0), 1.0 - mask.r);
    }
  `,
  spooky: /* glsl */ `
    uniform float uTime;
    uniform float uDistortion;
    uniform float uWidth;
    uniform float uSpeed;

    void main() {
      vec2 st = vUv;
      float distortion = sin(st.y * uDistortion + uTime) * uWidth;
      gl_FragColor = texture2D(
        tDiffuse,
        vec2(st.x + distortion, st.y - sin(uTime * uSpeed) / 4.0)
      );
    }
  `,
  "impact-ripple": /* glsl */ `
    uniform float uTime;
    uniform float uWaveFrequency;
    uniform float uWaveAmplitude;
    uniform float uWaveWidth;
    uniform float uCenterX;
    uniform float uCenterY;
    uniform float uManualControl;
    uniform float uManualProgression;
    uniform float uAutoFrequency;
    uniform float uBrightnessMultiplier;

    float saw(float x) {
      return fract(x);
    }

    void main() {
      float currentTime = uManualControl > 0.5
        ? uManualProgression
        : saw(uTime * uAutoFrequency);
      vec3 waveParams = vec3(uWaveFrequency, uWaveAmplitude, uWaveWidth * 0.1);
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 waveCenter = vec2(uCenterX, uCenterY);
      vec2 texCoord = (vUv - 0.5) * vec2(aspect, 1.0) + 0.5;
      float dist = distance(texCoord, waveCenter);
      vec4 color = texture2D(tDiffuse, vUv);
      float waveStart = currentTime - waveParams.z;
      float waveEnd = currentTime + waveParams.z;
      if (dist >= waveStart && dist <= waveEnd) {
        float diff = dist - currentTime;
        float scaleDiff = 1.0 - pow(abs(diff * waveParams.x), waveParams.y);
        float diffTime = diff * scaleDiff;
        vec2 diffTexCoord = normalize(texCoord - waveCenter);
        float denom = currentTime * dist * 40.0;
        if (abs(denom) < 0.0001) denom = denom < 0.0 ? -0.0001 : 0.0001;
        vec2 newTexCoord = vUv + ((diffTexCoord * diffTime) / denom);
        if (
          newTexCoord.x >= 0.0 && newTexCoord.x <= 1.0 &&
          newTexCoord.y >= 0.0 && newTexCoord.y <= 1.0
        ) {
          color = texture2D(tDiffuse, newTexCoord);
          if (uBrightnessMultiplier != 0.0) {
            float brightDenom = currentTime * dist * 40.0 / uBrightnessMultiplier;
            if (abs(brightDenom) < 0.0001) brightDenom = brightDenom < 0.0 ? -0.0001 : 0.0001;
            color += (color * scaleDiff) / brightDenom;
          }
        }
      }
      gl_FragColor = color;
    }
  `,
  "render-layer": /* glsl */ `
    uniform sampler2D uLayTexture;

    void main() {
      vec4 inputColor = texture2D(tDiffuse, vUv);
      vec4 layerColor = texture2D(uLayTexture, vUv);
      gl_FragColor = mix(inputColor, layerColor, layerColor.a);
    }
  `,
  "repeating-ripple": /* glsl */ `
    uniform float uTime;
    uniform float uDistortionIntensity;
    uniform float uAnimationSpeed;
    uniform float uCenterX;
    uniform float uCenterY;
    uniform float uWaveFrequency;

    void main() {
      vec2 uv = vUv;
      vec2 center = vec2(uCenterX, uCenterY);
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 centerPosition = (uv - center) * vec2(aspect, 1.0);
      float centerLength = max(length(centerPosition), 0.0001);
      vec2 distortedUv = uv +
        (centerPosition / centerLength) *
        cos(centerLength * uWaveFrequency - uTime * uAnimationSpeed) *
        uDistortionIntensity;
      vec3 color = texture2D(tDiffuse, distortedUv).xyz;
      gl_FragColor = vec4(color, 1.0);
    }
  `,
  "rgb-displace": /* glsl */ `
    // Reference module 1329 (main~56930160.81d4160c.chunk.pretty.js @1131):
    // each channel is sampled at its own offset and written straight through:
    // gl_FragColor = vec4(red.r, green.g, blue.b, totalAlpha), with
    // totalAlpha = (red.a + green.a + blue.a) / 3.0. Our layer buffers are
    // premultiplied, so the shipped expression is already correct; the previous
    // version divided every channel by its own alpha and re-weighted it by the
    // average, which brightened each channel differently on any texel with
    // partial alpha and produced the cyan/yellow fringe on swim's wordmark.
    uniform float uDisplaceRX;
    uniform float uDisplaceRY;
    uniform float uScaleR;
    uniform float uDisplaceGX;
    uniform float uDisplaceGY;
    uniform float uScaleG;
    uniform float uDisplaceBX;
    uniform float uDisplaceBY;
    uniform float uScaleB;

    bool inBounds(vec2 pos) {
      return pos.x >= 0.0 && pos.x <= 1.0 && pos.y >= 0.0 && pos.y <= 1.0;
    }
    vec2 scaleCoords(float s, vec2 p) {
      return ((p - 0.5) / max(s, 0.0001)) + 0.5;
    }

    void main() {
      vec2 rPos = scaleCoords(uScaleR, vUv) + vec2(uDisplaceRX / 100.0, uDisplaceRY / 100.0);
      vec4 red = inBounds(rPos) ? texture2D(tDiffuse, rPos) : vec4(0.0);
      vec2 gPos = scaleCoords(uScaleG, vUv) + vec2(uDisplaceGX / 100.0, uDisplaceGY / 100.0);
      vec4 green = inBounds(gPos) ? texture2D(tDiffuse, gPos) : vec4(0.0);
      vec2 bPos = scaleCoords(uScaleB, vUv) + vec2(uDisplaceBX / 100.0, uDisplaceBY / 100.0);
      vec4 blue = inBounds(bPos) ? texture2D(tDiffuse, bPos) : vec4(0.0);
      float totalAlpha = (red.a + green.a + blue.a) / 3.0;
      gl_FragColor = vec4(red.r, green.g, blue.b, totalAlpha);
    }
  `,
  scale: /* glsl */ `
    uniform float uScaleX;
    uniform float uScaleY;

    void main() {
      vec2 factor = vec2(uScaleX, uScaleY);
      gl_FragColor = texture2D(tDiffuse, ((vUv - 0.5) * factor) + 0.5);
    }
  `,
  "channel-blur": /* glsl */ `
    uniform float uRedBlur;
    uniform float uGreenBlur;
    uniform float uBlueBlur;

    const float weights[5] = float[5](0.227027, 0.194595, 0.121622, 0.054054, 0.016216);

    float sampleChannel(vec4 s, int channel) {
      return channel == 0 ? s.r : (channel == 1 ? s.g : s.b);
    }

    vec2 blur5Premul(vec2 uv, vec2 direction, float amount, int channel) {
      vec4 c0 = texture2D(tDiffuse, uv);
      float colorAcc = sampleChannel(c0, channel) * c0.a * weights[0];
      float alphaAcc = c0.a * weights[0];
      float normalizedAmount = amount * 0.001;
      vec2 texelSize = direction * normalizedAmount;
      if (direction.x != 0.0) {
        texelSize.x /= max(uResolution.x / uResolution.y, 0.0001);
      }
      for (int i = 1; i < 5; i++) {
        vec2 offset = texelSize * float(i);
        vec4 s1 = texture2D(tDiffuse, uv + offset);
        vec4 s2 = texture2D(tDiffuse, uv - offset);
        colorAcc += sampleChannel(s1, channel) * s1.a * weights[i];
        colorAcc += sampleChannel(s2, channel) * s2.a * weights[i];
        alphaAcc += s1.a * weights[i];
        alphaAcc += s2.a * weights[i];
      }
      return vec2(colorAcc, alphaAcc);
    }

    void main() {
      vec2 rH = blur5Premul(vUv, vec2(1.0, 0.0), uRedBlur, 0);
      vec2 rV = blur5Premul(vUv, vec2(0.0, 1.0), uRedBlur, 0);
      float rPremul = 0.5 * (rH.x + rV.x);
      float aR = 0.5 * (rH.y + rV.y);
      vec2 gH = blur5Premul(vUv, vec2(1.0, 0.0), uGreenBlur, 1);
      vec2 gV = blur5Premul(vUv, vec2(0.0, 1.0), uGreenBlur, 1);
      float gPremul = 0.5 * (gH.x + gV.x);
      float aG = 0.5 * (gH.y + gV.y);
      vec2 bH = blur5Premul(vUv, vec2(1.0, 0.0), uBlueBlur, 2);
      vec2 bV = blur5Premul(vUv, vec2(0.0, 1.0), uBlueBlur, 2);
      float bPremul = 0.5 * (bH.x + bV.x);
      float aB = 0.5 * (bH.y + bV.y);
      float alpha = max(aR, max(aG, aB));
      vec3 rgb;
      rgb.r = rPremul / max(aR, 0.00001);
      rgb.g = gPremul / max(aG, 0.00001);
      rgb.b = bPremul / max(aB, 0.00001);
      gl_FragColor = vec4(rgb * alpha, alpha);
    }
  `,
  "god-rays": /* glsl */ `
    uniform float uTime;
    uniform float uDecay;
    uniform float uDensity;
    uniform float uWeight;
    uniform float uRayCenterX;
    uniform float uRayCenterY;
    uniform float uAlphaMult;
    uniform float uSaturationMult;
    uniform float uIgnoreDark;
    uniform float uRenderInputOnTop;
    uniform float uThreshold;
    uniform sampler2D uCoverageMap;
    uniform float uHasCoverage;
    uniform int uSamples;

    float blendScreen(float base, float blend) {
      return 1.0 - ((1.0 - base) * (1.0 - blend));
    }
    vec4 blendScreen(vec4 base, vec4 blend) {
      return vec4(
        blendScreen(base.r, blend.r),
        blendScreen(base.g, blend.g),
        blendScreen(base.b, blend.b),
        blendScreen(base.a, blend.a)
      );
    }
    vec4 blendScreen(vec4 base, vec4 blend, float opacity) {
      return blendScreen(base, blend) * opacity + base * (1.0 - opacity);
    }
    vec3 blendScreen(vec3 base, vec3 blend) {
      return vec3(
        blendScreen(base.r, blend.r),
        blendScreen(base.g, blend.g),
        blendScreen(base.b, blend.b)
      );
    }
    vec3 blendScreen(vec3 base, vec3 blend, float opacity) {
      return blendScreen(base, blend) * opacity + base * (1.0 - opacity);
    }
    vec4 saturation(vec4 color, float adjustment) {
      const vec3 W = vec3(0.2125, 0.7154, 0.0721);
      vec3 intensity = vec3(dot(color.rgb, W));
      return mix(vec4(intensity, color.a), color, adjustment);
    }

    vec4 crepuscularRays(vec2 texCoords, vec2 pos) {
      vec2 tc = vUv;
      vec2 delta = tc - pos.xy;
      delta *= (1.0 / float(max(uSamples, 1)) * uDensity);
      float illuminationDecay = 1.0;
      vec4 color = texture2D(tDiffuse, tc.xy);
      tc += delta * fract(
        sin(dot(texCoords.xy + fract(uTime), vec2(12.9898, 78.233))) * 43758.5453
      );
      for (int i = 0; i < 100; i++) {
        if (i >= uSamples) break;
        tc -= delta;
        vec4 sampleColor = texture2D(tDiffuse, tc.xy);
        float luminance = dot(sampleColor.rgb, vec3(0.299, 0.587, 0.114));
        if (luminance > uThreshold) {
          sampleColor *= illuminationDecay * uWeight;
          if (uIgnoreDark > 0.5) {
            color = vec4(blendScreen(color.rgb, sampleColor.rgb, uAlphaMult), color.a);
          } else {
            color = blendScreen(color, sampleColor, uAlphaMult);
          }
        }
        illuminationDecay *= uDecay;
      }
      color = saturation(color, uSaturationMult);
      if (uRenderInputOnTop > 0.5) {
        vec4 inputColor = texture2D(tDiffuse, vUv);
        // (module 361): the composition clears with clearAlpha 0, so the alpha
        // this branch reads is the layer stack's coverage - not 1. A
        // composition-wide chain is fed an opaque RGB frame here, so the
        // coverage arrives on its own map (see StageRenderer's coverage path).
        float coverage = uHasCoverage > 0.5
          ? texture2D(uCoverageMap, vUv).a
          : inputColor.a;
        color.rgb *= vec3(1.0 - coverage);
        color.rgb += inputColor.rgb;
      }
      return color;
    }

    void main() {
      vec2 pos = vec2(0.5 - uRayCenterX, 0.5 - uRayCenterY);
      gl_FragColor = crepuscularRays(vUv, pos);
    }
  `,
  "chroma-key": /* glsl */ `
    uniform vec3 uKeyColor;
    uniform float uColorCutoff;
    uniform float uColorFeathering;
    uniform float uDespillAmt;
    uniform float uDespillLuminanceAdd;

    float rgb2y(vec3 c) {
      return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b;
    }
    float rgb2cb(vec3 c) {
      return 0.5 - 0.168736 * c.r - 0.331264 * c.g + 0.5 * c.b;
    }
    float rgb2cr(vec3 c) {
      return 0.5 + 0.5 * c.r - 0.418688 * c.g - 0.081312 * c.b;
    }
    float colorclose(float cbP, float crP, float cbKey, float crKey, float tola, float tolb) {
      float temp = (cbKey - cbP) * (cbKey - cbP) + (crKey - crP) * (crKey - crP);
      float tola2 = tola * tola;
      float tolb2 = tolb * tolb;
      if (temp < tola2) return 0.0;
      if (temp < tolb2) return (temp - tola2) / max(tolb2 - tola2, 0.00001);
      return 1.0;
    }
    float maskFor(vec4 color) {
      float keyCb = rgb2cb(uKeyColor);
      float keyCr = rgb2cr(uKeyColor);
      float pixCb = rgb2cb(color.rgb);
      float pixCr = rgb2cr(color.rgb);
      return colorclose(pixCb, pixCr, keyCb, keyCr, uColorCutoff, uColorFeathering);
    }

    void main() {
      vec4 color = straight(vUv);
      float mask = maskFor(color);
      vec4 result = color * mask;
      float v = (2.0 * result.b + result.r) / 4.0;
      if (result.g > v) result.g = mix(result.g, v, uDespillAmt);
      vec4 dif = color - result;
      float desaturatedDif = rgb2y(dif.xyz);
      result += mix(0.0, desaturatedDif, uDespillLuminanceAdd);
      float alpha = mask * color.a;
      // The shipped program writes *straight* RGB with the mask alpha
      // (gl_FragColor = vec4(result.xyz, mask*color.a), module 1299 of
      // main~56930160). Premultiplying here a second time drops every keyed
      // colour to zero: a black key has the same chroma as white, so
      // trap-city-2012's white title keyed out completely instead of surviving
      // through the additive layer composite.
      gl_FragColor = vec4(result.rgb, alpha);
    }
  `,
  "edge-detection": /* glsl */ `
    uniform float uStrength;
    uniform float uThreshold;
    uniform float uThickness;
    uniform float uEdgeMode;
    uniform vec3 uEdgeColor;
    uniform float uUseOriginalColor;
    uniform float uMaskToAlpha;
    uniform float uOverlay;
    uniform float uInvert;
    uniform float uOpacity;
    uniform float uSourceOpacity;

    float getValue(vec2 uv) {
      vec2 physicalPixel = 1.0 / uResolution;
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 texel = vec2(1.0 / (1080.0 * aspect), 1.0 / 1080.0) * uThickness;
      vec2 margin = max(0.5 * texel, 1.5 * physicalPixel);
      vec2 clampedUv = clamp(uv, margin, 1.0 - margin);
      vec4 c = texture2D(tDiffuse, clampedUv);
      vec3 unpremult = c.rgb / max(c.a, 0.001);
      return dot(unpremult, vec3(0.299, 0.587, 0.114)) * c.a;
    }

    void main() {
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 texel = vec2(1.0 / (1080.0 * aspect), 1.0 / 1080.0) * uThickness;
      float t00 = getValue(vUv + vec2(-texel.x, -texel.y));
      float t10 = getValue(vUv + vec2(0.0, -texel.y));
      float t20 = getValue(vUv + vec2(texel.x, -texel.y));
      float t01 = getValue(vUv + vec2(-texel.x, 0.0));
      float t11 = getValue(vUv);
      float t21 = getValue(vUv + vec2(texel.x, 0.0));
      float t02 = getValue(vUv + vec2(-texel.x, texel.y));
      float t12 = getValue(vUv + vec2(0.0, texel.y));
      float t22 = getValue(vUv + vec2(texel.x, texel.y));

      float g = 0.0;
      int mode = int(uEdgeMode);
      if (mode == 0) {
        float gx = -t00 - 2.0 * t01 - t02 + t20 + 2.0 * t21 + t22;
        float gy = -t00 - 2.0 * t10 - t20 + t02 + 2.0 * t12 + t22;
        g = length(vec2(gx, gy)) / 4.0;
      } else if (mode == 1) {
        g = abs(8.0 * t11 - t00 - t10 - t20 - t01 - t21 - t02 - t12 - t22) / 8.0;
      } else if (mode == 2) {
        float gx = -t00 - t01 - t02 + t20 + t21 + t22;
        float gy = -t00 - t10 - t20 + t02 + t12 + t22;
        g = length(vec2(gx, gy)) / 3.0;
      } else {
        float gx = t00 - t22;
        float gy = t20 - t02;
        g = length(vec2(gx, gy));
      }
      if (uThreshold > 0.0) g = smoothstep(uThreshold, uThreshold + 0.05, g);
      g = clamp(g * uStrength, 0.0, 1.0);

      vec4 original = texture2D(tDiffuse, vUv);
      if (uMaskToAlpha > 0.5) g *= original.a;
      if (uInvert > 0.5) g = (uMaskToAlpha > 0.5 ? original.a : 1.0) - g;
      if (original.a > 0.0) original.rgb /= original.a;
      vec3 edgeColor = uUseOriginalColor > 0.5
        ? mix(uEdgeColor, original.rgb, original.a)
        : uEdgeColor;
      float effectiveG = g * uOpacity;
      vec3 result;
      float finalAlpha;
      if (uOverlay > 0.5) {
        float srcAlpha = original.a * uSourceOpacity;
        vec3 premultSource = original.rgb * srcAlpha;
        vec3 premultEdge = edgeColor * effectiveG;
        vec3 premult = premultEdge + premultSource * (1.0 - effectiveG);
        finalAlpha = effectiveG + srcAlpha * (1.0 - effectiveG);
        result = finalAlpha > 0.0 ? premult / finalAlpha : vec3(0.0);
      } else {
        result = edgeColor;
        finalAlpha = effectiveG;
      }
      gl_FragColor = vec4(result * finalAlpha, finalAlpha);
    }
  `,
  fxaa: /* glsl */ `
    uniform float uReduceMin;
    uniform float uReduceMax;
    uniform float uSpanMax;

    void main() {
      vec2 resolution = uResolution;
      vec2 inverseResolution = 1.0 / resolution;
      vec2 screenPos = vUv * resolution;
      vec4 rgbaNW = texture2D(tDiffuse, (screenPos + vec2(-1.0, -1.0)) * inverseResolution);
      vec4 rgbaNE = texture2D(tDiffuse, (screenPos + vec2(1.0, -1.0)) * inverseResolution);
      vec4 rgbaSW = texture2D(tDiffuse, (screenPos + vec2(-1.0, 1.0)) * inverseResolution);
      vec4 rgbaSE = texture2D(tDiffuse, (screenPos + vec2(1.0, 1.0)) * inverseResolution);
      vec4 rgbaM = texture2D(tDiffuse, screenPos * inverseResolution);
      float lumaNW = dot(rgbaNW.rgb, vec3(0.299, 0.587, 0.114));
      float lumaNE = dot(rgbaNE.rgb, vec3(0.299, 0.587, 0.114));
      float lumaSW = dot(rgbaSW.rgb, vec3(0.299, 0.587, 0.114));
      float lumaSE = dot(rgbaSE.rgb, vec3(0.299, 0.587, 0.114));
      float lumaM = dot(rgbaM.rgb, vec3(0.299, 0.587, 0.114));
      float lumaMin = min(lumaM, min(min(lumaNW, lumaNE), min(lumaSW, lumaSE)));
      float lumaMax = max(lumaM, max(max(lumaNW, lumaNE), max(lumaSW, lumaSE)));
      vec2 dir;
      dir.x = -((lumaNW + lumaNE) - (lumaSW + lumaSE));
      dir.y = ((lumaNW + lumaSW) - (lumaNE + lumaSE));
      float dirReduce = max(
        (lumaNW + lumaNE + lumaSW + lumaSE) * (0.25 / max(uReduceMax, 0.0001)),
        1.0 / max(uReduceMin, 0.0001)
      );
      float rcpDirMin = 1.0 / (min(abs(dir.x), abs(dir.y)) + dirReduce);
      dir = min(
        vec2(uSpanMax, uSpanMax),
        max(vec2(-uSpanMax, -uSpanMax), dir * rcpDirMin)
      ) * inverseResolution;
      vec4 rgbaA = 0.5 * (
        texture2D(tDiffuse, screenPos * inverseResolution + dir * (1.0 / 3.0 - 0.5)) +
        texture2D(tDiffuse, screenPos * inverseResolution + dir * (2.0 / 3.0 - 0.5))
      );
      vec4 rgbaB = rgbaA * 0.5 + 0.25 * (
        texture2D(tDiffuse, screenPos * inverseResolution + dir * (0.0 - 0.5)) +
        texture2D(tDiffuse, screenPos * inverseResolution + dir * (1.0 - 0.5))
      );
      float lumaB = dot(rgbaB.rgb, vec3(0.299, 0.587, 0.114));
      gl_FragColor = (lumaB < lumaMin || lumaB > lumaMax) ? rgbaA : rgbaB;
    }
  `,
  "bloom-highpass": /* glsl */ `
    uniform float uThreshold;
    uniform float uSmoothWidth;

    void main() {
      vec4 texel = texture2D(tDiffuse, vUv);
      vec3 luma = vec3(0.299, 0.587, 0.114);
      float v = dot(texel.xyz, luma);
      float alpha = smoothstep(uThreshold, uThreshold + uSmoothWidth, v);
      gl_FragColor = mix(vec4(0.0), texel, alpha);
    }
  `,
  "bloom-blur": /* glsl */ `
    uniform vec2 uTexSize;
    uniform vec2 uDirection;
    uniform float uKernelRadius;
    uniform float uSigma;

    float gaussianPdf(float x, float sigma) {
      return 0.39894 * exp(-0.5 * x * x / (sigma * sigma)) / sigma;
    }

    void main() {
      vec2 invSize = 1.0 / uTexSize;
      float sigma = max(uSigma, 0.001);
      float weightSum = gaussianPdf(0.0, sigma);
      vec3 sum = texture2D(tDiffuse, vUv).rgb * weightSum;
      for (int i = 1; i < 11; i++) {
        if (float(i) >= uKernelRadius) break;
        float x = float(i);
        float w = gaussianPdf(x, sigma);
        vec2 offset = uDirection * invSize * x;
        vec3 sample1 = texture2D(tDiffuse, vUv + offset).rgb;
        vec3 sample2 = texture2D(tDiffuse, vUv - offset).rgb;
        sum += (sample1 + sample2) * w;
        weightSum += 2.0 * w;
      }
      gl_FragColor = vec4(sum / weightSum, 1.0);
    }
  `,
  "bloom-composite": /* glsl */ `
    uniform sampler2D uBlur1;
    uniform sampler2D uBlur2;
    uniform sampler2D uBlur3;
    uniform sampler2D uBlur4;
    uniform sampler2D uBlur5;
    uniform float uStrength;
    uniform float uRadius;

    float lerpBloomFactor(float factor) {
      float mirrorFactor = 1.2 - factor;
      return mix(factor, mirrorFactor, uRadius);
    }

    void main() {
      vec3 bloom =
        lerpBloomFactor(1.0) * texture2D(uBlur1, vUv).rgb +
        lerpBloomFactor(0.8) * texture2D(uBlur2, vUv).rgb +
        lerpBloomFactor(0.6) * texture2D(uBlur3, vUv).rgb +
        lerpBloomFactor(0.4) * texture2D(uBlur4, vUv).rgb +
        lerpBloomFactor(0.2) * texture2D(uBlur5, vUv).rgb;
      gl_FragColor = vec4(bloom * uStrength, 1.0);
    }
  `,
  "bloom-final": /* glsl */ `
    uniform sampler2D uBloomTexture;
    uniform float uRenderBaseTexture;
    uniform float uRenderBaseAdditive;

    void main() {
      vec4 baseColor = texture2D(tDiffuse, vUv);
      vec3 bloom = texture2D(uBloomTexture, vUv).rgb;
      float bloomAlpha = (bloom.r + bloom.g + bloom.b) / 3.0;
      vec4 color = vec4(bloom, 1.0);
      if (uRenderBaseTexture > 0.5) {
        color.rgb *= vec3(1.0 - baseColor.a);
        color.rgb += baseColor.rgb;
        color.a = baseColor.a + bloomAlpha;
      }
      if (uRenderBaseAdditive > 0.5) {
        // The shipped final pass keeps bloom visible over transparent base
        // pixels; sign(0) selects the bloom alpha there. The base RGB is only
        // included when uRenderBaseTexture is on: otherwise a layer with
        // renderBaseAdditive true would still paint its underlying image
        // (foliage's additive bloom layers).
        float alpha = mix(bloomAlpha, baseColor.a, sign(baseColor.a));
        vec3 rgb = bloom + (uRenderBaseTexture > 0.5 ? baseColor.rgb : vec3(0.0));
        gl_FragColor = vec4(rgb, alpha);
      } else {
        gl_FragColor = color;
      }
    }
  `,
  fisheye: /* glsl */ `
    uniform float uAmount;
    uniform float uPreScale;

    void main() {
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 ndcPos = (vUv * 2.0 - 1.0) / uPreScale;
      float eyeAngle = abs(uAmount);
      float halfAngle = eyeAngle / 2.0;
      float halfDist = tan(halfAngle);
      vec2 vpScale = vec2(aspect, 1.0);
      vec2 p = ndcPos * vpScale;
      float vpDia = length(vpScale);
      float relDist = length(p) / vpDia;
      vec2 relP = normalize(p) / normalize(vpScale);
      vec2 posPrj = ndcPos;
      if (uAmount > 0.0) {
        float beta = relDist * halfAngle;
        posPrj = relP * tan(beta) / halfDist;
      } else if (uAmount < 0.0) {
        float beta = atan(relDist * halfDist);
        posPrj = relP * beta / halfAngle;
      }
      vec2 uv = posPrj * 0.5 + 0.5;
      vec2 rangeCheck = step(vec2(0.0), uv) * step(uv, vec2(1.0));
      if (rangeCheck.x * rangeCheck.y < 0.5) discard;
      gl_FragColor = texture2D(tDiffuse, uv);
    }
  `,
  "fisheye-2": /* glsl */ `
    uniform float uA;
    uniform float uB;
    uniform float uF;
    uniform float uScale;

    vec2 glCoord2TextureCoord(vec2 glCoord) {
      return glCoord * vec2(1.0, -1.0) / 2.0 + vec2(0.5, 0.5);
    }

    void main() {
      vec2 vPosition = (vUv - 0.5) * 2.0;
      vPosition.y *= -1.0;
      float a = 3.0 - uA;
      float b = 4.0 - uB;
      float f = 4.0 - uF;
      float scale = max(uScale, 0.0001);
      float l = length(vec3(vPosition.xy / scale, f));
      vec2 vMapping = vPosition.xy * f / max(l, 0.0001);
      vMapping *= vec2(a, b);
      vMapping = glCoord2TextureCoord(vMapping / scale);
      vec4 color = texture2D(tDiffuse, vMapping);
      if (
        vMapping.x > 0.99 || vMapping.x < 0.01 ||
        vMapping.y > 0.99 || vMapping.y < 0.01
      ) {
        color = vec4(0.0, 0.0, 0.0, 1.0);
      }
      gl_FragColor = color;
    }
  `,
  mirror: /* glsl */ `
    uniform float uPos;
    uniform float uLeft;
    uniform float uRight;
    uniform float uTop;
    uniform float uBottom;

    void main() {
      vec2 p = vUv;
      if (uLeft > 0.5) p.x -= step(uPos, p.x) * (p.x - uPos) * 2.0;
      if (uRight > 0.5) p.x += step(p.x, uPos) * (uPos - p.x) * 2.0;
      if (uTop > 0.5) p.y -= step(p.y, uPos) * (p.y - uPos) * 2.0;
      if (uBottom > 0.5) p.y += step(uPos, p.y) * (uPos - p.y) * 2.0;
      vec4 color = texture2D(tDiffuse, p);
      if (p.x > 1.0 || p.y > 1.0 || p.x < 0.0 || p.y < 0.0) {
        color = vec4(0.0);
      }
      gl_FragColor = color;
    }
  `,
  skew: /* glsl */ `
    uniform float uSkewX;
    uniform float uSkewY;
    uniform float uCenterX;
    uniform float uCenterY;

    void main() {
      vec2 uv = vUv;
      vec2 center = vec2(uCenterX, uCenterY);
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 offset = uv - center;
      uv.x += offset.y * uSkewX / aspect;
      uv.y += offset.x * uSkewY * aspect;
      vec2 clamped = clamp(uv, vec2(0.0), vec2(1.0));
      vec4 color = texture2D(tDiffuse, clamped);
      if (distance(uv, clamped) > 0.0) color *= 0.0;
      gl_FragColor = color;
    }
  `,
  twirl: /* glsl */ `
    uniform float uAmount;
    uniform float uCenterX;
    uniform float uCenterY;

    void main() {
      vec2 uv = vUv;
      vec2 center = vec2(uCenterX, uCenterY);
      vec2 delta = uv - center;
      float angle = uAmount * length(delta);
      float x = cos(angle) * delta.x - sin(angle) * delta.y;
      float y = sin(angle) * delta.x + cos(angle) * delta.y;
      uv = vec2(x + center.x, y + center.y);
      gl_FragColor = texture2D(tDiffuse, uv);
    }
  `,
  "polar-coordinates": /* glsl */ `
    uniform float uCurvature;
    const float PI = 3.141592653589793;

    vec2 rectToPolar(vec2 rect) {
      vec2 norm = (rect - vec2(0.5)) * vec2(uResolution.x / uResolution.y, -1.0);
      norm *= vec2(2.0);
      float theta = atan(norm.x, norm.y) + PI;
      return vec2(theta / (2.0 * PI), 1.0 - length(norm));
    }

    vec2 polarToRect(vec2 polar) {
      float theta = polar.x * 2.0 * PI;
      float r = polar.y;
      return vec2(r, theta / (2.0 * PI));
    }

    vec2 interpolateCoords(vec2 rect, float t) {
      if (t >= 0.0) {
        vec2 polar = rectToPolar(rect);
        return mix(rect, polar, t);
      }
      vec2 polar = rectToPolar(rect);
      return mix(rect, polarToRect(polar), -t);
    }

    void main() {
      vec2 uv = vUv;
      if (uv.x > 1.0 || uv.y > 1.0 || uv.x < 0.0 || uv.y < 0.0) discard;
      vec2 interpolated = interpolateCoords(uv, uCurvature);
      if (
        interpolated.x > 1.0 || interpolated.y > 1.0 ||
        interpolated.x < 0.0 || interpolated.y < 0.0
      ) discard;
      gl_FragColor = texture2D(tDiffuse, interpolated);
    }
  `,
  "bulge-pinch": /* glsl */ `
    uniform float uCenterX;
    uniform float uCenterY;
    uniform float uRadius;
    uniform float uStrength;
    uniform float uSmoothEdge;

    void main() {
      vec2 dimensions = uResolution;
      float radius = uRadius * min(dimensions.x, dimensions.y);
      vec2 coord = vUv * dimensions;
      coord -= vec2(uCenterX, uCenterY) * dimensions;
      float distanceFromCenter = length(coord);
      if (distanceFromCenter < radius && distanceFromCenter > 0.0) {
        float percent = distanceFromCenter / radius;
        if (uStrength > 0.0) {
          coord *= mix(
            1.0,
            smoothstep(0.0, radius / distanceFromCenter, percent),
            uStrength * 0.75
          );
        } else {
          coord *= mix(
            1.0,
            pow(percent, 1.0 + uStrength * 0.75) * radius / distanceFromCenter,
            1.0 - percent
          );
        }
      }
      coord += vec2(uCenterX, uCenterY) * dimensions;
      coord /= dimensions;
      vec2 clamped = clamp(coord, vec2(0.0), vec2(1.0));
      vec4 color = texture2D(tDiffuse, clamped);
      float edgeDistance = length(coord - clamped);
      if (edgeDistance > 0.0) {
        color *= max(0.0, 1.0 - edgeDistance / max(uSmoothEdge, 0.0001));
      }
      gl_FragColor = color;
    }
  `,
  "tilt-shift": /* glsl */ `
    uniform float uAmount;
    uniform float uFocusPosition;
    uniform float uFocusRange;
    uniform float uRotation;
    uniform int uAxis;
    uniform float uAspect;

    vec2 rotateUv(vec2 uv, float rotation) {
      float mid = 0.5;
      return vec2(
        cos(rotation) * (uv.x - mid) + sin(rotation) * (uv.y - mid) + mid,
        cos(rotation) * (uv.y - mid) - sin(rotation) * (uv.x - mid) + mid
      );
    }

    float getBlurAmount(vec2 uv) {
      vec2 rotatedUv = rotateUv(uv, radians(uRotation));
      return smoothstep(0.0, max(uFocusRange, 0.0001), abs(rotatedUv.y - uFocusPosition));
    }

    float gauss(float x, float sigma) {
      return exp(-(x * x) / (2.0 * sigma * sigma));
    }

    void main() {
      float amount = uAxis == 0 ? uAmount / max(uAspect, 0.0001) : uAmount;
      float blurAmount = amount * getBlurAmount(vUv);
      float sigma = max(blurAmount, 0.01);
      vec4 blurred = vec4(0.0);
      float totalWeight = 0.0;
      for (int i = -30; i <= 30; i++) {
        float offset = float(i) / 30.0;
        vec2 sampleUv = uAxis == 0
          ? vUv + vec2(offset * sigma / 500.0, 0.0)
          : vUv + vec2(0.0, offset * sigma / 500.0);
        float weight = gauss(offset, 1.0);
        blurred += texture2D(tDiffuse, sampleUv) * weight;
        totalWeight += weight;
      }
      gl_FragColor = vec4(blurred.rgb / totalWeight, blurred.a / totalWeight);
    }
  `,
  "zoom-blur": /* glsl */ `
    uniform float uCenterX;
    uniform float uCenterY;
    uniform float uStrength;
    uniform float uInnerRadius;
    uniform float uPasses;
    uniform float uGradientLength;

    float zoomRand(vec2 co, float seed) {
      float a = 12.9898;
      float b = 78.233;
      float c = 43758.5453;
      float dt = dot(co + seed, vec2(a, b));
      float sn = mod(dt, 3.14159);
      return fract(sin(sn) * c + seed);
    }

    void main() {
      vec2 iCenter = vec2(uCenterX, uCenterY);
      float iStrength = uStrength / 10.0;
      float iInnerRadius = uInnerRadius / 100.0;
      float iRadius = 10000.0;
      float iMaxKernelSize = max(uPasses, 1.0);

      vec2 vTextureCoord = vUv;
      iCenter *= uResolution.xy;
      iInnerRadius *= min(uResolution.x, uResolution.y);
      iRadius *= min(uResolution.x, uResolution.y);

      float minGradient = iInnerRadius * 0.3 * uGradientLength;
      float innerRadius = (iInnerRadius + minGradient * 0.5) / uResolution.x;
      float gradient = iRadius * 0.3;
      float radius = (iRadius - gradient * 0.5) / uResolution.x;
      float countLimit = iMaxKernelSize;

      vec2 dir = vec2(iCenter.xy / uResolution.xy - vTextureCoord);
      float dist = length(vec2(dir.x, dir.y * uResolution.y / uResolution.x));

      float strength = iStrength;
      float delta = 0.0;
      float gap = 0.0;
      if (dist < innerRadius) {
        delta = innerRadius - dist;
        gap = minGradient;
      } else if (radius >= 0.0 && dist > radius) {
        delta = dist - radius;
        gap = gradient;
      }

      if (delta > 0.0) {
        float normalCount = max(gap / uResolution.x, 0.0001);
        delta = (normalCount - delta) / normalCount;
        countLimit *= delta;
        strength *= delta;
        if (countLimit < 1.0) {
          gl_FragColor = texture2D(tDiffuse, vTextureCoord);
          return;
        }
      }

      float offset = zoomRand(vTextureCoord, 0.0);
      float total = 0.0;
      vec4 color = vec4(0.0);
      dir *= strength;

      for (int i = 0; i < 100; i++) {
        float t = float(i);
        if (t >= iMaxKernelSize) break;
        float percent = (t + offset) / iMaxKernelSize;
        float weight = 4.0 * (percent - percent * percent);
        vec2 p = vTextureCoord + dir * percent;
        color += straight(p) * weight;
        total += weight;
        if (t > countLimit) break;
      }
      if (total > 0.0001) color /= total;
      gl_FragColor = vec4(color.rgb * color.a, color.a);
    }
  `,
  blending: /* glsl */ `
    uniform sampler2D bDiffuse;
    uniform float uOpacity;
    uniform float uBlendGamma;
uniform float uHasBlendTarget;
    uniform int uBlendMode;

    vec3 rgbToHsl(vec3 color) {
      float fmin = min(min(color.r, color.g), color.b);
      float fmax = max(max(color.r, color.g), color.b);
      float delta = fmax - fmin;
      vec3 hsl;
      hsl.z = (fmax + fmin) * 0.5;
      if (delta == 0.0) {
        hsl.x = 0.0;
        hsl.y = 0.0;
      } else {
        hsl.y = hsl.z < 0.5 ? delta / (fmax + fmin) : delta / (2.0 - fmax - fmin);
        float deltaR = (((fmax - color.r) / 6.0) + (delta * 0.5)) / delta;
        float deltaG = (((fmax - color.g) / 6.0) + (delta * 0.5)) / delta;
        float deltaB = (((fmax - color.b) / 6.0) + (delta * 0.5)) / delta;
        if (color.r == fmax) hsl.x = deltaB - deltaG;
        else if (color.g == fmax) hsl.x = (1.0 / 3.0) + deltaR - deltaB;
        else hsl.x = (2.0 / 3.0) + deltaG - deltaR;
        if (hsl.x < 0.0) hsl.x += 1.0;
        else if (hsl.x > 1.0) hsl.x -= 1.0;
      }
      return hsl;
    }

    float hueToRgb(float f1, float f2, float hue) {
      if (hue < 0.0) hue += 1.0;
      else if (hue > 1.0) hue -= 1.0;
      if ((6.0 * hue) < 1.0) return f1 + (f2 - f1) * 6.0 * hue;
      if ((2.0 * hue) < 1.0) return f2;
      if ((3.0 * hue) < 2.0) return f1 + (f2 - f1) * ((2.0 / 3.0) - hue) * 6.0;
      return f1;
    }

    vec3 hslToRgb(vec3 hsl) {
      if (hsl.y == 0.0) return vec3(hsl.z);
      float f2 = hsl.z < 0.5 ? hsl.z * (1.0 + hsl.y) : (hsl.z + hsl.y) - (hsl.y * hsl.z);
      float f1 = 2.0 * hsl.z - f2;
      return vec3(
        hueToRgb(f1, f2, hsl.x + (1.0 / 3.0)),
        hueToRgb(f1, f2, hsl.x),
        hueToRgb(f1, f2, hsl.x - (1.0 / 3.0))
      );
    }

    vec3 blendMode(int mode, vec3 base, vec3 blend) {
      if (mode == 0) return blend;
      if (mode == 1) return max(blend, base);
      if (mode == 2) return min(blend, base);
      if (mode == 3) return base * blend;
      if (mode == 4) return base + blend * 0.5;
      if (mode == 5) return min(base + blend, vec3(1.0));
      if (mode == 6) return max(base - blend, vec3(0.0));
      if (mode == 7) return base / max(blend, vec3(0.0001));
      if (mode == 8) return abs(base - blend);
      if (mode == 9) return vec3(1.0) - abs(vec3(1.0) - base - blend);
      if (mode == 10) return base + blend - 2.0 * base * blend;
      if (mode == 11) return vec3(1.0) - ((vec3(1.0) - base) * (vec3(1.0) - blend));
      if (mode == 12) return min(base + blend, vec3(1.0));
      if (mode == 13) return min(base, blend) - max(base, blend) + vec3(1.0);
      if (mode == 14) return max(base + blend - vec3(1.0), vec3(0.0));
      if (mode == 15) return hslToRgb(vec3(rgbToHsl(blend).x, rgbToHsl(base).yz));
      if (mode == 16) return hslToRgb(vec3(rgbToHsl(base).x, rgbToHsl(blend).y, rgbToHsl(base).z));
      if (mode == 17) return hslToRgb(vec3(rgbToHsl(blend).xy, rgbToHsl(base).z));
      if (mode == 18) return hslToRgb(vec3(rgbToHsl(base).xy, rgbToHsl(blend).z));
      if (mode == 19) {
        return (blend.r + blend.g + blend.b) < (base.r + base.g + base.b) ? blend : base;
      }
      if (mode == 20) {
        return (blend.r + blend.g + blend.b) > (base.r + base.g + base.b) ? blend : base;
      }
      if (mode == 21) {
        return vec3(
          base.r < 0.5 ? 2.0 * base.r * blend.r : 1.0 - 2.0 * (1.0 - base.r) * (1.0 - blend.r),
          base.g < 0.5 ? 2.0 * base.g * blend.g : 1.0 - 2.0 * (1.0 - base.g) * (1.0 - blend.g),
          base.b < 0.5 ? 2.0 * base.b * blend.b : 1.0 - 2.0 * (1.0 - base.b) * (1.0 - blend.b)
        );
      }
      if (mode == 22) {
        return vec3(
          blend.r < 0.5 ? 2.0 * base.r * blend.r + base.r * base.r * (1.0 - 2.0 * blend.r)
            : sqrt(base.r) * (2.0 * blend.r - 1.0) + 2.0 * base.r * (1.0 - blend.r),
          blend.g < 0.5 ? 2.0 * base.g * blend.g + base.g * base.g * (1.0 - 2.0 * blend.g)
            : sqrt(base.g) * (2.0 * blend.g - 1.0) + 2.0 * base.g * (1.0 - blend.g),
          blend.b < 0.5 ? 2.0 * base.b * blend.b + base.b * base.b * (1.0 - 2.0 * blend.b)
            : sqrt(base.b) * (2.0 * blend.b - 1.0) + 2.0 * base.b * (1.0 - blend.b)
        );
      }
      if (mode == 23) {
        return vec3(
          blend.r < 0.5 ? 2.0 * base.r * blend.r : 1.0 - 2.0 * (1.0 - base.r) * (1.0 - blend.r),
          blend.g < 0.5 ? 2.0 * base.g * blend.g : 1.0 - 2.0 * (1.0 - base.g) * (1.0 - blend.g),
          blend.b < 0.5 ? 2.0 * base.b * blend.b : 1.0 - 2.0 * (1.0 - base.b) * (1.0 - blend.b)
        );
      }
      if (mode == 24) return min(base / max(vec3(1.0) - blend, vec3(0.0001)), vec3(1.0));
      if (mode == 25) return max(vec3(1.0) - ((vec3(1.0) - base) / max(blend, vec3(0.0001))), vec3(0.0));
      if (mode == 26) {
        vec3 burn = max(base + 2.0 * blend - vec3(1.0), vec3(0.0));
        vec3 dodge = min(base + 2.0 * (blend - vec3(0.5)), vec3(1.0));
        return mix(burn, dodge, step(vec3(0.5), blend));
      }
      if (mode == 27) {
        vec3 burn = max(vec3(1.0) - ((vec3(1.0) - base) / max(2.0 * blend, vec3(0.0001))), vec3(0.0));
        vec3 dodge = min(base / max(vec3(1.0) - 2.0 * (blend - vec3(0.5)), vec3(0.0001)), vec3(1.0));
        return mix(burn, dodge, step(vec3(0.5), blend));
      }
      if (mode == 28) {
        vec3 dark = min(base, 2.0 * blend);
        vec3 light = max(base, 2.0 * (blend - vec3(0.5)));
        return mix(dark, light, step(vec3(0.5), blend));
      }
      if (mode == 29) {
        vec3 burn = max(vec3(1.0) - ((vec3(1.0) - base) / max(2.0 * blend, vec3(0.0001))), vec3(0.0));
        vec3 dodge = min(base / max(vec3(1.0) - 2.0 * (blend - vec3(0.5)), vec3(0.0001)), vec3(1.0));
        vec3 vivid = mix(burn, dodge, step(vec3(0.5), blend));
        return step(vec3(0.5), vivid);
      }
      if (mode == 30) return min(base * base / max(vec3(1.0) - blend, vec3(0.0001)), vec3(1.0));
      if (mode == 31) return min(blend * blend / max(vec3(1.0) - base, vec3(0.0001)), vec3(1.0));
      return blend;
    }

    void main() {
      // Exactly the shipped Blending program: gamma-space samples, opacity
      // weighted by the blend layer's alpha, and the other layer's alpha as the
      // result. Un-premultiplying here amplified the tiny alpha left by earlier
      // passes into a full-frame grey wash.
      float gamma = max(uBlendGamma, 0.001);
      vec4 topSample = texture2D(tDiffuse, vUv);
      vec4 topPixel = vec4(pow(max(topSample.rgb, vec3(0.0)), vec3(gamma)), topSample.a);
      vec4 bottomSample = texture2D(bDiffuse, vUv);
      vec4 bottomPixel = bottomSample;
      if (topPixel.a == 0.0) {
        gl_FragColor = bottomPixel;
        return;
      }
      // No blend source: the blend target is unset, or that layer's buffer is
      // *colourless* (watercolor-cave's Sphere test holds a Spherical Field at
      // opacity 0). The shipped program only guards the empty *input*; with a
      // truly empty base every mode degenerates into a hard contrast curve over
      // black (pinlight(0, b) = max(0, 2b - 1)) and the result carries the
      // base's alpha of 0, so the RGB still reached the frame through the
      // premultiplied layer composite. Nothing to blend against means no blend.
      //
      // The base must be colourless for this to apply: watercolor-cave's blend
      // source is Butterchurn output with RGB around 72/255 and alpha 0, and
      // passing that through instead of blending against it cost 21.22 -> 57.88.
      // c-yt-b-blue's source is an empty particle layer (RGB 0, alpha 0), where
      // the same pass-through is what restores the badge (16.79 -> 2.15).
      if (
        uHasBlendTarget > 0.5 &&
        bottomPixel.a == 0.0 &&
        max(bottomPixel.r, max(bottomPixel.g, bottomPixel.b)) < (0.5 / 255.0)
      ) {
        // Raw, unlifted sample: topPixel is pow(top, blendGamma), and with
        // c-yt-b-blue's gamma of 20 that pass-through painted the layer black.
        gl_FragColor = topSample;
        return;
      }
      // No blend source at all: blendWith named no layer. The effect default is
      // the placeholder string "Screen" (main~b45a2766 sets this.blendWith =
      // "Screen") and renderEffect only assigns the uniform when the lookup
      // finds a layer:
      //
      //   const u = s.a.Instance.tryGetLayerTarget(this.blendWith);
      //   u && (this.uniforms.bDiffuse.value = u.texture)
      //
      // This branch restates the shipped expression for the null-sampler case and
      // is mathematically **redundant**: uHasBlendTarget is set in lockstep
      // with bDiffuse (see applyParams), a null sampler binds three's 1x1
      // empty texture (0,0,0,0), so the fall-through already evaluates exactly
      // this mix() at alpha 0. It is kept as documentation, not as a fix.
      //
      // Do not credit it with plasma-pill-kn's Color Wheel wash: the A/B in
      // docs/manager-log.md (2026-11-18) attributes that gain to the module 1293
      // alpha shader - reverting alpha costs the row +54.41, while removing
      // the two-pass pass count (the other candidate) costs +0.38. The
      // layer-composite rule that makes the wash visible (ONE /
      // ONE_MINUS_SRC_ALPHA) is the fall-through's own behaviour; zeroing the
      // RGB hid it and forcing alpha 1 painted barcode and burning-moon black,
      // but neither of those outcomes depends on this branch.
      if (uHasBlendTarget < 0.5) {
        vec3 blendedFromZero = blendMode(uBlendMode, vec3(0.0), topPixel.rgb);
        float topWeight = clamp(uOpacity * topPixel.a, 0.0, 1.0);
        gl_FragColor = vec4(
          pow(
            max(mix(vec3(0.0), blendedFromZero, topWeight), vec3(0.0)),
            vec3(1.0 / gamma)
          ),
          0.0
        );
        return;
      }
      // The shipped program gamma-lifts only the *blend* (top) sample; the base
      // stays in display space and the mixed result is un-gamma'd once. Lifting
      // the base as well turned any blendGamma below 1 into a near-white
      // additive plane: plasma-bloqy's particle layer (Blending with "Screen",
      // gamma 0.08, perspective -> additive) washed the whole frame white, while
      // the layer disabled leaves the correct teal sky.
      // The shipped program lifts both samples: it applies linear() to the
      // base inside the non-empty branch. Removing the base lift made a dark
      // base darken further after the un-gamma (swim's vhs layer read 152
      // grey); with the placeholder target fixed, lifting both is safe again.
      bottomPixel = vec4(
        pow(max(bottomPixel.rgb, vec3(0.0)), vec3(gamma)),
        bottomPixel.a
      );
      vec3 blended = blendMode(uBlendMode, bottomPixel.rgb, topPixel.rgb);
      // A fully transparent blend is the base frame untouched. Un-gammaing the
      // unlifted base is not identity: swim's Blending opacity is 0 at 24.72 s
      // and pow(26/255, 1/4) painted its whole vhs layer 144 grey.
      float weight = clamp(uOpacity * topPixel.a, 0.0, 1.0);
      if (weight <= 0.0) {
        // The shipped expression degenerates to the raw base at zero weight
        // (mix(base, blend, 0) = base), which is what eternal-pulse relies on:
        // its Noise layer's Blending has opacity 0 and blendWith the Background,
        // so the reference shows the background and never the noise wedge.
        // Returning the layer's own content there painted the noise at full
        // strength (mean 65.42 against the reference).
        gl_FragColor = bottomSample;
        return;
      }
      vec3 mixed = mix(bottomPixel.rgb, blended, weight);
      gl_FragColor = vec4(
        pow(max(mixed, vec3(0.0)), vec3(1.0 / gamma)),
        bottomPixel.a
      );
    }
  `,
  kaleidoscope: /* glsl */ `
    uniform float uSegments;
    uniform float uOffset;
    uniform bool uPreserveAspect;
    const float PI = 3.14159265359;
    const float TAU = 6.28318530718;
    void main() {
      if (uSegments == 0.0) {
        gl_FragColor = texture2D(tDiffuse, vUv);
        return;
      }
      vec2 aspect = uResolution / min(uResolution.x, uResolution.y);
      vec2 centered = (vUv - 0.5) * aspect;
      float r = length(centered);
      float theta = atan(centered.y, centered.x);
      theta = mod(theta, TAU / uSegments);
      theta = abs(theta - PI / uSegments);
      vec2 coords = r * vec2(cos(theta), sin(theta));
      if (uPreserveAspect) coords /= aspect;
      coords = mod(coords - uOffset, 1.0);
      gl_FragColor = texture2D(tDiffuse, coords);
    }
  `,
  crop: /* glsl */ `
    uniform float uTop;
    uniform float uBottom;
    uniform float uLeft;
    uniform float uRight;
    uniform bool uInvertCrop;
    uniform bool uClampEdges;
    vec4 lc(vec4 col, vec2 uv, float size, bool invert) {
      float l = invert ? step(uv.x, size) : step(size, uv.x);
      return col * l;
    }
    vec4 rc(vec4 col, vec2 uv, float size, bool invert) {
      float r = invert ? step(1.0 - uv.x, size) : step(size, 1.0 - uv.x);
      return col * r;
    }
    vec4 bc(vec4 col, vec2 uv, float size, bool invert) {
      float b = invert ? step(uv.y, size) : step(size, uv.y);
      return col * b;
    }
    vec4 tc(vec4 col, vec2 uv, float size, bool invert) {
      float t = invert ? step(1.0 - uv.y, size) : step(size, 1.0 - uv.y);
      return col * t;
    }
    void main() {
      vec2 uv = vUv;
      float left = uLeft / 100.0;
      float right = uRight / 100.0;
      float top = uTop / 100.0;
      float bottom = uBottom / 100.0;
      if (uClampEdges) {
        if (uInvertCrop) {
          uv.x = clamp(uv.x, 0.0, 1.0);
          uv.y = clamp(uv.y, 0.0, 1.0);
          if (vUv.x > left && vUv.x < (1.0 - right) && vUv.y > bottom && vUv.y < (1.0 - top)) {
            float dl = vUv.x - left;
            float dr = (1.0 - right) - vUv.x;
            float db = vUv.y - bottom;
            float dt = (1.0 - top) - vUv.y;
            if (min(dl, dr) < min(db, dt)) uv.x = dl < dr ? left : (1.0 - right);
            else uv.y = db < dt ? bottom : (1.0 - top);
          }
        } else {
          uv.x = clamp(uv.x, left, 1.0 - right);
          uv.y = clamp(uv.y, bottom, 1.0 - top);
        }
      }
      vec4 col = texture2D(tDiffuse, uv);
      if (uInvertCrop && !uClampEdges) {
        if (vUv.x > left && vUv.x < (1.0 - right) && vUv.y > bottom && vUv.y < (1.0 - top)) {
          col = vec4(0.0);
        }
      } else if (!uClampEdges) {
        col = lc(col, vUv, left, false);
        col = rc(col, vUv, right, false);
        col = tc(col, vUv, top, false);
        col = bc(col, vUv, bottom, false);
      }
      gl_FragColor = col;
    }
  `,
  trail: /* glsl */ `
    uniform sampler2D ptDiffuse;
    uniform float uAmount;
    void main() {
      vec4 prevCol = texture2D(ptDiffuse, vUv);
      vec4 currCol = texture2D(tDiffuse, vUv);
      prevCol *= uAmount;
      prevCol.a -= 0.01;
      if (prevCol.a < 0.001) prevCol = vec4(0.0);
      gl_FragColor = currCol * currCol.a + prevCol * (1.0 - currCol.a);
    }
  `,
  "bokeh-blur": /* glsl */ `
    uniform float uAmount;
    uniform float uBokehScale;
    uniform int uShapeType;
    uniform int uSamples;
    uniform bool uSmooth;
    uniform float uUseCustomAperture;
    uniform sampler2D uApertureTexture;

    const vec2 POISSON[24] = vec2[](
      vec2(-0.326,-0.406), vec2(-0.840,-0.074), vec2(-0.696, 0.457), vec2(-0.203, 0.621),
      vec2( 0.962,-0.195), vec2( 0.473,-0.480), vec2( 0.519, 0.767), vec2( 0.185,-0.893),
      vec2( 0.507, 0.064), vec2( 0.896, 0.412), vec2(-0.322,-0.933), vec2(-0.792,-0.598),
      vec2(-0.633, 0.143), vec2(-0.139, 0.936), vec2( 0.283,-0.290), vec2( 0.274, 0.543),
      vec2( 0.717,-0.714), vec2(-0.248, 0.133), vec2(-0.540,-0.295), vec2(-0.120,-0.754),
      vec2( 0.402, 0.237), vec2( 0.082, 0.846), vec2(-0.280, 0.799), vec2( 0.812,-0.006)
    );
    float hash(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }
    mat2 rot(float a) {
      float c = cos(a), s = sin(a);
      return mat2(c, -s, s, c);
    }
    float apertureMask(vec2 pNorm) {
      float r = length(pNorm);
      if (r > 1.0) return 0.0;
      if (uUseCustomAperture > 0.5) {
        vec2 uv = pNorm * 0.5 + 0.5;
        uv.x = 1.0 - uv.x;
        uv.y = 1.0 - uv.y;
        return texture2D(uApertureTexture, uv).r;
      }
      if (uShapeType == 0) return smoothstep(1.0, 0.85, r);
      if (uShapeType == 1) {
        vec2 q = abs(pNorm);
        float h = max(dot(q, vec2(0.8660254, 0.5)), q.y);
        return smoothstep(1.0, 0.9, h);
      }
      float a = atan(pNorm.y, pNorm.x);
      float m = cos(5.0 * a) * 0.3 + 0.7;
      return smoothstep(1.0, 0.9, r / m);
    }
    void main() {
      float blur = uAmount;
      if (blur < 0.05) {
        vec4 src = straight(vUv);
        gl_FragColor = vec4(src.rgb * src.a, src.a);
        return;
      }
      float normalizedSize = blur * uBokehScale * 0.001;
      float aspect = uResolution.x / uResolution.y;
      float rX = normalizedSize / aspect;
      float rY = normalizedSize;
      float jitter = uSmooth ? 0.0 : (hash(vUv) - 0.5) * 6.2831853;
      mat2 R = rot(jitter);
      vec4 acc = vec4(0.0);
      float wsum = 0.0;
      for (int i = 0; i < 24; i++) {
        if (i >= uSamples) break;
        vec2 p = POISSON[i];
        vec2 pRot = R * p;
        float w = apertureMask(pRot);
        if (w > 0.0) {
          vec4 s = straight(vUv + vec2(pRot.x * rX, pRot.y * rY));
          acc += vec4(s.rgb * s.a, s.a) * w;
          wsum += w;
        }
      }
      if (wsum < 1e-5) {
        vec4 src = straight(vUv);
        gl_FragColor = vec4(src.rgb * src.a, src.a);
        return;
      }
      vec4 result = acc / wsum;
      gl_FragColor = result;
    }
  `,
  "camera-shake": /* glsl */ `
    uniform vec4 uCurrentTransform;
    uniform vec4 uPreviousTransform;
    uniform int uTextureWrapping;
    uniform int uRepeatType;
    uniform int uUseRgbSplit;
    uniform float uRgbSplitLength;
    uniform int uUseMotionBlur;
    uniform float uMotionBlurLength;
    uniform int uMotionBlurIterations;
    uniform float uAspect;

    vec2 rotate(vec2 v, float a) {
      float s = sin(a);
      float c = cos(a);
      mat2 m = mat2(c, -s, s, c);
      v.x *= uAspect;
      v = m * v;
      v.x /= uAspect;
      return v;
    }
    vec4 getColor(vec2 p, float r, float s) {
      vec2 centeredUv = (vUv - 0.5) * 2.0;
      vec2 transformedUv = centeredUv + p.xy;
      transformedUv = rotate(transformedUv, r);
      transformedUv /= s;
      transformedUv = (transformedUv + 1.0) / 2.0;
      vec2 pos = transformedUv;
      vec2 clampedPos = pos;
      if (uTextureWrapping == 1) {
        clampedPos = mod(pos, 1.0);
        if (uRepeatType == 1 && (pos.x > 1.0 || pos.x < 0.0)) clampedPos = mod(vec2(1.0 - pos.x, pos.y), 1.0);
        if (uRepeatType == 2 && (pos.y > 1.0 || pos.y < 0.0)) clampedPos = mod(vec2(pos.x, 1.0 - pos.y), 1.0);
        if (uRepeatType == 3 && (pos.x > 1.0 || pos.x < 0.0 || pos.y > 1.0 || pos.y < 0.0)) clampedPos = mod(1.0 - pos, 1.0);
        if (uRepeatType == 4) {
          vec2 flip = mod(pos, 2.0);
          if (flip.y > 1.0) pos.y = 1.0 - pos.y;
          if (flip.x > 1.0) pos.x = 1.0 - pos.x;
          clampedPos = mod(pos, 1.0);
        }
      } else if (uTextureWrapping == 2 && (pos.x > 1.0 || pos.y > 1.0 || pos.x < 0.0 || pos.y < 0.0)) {
        return vec4(0.0);
      }
      vec4 col = texture2D(tDiffuse, clampedPos);
      if (uUseRgbSplit == 1) {
        float amount = distance(uCurrentTransform.x, uCurrentTransform.y);
        vec2 offset = amount * uCurrentTransform.xy;
        vec4 cr = texture2D(tDiffuse, clampedPos + offset * uRgbSplitLength);
        vec4 cga = texture2D(tDiffuse, clampedPos + offset * 2.0 * uRgbSplitLength);
        vec4 cb = texture2D(tDiffuse, clampedPos + offset * 3.0 * uRgbSplitLength);
        col = vec4(cr.r, cga.g, cb.b, cga.a);
      }
      return col;
    }
    void main() {
      vec4 col = vec4(0.0);
      if (uUseMotionBlur == 0) {
        col = getColor(uCurrentTransform.xy, uCurrentTransform.z, uCurrentTransform.w);
      } else {
        for (int i = 0; i < 100; i += 1) {
          if (i >= uMotionBlurIterations) break;
          // Shipped module 1291 computes
          //   float t = float(i) / motionBlurLength;
          // with no clamp, so a shutter longer than one sample step
          // (motionBlurIterations > motionBlurLength) walks past the current
          // pose and keeps going: retro reads 33x the per-frame travel with
          // 100 iterations over a length of 3, and with textureWrap Repeat /
          // repeatType Either those samples wrap into visible bands. Clamping
          // t to 0..1 turned that into a plain A-to-B smear.
          float t = float(i) / max(uMotionBlurLength, 0.001);
          vec4 ip = mix(uPreviousTransform, uCurrentTransform, t);
          col += getColor(ip.xy, ip.z, ip.w);
        }
        col /= float(max(uMotionBlurIterations, 1));
      }
      gl_FragColor = col;
    }
  `,
};

function uniformsFor(type: string): Record<string, THREE.IUniform> {
  const base = {
    tDiffuse: { value: null },
    uResolution: { value: new THREE.Vector2(1, 1) },
  };
  switch (type) {
    case "color-tint":
      return {
        ...base,
        uAmount: { value: 1 },
        uWeight: { value: 1 },
        uInvert: { value: 0 },
        uMapBlack: { value: new THREE.Vector3(0, 0, 0) },
        uMapWhite: { value: new THREE.Vector3(1, 1, 1) },
      };
    case "invert":
    case "alpha":
      return { ...base, ...(type === "invert" ? { uAmount: { value: 0 } } : { uAlpha: { value: 1 } }) };
    case "gray-scale":
      return { ...base, uAmount: { value: 50 } };
    case "sepia":
      return { ...base, uAmount: { value: 20 } };
    case "flicker":
      return {
        ...base,
        uTime: { value: 0 },
        uAmplitudeBrightness: { value: 1 },
        uFrequencyBrightness: { value: 7 },
        uAmplitudeColor: { value: 0.5 },
        uFrequencyColor: { value: 4 },
        uSeedColor: { value: 123 },
        uBrightness: { value: 1 },
        uContrast: { value: 1 },
        uDarken: { value: 1 },
      };
    case "color-correction":
      return {
        ...base,
        uHueAmount: { value: 0 },
        uBrightness: { value: 1 },
        uContrast: { value: 1 },
        uVibrance: { value: 0 },
        uSaturation: { value: 1 },
        uShadows: { value: 0 },
        uHighlights: { value: 0 },
        uInvert: { value: 0 },
        uAddR: { value: 0 },
        uAddG: { value: 0 },
        uAddB: { value: 0 },
        uMulR: { value: 1 },
        uMulG: { value: 1 },
        uMulB: { value: 1 },
      };
    case "directional-blur":
      return {
        ...base,
        uAmount: { value: 5 },
        uAngle: { value: 0 },
        uSamples: { value: 15 },
      };
    case "radial-blur":
      return {
        ...base,
        uAmount: { value: 10 },
        uCenter: { value: new THREE.Vector2(0.5, 0.5) },
        uSamples: { value: 16 },
      };
    case "horizontal-blur":
    case "vertical-blur":
      return { ...base, uAmount: { value: 1 } };
    case "glow":
      return {
        ...base,
        uGlowColor: { value: new THREE.Vector3(0.31, 0.18, 0.7) },
        uDistance: { value: 15 },
        uOuterStrength: { value: 2 },
        uInnerStrength: { value: 0 },
        uXSpread: { value: 251 },
        uYSpread: { value: 251 },
      };
    case "vignette":
      return {
        ...base,
        uVignetteColor: { value: new THREE.Vector3(0, 0, 0) },
        uTime: { value: 0 },
        uSize: { value: 0.5 },
        uSmoothness: { value: 0.5 },
        uRoundness: { value: 1 },
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
        uOpacity: { value: 1 },
        uDither: { value: 0.1 },
        uUseAlpha: { value: 0 },
        uMoveNoise: { value: 0 },
        uUseScreenAspect: { value: 0 },
      };
    case "camera-shake":
      return {
        ...base,
        uCurrentTransform: { value: new THREE.Vector4() },
        uPreviousTransform: { value: new THREE.Vector4() },
        uTextureWrapping: { value: 2 },
        uRepeatType: { value: 0 },
        uUseRgbSplit: { value: 0 },
        uRgbSplitLength: { value: 1 },
        uUseMotionBlur: { value: 0 },
        uMotionBlurLength: { value: 5 },
        uMotionBlurIterations: { value: 8 },
        uAspect: { value: 1 },
      };
    case "transform":
      return {
        ...base,
        uTransformData: {
          value: [new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4()],
        },
        uUseMotionBlur: { value: 0 },
        uMotionBlurLength: { value: 8 },
        uMotionBlurIterations: { value: 8 },
        uRepeatType: { value: 0 },
        uAspect: { value: 1 },
      };
    case "twirl":
      return {
        ...base,
        uAmount: { value: 2.5 },
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
      };
    case "skew":
      return {
        ...base,
        uSkewX: { value: 0 },
        uSkewY: { value: 0 },
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
      };
    case "mirror":
      return {
        ...base,
        uPos: { value: 0.5 },
        uLeft: { value: 1 },
        uRight: { value: 0 },
        uTop: { value: 0 },
        uBottom: { value: 0 },
      };
    case "fisheye-2":
      return {
        ...base,
        uA: { value: 2 },
        uB: { value: 3 },
        uF: { value: 3 },
        uScale: { value: 1 },
      };
    case "fisheye":
      return {
        ...base,
        uAmount: { value: 1 },
        uPreScale: { value: 1 },
      };
    case "polar-coordinates":
      return {
        ...base,
        uCurvature: { value: 1 },
      };
    case "bulge-pinch":
      return {
        ...base,
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
        uRadius: { value: 0.25 },
        uStrength: { value: 0.5 },
        uSmoothEdge: { value: 0.01 },
      };
    case "tilt-shift":
      return {
        ...base,
        uAmount: { value: 20 },
        uFocusPosition: { value: 0.5 },
        uFocusRange: { value: 0.1 },
        uRotation: { value: 0 },
        uAxis: { value: 0 },
        uAspect: { value: 1 },
      };
    case "zoom-blur":
      return {
        ...base,
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
        uStrength: { value: 1 },
        uInnerRadius: { value: 50 },
        uPasses: { value: 25 },
        uGradientLength: { value: 5 },
      };
    case "blending":
      return {
        ...base,
        bDiffuse: { value: null },
        uOpacity: { value: 1 },
        uBlendGamma: { value: 2.2 },
        uBlendMode: { value: 0 },
        uHasBlendTarget: { value: 0 },
      };
    case "trail":
      return {
        ...base,
        ptDiffuse: { value: null },
        uAmount: { value: 0.5 },
      };
    case "kaleidoscope":
      return {
        ...base,
        uSegments: { value: 1 },
        uOffset: { value: 0 },
        uPreserveAspect: { value: 0 },
      };
    case "crop":
      return {
        ...base,
        uTop: { value: 10 },
        uBottom: { value: 10 },
        uLeft: { value: 10 },
        uRight: { value: 10 },
        uInvertCrop: { value: 0 },
        uClampEdges: { value: 0 },
      };
    case "bokeh-blur":
      return {
        ...base,
        uAmount: { value: 10 },
        uBokehScale: { value: 1 },
        uShapeType: { value: 0 },
        uSamples: { value: 24 },
        uSmooth: { value: 0 },
        uUseCustomAperture: { value: 0 },
        uApertureTexture: { value: null },
      };
    case "pixelate":
      return { ...base, uAmount: { value: 1 } };
    case "chromatic-aberration":
      return { ...base, uX: { value: 0 }, uY: { value: 0 } };
    case "box-blur":
    case "box-blur-horizontal":
    case "box-blur-vertical":
      return { ...base, uRadius: { value: 0 }, uPasses: { value: 1 } };
    case "fidelityfx-cas":
      return {
        ...base,
        contrastAmt: { value: 1 },
        sharpeningAmt: { value: 1 },
      };
    case "liquify":
      return {
        ...base,
        uIntensity: { value: 50 },
        uControl: { value: 0 },
        uZoom: { value: 5 },
        uComplexity: { value: 8 },
        uScalDiv: { value: 40 },
        uBlobs: { value: 0 },
      };
    case "gradient-map":
      return {
        ...base,
        uLayTexture: { value: null },
        uStrength: { value: 1 },
        uInvert: { value: 0 },
      };
    case "chroma-shift":
      return {
        ...base,
        uTime: { value: 0 },
        uIntensity: { value: 1 },
        uTimeSpeed: { value: 0.5 },
        uTimeOffset: { value: 0 },
        uColorFrequency: { value: 0.7 },
        uPosterizationLevels: { value: 32 },
        uColorPalette: { value: 6 },
      };
    case "premultiply-alpha":
      return {
        ...base,
        uDemultiply: { value: 0 },
      };
    case "distance-field":
      return {
        ...base,
        uDistanceField: { value: null },
        uMaxDistance: { value: 100 },
        uInvertField: { value: 0 },
        uNormalizeField: { value: 1 },
        uFieldOpacity: { value: 1 },
        uVisualizationMode: { value: 0 },
      };
    case "advanced-outline":
      return {
        ...base,
        uDistanceField: { value: null },
        uOutlineColor: { value: new THREE.Vector3(1, 0, 0) },
        uThreshLow: { value: 1 },
        uThreshHigh: { value: 25 },
        uOutlineOpacity: { value: 1 },
        uOutlineOnly: { value: 0 },
      };
    case "advanced-shadow":
      return {
        ...base,
        uDistanceField: { value: null },
        uShadowColor: { value: new THREE.Vector3(0, 0, 0) },
        uShadowOpacity: { value: 0.35 },
        uShadowOffset: { value: new THREE.Vector2(0, 0) },
        uShadowSize: { value: 50 },
        uShadowSpread: { value: 0 },
        uShadowOnly: { value: 0 },
      };
    case "glitch":
      return {
        ...base,
        uByp: { value: 1 },
        uSnowAmount: { value: 0.3 },
        uDisplacementAmount: { value: 1 },
        tDisp: { value: null },
        uAmount: { value: 0.5 },
        uAngle: { value: 0 },
        uSeed: { value: 1 },
        uSeedX: { value: 1 },
        uSeedY: { value: 1 },
        uDistortionX: { value: 1 },
        uDistortionY: { value: 1 },
        uColS: { value: 1 },
      };
    case "render":
      return {
        ...base,
        uOpa: { value: 1 },
      };
    case "blur-triangle":
      return {
        ...base,
        uAmount: { value: 50 },
      };
    case "vhs":
      return {
        ...base,
        uTime: { value: 0 },
        uNoise: { value: null },
      };
    case "vhs2":
      return {
        ...base,
        uTime: { value: 0 },
        uScanlineStrength: { value: 1 },
        uNoiseStrength: { value: 0.5 },
        uNoiseSpeed: { value: 10 },
        uBloomStrength: { value: 5 },
        uDistortionStrength: { value: 1 },
        uClarity: { value: -0.5 },
      };
    case "outline":
      return {
        ...base,
        uOutlineColor: { value: new THREE.Vector3(0, 0, 0) },
        uOutlineThickness: { value: 1 },
        uOutlineOpacity: { value: 1 },
        uOutlineOnly: { value: 0 },
      };
    case "drop-shadow":
      return {
        ...base,
        uOffset: { value: new THREE.Vector2(4, 4) },
        uColor: { value: new THREE.Vector3(0, 0, 0) },
        uOpacity: { value: 0.35 },
        uSpread: { value: 0 },
        uSize: { value: 5 },
        uSteps: { value: 10 },
        uIsInner: { value: 0 },
        uShadowOnly: { value: 0 },
      };
    case "streak-glow":
      return {
        ...base,
        uRange: { value: 0.1 },
        uSteps: { value: 0.005 },
        uThreshold: { value: 0.6 },
        uBrightness: { value: 5 },
        uNumRays: { value: 4 },
        uAngleOffset: { value: Math.PI / 4 },
        uRenderInputOnTop: { value: 0 },
        uCoverageMap: { value: null },
        uHasCoverage: { value: 0 },
      };
    case "morphing-fractal":
      return {
        ...base,
        uTime: { value: 0 },
        uTimeOffset: { value: 0 },
        uBaseTimeRate: { value: 1 },
        uX: { value: 0.5 },
        uY: { value: 0.5 },
        uColMult: { value: new THREE.Vector3(1, 1, 1) },
        uTwirl: { value: 0.002 },
        uFriction: { value: 3 },
        uIterations: { value: 100 },
      };
    case "displacement":
      return {
        ...base,
        uLayTexture: { value: null },
        uHasMap: { value: 0 },
        uDisplacementX: { value: 0.1 },
        uDisplacementY: { value: 0.1 },
        uTexScale: { value: 1 },
        uNormalsMode: { value: 0 },
      };
    case "image-mask":
      return {
        ...base,
        uLayTexture: { value: null },
        uHasMap: { value: 0 },
      };
    case "spooky":
      return {
        ...base,
        uTime: { value: 0 },
        uDistortion: { value: 25 },
        uWidth: { value: 0.02 },
        uSpeed: { value: 0.05 },
      };
    case "impact-ripple":
      return {
        ...base,
        uTime: { value: 0 },
        uWaveFrequency: { value: 10 },
        uWaveAmplitude: { value: 0.8 },
        uWaveWidth: { value: 1 },
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
        uManualControl: { value: 0 },
        uManualProgression: { value: 0 },
        uAutoFrequency: { value: 1 },
        uBrightnessMultiplier: { value: 1 },
      };
    case "render-layer":
      return {
        ...base,
        uLayTexture: { value: null },
      };
    case "repeating-ripple":
      return {
        ...base,
        uTime: { value: 0 },
        uDistortionIntensity: { value: 0.02 },
        uAnimationSpeed: { value: 4 },
        uCenterX: { value: 0.5 },
        uCenterY: { value: 0.5 },
        uWaveFrequency: { value: 12 },
      };
    case "rgb-displace":
      return {
        ...base,
        uDisplaceRX: { value: 10 },
        uDisplaceRY: { value: 0 },
        uScaleR: { value: 1 },
        uDisplaceGX: { value: 0 },
        uDisplaceGY: { value: 0 },
        uScaleG: { value: 1 },
        uDisplaceBX: { value: -10 },
        uDisplaceBY: { value: 0 },
        uScaleB: { value: 1 },
      };
    case "scale":
      return {
        ...base,
        uScaleX: { value: 1.5 },
        uScaleY: { value: 1.5 },
      };
    case "channel-blur":
      return {
        ...base,
        uRedBlur: { value: 5 },
        uGreenBlur: { value: 3 },
        uBlueBlur: { value: 1 },
      };
    case "god-rays":
      return {
        ...base,
        uTime: { value: 0 },
        uDecay: { value: 0.9 },
        uDensity: { value: 1 },
        uWeight: { value: 0.58767 },
        uRayCenterX: { value: 0 },
        uRayCenterY: { value: 0 },
        uAlphaMult: { value: 1 },
        uSaturationMult: { value: 1 },
        uIgnoreDark: { value: 0 },
        uRenderInputOnTop: { value: 0 },
        uCoverageMap: { value: null },
        uHasCoverage: { value: 0 },
        uThreshold: { value: 0 },
        uSamples: { value: 50 },
      };
    case "chroma-key":
      return {
        ...base,
        uKeyColor: { value: new THREE.Vector3(0, 1, 0) },
        uColorCutoff: { value: 0.2 },
        uColorFeathering: { value: 0.33 },
        uDespillAmt: { value: 1 },
        uDespillLuminanceAdd: { value: 0.2 },
      };
    case "edge-detection":
      return {
        ...base,
        uStrength: { value: 10 },
        uThreshold: { value: 0 },
        uThickness: { value: 3 },
        uEdgeMode: { value: 0 },
        uEdgeColor: { value: new THREE.Vector3(1, 1, 1) },
        uUseOriginalColor: { value: 1 },
        uMaskToAlpha: { value: 1 },
        uOverlay: { value: 0 },
        uInvert: { value: 0 },
        uOpacity: { value: 1 },
        uSourceOpacity: { value: 1 },
      };
    case "fxaa":
      return {
        ...base,
        uReduceMin: { value: 8 },
        uReduceMax: { value: 1 },
        uSpanMax: { value: 8 },
      };
    case "bloom":
    case "glow-bloom":
      return { ...base, uThreshold: { value: 2 }, uIntensity: { value: 0 } };
    default:
      return base;
  }
}

export class PostProcessingManager {
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private readonly quad: THREE.Mesh;
  private readonly materials = new Map<string, THREE.ShaderMaterial>();
  private readonly shakes = new Map<string, CameraShakeTransform>();
  private readonly previousShake = new Map<string, THREE.Vector4>();
  private readonly previousShakeTime = new Map<string, number>();
  private readonly previousTransform = new Map<
    string,
    { x: number; y: number; scaleX: number; scaleY: number; rotation: number }
  >();
  private readonly previousTransformTime = new Map<string, number>();
  private readonly trailStores = new Map<string, THREE.WebGLRenderTarget>();
  private readonly tiltStores = new Map<string, THREE.WebGLRenderTarget>();
  /** Scratch copies of a Transform's target when an earlier row sampled it. */
  private readonly transformTargetCopies = new Map<string, THREE.WebGLRenderTarget>();
  private readonly bloomTargets = new Map<string, BloomResources>();
  private readonly glitchTextures = new Map<number, THREE.DataTexture>();
  private readonly gradientTextures = new Map<string, THREE.CanvasTexture>();
  private readonly effectImages = new Map<string, THREE.Texture>();
  private readonly jfaResources = new Map<string, JfaResources>();
  private readonly timeStopHistories = new Map<string, TimeStopHistory>();
  private jfaUvMaterial: THREE.ShaderMaterial | null = null;
  private jfaJumpMaterial: THREE.ShaderMaterial | null = null;
  private bloomHighPassMaterial: THREE.ShaderMaterial | null = null;
  private bloomBlurMaterial: THREE.ShaderMaterial | null = null;
  private bloomCompositeMaterial: THREE.ShaderMaterial | null = null;
  private bloomFinalMaterial: THREE.ShaderMaterial | null = null;
  private readonly copyScene = new THREE.Scene();
  private readonly copyQuad: THREE.Mesh;
  private readonly copyMaterial: THREE.ShaderMaterial;
  private readonly opaqueCopyMaterial: THREE.ShaderMaterial;
  private readBuffer: THREE.WebGLRenderTarget | null = null;
  private writeBuffer: THREE.WebGLRenderTarget | null = null;

  constructor() {
    this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial());
    this.scene.add(this.quad);
    this.copyMaterial = new THREE.ShaderMaterial({
      uniforms: { tDiffuse: { value: null } },
      vertexShader: VERTEX_SHADER,
      fragmentShader: `${PRELUDE}\nvoid main() { gl_FragColor = texture2D(tDiffuse, vUv); }`,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    this.copyQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.copyMaterial);
    this.copyScene.add(this.copyQuad);
    this.opaqueCopyMaterial = new THREE.ShaderMaterial({
      uniforms: { tDiffuse: { value: null } },
      vertexShader: VERTEX_SHADER,
      fragmentShader: `${PRELUDE}\nvoid main() { vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(c.rgb, 1.0); }`,
      transparent: false,
      blending: THREE.NoBlending,
      depthTest: false,
      depthWrite: false,
    });
  }

  setSize(width: number, height: number): void {
    const w = Math.max(1, Math.floor(width));
    const h = Math.max(1, Math.floor(height));
    if (this.readBuffer && this.readBuffer.width === w && this.readBuffer.height === h) return;
    this.readBuffer?.dispose();
    this.writeBuffer?.dispose();
    this.readBuffer = new THREE.WebGLRenderTarget(w, h);
    this.writeBuffer = new THREE.WebGLRenderTarget(w, h);
  }

  /** The target the scene should be rendered into before the chain runs. */
  get inputTarget(): THREE.WebGLRenderTarget | null {
    return this.readBuffer;
  }

  /**
   * Release the working buffers. Project imports reuse one StageRenderer, so
   * without this every imported template keeps two full-resolution targets per
   * layer alive and a 90-template run exhausts GPU memory (the WebGL context is
   * then lost and every later frame is blank).
   */
  dispose(): void {
    this.readBuffer?.dispose();
    this.writeBuffer?.dispose();
    this.readBuffer = null;
    this.writeBuffer = null;
    for (const target of this.trailStores.values()) target.dispose();
    this.trailStores.clear();
    for (const target of this.tiltStores.values()) target.dispose();
    this.tiltStores.clear();
    for (const target of this.transformTargetCopies.values()) target.dispose();
    this.transformTargetCopies.clear();
    for (const bloom of this.bloomTargets.values()) {
      bloom.bright.dispose();
      for (const target of bloom.horizontal) target.dispose();
      for (const target of bloom.vertical) target.dispose();
    }
    this.bloomTargets.clear();
    for (const texture of this.glitchTextures.values()) texture.dispose();
    this.glitchTextures.clear();
    for (const texture of this.gradientTextures.values()) texture.dispose();
    this.gradientTextures.clear();
    for (const texture of this.effectImages.values()) texture.dispose();
    this.effectImages.clear();
    for (const jfa of this.jfaResources.values()) {
      for (const target of jfa.targets) target.dispose();
    }
    this.jfaResources.clear();
    for (const history of this.timeStopHistories.values()) {
      for (const target of history.targets) target.dispose();
    }
    this.timeStopHistories.clear();
    for (const material of this.materials.values()) material.dispose();
    this.materials.clear();
  }

  hasActiveEffect(effects: readonly EffectInstance[]): boolean {
    return effects.some((effect) => effect.enabled);
  }

  private materialFor(effect: EffectInstance): THREE.ShaderMaterial {
    let material = this.materials.get(effect.type);
    if (!material) {
      const fragment = SHADERS[effect.type];
      if (!fragment) {
        material = new THREE.ShaderMaterial({ uniforms: uniformsFor("none"), vertexShader: VERTEX_SHADER, fragmentShader: PRELUDE + "void main(){ gl_FragColor = texture2D(tDiffuse, vUv); }" });
      } else {
        material = new THREE.ShaderMaterial({
          uniforms: uniformsFor(effect.type),
          vertexShader: VERTEX_SHADER,
          fragmentShader: PRELUDE + fragment,
          depthTest: false,
          depthWrite: false,
          // Alpha is carried through the chain so a layer's result can be
          // composited over the frame beneath it.
          transparent: true,
          // The reference builds every effect material through
          // `getBlendingParams()`: CustomBlending with src ONE and dst
          // ONE_MINUS_SRC_ALPHA (ONE/ONE for a perspective layer). A pass may
          // output alpha 0 and still contribute RGB; NormalBlending
          // multiplied that RGB away, which cost `abnormal` 81.06 -> 45.24.
          blending: THREE.CustomBlending,
          blendEquation: THREE.AddEquation,
          blendSrc: THREE.OneFactor,
          blendDst: THREE.OneMinusSrcAlphaFactor,
        });
      }
      this.materials.set(effect.type, material);
    }
    return material;
  }

  private applyCameraShake(
    material: THREE.ShaderMaterial,
    effect: EffectInstance,
    time: number,
  ): void {
    let shake = this.shakes.get(effect.id);
    if (!shake) {
      shake = new CameraShakeTransform();
      this.shakes.set(effect.id, shake);
    }
    const number = (key: string, fallback: number): number => {
      const value = effect.params[key];
      const parsed = typeof value === "boolean" ? (value ? 1 : 0) : Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    };
    shake.setSettings({
      amplitudeX: number("amplitudeX", 8),
      amplitudeY: number("amplitudeY", 8),
      rotation: number("rotation", 2),
      frequency: number("frequency", 1.5),
      octaves: number("octaves", 1),
      autoScale: number("autoScale", 1) > 0.5,
      preScale: number("preScale", 1),
    });
    const transform = shake.transform(time);
    const current = material.uniforms.uCurrentTransform.value as THREE.Vector4;
    current.set(transform.x, transform.y, transform.angle, transform.scale);
    // A repeated playhead is a zero-length shutter: with an audio-driven
    // frequency the pose still moves between identical ticks, which swept the
    // whole frame on a settled capture.
    const lastTime = this.previousShakeTime.get(effect.id);
    const previous =
      lastTime !== undefined && Math.abs(lastTime - time) > 1e-6
        ? this.previousShake.get(effect.id) ?? current.clone()
        : current.clone();
    (material.uniforms.uPreviousTransform.value as THREE.Vector4).copy(previous);
    const wrap = String(effect.params.textureWrap ?? "Discard");
    material.uniforms.uTextureWrapping.value = wrap === "Repeat" ? 1 : wrap === "Clamp" ? 0 : 2;
    const repeat = String(effect.params.repeatType ?? "Default");
    material.uniforms.uRepeatType.value =
      repeat === "Vertical" ? 1 : repeat === "Horizontal" ? 2 : repeat === "Both" ? 3 : repeat === "Either" ? 4 : 0;
    const useMotionBlur = number("useMotionBlur", 0) > 0.5 && time > 0;
    material.uniforms.uUseMotionBlur.value = useMotionBlur ? 1 : 0;
    material.uniforms.uMotionBlurLength.value = Math.max(0.001, number("motionBlurLength", 5));
    material.uniforms.uMotionBlurIterations.value = Math.max(
      1,
      Math.min(100, Math.round(number("motionBlurIterations", 8))),
    );
    material.uniforms.uUseRgbSplit.value = number("useRgbSplit", 0) > 0.5 ? 1 : 0;
    material.uniforms.uRgbSplitLength.value = number("rgbSplitLength", 1);
    material.uniforms.uAspect.value = material.uniforms.uResolution.value.x /
      Math.max(1, material.uniforms.uResolution.value.y);
    this.previousShake.set(effect.id, current.clone());
    this.previousShakeTime.set(effect.id, time);
  }

  private applyTransformBlending(
    material: THREE.ShaderMaterial,
    effect: EffectInstance,
  ): void {
    material.blending = THREE.CustomBlending;
    material.blendEquation =
      TRANSFORM_BLEND_EQUATIONS[String(effect.params.blendEquation ?? "Add")] ??
      THREE.AddEquation;
    material.blendSrc =
      TRANSFORM_BLEND_FACTORS[String(effect.params.srcBlending ?? "One")] ??
      THREE.OneFactor;
    material.blendDst =
      TRANSFORM_BLEND_FACTORS[String(effect.params.dstBlending ?? "OneMinusSrcAlpha")] ??
      THREE.OneMinusSrcAlphaFactor;
  }

  private applyTransform(material: THREE.ShaderMaterial, effect: EffectInstance, time: number): void {
    const number = (key: string, fallback: number): number => {
      const value = effect.params[key];
      const parsed = typeof value === "boolean" ? (value ? 1 : 0) : Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    };
    const current = {
      x: number("matPositionX", 0),
      y: number("matPositionY", 0),
      scaleX: number("matScaleX", 1),
      scaleY: number("matScaleY", 1),
      rotation: (number("matRotation", 0) * Math.PI) / 180,
    };
    const previous = this.previousTransform.get(effect.id) ?? current;
    const data = material.uniforms.uTransformData.value as THREE.Vector4[];
    data[0].set(current.x, current.y, previous.x, previous.y);
    data[1].set(current.scaleX, current.scaleY, previous.scaleX, previous.scaleY);
    const wrap = String(effect.params.textureWrap ?? "Discard");
    data[2].set(
      previous.rotation,
      current.rotation,
      Math.max(0, Math.min(1, number("alpha", 1))),
      wrap === "Repeat" ? 1 : wrap === "Clamp" ? 0 : 2,
    );
    const repeat = String(effect.params.repeatType ?? "Default");
    material.uniforms.uRepeatType.value =
      repeat === "Horizontal" ? 1 : repeat === "Vertical" ? 2 : repeat === "Both" ? 3 : repeat === "Either" ? 4 : 0;
    const useMotionBlur = number("useMotionBlur", 0) > 0.5 && time > 0;
    material.uniforms.uUseMotionBlur.value = useMotionBlur ? 1 : 0;
    // Shipped module 361 feeds the authored length straight into the shader, which
    // divides by it (`float t = float(i) / motionBlurLength`). The /900 here was
    // module 22's point-size helper, wrongly applied to a blur span: with 8/900
    // every sample lands far outside the frame, so `1735` (length 8, iterations 8)
    // rendered 14.2 instead of 5.3 once the samples stopped being clamped.
    material.uniforms.uMotionBlurLength.value = Math.max(0.001, number("motionBlurLength", 8));
    material.uniforms.uMotionBlurIterations.value = Math.max(
      1,
      Math.min(100, Math.round(number("motionBlurIterations", 8))),
    );
    material.uniforms.uAspect.value =
      material.uniforms.uResolution.value.x / Math.max(1, material.uniforms.uResolution.value.y);
    // Reference module 361 refreshes the previous matrix only on a playback
    // frame:
    //   !e.rerender && this.useMotionBlur && (this.pMatScaleX = this.matScaleX, ...)
    // while `setUniforms` always uploads both pairs. A paused re-render therefore
    // keeps smearing between the current transform and the last *playback* one.
    // Storing the pair unconditionally made a settled capture render no blur at
    // all (previous == current).
    const previousTime = this.previousTransformTime.get(effect.id);
    if (previousTime === undefined || Math.abs(previousTime - time) > 1e-6) {
      this.previousTransform.set(effect.id, current);
    }
    this.previousTransformTime.set(effect.id, time);
  }

  private applyParams(
    material: THREE.ShaderMaterial,
    effect: EffectInstance,
    layerTexture?: (
      layerId: string,
      preferRaw?: boolean,
      selfTexture?: THREE.Texture | null,
    ) => THREE.Texture | null,
    screenTexture?: THREE.Texture | null,
    selfTexture?: THREE.Texture | null,
  ): void {
    const value = (key: string, fallback = 0): number => {
      const raw = effect.params[key];
      const numeric = typeof raw === "boolean" ? (raw ? 1 : 0) : Number(raw);
      return Number.isFinite(numeric) ? numeric : fallback;
    };
    const uniforms = material.uniforms;
    switch (effect.type) {
      case "color-tint": {
        // Reference units are 0..1; earlier saves stored percentages.
        const amount = value("amount", 1);
        uniforms.uAmount.value = amount > 1.001 ? amount / 100 : amount;
        uniforms.uWeight.value = value("weight", 1);
        uniforms.uInvert.value = value("invert", 0) > 0.5 ? 1 : 0;
        const black = hexRgb(String(effect.params.mapBlackTo ?? "#000000"));
        const white = hexRgb(String(effect.params.mapWhiteTo ?? "#ffffff"));
        (uniforms.uMapBlack.value as THREE.Vector3).set(black[0], black[1], black[2]);
        (uniforms.uMapWhite.value as THREE.Vector3).set(white[0], white[1], white[2]);
        break;
      }
      case "invert":
        uniforms.uAmount.value =
          effect.params.strength !== undefined
            ? value("strength", 1)
            : value("amount", 100) / 100;
        break;
      case "gray-scale":
        uniforms.uAmount.value = value("amount", 50);
        break;
      case "sepia":
        uniforms.uAmount.value = value("amount", 20);
        break;
      case "flicker":
        uniforms.uAmplitudeBrightness.value = value("amplitudeBrightness", 1);
        uniforms.uFrequencyBrightness.value = value("frequencyBrightness", 7);
        uniforms.uAmplitudeColor.value = value("amplitudeColor", 0.5);
        uniforms.uFrequencyColor.value = value("frequencyColor", 4);
        uniforms.uSeedColor.value = value("seedColor", 123);
        uniforms.uBrightness.value = value("brightness", 1);
        uniforms.uContrast.value = value("contrast", 1);
        uniforms.uDarken.value = value("darken", 1) > 0.5 ? 1 : 0;
        break;
      case "color-correction":
        uniforms.uHueAmount.value = value("hueAmount", 0);
        uniforms.uBrightness.value = value("brightness", 1);
        uniforms.uContrast.value = value("contrast", 1);
        uniforms.uVibrance.value = value("vibrance", 0);
        uniforms.uSaturation.value = value("saturation", 1);
        uniforms.uShadows.value = value("shadows", 0);
        uniforms.uHighlights.value = value("highlights", 0);
        uniforms.uInvert.value = value("invert", 0) > 0.5 ? 1 : 0;
        uniforms.uAddR.value = value("addR", 0);
        uniforms.uAddG.value = value("addG", 0);
        uniforms.uAddB.value = value("addB", 0);
        uniforms.uMulR.value = value("mulR", 1);
        uniforms.uMulG.value = value("mulG", 1);
        uniforms.uMulB.value = value("mulB", 1);
        break;
      case "directional-blur":
        uniforms.uAmount.value = value("amount", 5);
        uniforms.uAngle.value = value("angle", 0);
        uniforms.uSamples.value = Math.max(1, Math.min(64, Math.round(value("samples", 15))));
        break;
      case "radial-blur":
        uniforms.uAmount.value = value("amount", 10);
        (uniforms.uCenter.value as THREE.Vector2).set(
          value("centerX", 0.5),
          value("centerY", 0.5),
        );
        uniforms.uSamples.value = Math.max(1, Math.min(64, Math.round(value("samples", 16))));
        break;
      case "horizontal-blur":
      case "vertical-blur":
        uniforms.uAmount.value = value("amount", 1);
        break;
      case "glow": {
        const color = hexRgb(String(effect.params.glowColor ?? "#4f2eb2"));
        (uniforms.uGlowColor.value as THREE.Vector3).set(color[0], color[1], color[2]);
        uniforms.uDistance.value = Math.max(0, value("distance", 15));
        uniforms.uOuterStrength.value = value("outerStrength", 2);
        uniforms.uInnerStrength.value = value("innerStrength", 0);
        uniforms.uXSpread.value = 501 - Math.min(500, Math.max(0, value("xSpread", 50) * 5));
        uniforms.uYSpread.value = 501 - Math.min(500, Math.max(0, value("ySpread", 50) * 5));
        break;
      }
      case "vignette": {
        const color = hexRgb(String(effect.params.vignetteColor ?? "#000000"));
        (uniforms.uVignetteColor.value as THREE.Vector3).set(color[0], color[1], color[2]);
        uniforms.uSize.value = value("size", 0.5);
        uniforms.uSmoothness.value = value("smoothness", 0.5);
        uniforms.uRoundness.value = value("roundness", 1);
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        uniforms.uOpacity.value = value("opacity", 1);
        uniforms.uDither.value = value("dither", 0.1);
        uniforms.uUseAlpha.value = value("useAlpha", 0) > 0.5 ? 1 : 0;
        uniforms.uMoveNoise.value = value("moveNoise", 0) > 0.5 ? 1 : 0;
        uniforms.uUseScreenAspect.value = value("useScreenAspect", 0) > 0.5 ? 1 : 0;
        break;
      }
      case "pixelate": {
        // Reference `amount` is the number of blocks along an axis; older saves
        // store a block size in pixels.
        const amount =
          effect.params.amount !== undefined
            ? value("amount", 12)
            : Math.max(1, Math.round(uniforms.uResolution.value.y / Math.max(1, value("size", 12))));
        uniforms.uAmount.value = Math.max(1, amount);
        break;
      }
      case "chromatic-aberration":
        uniforms.uX.value = effect.params.x !== undefined ? value("x", 4) : value("offset", 4);
        uniforms.uY.value = value("y", 0);
        break;
      case "box-blur":
      case "box-blur-horizontal":
      case "box-blur-vertical":
        uniforms.uRadius.value = value("radius", 3);
        uniforms.uPasses.value = Math.max(1, value("nrPasses", 1));
        break;
      case "glitch": {
        const amount = value("amount", 0.5);
        const threshold = value("threshold", 0.5);
        const randomTrigger = value("randomTrigger", 0) > 0.5;
        const active = amount >= threshold || (randomTrigger && Math.random() < 0.2);
        uniforms.uByp.value = active ? 0 : 1;
        uniforms.uSnowAmount.value = value("snowAmount", 0.3);
        uniforms.uDisplacementAmount.value = value("displacementAmount", 1);
        uniforms.tDisp.value = this.glitchTexture(
          effect.params.dt_size !== undefined ? value("dt_size", 64) : value("dtSize", 64),
        );
        // The shipped program declares `col_s`, but its JS only ever creates a
        // `col_S` uniform (different case), so the band-width uniform is never
        // supplied and stays at the GLSL default 0. Setting it to 1 made the
        // whole frame remap outside the texture and go black.
        uniforms.uColS.value = 0;
        if (active) {
          uniforms.uAmount.value = (amount * Math.random()) / 30;
          uniforms.uAngle.value = Math.random() * Math.PI * 2 - Math.PI;
          uniforms.uSeed.value = Math.random();
          uniforms.uSeedX.value =
            (Math.random() * 2 - 1) * uniforms.uDisplacementAmount.value;
          uniforms.uSeedY.value =
            (Math.random() * 2 - 1) * uniforms.uDisplacementAmount.value;
          uniforms.uDistortionX.value = Math.random() * uniforms.uDisplacementAmount.value;
          uniforms.uDistortionY.value = Math.random() * uniforms.uDisplacementAmount.value;
        }
        break;
      }
      case "render":
        uniforms.uOpa.value = Math.max(0, Math.min(1, value("opa", 1)));
        break;
      case "blur-triangle":
        uniforms.uAmount.value = value("amount", 50);
        break;
      case "vhs":
        uniforms.uNoise.value = this.glitchTexture(256);
        break;
      case "vhs2":
        uniforms.uScanlineStrength.value = value("scanlineStrength", 1);
        uniforms.uNoiseStrength.value = value("noiseStrength", 0.5);
        uniforms.uNoiseSpeed.value = value("noiseSpeed", 10);
        uniforms.uBloomStrength.value = value("bloomStrength", 5);
        uniforms.uDistortionStrength.value = value("distortionStrength", 1);
        uniforms.uClarity.value = value("clarity", -0.5);
        break;
      case "fidelityfx-cas":
        uniforms.contrastAmt.value = value("contrastAmt", 1);
        uniforms.sharpeningAmt.value = value("sharpeningAmt", 1);
        break;
      case "liquify":
        uniforms.uIntensity.value = value("intensity", 50);
        uniforms.uControl.value = value("control", 0);
        uniforms.uZoom.value = value("zoom", 5);
        uniforms.uComplexity.value = Math.max(0, value("complexity", 8));
        uniforms.uScalDiv.value = Math.max(0.01, value("scalDiv", 40));
        uniforms.uBlobs.value = Math.max(0, value("blobs", 0));
        break;
      case "gradient-map": {
        const source = String(effect.params.paletteSource ?? "Manual gradient");
        if (source === "Layer") {
          const target = String(effect.params.targetLayer ?? "Screen");
          uniforms.uLayTexture.value =
            target !== "Screen" && layerTexture
              ? layerTexture(target, false, selfTexture)
              : null;
        } else if (source === "Image") {
          uniforms.uLayTexture.value = this.effectImage(
            String(effect.params.imageSrc ?? ""),
          );
        } else {
          uniforms.uLayTexture.value = this.gradientTexture(
            String(effect.params.gradientStops ?? "0.0:#000000,1.0:#FFFFFF"),
          );
        }
        uniforms.uStrength.value = value("strength", 1);
        uniforms.uInvert.value = value("invert", 0) > 0.5 ? 1 : 0;
        break;
      }
      case "chroma-shift":
        uniforms.uIntensity.value = value("intensity", 1);
        uniforms.uTimeSpeed.value = value("timeSpeed", 0.5);
        uniforms.uTimeOffset.value = value("timeOffset", 0);
        uniforms.uColorFrequency.value = value("colorFrequency", 0.7);
        uniforms.uPosterizationLevels.value = Math.max(
          2,
          Math.round(value("posterizationLevels", 32)),
        );
        uniforms.uColorPalette.value = Number(effect.params.colorPalette ?? 6);
        break;
      case "premultiply-alpha":
        uniforms.uDemultiply.value = value("demultiply", 0) > 0.5 ? 1 : 0;
        break;
      case "outline": {
        const color = hexRgb(String(effect.params.outlineColor ?? "#000000"));
        (uniforms.uOutlineColor.value as THREE.Vector3).set(color[0], color[1], color[2]);
        uniforms.uOutlineThickness.value = value("outlineThickness", 1);
        uniforms.uOutlineOpacity.value = value("outlineOpacity", 1);
        uniforms.uOutlineOnly.value = value("outlineOnly", 0) > 0.5 ? 1 : 0;
        break;
      }
      case "drop-shadow": {
        const color = hexRgb(String(effect.params.color ?? "#000000"));
        (uniforms.uOffset.value as THREE.Vector2).set(
          value("offsetX", 4),
          value("offsetY", 4),
        );
        (uniforms.uColor.value as THREE.Vector3).set(color[0], color[1], color[2]);
        // The reference declares this controller as `min: 0, max: 1`
        // (`Simple Shadow` in main~b45a2766, initialValue .35) and the shader
        // multiplies the accumulated shadow alpha by it. `monochromatic-bloom`
        // exports 16, which is outside that domain: at 16 every tap over 1/16
        // alpha saturates, so the drop shadow of the spectrum rosette became a
        // solid black lattice cell instead of the reference's soft grey one
        // (42.02 -> 32.86 when clamped to 1). Clamp like the other 0..1
        // controllers rather than trusting invalid data.
        uniforms.uOpacity.value = Math.min(1, Math.max(0, value("opacity", 0.35)));
        uniforms.uSpread.value = value("spread", 0) / 100;
        uniforms.uSize.value = value("size", 5);
        uniforms.uSteps.value = Math.max(0, Math.min(25, Math.round(value("steps", 10))));
        uniforms.uIsInner.value = value("isInner", 0) > 0.5 ? 1 : 0;
        uniforms.uShadowOnly.value = value("shadowOnly", 0) > 0.5 ? 1 : 0;
        break;
      }
      case "streak-glow":
        uniforms.uRange.value = value("range", 0.1);
        uniforms.uSteps.value = value("_steps", 0.005);
        uniforms.uThreshold.value = value("threshold", 0.6);
        uniforms.uBrightness.value = value("brightness", 5);
        uniforms.uNumRays.value = Math.max(1, Math.round(value("numRays", 4)));
        uniforms.uAngleOffset.value = value("angleOffset", Math.PI / 4);
        uniforms.uRenderInputOnTop.value = value("renderInputOnTop", 0) > 0.5 ? 1 : 0;
        break;
      case "morphing-fractal": {
        const color = hexRgb(String(effect.params.morphColor ?? "#ffffff"));
        uniforms.uTimeOffset.value = value("timeOffset", 0);
        uniforms.uBaseTimeRate.value = value("baseTimeRate", 1);
        uniforms.uX.value = value("x", 0.5);
        uniforms.uY.value = value("y", 0.5);
        (uniforms.uColMult.value as THREE.Vector3).set(color[0], color[1], color[2]);
        uniforms.uTwirl.value = value("twirl", 0.002);
        uniforms.uFriction.value = value("friction", 3);
        uniforms.uIterations.value = Math.max(1, Math.min(100, Math.round(value("iterations", 100))));
        break;
      }
      case "displacement": {
        const useImage = value("useImageTexture", 0) > 0.5;
        const target = String(effect.params.targetLayer ?? "Screen");
        const texture = useImage
          ? this.effectImage(String(effect.params.imageSrc ?? ""))
          : target !== "Screen" && layerTexture
            ? layerTexture(target, false, selfTexture)
            : null;
        uniforms.uLayTexture.value = texture;
        uniforms.uHasMap.value = texture ? 1 : 0;
        uniforms.uDisplacementX.value = value("displacementX", 0.1);
        uniforms.uDisplacementY.value = value("displacementY", 0.1);
        uniforms.uTexScale.value = value("texScale", 1);
        uniforms.uNormalsMode.value = value("normalsMode", 0) > 0.5 ? 1 : 0;
        break;
      }
      case "image-mask": {
        const useImage = value("useImageTexture", 1) > 0.5;
        const target = String(effect.params.targetLayer ?? "Screen");
        const texture = useImage
          ? this.effectImage(String(effect.params.imageSrc ?? ""))
          : target !== "Screen" && layerTexture
            ? layerTexture(target, false, selfTexture)
            : null;
        uniforms.uLayTexture.value = texture;
        uniforms.uHasMap.value = texture ? 1 : 0;
        break;
      }
      case "spooky":
        uniforms.uDistortion.value = value("distortion", 25);
        uniforms.uWidth.value = value("width", 0.02);
        uniforms.uSpeed.value = value("speed", 0.05);
        break;
      case "impact-ripple":
        uniforms.uWaveFrequency.value = value("waveFrequency", 10);
        uniforms.uWaveAmplitude.value = value("waveAmplitude", 0.8);
        uniforms.uWaveWidth.value = value("waveWidth", 1);
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        uniforms.uManualControl.value = value("manualControl", 0) > 0.5 ? 1 : 0;
        uniforms.uManualProgression.value = value("manualProgression", 0);
        uniforms.uAutoFrequency.value = value("autoFrequency", 1);
        uniforms.uBrightnessMultiplier.value = value("brightnessMultiplier", 1);
        break;
      case "render-layer": {
        const target = String(effect.params.targetLayer ?? "Screen");
        uniforms.uLayTexture.value =
          target !== "Screen" && layerTexture
            ? layerTexture(target, false, selfTexture)
            : null;
        break;
      }
      case "repeating-ripple":
        uniforms.uDistortionIntensity.value = value("distortionIntensity", 0.02);
        uniforms.uAnimationSpeed.value = value("animationSpeed", 4);
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        uniforms.uWaveFrequency.value = value("waveFrequency", 12);
        break;
      case "rgb-displace":
        uniforms.uDisplaceRX.value = value("displaceRX", 10);
        uniforms.uDisplaceRY.value = value("displaceRY", 0);
        uniforms.uScaleR.value = value("scaleR", 1);
        uniforms.uDisplaceGX.value = value("displaceGX", 0);
        uniforms.uDisplaceGY.value = value("displaceGY", 0);
        uniforms.uScaleG.value = value("scaleG", 1);
        uniforms.uDisplaceBX.value = value("displaceBX", -10);
        uniforms.uDisplaceBY.value = value("displaceBY", 0);
        uniforms.uScaleB.value = value("scaleB", 1);
        break;
      case "scale":
        uniforms.uScaleX.value = value("scaleX", 1.5);
        uniforms.uScaleY.value = value("scaleY", 1.5);
        break;
      case "channel-blur":
        uniforms.uRedBlur.value = Math.max(0, value("redBlur", 5));
        uniforms.uGreenBlur.value = Math.max(0, value("greenBlur", 3));
        uniforms.uBlueBlur.value = Math.max(0, value("blueBlur", 1));
        break;
      case "god-rays":
        uniforms.uDecay.value = value("decay", 0.9);
        uniforms.uDensity.value = value("density", 1);
        uniforms.uWeight.value = value("weight", 0.58767);
        uniforms.uRayCenterX.value = value("rayCenterX", 0);
        uniforms.uRayCenterY.value = value("rayCenterY", 0);
        uniforms.uAlphaMult.value = value("alphaMult", 1);
        uniforms.uSaturationMult.value = value("saturationMult", 1);
        uniforms.uThreshold.value = value("threshold", 0);
        uniforms.uIgnoreDark.value = value("ignoreDark", 0) > 0.5 ? 1 : 0;
        uniforms.uRenderInputOnTop.value = value("renderInputOnTop", 0) > 0.5 ? 1 : 0;
        uniforms.uSamples.value = Math.max(1, Math.min(100, Math.round(value("nsamples", 50))));
        break;
      case "chroma-key": {
        const key = hexRgb(String(effect.params.keyColor ?? "#00ff00"));
        (uniforms.uKeyColor.value as THREE.Vector3).set(key[0], key[1], key[2]);
        uniforms.uColorCutoff.value = value("colorCutoff", 0.2);
        uniforms.uColorFeathering.value = value("colorFeathering", 0.33);
        uniforms.uDespillAmt.value = value("despillAmt", 1);
        uniforms.uDespillLuminanceAdd.value = value("despillLuminanceAdd", 0.2);
        break;
      }
      case "edge-detection": {
        const color = hexRgb(String(effect.params.color ?? "#ffffff"));
        (uniforms.uEdgeColor.value as THREE.Vector3).set(color[0], color[1], color[2]);
        const mode = String(effect.params.edgeMode ?? "Sobel");
        uniforms.uEdgeMode.value =
          mode === "Laplacian" ? 1 : mode === "Prewitt" ? 2 : mode === "Roberts Cross" ? 3 : 0;
        uniforms.uStrength.value = value("strength", 10);
        uniforms.uThreshold.value = value("threshold", 0);
        uniforms.uThickness.value = Math.max(0.1, value("thickness", 3));
        uniforms.uOpacity.value = value("opacity", 1);
        uniforms.uUseOriginalColor.value = value("useOriginalColor", 1) > 0.5 ? 1 : 0;
        uniforms.uMaskToAlpha.value = value("maskToAlpha", 1) > 0.5 ? 1 : 0;
        uniforms.uOverlay.value = value("overlay", 0) > 0.5 ? 1 : 0;
        uniforms.uInvert.value = value("invert", 0) > 0.5 ? 1 : 0;
        uniforms.uSourceOpacity.value = value("sourceOpacity", 1);
        break;
      }
      case "fxaa":
        uniforms.uReduceMin.value = Math.max(1, value("reduceMin", 8));
        uniforms.uReduceMax.value = Math.max(0.0001, value("reduceMax", 1));
        uniforms.uSpanMax.value = Math.max(0, value("spanMax", 8));
        break;
      case "bloom":
        uniforms.uThreshold.value =
          value("threshold", 0) > 1 ? value("threshold", 0) / 100 : value("threshold", 0);
        uniforms.uIntensity.value =
          effect.params.strength !== undefined
            ? value("strength", 1)
            : value("intensity", 90) / 100;
        break;
      case "alpha":
        uniforms.uAlpha.value = Math.max(0, Math.min(1, value("alpha", 100) / 100));
        break;
      case "twirl":
        uniforms.uAmount.value = value("amount", 2.5);
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        break;
      case "skew":
        uniforms.uSkewX.value = value("skewX", 0);
        uniforms.uSkewY.value = value("skewY", 0);
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        break;
      case "mirror":
        uniforms.uPos.value = value("pos", 0.5);
        uniforms.uLeft.value = value("left", 1) > 0.5 ? 1 : 0;
        uniforms.uRight.value = value("right", 0) > 0.5 ? 1 : 0;
        uniforms.uTop.value = value("top", 0) > 0.5 ? 1 : 0;
        uniforms.uBottom.value = value("bottom", 0) > 0.5 ? 1 : 0;
        break;
      case "fisheye-2":
        uniforms.uA.value = value("a", 2);
        uniforms.uB.value = value("b", 3);
        uniforms.uF.value = value("F", 3);
        uniforms.uScale.value = Math.max(0.0001, value("scale", 1));
        break;
      case "fisheye": {
        uniforms.uAmount.value = value("amount", 1);
        const preScale = value("preScale", 1);
        uniforms.uPreScale.value = Math.abs(preScale) < 0.0001 ? 0.0001 : preScale;
        break;
      }
      case "polar-coordinates":
        uniforms.uCurvature.value = Math.max(-1, Math.min(1, value("curvature", 1)));
        break;
      case "bulge-pinch":
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        uniforms.uRadius.value = Math.max(0, value("radius", 0.25));
        uniforms.uStrength.value = Math.max(-1, Math.min(1, value("strength", 0.5)));
        uniforms.uSmoothEdge.value = Math.max(0, value("smoothEdge", 0.01));
        break;
      case "tilt-shift":
        uniforms.uAmount.value = Math.max(0, value("amount", 20));
        uniforms.uFocusPosition.value = value("focusPosition", 0.5);
        uniforms.uFocusRange.value = Math.max(0, value("focusRange", 0.1));
        uniforms.uRotation.value = value("rotation", 0);
        break;
      case "zoom-blur":
        uniforms.uCenterX.value = value("centerX", 0.5);
        uniforms.uCenterY.value = value("centerY", 0.5);
        uniforms.uStrength.value = Math.max(0, value("strength", 1));
        uniforms.uInnerRadius.value = Math.max(0, value("innerRadius", 50));
        uniforms.uPasses.value = Math.max(1, Math.min(100, Math.round(value("passes", 25))));
        uniforms.uGradientLength.value = Math.max(0, value("gradientLength", 5));
        break;
      case "blending": {
        const target = String(effect.params.blendWith ?? "Screen");
        // `blendWith` names a *layer id*; the placeholder "Screen" (the
        // reference's default) resolves to no layer at all, so `bDiffuse` is
        // never bound and the pass leaves the frame untouched. Binding the
        // composition there made an opaque top (a white-to-black gradient)
        // normal-blend over everything (`radiant`, `plasma-bloqy`).
        const blendSource = layerTexture ? layerTexture(target, true, selfTexture) : null;
        uniforms.bDiffuse.value = blendSource;
        uniforms.uHasBlendTarget.value = blendSource ? 1 : 0;
        // The shipped effect feeds `opacity` and `blendGamma` to the shader
        // verbatim (C-YT-B stores opacity 40); the shader weights opacity by the
        // blend layer's alpha, so legacy percentage-style saves behave like the
        // reference without rescaling.
        uniforms.uOpacity.value = Math.max(0, value("opacity", 1));
        uniforms.uBlendGamma.value = Math.max(0.01, value("blendGamma", 2.2));
        const mode = BLEND_MODES.indexOf(
          String(effect.params.blendFunc ?? "normal") as (typeof BLEND_MODES)[number],
        );
        uniforms.uBlendMode.value = mode >= 0 ? mode : 0;
        break;
      }
      case "trail":
        uniforms.uAmount.value = Math.max(0, Math.min(1, value("amount", 0.5)));
        break;
      case "kaleidoscope":
        uniforms.uSegments.value = value("segments", 1);
        uniforms.uOffset.value = value("offset", 0);
        uniforms.uPreserveAspect.value = value("preserveAspect", 0) > 0.5 ? 1 : 0;
        break;
      case "crop":
        uniforms.uTop.value = value("tCrop", 10);
        uniforms.uBottom.value = value("bCrop", 10);
        uniforms.uLeft.value = value("lCrop", 10);
        uniforms.uRight.value = value("rCrop", 10);
        uniforms.uInvertCrop.value = value("invertCrop", 0) > 0.5 ? 1 : 0;
        uniforms.uClampEdges.value = value("clampEdges", 0) > 0.5 ? 1 : 0;
        break;
      case "bokeh-blur": {
        uniforms.uAmount.value = value("amount", 10);
        uniforms.uBokehScale.value = value("bokehScale", 1);
        const shape = String(effect.params.shapeType ?? "Circle");
        const customAperture = value("useCustomTexture", 0) > 0.5;
        uniforms.uUseCustomAperture.value = customAperture ? 1 : 0;
        uniforms.uApertureTexture.value = customAperture
          ? this.effectImage(String(effect.params.imageSrc ?? ""))
          : null;
        uniforms.uShapeType.value = customAperture
          ? 3
          : shape === "Hexagon"
            ? 1
            : shape === "Star"
              ? 2
              : 0;
        uniforms.uSamples.value = Math.max(1, Math.min(24, Math.round(value("samples", 24))));
        uniforms.uSmooth.value = String(effect.params.smoothMode ?? "Grainy") === "Smooth" ? 1 : 0;
        break;
      }
      default:
        break;
    }
  }

  private ensureJfaMaterials(): {
    uv: THREE.ShaderMaterial;
    jump: THREE.ShaderMaterial;
  } {
    if (!this.jfaUvMaterial) {
      this.jfaUvMaterial = new THREE.ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          uResolution: { value: new THREE.Vector2(1, 1) },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["jfa-uv"]}`,
        depthTest: false,
        depthWrite: false,
      });
    }
    if (!this.jfaJumpMaterial) {
      this.jfaJumpMaterial = new THREE.ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          uResolution: { value: new THREE.Vector2(1, 1) },
          uJumpOffset: { value: 1 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["jfa-jump"]}`,
        depthTest: false,
        depthWrite: false,
      });
    }
    return { uv: this.jfaUvMaterial, jump: this.jfaJumpMaterial };
  }

  private ensureJfaResources(
    effectId: string,
    width: number,
    height: number,
  ): JfaResources {
    const existing = this.jfaResources.get(effectId);
    if (existing && existing.width === width && existing.height === height) {
      return existing;
    }
    if (existing) {
      existing.targets.forEach((target) => target.dispose());
    }
    const options = {
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat,
      type: THREE.FloatType,
      depthBuffer: false,
      stencilBuffer: false,
    };
    const resources: JfaResources = {
      width,
      height,
      targets: [
        new THREE.WebGLRenderTarget(width, height, options),
        new THREE.WebGLRenderTarget(width, height, options),
      ],
    };
    this.jfaResources.set(effectId, resources);
    return resources;
  }

  private generateDistanceField(
    renderer: THREE.WebGLRenderer,
    effectId: string,
    source: THREE.Texture,
    width: number,
    height: number,
    maxDistance: number,
  ): THREE.Texture {
    const materials = this.ensureJfaMaterials();
    const resources = this.ensureJfaResources(effectId, width, height);
    const draw = (drawMaterial: THREE.ShaderMaterial, target: THREE.WebGLRenderTarget): void => {
      drawMaterial.blending = THREE.NoBlending;
      this.quad.material = drawMaterial;
      renderer.setRenderTarget(target);
      renderer.clear(true, false, false);
      renderer.render(this.scene, this.camera);
    };

    materials.uv.uniforms.tDiffuse.value = source;
    (materials.uv.uniforms.uResolution.value as THREE.Vector2).set(width, height);
    draw(materials.uv, resources.targets[1]);

    const iterations = Math.ceil(Math.log2(Math.max(2, maxDistance)));
    let jumpOffset = Math.pow(2, iterations - 1);
    let index = 0;
    for (let step = 0; step < iterations; step += 1) {
      materials.jump.uniforms.tDiffuse.value = resources.targets[1 - index].texture;
      (materials.jump.uniforms.uResolution.value as THREE.Vector2).set(width, height);
      materials.jump.uniforms.uJumpOffset.value = jumpOffset;
      draw(materials.jump, resources.targets[index]);
      index = 1 - index;
      jumpOffset = Math.floor(jumpOffset / 2);
    }
    return resources.targets[1 - index].texture;
  }

  private timeStopHistory(
    effectId: string,
    width: number,
    height: number,
    size: number,
  ): TimeStopHistory {
    const targetSize = Math.max(1, Math.round(size));
    let history = this.timeStopHistories.get(effectId);
    if (
      !history ||
      history.width !== width ||
      history.height !== height
    ) {
      history?.targets.forEach((target) => target.dispose());
      history = {
        width,
        height,
        targets: [],
        writeIndex: 0,
        framesCaptured: 0,
        lastTime: null,
      };
      this.timeStopHistories.set(effectId, history);
    }
    if (history.targets.length !== targetSize) {
      if (history.targets.length > targetSize) {
        history.targets.splice(targetSize).forEach((target) => target.dispose());
        history.writeIndex %= targetSize;
        history.framesCaptured = Math.min(history.framesCaptured, targetSize);
      } else {
        while (history.targets.length < targetSize) {
          history.targets.push(new THREE.WebGLRenderTarget(width, height));
        }
      }
    }
    return history;
  }

  private effectImage(src: string): THREE.Texture | null {
    const url = src.trim();
    if (!url) return null;
    const cached = this.effectImages.get(url);
    if (cached) return cached;
    const texture = new THREE.TextureLoader().load(url, (loaded) => {
      loaded.colorSpace = THREE.NoColorSpace;
      loaded.minFilter = THREE.LinearFilter;
      loaded.magFilter = THREE.LinearFilter;
      loaded.generateMipmaps = false;
      loaded.needsUpdate = true;
    });
    texture.colorSpace = THREE.NoColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = false;
    this.effectImages.set(url, texture);
    return texture;
  }

  private gradientTexture(stops: string): THREE.CanvasTexture {
    const key = stops || "0.0:#000000,1.0:#FFFFFF";
    const cached = this.gradientTextures.get(key);
    if (cached) return cached;
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 1;
    const context = canvas.getContext("2d");
    if (context) {
      const gradient = context.createLinearGradient(0, 0, 512, 0);
      const parsed = key
        .split(",")
        .map((entry) => {
          const split = entry.lastIndexOf(":");
          if (split < 0) return null;
          const position = Number(entry.slice(0, split));
          const color = entry.slice(split + 1).trim();
          return Number.isFinite(position) && color ? { position, color } : null;
        })
        .filter((entry): entry is { position: number; color: string } => Boolean(entry));
      if (parsed.length === 0) {
        gradient.addColorStop(0, "#000000");
        gradient.addColorStop(1, "#ffffff");
      } else {
        parsed.sort((a, b) => a.position - b.position);
        for (const stop of parsed) {
          gradient.addColorStop(Math.max(0, Math.min(1, stop.position)), stop.color);
        }
      }
      context.fillStyle = gradient;
      context.fillRect(0, 0, 512, 1);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = false;
    texture.needsUpdate = true;
    this.gradientTextures.set(key, texture);
    return texture;
  }

  private glitchTexture(size: number): THREE.DataTexture {
    const pixelSize = Math.max(1, Math.min(256, Math.round(size || 64)));
    const cached = this.glitchTextures.get(pixelSize);
    if (cached) return cached;
    const data = new Uint8Array(pixelSize * pixelSize * 4);
    for (let index = 0; index < data.length; index += 1) {
      data[index] = Math.floor(Math.random() * 256);
    }
    const texture = new THREE.DataTexture(
      data,
      pixelSize,
      pixelSize,
      THREE.RGBAFormat,
      THREE.UnsignedByteType,
    );
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.needsUpdate = true;
    this.glitchTextures.set(pixelSize, texture);
    return texture;
  }

  private ensureBloomMaterials(): {
    highPass: THREE.ShaderMaterial;
    blur: THREE.ShaderMaterial;
    composite: THREE.ShaderMaterial;
    final: THREE.ShaderMaterial;
  } {
    if (!this.bloomHighPassMaterial) {
      this.bloomHighPassMaterial = new THREE.ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          uThreshold: { value: 0 },
          uSmoothWidth: { value: 0.01 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["bloom-highpass"]}`,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      });
    }
    if (!this.bloomBlurMaterial) {
      this.bloomBlurMaterial = new THREE.ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          uTexSize: { value: new THREE.Vector2(1, 1) },
          uDirection: { value: new THREE.Vector2(1, 0) },
          uKernelRadius: { value: 3 },
          uSigma: { value: 3 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["bloom-blur"]}`,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      });
    }
    if (!this.bloomCompositeMaterial) {
      this.bloomCompositeMaterial = new THREE.ShaderMaterial({
        uniforms: {
          uBlur1: { value: null },
          uBlur2: { value: null },
          uBlur3: { value: null },
          uBlur4: { value: null },
          uBlur5: { value: null },
          uStrength: { value: 1 },
          uRadius: { value: 0.1 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["bloom-composite"]}`,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      });
    }
    if (!this.bloomFinalMaterial) {
      this.bloomFinalMaterial = new THREE.ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          uBloomTexture: { value: null },
          uRenderBaseTexture: { value: 0 },
          uRenderBaseAdditive: { value: 1 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `${PRELUDE}\n${SHADERS["bloom-final"]}`,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      });
    }
    return {
      highPass: this.bloomHighPassMaterial,
      blur: this.bloomBlurMaterial,
      composite: this.bloomCompositeMaterial,
      final: this.bloomFinalMaterial,
    };
  }

  private bloomTarget(width: number, height: number): THREE.WebGLRenderTarget {
    const target = new THREE.WebGLRenderTarget(
      Math.max(1, Math.floor(width)),
      Math.max(1, Math.floor(height)),
      {
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
        format: THREE.RGBAFormat,
      },
    );
    target.texture.generateMipmaps = false;
    return target;
  }

  private ensureBloomResources(
    effectId: string,
    width: number,
    height: number,
  ): BloomResources {
    const existing = this.bloomTargets.get(effectId);
    if (
      existing &&
      existing.sourceWidth === width &&
      existing.sourceHeight === height
    ) {
      return existing;
    }
    if (existing) {
      existing.bright.dispose();
      existing.horizontal.forEach((target) => target.dispose());
      existing.vertical.forEach((target) => target.dispose());
    }

    const halfWidth = Math.max(1, Math.round(width / 2));
    const halfHeight = Math.max(1, Math.round(height / 2));
    const resources: BloomResources = {
      sourceWidth: width,
      sourceHeight: height,
      bright: this.bloomTarget(halfWidth, halfHeight),
      horizontal: [],
      vertical: [],
    };
    let mipWidth = halfWidth;
    let mipHeight = halfHeight;
    for (let index = 0; index < 5; index += 1) {
      resources.horizontal.push(this.bloomTarget(mipWidth, mipHeight));
      resources.vertical.push(this.bloomTarget(mipWidth, mipHeight));
      mipWidth = Math.max(1, Math.round(mipWidth / 2));
      mipHeight = Math.max(1, Math.round(mipHeight / 2));
    }
    this.bloomTargets.set(effectId, resources);
    return resources;
  }

  private ensureTiltStore(effectId: string, width: number, height: number): THREE.WebGLRenderTarget {
    let store = this.tiltStores.get(effectId);
    if (!store) {
      store = new THREE.WebGLRenderTarget(Math.max(1, width), Math.max(1, height));
      this.tiltStores.set(effectId, store);
    } else if (store.width !== width || store.height !== height) {
      store.setSize(Math.max(1, width), Math.max(1, height));
    }
    return store;
  }

  private ensureTrailStore(effectId: string, width: number, height: number): THREE.WebGLRenderTarget {
    let store = this.trailStores.get(effectId);
    if (!store) {
      store = new THREE.WebGLRenderTarget(Math.max(1, width), Math.max(1, height));
      this.trailStores.set(effectId, store);
    } else if (store.width !== width || store.height !== height) {
      store.setSize(Math.max(1, width), Math.max(1, height));
    }
    return store;
  }

  private ensureTransformTargetCopy(
    effectId: string,
    width: number,
    height: number,
  ): THREE.WebGLRenderTarget {
    let copy = this.transformTargetCopies.get(effectId);
    if (!copy) {
      copy = new THREE.WebGLRenderTarget(Math.max(1, width), Math.max(1, height));
      this.transformTargetCopies.set(effectId, copy);
    } else if (copy.width !== width || copy.height !== height) {
      copy.setSize(Math.max(1, width), Math.max(1, height));
    }
    return copy;
  }

  /** Copy a texture into a buffer, replacing its contents. */
  copyTo(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget,
  ): void {
    this.copyTexture(renderer, texture, target, false);
  }

  /**
   * Copy the RGB of a premultiplied texture into a buffer with alpha 1.
   *
   * A composition composed over a transparent base carries the layer stack's
   * coverage in its alpha (that is what God rays' `renderInputOnTop` reads) but
   * its RGB is already premultiplied by that coverage, so handing the alpha on
   * to the chain would attenuate the frame a second time.
   */
  copyOpaque(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget,
  ): void {
    const previous = this.copyQuad.material;
    this.opaqueCopyMaterial.uniforms.tDiffuse.value = texture;
    this.copyQuad.material = this.opaqueCopyMaterial;
    const previousAutoClear = renderer.autoClear;
    renderer.autoClear = false;
    renderer.setRenderTarget(target);
    renderer.render(this.copyScene, this.camera);
    renderer.autoClear = previousAutoClear;
    this.copyQuad.material = previous;
  }

  /** Draw a finished layer texture over the frame (or replace the screen). */
  composite(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    blend = true,
    additive = false,
  ): void {
    this.copyTexture(renderer, texture, null, blend, additive);
  }

  /** Composite a finished layer into a specific target (e.g. the effect input). */
  compositeTo(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget,
    blend = true,
    additive = false,
  ): void {
    this.copyTexture(renderer, texture, target, blend, additive);
  }

  /**
   * Composite a finished layer with the Bloom effect's own material blending.
   *
   * Reference `main~b45a2766` @577: the Bloom final quad is
   * `new ShaderMaterial({ transparent: true, blending: THREE.AdditiveBlending })`,
   * i.e. `SrcAlpha / One`. That pass is the *last* effect of a layer chain, and
   * `PostProcessingManager.render` (`main~053e68a9` @4228) sends the last pass to
   * `renderTo` = `SCREEN_BUFFER` unless the layer is a buffer. A layer that is
   * not a buffer therefore lands on the composition with `SrcAlpha / One`, never
   * with the layer's `ONE / ONE_MINUS_SRC_ALPHA`.
   */
  compositeBloomAdditive(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget | null,
  ): void {
    this.copyTexture(renderer, texture, target, true, true, THREE.SrcAlphaFactor);
  }

  /** Composite using the reference layer's final effect blend factors. */
  compositeBlend(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget | null,
    blendEquation: string,
    srcBlending: string,
    dstBlending: string,
  ): void {
    const previousAutoClear = renderer.autoClear;
    this.copyMaterial.uniforms.tDiffuse.value = texture;
    this.copyMaterial.blending = THREE.CustomBlending;
    this.copyMaterial.blendEquation =
      TRANSFORM_BLEND_EQUATIONS[blendEquation] ?? THREE.AddEquation;
    this.copyMaterial.blendSrc =
      TRANSFORM_BLEND_FACTORS[srcBlending] ?? THREE.OneFactor;
    this.copyMaterial.blendDst =
      TRANSFORM_BLEND_FACTORS[dstBlending] ?? THREE.OneMinusSrcAlphaFactor;
    this.copyQuad.material = this.copyMaterial;
    renderer.autoClear = false;
    renderer.setRenderTarget(target);
    renderer.render(this.copyScene, this.camera);
    renderer.autoClear = previousAutoClear;
  }

  private copyTexture(
    renderer: THREE.WebGLRenderer,
    texture: THREE.Texture,
    target: THREE.WebGLRenderTarget | null,
    blend: boolean,
    additive = false,
    blendSrc: THREE.BlendingSrcFactor = THREE.OneFactor,
  ): void {
    const previousClearColor = new THREE.Color();
    const previousClearAlpha = renderer.getClearAlpha();
    const previousAutoClear = renderer.autoClear;
    renderer.getClearColor(previousClearColor);
    this.copyMaterial.uniforms.tDiffuse.value = texture;
    this.copyMaterial.blending = blend ? THREE.CustomBlending : THREE.NoBlending;
    // Reference module 53 `getBlendingParams`: layer buffers composite with
    // `ONE / ONE_MINUS_SRC_ALPHA` for an orthographic camera and `ONE / ONE`
    // for a perspective one; the only `SrcAlpha / One` material in the shipped
    // code is the Bloom pass's final quad, which is not this one.
    this.copyMaterial.blendSrc = blendSrc;
    this.copyMaterial.blendDst = additive ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor;
    // `compositeBlend` overwrites this material's equation with the terminal
    // Transform's own blend (e.g. `Min`); the next plain layer copy must go back
    // to `Add`, or every layer composited after such a layer is min()'d against
    // the frame and vanishes (`abnormal`'s video layer).
    this.copyMaterial.blendEquation = THREE.AddEquation;
    this.copyQuad.material = this.copyMaterial;
    renderer.autoClear = false;
    renderer.setRenderTarget(target);
    renderer.setClearColor(0x000000, 0);
    if (!blend) renderer.clear(true, false, false);
    renderer.render(this.copyScene, this.camera);
    renderer.setClearColor(previousClearColor, previousClearAlpha);
    renderer.autoClear = previousAutoClear;
  }

  /**
   * Run the active effects over `inputTarget`.
   *
   * `blend` composites the final pass over whatever is already on screen
   * (used by per-layer chains); without it the result replaces the screen, which
   * is what a composition-wide chain does.
   */
  render(
    renderer: THREE.WebGLRenderer,
    effects: readonly EffectInstance[],
    options: {
      blend?: boolean;
      time?: number;
      /**
       * True when this pass is not a playback step but the reference's
       * `rerender` frame (a seek/paused re-render). The reference's frame
       * context then carries the *initial* `time: 0`
       * (`docs/camera-shake-phase.md` Â§2), so every uniform fed from that clock
       * must see 0 instead of the playhead.
       */
      rerender?: boolean;
      /** Final target; null means the screen. Omit to keep the old screen-or-buffer rule. */
      output?: THREE.WebGLRenderTarget | null;
      layerTexture?: (
        layerId: string,
        preferRaw?: boolean,
        selfTexture?: THREE.Texture | null,
      ) => THREE.Texture | null;
      layerTarget?: (layerId: string) => THREE.WebGLRenderTarget | null;
      /**
       * True when the layer running this chain is `renderToBuffer`: its buffer
       * is a mask source other layers sample, so a Transform's authored factor
       * pair is observable and must be kept. A composited layer instead shows
       * its target's blend result over the frame, where a `SrcColor` multiply
       * leaves the layer's alpha intact and turns it into an opaque card.
       */
      authoredTransformBlending?: boolean;
      /** Base composition texture used by Blending's "Screen" target. */
      screenTexture?: THREE.Texture | null;
      /**
       * The composition's *coverage* alpha, for the `renderInputOnTop` branch of
       * God rays and Streak Glow (`color.rgb *= 1 - inputColor.a`, module
       * 1300/1313/1334). A composition-wide chain is fed an opaque RGB frame, so
       * without this the branch reads alpha 1 and zeroes every ray. Layer chains
       * leave it unset: their buffer alpha is already the layer's coverage.
       */
      coverageTexture?: THREE.Texture | null;
      /**
       * Targets that an earlier row already sampled this frame. A Transform
       * into one of these draws into a scratch copy so the persisted buffer
       * keeps what that row read (the reference re-renders it before the row).
       */
      preserveTargets?: Set<string>;
    } = {},
  ): boolean {
    const active = effects.filter((effect) => effect.enabled);
    if (active.length === 0 || !this.readBuffer || !this.writeBuffer) return false;

    const output = options.output ?? null;
    let read = this.readBuffer;
    let write = this.writeBuffer;

    // Every pass blends the way the reference's 2D effects do: source is
    // assumed premultiplied, destination is attenuated by (1 - source alpha).
    // Intermediate buffers are cleared first, so a pass still replaces its
    // target; the last pass blends onto the frame when compositing a layer.
    const previousAutoClear = renderer.autoClear;
    const previousClearColor = new THREE.Color();
    renderer.getClearColor(previousClearColor);
    const previousClearAlpha = renderer.getClearAlpha();
    renderer.autoClear = false;
    try {
      for (let index = 0; index < active.length; index += 1) {
        const last = index === active.length - 1;
        const material = this.materialFor(active[index]);
        // `applyTransform` derives `uAspect` from `uResolution`, so the pass has
        // to describe the current source *before* the effect reads it. Setting
        // these after the call gave the first Transform of every chain the
        // previous pass's aspect (a square frame on the first render), which
        // skews `matPositionX` and `matScaleX` by the frame aspect.
        material.uniforms.tDiffuse.value = read.texture;
        (material.uniforms.uResolution.value as THREE.Vector2).set(read.width, read.height);
        if (material.uniforms.uTime) {
          // `uTime` is the reference's frame-context clock, not the playhead
          // (`docs/camera-shake-phase.md` Â§2). A `rerender` frame is a seek or a
          // paused re-render and carries the initial `time: 0`; Chroma Shift
          // (module 1300) reads it for its palette phase, which is why
          // `abnormal` @37.48875 sat on the playhead phase and came out orange
          // where the reference's phase-0 palette is blue.
          material.uniforms.uTime.value = options.rerender ? 0 : options.time ?? 0;
        }
        this.applyParams(
          material,
          active[index],
          options.layerTexture,
          options.screenTexture,
          read.texture,
        );
        // The coverage map is a property of the frame, not of the effect's
        // params: a composition-wide chain has no coverage in its own alpha.
        if (material.uniforms.uHasCoverage) {
          material.uniforms.uHasCoverage.value = options.coverageTexture ? 1 : 0;
          if (options.coverageTexture) {
            material.uniforms.uCoverageMap.value = options.coverageTexture;
          }
        }
        if (active[index].type === "camera-shake") {
          this.applyCameraShake(material, active[index], options.time ?? 0);
        } else if (active[index].type === "transform") {
          this.applyTransform(material, active[index], options.time ?? 0);
        }
        if (active[index].type === "trail") {
          const store = this.ensureTrailStore(active[index].id, read.width, read.height);
          material.uniforms.tDiffuse.value = read.texture;
          material.uniforms.ptDiffuse.value = store.texture;
          material.uniforms.uAmount.value = Math.max(0, Math.min(1, Number(active[index].params.amount ?? 0.5)));
          material.blending = THREE.NoBlending;
          this.quad.material = material;
          renderer.setRenderTarget(write);
          renderer.setClearColor(0x000000, 0);
          renderer.clear(true, false, false);
          renderer.render(this.scene, this.camera);
          this.copyTexture(renderer, write.texture, store, false);
          if (last) {
            this.copyTexture(
              renderer,
              write.texture,
              output,
              output ? false : Boolean(options.blend),
            );
            break;
          }
          const swap = read;
          read = write;
          write = swap;
          continue;
        }
        if (active[index].type === "tilt-shift") {
          const passes = Math.max(
            1,
            Math.min(10, Math.round(Number(active[index].params.nrPasses ?? 1))),
          );
          const store = this.ensureTiltStore(active[index].id, read.width, read.height);
          let source = read;
          this.quad.material = material;
          for (let pass = 0; pass < passes; pass += 1) {
            const lastPass = pass === passes - 1;
            (material.uniforms.uResolution.value as THREE.Vector2).set(
              source.width,
              source.height,
            );
            material.uniforms.uAspect.value = source.width / Math.max(1, source.height);

            // Horizontal half of the separable Gaussian.
            material.uniforms.tDiffuse.value = source.texture;
            material.uniforms.uAxis.value = 0;
            material.blending = THREE.NoBlending;
            renderer.setRenderTarget(store);
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
            renderer.render(this.scene, this.camera);

            // Vertical half, then hand the result to the next pass/effect/frame.
            const dest = lastPass ? (last ? output : write) : write;
            const blendScreen = lastPass && last && !output && Boolean(options.blend);
            material.uniforms.tDiffuse.value = store.texture;
            material.uniforms.uAxis.value = 1;
            material.blending = blendScreen ? THREE.CustomBlending : THREE.NoBlending;
            material.blendSrc = THREE.OneFactor;
            material.blendDst = THREE.OneMinusSrcAlphaFactor;
            renderer.setRenderTarget(dest);
            if (dest || !blendScreen) {
              renderer.setClearColor(0x000000, 0);
              renderer.clear(true, false, false);
            }
            renderer.render(this.scene, this.camera);

            if (!lastPass || !last) {
              const swap = read;
              read = write;
              write = swap;
              source = read;
            }
          }
          if (last) break;
          continue;
        }
        if (
          active[index].type === "bloom" ||
          active[index].type === "glow-bloom"
        ) {
          const parameter = (key: string, fallback: number): number => {
            const parsed = Number(active[index].params[key]);
            return Number.isFinite(parsed) ? parsed : fallback;
          };
          const resources = this.ensureBloomResources(active[index].id, read.width, read.height);
          const bloom = this.ensureBloomMaterials();
          const draw = (drawMaterial: THREE.ShaderMaterial, target: THREE.WebGLRenderTarget): void => {
            drawMaterial.blending = THREE.NoBlending;
            this.quad.material = drawMaterial;
            renderer.setRenderTarget(target);
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
            renderer.render(this.scene, this.camera);
          };

          bloom.highPass.uniforms.tDiffuse.value = read.texture;
          bloom.highPass.uniforms.uThreshold.value = Math.max(
            0,
            Math.min(1, parameter("threshold", 0)),
          );
          bloom.highPass.uniforms.uSmoothWidth.value = 0.01;
          draw(bloom.highPass, resources.bright);

          let source: THREE.WebGLRenderTarget = resources.bright;
          const kernels = [3, 5, 7, 9, 11];
          for (let mip = 0; mip < 5; mip += 1) {
            const horizontal = resources.horizontal[mip];
            const vertical = resources.vertical[mip];
            const kernel = kernels[mip];
            bloom.blur.uniforms.tDiffuse.value = source.texture;
            (bloom.blur.uniforms.uTexSize.value as THREE.Vector2).set(
              horizontal.width,
              horizontal.height,
            );
            (bloom.blur.uniforms.uDirection.value as THREE.Vector2).set(1, 0);
            bloom.blur.uniforms.uKernelRadius.value = kernel;
            bloom.blur.uniforms.uSigma.value = kernel;
            draw(bloom.blur, horizontal);

            bloom.blur.uniforms.tDiffuse.value = horizontal.texture;
            (bloom.blur.uniforms.uDirection.value as THREE.Vector2).set(0, 1);
            draw(bloom.blur, vertical);
            source = vertical;
          }

          bloom.composite.uniforms.uBlur1.value = resources.vertical[0].texture;
          bloom.composite.uniforms.uBlur2.value = resources.vertical[1].texture;
          bloom.composite.uniforms.uBlur3.value = resources.vertical[2].texture;
          bloom.composite.uniforms.uBlur4.value = resources.vertical[3].texture;
          bloom.composite.uniforms.uBlur5.value = resources.vertical[4].texture;
          bloom.composite.uniforms.uStrength.value = Math.max(0, parameter("strength", 1));
          // The shipped composite feeds `bloomRadius` straight into
          // `mix(factor, 1.2 - factor, radius)`. It is not a 0..1 mix: a negative
          // radius (`perimeter` uses -1) boosts the sharp mip and pushes the
          // widest ones negative ÃŽâ€œÃƒâ€¡ÃƒÂ¶ a tight, brighter halo ÃŽâ€œÃƒâ€¡ÃƒÂ¶ and a radius above 1
          // does the reverse. Clamping to 0..1 collapsed every negative radius
          // onto 0, which spread the same energy over the wide mips and lost the
          // halo.
          bloom.composite.uniforms.uRadius.value = parameter("radius", 0.1);
          draw(bloom.composite, resources.horizontal[0]);

          bloom.final.uniforms.tDiffuse.value = read.texture;
          bloom.final.uniforms.uBloomTexture.value = resources.horizontal[0].texture;
          const renderBaseTexture =
            Number(active[index].params.renderBaseTexture ?? 0) > 0.5;
          bloom.final.uniforms.uRenderBaseTexture.value = renderBaseTexture ? 1 : 0;
          // Shipped module 1287 `renderEffect`:
          //   `renderBaseAdditive.value = !!renderBaseTexture && renderBaseAdditive`
          // so `renderBaseTexture: false` always takes the final shader's
          // `else { color = vec4(bloom, 1.0); }` branch - bloom RGB with alpha 1,
          // regardless of the authored additive flag. Keeping the layer's own
          // alpha here made the pass translucent; the composite is the Bloom's
          // own `AdditiveBlending` (`SrcAlpha / One`), so alpha 1 is what the
          // shipped adds (blooming-heart-eye 17.86 -> 23.56 with the translucent
          // buffer, 137.66 ref mean against 117.39).
          bloom.final.uniforms.uRenderBaseAdditive.value =
            renderBaseTexture && Number(active[index].params.renderBaseAdditive ?? 1) > 0.5
              ? 1
              : 0;
          const dest = last ? output : write;
          const blendScreen = last && !output && Boolean(options.blend);
          bloom.final.blending = blendScreen ? THREE.CustomBlending : THREE.NoBlending;
          bloom.final.blendSrc = THREE.OneFactor;
          bloom.final.blendDst = THREE.OneMinusSrcAlphaFactor;
          this.quad.material = bloom.final;
          renderer.setRenderTarget(dest);
          if (dest || !blendScreen) {
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
          }
          renderer.render(this.scene, this.camera);
          if (last) break;
          const swap = read;
          read = write;
          write = swap;
          continue;
        }
        if (active[index].type === "distance-field") {
          const width = read.width;
          const height = read.height;
          const scaleFactor =
            Math.sqrt((width / 1920) * (height / 1080)) *
            Math.sqrt(16 / 9 / (width / Math.max(1, height)));
          const rawMax = Number(active[index].params.maxDistance ?? 100);
          const maxDistance = Math.max(1, rawMax * scaleFactor);
          const field = this.generateDistanceField(
            renderer,
            active[index].id,
            read.texture,
            width,
            height,
            maxDistance,
          );
          const mode = String(active[index].params.visualizationMode ?? "grayscale");
          material.uniforms.tDiffuse.value = read.texture;
          material.uniforms.uDistanceField.value = field;
          material.uniforms.uMaxDistance.value = maxDistance;
          material.uniforms.uInvertField.value =
            Number(active[index].params.invertField ?? 0) > 0.5 ? 1 : 0;
          material.uniforms.uNormalizeField.value =
            Number(active[index].params.normalizeField ?? 1) > 0.5 ? 1 : 0;
          material.uniforms.uFieldOpacity.value = Math.max(
            0,
            Math.min(1, Number(active[index].params.fieldOpacity ?? 1)),
          );
          material.uniforms.uVisualizationMode.value =
            mode === "heatmap" ? 1 : mode === "rainbow" ? 2 : 0;
          (material.uniforms.uResolution.value as THREE.Vector2).set(width, height);
          material.blending = THREE.CustomBlending;
          material.blendSrc = THREE.OneFactor;
          material.blendDst = THREE.OneMinusSrcAlphaFactor;
          this.quad.material = material;
          const dest = last ? output : write;
          const blendScreen = last && !output && Boolean(options.blend);
          renderer.setRenderTarget(dest);
          if (dest || !blendScreen) {
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
          }
          renderer.render(this.scene, this.camera);
          if (last) break;
          const swap = read;
          read = write;
          write = swap;
          continue;
        }
        if (
          active[index].type === "advanced-outline" ||
          active[index].type === "advanced-shadow"
        ) {
          const width = read.width;
          const height = read.height;
          const scaleFactor =
            Math.sqrt((width / 1920) * (height / 1080)) *
            Math.sqrt(16 / 9 / (width / Math.max(1, height)));
          const parameter = (key: string, fallback: number): number => {
            const parsed = Number(active[index].params[key]);
            return Number.isFinite(parsed) ? parsed : fallback;
          };
          if (active[index].type === "advanced-outline") {
            const low = parameter("outlineThreshLow", 1) * scaleFactor;
            const high = parameter("outlineThreshHigh", 25) * scaleFactor;
            const field = this.generateDistanceField(
              renderer,
              active[index].id,
              read.texture,
              width,
              height,
              Math.max(high, scaleFactor),
            );
            const color = hexRgb(String(active[index].params.outlineColor ?? "#ff0000"));
            material.uniforms.tDiffuse.value = read.texture;
            material.uniforms.uDistanceField.value = field;
            (material.uniforms.uOutlineColor.value as THREE.Vector3).set(
              color[0],
              color[1],
              color[2],
            );
            material.uniforms.uThreshLow.value = low;
            material.uniforms.uThreshHigh.value = high;
            material.uniforms.uOutlineOpacity.value = parameter("outlineOpacity", 1);
            material.uniforms.uOutlineOnly.value =
              parameter("outlineOnly", 0) > 0.5 ? 1 : 0;
          } else {
            const size = parameter("shadowSize", 50) * scaleFactor;
            const field = this.generateDistanceField(
              renderer,
              active[index].id,
              read.texture,
              width,
              height,
              Math.max(size, 1),
            );
            const color = hexRgb(String(active[index].params.shadowColor ?? "#000000"));
            material.uniforms.tDiffuse.value = read.texture;
            material.uniforms.uDistanceField.value = field;
            (material.uniforms.uShadowColor.value as THREE.Vector3).set(
              color[0],
              color[1],
              color[2],
            );
            material.uniforms.uShadowOpacity.value = parameter("shadowOpacity", 0.35);
            (material.uniforms.uShadowOffset.value as THREE.Vector2).set(
              parameter("shadowOffsetX", 0) * scaleFactor,
              parameter("shadowOffsetY", 0) * scaleFactor,
            );
            material.uniforms.uShadowSize.value = size;
            material.uniforms.uShadowSpread.value = parameter("shadowSpread", 0);
            material.uniforms.uShadowOnly.value =
              parameter("shadowOnly", 0) > 0.5 ? 1 : 0;
          }
          (material.uniforms.uResolution.value as THREE.Vector2).set(width, height);
          material.blending = THREE.CustomBlending;
          material.blendSrc = THREE.OneFactor;
          material.blendDst = THREE.OneMinusSrcAlphaFactor;
          this.quad.material = material;
          const dest = last ? output : write;
          const blendScreen = last && !output && Boolean(options.blend);
          renderer.setRenderTarget(dest);
          if (dest || !blendScreen) {
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
          }
          renderer.render(this.scene, this.camera);
          if (last) break;
          const swap = read;
          read = write;
          write = swap;
          continue;
        }
        if (active[index].type === "box-blur") {
          // Shipped BoxBlur (module 1289): `nrPasses` iterations of a 9-tap
          // horizontal then vertical pass. Replacing the old single widened
          // 3x3 tap with the shipped pair removes the banded tiles the huge
          // kernel produced when it wrapped around `eternal-pulse`'s frame.
          const passes = Math.max(
            1,
            Math.min(10, Math.round(Number(active[index].params.nrPasses ?? 1))),
          );
          const radius = Math.max(0, Number(active[index].params.radius ?? 0));
          const store = this.ensureTiltStore(
            `${active[index].id}:box-blur`,
            read.width,
            read.height,
          );
          const horizontalEffect = {
            ...active[index],
            type: "box-blur-horizontal",
            id: `${active[index].id}:horizontal`,
          };
          const verticalEffect = {
            ...active[index],
            type: "box-blur-vertical",
            id: `${active[index].id}:vertical`,
          };
          const horizontalMaterial = this.materialFor(horizontalEffect);
          const verticalMaterial = this.materialFor(verticalEffect);
          let source = read;
          for (let pass = 0; pass < passes; pass += 1) {
            const lastPass = pass === passes - 1;
            horizontalMaterial.uniforms.tDiffuse.value = source.texture;
            horizontalMaterial.uniforms.uRadius.value = radius;
            (horizontalMaterial.uniforms.uResolution.value as THREE.Vector2).set(
              source.width,
              source.height,
            );
            horizontalMaterial.blending = THREE.NoBlending;
            this.quad.material = horizontalMaterial;
            renderer.setRenderTarget(store);
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
            renderer.render(this.scene, this.camera);

            const dest = lastPass ? (last ? output : write) : write;
            const blendScreen = lastPass && last && !output && Boolean(options.blend);
            verticalMaterial.uniforms.tDiffuse.value = store.texture;
            verticalMaterial.uniforms.uRadius.value = radius;
            (verticalMaterial.uniforms.uResolution.value as THREE.Vector2).set(
              source.width,
              source.height,
            );
            verticalMaterial.blending = blendScreen
              ? THREE.CustomBlending
              : THREE.NoBlending;
            verticalMaterial.blendSrc = THREE.OneFactor;
            verticalMaterial.blendDst = THREE.OneMinusSrcAlphaFactor;
            this.quad.material = verticalMaterial;
            renderer.setRenderTarget(dest);
            if (dest || !blendScreen) {
              renderer.setClearColor(0x000000, 0);
              renderer.clear(true, false, false);
            }
            renderer.render(this.scene, this.camera);
            if (!lastPass || !last) {
              const swap = read;
              read = write;
              write = swap;
              source = read;
            }
          }
          if (last) break;
          continue;
        }
        if (active[index].type === "two-pass-blur") {
          // The shipped pass (`main~56930160`, TwoPassBlur) runs the authored
          // `nrPasses` iterations; the 10 cap here silently cut templates that
          // author more (plasma-pill-kn wants 25) to a different blur entirely.
          const passes = Math.max(
            1,
            Math.min(64, Math.round(Number(active[index].params.nrPasses ?? 1))),
          );
          const store = this.ensureTiltStore(
            `${active[index].id}:two-pass`,
            read.width,
            read.height,
          );
          const horizontalEffect = {
            ...active[index],
            type: "horizontal-blur",
            id: `${active[index].id}:horizontal`,
          };
          const verticalEffect = {
            ...active[index],
            type: "vertical-blur",
            id: `${active[index].id}:vertical`,
          };
          const horizontalMaterial = this.materialFor(horizontalEffect);
          const verticalMaterial = this.materialFor(verticalEffect);
          this.applyParams(horizontalMaterial, horizontalEffect);
          this.applyParams(verticalMaterial, verticalEffect);
          let source = read;
          for (let pass = 0; pass < passes; pass += 1) {
            const lastPass = pass === passes - 1;
            horizontalMaterial.uniforms.tDiffuse.value = source.texture;
            (horizontalMaterial.uniforms.uResolution.value as THREE.Vector2).set(
              source.width,
              source.height,
            );
            horizontalMaterial.blending = THREE.NoBlending;
            this.quad.material = horizontalMaterial;
            renderer.setRenderTarget(store);
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
            renderer.render(this.scene, this.camera);

            const dest = lastPass ? (last ? output : write) : write;
            const blendScreen = lastPass && last && !output && Boolean(options.blend);
            verticalMaterial.uniforms.tDiffuse.value = store.texture;
            (verticalMaterial.uniforms.uResolution.value as THREE.Vector2).set(
              source.width,
              source.height,
            );
            verticalMaterial.blending = blendScreen
              ? THREE.CustomBlending
              : THREE.NoBlending;
            verticalMaterial.blendSrc = THREE.OneFactor;
            verticalMaterial.blendDst = THREE.OneMinusSrcAlphaFactor;
            this.quad.material = verticalMaterial;
            renderer.setRenderTarget(dest);
            if (dest || !blendScreen) {
              renderer.setClearColor(0x000000, 0);
              renderer.clear(true, false, false);
            }
            renderer.render(this.scene, this.camera);
            if (!lastPass || !last) {
              const swap = read;
              read = write;
              write = swap;
              source = read;
            }
          }
          if (last) break;
          continue;
        }
        if (active[index].type === "time-stop") {
          const time = options.time ?? 0;
          const delay = Math.max(
            0,
            Math.min(5, Number(active[index].params.delaySeconds ?? 0)),
          );
          const skip = Math.max(
            0,
            Math.round(Number(active[index].params.frameSkip ?? 1)),
          );
          const historySize = Math.max(1, Math.round(delay * 60) + 1);
          const history = this.timeStopHistory(
            active[index].id,
            read.width,
            read.height,
            historySize,
          );
          if (
            history.lastTime !== null &&
            (time < history.lastTime - 0.05 || time - history.lastTime > 0.5)
          ) {
            history.writeIndex = 0;
            history.framesCaptured = 0;
          }
          const frameIndex = Math.floor(time * 60);
          const shouldCapture =
            history.framesCaptured === 0 ||
            (skip > 0 && frameIndex % skip === 0);
          if (shouldCapture) {
            const target = history.targets[history.writeIndex];
            this.copyTexture(renderer, read.texture, target, false);
            history.writeIndex = (history.writeIndex + 1) % history.targets.length;
            history.framesCaptured = Math.min(
              history.targets.length,
              history.framesCaptured + 1,
            );
          }
          history.lastTime = time;
          const delayFrames = Math.max(0, Math.round(delay * 60));
          const selected =
            delayFrames === 0
              ? 0
              : Math.min(delayFrames, Math.max(0, history.framesCaptured - 1));
          const sourceIndex =
            (history.writeIndex - 1 - selected + history.targets.length) %
            history.targets.length;
          const source = history.targets[sourceIndex] ?? read;
          const dest = last ? output : write;
          const blendScreen = last && !output && Boolean(options.blend);
          this.copyTexture(renderer, source.texture, dest, blendScreen);
          if (last) break;
          read = source;
          continue;
        }
        if (active[index].type === "transform") {
          const targetId = String(active[index].params.targetLayer ?? "Screen");
          const transformTarget =
            targetId !== "Screen" && options.layerTarget
              ? options.layerTarget(targetId)
              : null;
          if (transformTarget && transformTarget !== read) {
            material.uniforms.tDiffuse.value = read.texture;
            (material.uniforms.uResolution.value as THREE.Vector2).set(
              read.width,
              read.height,
            );
            if (material.uniforms.uTime) {
              material.uniforms.uTime.value = options.rerender ? 0 : options.time ?? 0;
            }
            // The reference applies the authored factor pair, mapped through the
            // app's own table (`main~25704ef2`): `SRC_COLOR: SrcAlphaFactor`.
            // So `dstBlending: "SrcColor"` is a *source-alpha* attenuation, not
            // a colour multiply: the target survives under an opaque mask and is
            // cleared where the mask is transparent. (The UI text says "multiply
            // by the source color", but the shipped map is what runs.)
            this.applyTransformBlending(material, active[index]);
            this.quad.material = material;

            // Reference `Transform.renderEffect`: the transformed quad is
            // rendered into the *target layer's own* render target (no clear),
            // then the target's blend-result quad is drawn into the current
            // destination. Writing back matters: later chains sampling that
            // layer must see the merged content.
            //
            // A target that an earlier row already sampled this frame keeps its
            // persisted buffer: the reference re-renders that layer in row
            // order before the row that read it, which our all-raw-first pass
            // does not. Draw into a copy for those targets so next frame's
            // earlier row still sees the pre-mask content (`equinox`).
            const preserve = Boolean(options.preserveTargets?.has(targetId));
            const destination = preserve
              ? this.ensureTransformTargetCopy(
                  active[index].id,
                  transformTarget.width,
                  transformTarget.height,
                )
              : transformTarget;
            if (preserve) {
              this.copyTexture(renderer, transformTarget.texture, destination, false);
            }
            const transformAutoClear: boolean = renderer.autoClear;
            renderer.autoClear = false;
            renderer.setRenderTarget(destination);
            renderer.render(this.scene, this.camera);
            renderer.autoClear = transformAutoClear;

            const dest = last ? output : write;
            const blendScreen = last && !output && Boolean(options.blend);
            this.copyTexture(renderer, destination.texture, dest, blendScreen);
            if (last) break;
            const swap = read;
            read = write;
            write = swap;
            continue;
          }
        }
        material.blending = THREE.CustomBlending;
        material.blendSrc = THREE.OneFactor;
        material.blendDst = THREE.OneMinusSrcAlphaFactor;
        material.blendEquation = THREE.AddEquation;
        if (active[index].type === "transform") {
          const targetId = String(active[index].params.targetLayer ?? "Screen");
          // A terminal Transform Ã¢â€ â€™ Screen is composited onto the composition
          // with its own factors (renderer.ts terminalBlends). Applying the same
          // factors inside the cleared layer buffer too zeroed it for
          // OneMinusSrcAlpha/SrcAlpha chains (ground-shader-line).
          if (!(last && targetId === "Screen")) {
            this.applyTransformBlending(material, active[index]);
          }
        }
        this.quad.material = material;

        renderer.setRenderTarget(last ? output : write);
        if (last) {
          if (output || !options.blend) {
            renderer.setClearColor(0x000000, 0);
            renderer.clear(true, false, false);
          }
        } else {
          renderer.setClearColor(0x000000, 0);
          renderer.clear(true, false, false);
        }
        renderer.render(this.scene, this.camera);
        if (!last) {
          const swap = read;
          read = write;
          write = swap;
        }
      }
    } finally {
      renderer.setClearColor(previousClearColor, previousClearAlpha);
      renderer.autoClear = previousAutoClear;
    }

    renderer.setRenderTarget(null);
    return true;
  }
}

function hexRgb(hex: string): [number, number, number] {
  const raw = hex.trim().replace(/^#/, "");
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((char) => char + char)
          .join("")
      : raw;
  if (!/^[0-9a-f]{6}$/i.test(full)) return [1, 1, 1];
  return [0, 2, 4].map((offset) => parseInt(full.slice(offset, offset + 2), 16) / 255) as [
    number,
    number,
    number,
  ];
}
