import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import {
  buildPreviewGpuCapabilityProfile,
  resolvePreviewQualityPolicy,
  type PreviewGpuCapabilityProfile,
  type PreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

export type WebGpuSpectrumInstance = {
  baseX: number
  baseY: number
  dirX: number
  dirY: number
  halfWidth: number
  length: number
  red: number
  green: number
  blue: number
  alpha: number
  softness: number
  glow: number
  variant: number
  blendMode: string
  gradientU: number
  gradientV: number
}

export type WebGpuSpectrumGradientAtlas = {
  width: number
  height: number
  rgba: Uint8Array
}

export type WebGpuParticleInstance = {
  spawnX: number
  spawnY: number
  dirX: number
  dirY: number
  halfWidth: number
  halfHeight: number
  speed: number
  spawnSec: number
  lifetimeSec: number
  opacity: number
  style: number
  softness: number
  noiseSeed: number
}

export type WebGpuParticleSimulationSettings = {
  timeSec: number
  centerX: number
  centerY: number
  reactiveEnv: number
  triggerEnv: number
  driftStrength: number
  swirlStrength: number
  reactivity: number
  audioTravelBoost: number
  audioMotionMode: number
  opacity: number
  red: number
  green: number
  blue: number
  baseRed: number
  baseGreen: number
  baseBlue: number
  reactRed: number
  reactGreen: number
  reactBlue: number
  reactStrength: number
}

export type WebGpuAtmosphereSettings = {
  timeSec: number
  smokeEnabled: boolean
  smokeOpacity: number
  smokeStrength: number
  smokeBlur: number
  smokeNoise: number
  smokeSpeed: number
  smokeRed: number
  smokeGreen: number
  smokeBlue: number
  vignetteEnabled: boolean
  vignetteStrength: number
  vignetteFeather: number
  vignetteOpacity: number
  vignetteRed: number
  vignetteGreen: number
  vignetteBlue: number
}

export type WebGpuPostFxSettings = {
  enabled: boolean
  threshold: number
  knee: number
  intensity: number
  bloomStrength: number
  blurScale: number
  motionBlurStrength?: number
  motionBlurShutterAngle?: number
  motionBlurSamples?: number
}

type WebGpuSpectrumFrame = {
  width: number
  height: number
  dpr: number
  audioSignal?: PreviewGpuAudioSignalFrame | null
  spectrumGradientAtlas?: WebGpuSpectrumGradientAtlas | null
  instances: WebGpuSpectrumInstance[]
  particles?: WebGpuParticleInstance[]
  particleSimulation?: WebGpuParticleSimulationSettings | null
  backdropSource?: CanvasImageSource | null
  overlaySource?: CanvasImageSource | null
  atmosphere?: WebGpuAtmosphereSettings | null
  fallbackScene?: boolean
  postFx?: WebGpuPostFxSettings | null
}

type WebGpuInitializeOptions = {
  onDeviceLost?: (message: string) => void
}

export type WebGpuInitializeResult = {
  capabilityProfile: PreviewGpuCapabilityProfile
  qualityPolicy: PreviewQualityPolicy
}

const INSTANCE_STRIDE_FLOATS = 15
const INSTANCE_STRIDE_BYTES = INSTANCE_STRIDE_FLOATS * Float32Array.BYTES_PER_ELEMENT
const PARTICLE_INSTANCE_STRIDE_FLOATS = 13
const PARTICLE_INSTANCE_STRIDE_BYTES = PARTICLE_INSTANCE_STRIDE_FLOATS * Float32Array.BYTES_PER_ELEMENT
const UNIFORM_STRIDE_FLOATS = 24
const UNIFORM_STRIDE_BYTES = UNIFORM_STRIDE_FLOATS * Float32Array.BYTES_PER_ELEMENT
const ATMOSPHERE_UNIFORM_STRIDE_FLOATS = 24
const ATMOSPHERE_UNIFORM_STRIDE_BYTES =
  ATMOSPHERE_UNIFORM_STRIDE_FLOATS * Float32Array.BYTES_PER_ELEMENT
const AUDIO_SIGNAL_HEADER_FLOATS = 16
const AUDIO_SIGNAL_BAND_FLOATS = 64
const AUDIO_SIGNAL_BUFFER_FLOATS = AUDIO_SIGNAL_HEADER_FLOATS + AUDIO_SIGNAL_BAND_FLOATS * 4
const AUDIO_SIGNAL_BUFFER_BYTES = AUDIO_SIGNAL_BUFFER_FLOATS * Float32Array.BYTES_PER_ELEMENT
const INITIAL_INSTANCE_CAPACITY = 2048
const GPU_BUFFER_USAGE_MAP_READ = 0x0001
const GPU_BUFFER_USAGE_COPY_DST = 0x0008
const GPU_BUFFER_USAGE_COPY_SRC = 0x0004
const GPU_BUFFER_USAGE_STORAGE = 0x0080
const GPU_BUFFER_USAGE_VERTEX = 0x0020
const GPU_BUFFER_USAGE_UNIFORM = 0x0040
const GPU_MAP_MODE_READ = 0x0001
const GPU_SHADER_STAGE_VERTEX = 0x1
const GPU_SHADER_STAGE_FRAGMENT = 0x2
const GPU_COLOR_WRITE_ALL = 0xf
const GPU_TEXTURE_USAGE_TEXTURE_BINDING = 0x04
const GPU_TEXTURE_USAGE_COPY_SRC = 0x01
const GPU_TEXTURE_USAGE_COPY_DST = 0x08
const GPU_TEXTURE_USAGE_RENDER_ATTACHMENT = 0x10
const DEFAULT_GRADIENT_ATLAS_RGBA = new Uint8Array([255, 255, 255, 255])

type WebGpuReadbackSlot = {
  buffer: any | null
  busy: boolean
}

const sendParticleReactColorDebug = createVideoDebugSender({
  sessionId: 'particle-react-color',
  runId: 'pre-fix',
})

const sendParticleMissingDebug = createVideoDebugSender({
  sessionId: 'particle-missing',
  runId: 'pre-fix',
})

const sendExportSpeedDebug = createVideoDebugSender({
  sessionId: 'manual-export-black-video',
  runId: 'pre-fix',
  endpoint: 'http://127.0.0.1:7780/event',
})

let lastParticleUniformDebugSecond = -1
let lastParticleInstanceDebugSecond = -1

type GpuAdapter = {
  requestDevice: () => Promise<any>
  features?: Iterable<string>
  isFallbackAdapter?: boolean
}

type GpuNavigator = {
  requestAdapter: () => Promise<GpuAdapter | null>
  getPreferredCanvasFormat: () => string
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

const SHADER_CODE = /* wgsl */ `
struct Uniforms {
  viewport: vec2f,
  _padding: vec2f,
}

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
  @location(1) color: vec4f,
  @location(2) softness: f32,
  @location(3) glow: f32,
  @location(4) variant: f32,
  @location(5) gradientUv: vec2f,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(1) @binding(0) var spectrumGradientSampler: sampler;
@group(1) @binding(1) var spectrumGradientTexture: texture_2d<f32>;

@vertex
fn vs_main(
  @builtin(vertex_index) vertexIndex: u32,
  @location(0) base: vec2f,
  @location(1) dir: vec2f,
  @location(2) halfWidth: f32,
  @location(3) length: f32,
  @location(4) color: vec4f,
  @location(5) softness: f32,
  @location(6) glow: f32,
  @location(7) variant: f32,
  @location(8) gradientUv: vec2f,
) -> VertexOutput {
  var quad = array<vec2f, 6>(
    vec2f(0.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(0.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(0.0, 1.0),
  );

  let local = quad[vertexIndex];
  let perp = vec2f(-dir.y, dir.x);
  let world = base + dir * length * local.x + perp * halfWidth * local.y;
  let clip = vec2f(
    (world.x / uniforms.viewport.x) * 2.0 - 1.0,
    1.0 - (world.y / uniforms.viewport.y) * 2.0,
  );

  var output: VertexOutput;
  output.position = vec4f(clip, 0.0, 1.0);
  output.uv = local;
  output.color = color;
  output.softness = softness;
  output.glow = glow;
  output.variant = variant;
  output.gradientUv = gradientUv;
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let gradientColor = textureSample(
    spectrumGradientTexture,
    spectrumGradientSampler,
    vec2f(clamp(input.gradientUv.x, 0.0, 1.0), clamp(input.gradientUv.y, 0.0, 1.0)),
  );
  // Fall back to the packed instance color when the atlas sample is invalid or all-zero.
  let gradientStrength = max(max(gradientColor.r, gradientColor.g), gradientColor.b);
  let resolvedColor = select(input.color.rgb, gradientColor.rgb, gradientStrength > 0.001);
  var safeSoftness = max(0.02, input.softness);
  if (input.variant >= 3.5 && input.variant < 4.5) {
    safeSoftness = max(0.0015, input.softness);
  }
  let tipBias = pow(clamp(input.uv.x, 0.0, 1.0), 1.35);
  let side = abs(input.uv.y);
  let radius = length(vec2f(input.uv.x * 2.0 - 1.0, input.uv.y));
  var edgeAlpha = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, side);
  var bodyAlpha =
    smoothstep(-0.04, 0.18, input.uv.x) *
    (1.0 - smoothstep(1.0, 1.08 + safeSoftness * 0.35, input.uv.x));
  var emission = 0.78 + tipBias * (0.9 + input.glow * 1.35);

  if (input.variant < 0.5) {
    // Premium bar / capsule body.
    edgeAlpha = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, side);
    bodyAlpha =
      smoothstep(-0.04, 0.18, input.uv.x) *
      (1.0 - smoothstep(1.0, 1.08 + safeSoftness * 0.35, input.uv.x));
    emission = 0.78 + tipBias * (0.9 + input.glow * 1.35);
  } else if (input.variant < 1.5) {
    // Dot matrix / segmented cell.
    let dotRadius = length(vec2f(input.uv.x * 2.0 - 1.0, input.uv.y));
    bodyAlpha = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, dotRadius);
    edgeAlpha = 1.0;
    emission = 0.92 + input.glow * 0.75;
  } else if (input.variant < 2.5) {
    // Ribbon / waveform band.
    let ribbonCenter = 0.14 * sin((input.uv.x * 1.1 - 0.08) * 3.14159);
    let ribbonDistance = abs(input.uv.y - ribbonCenter);
    let ribbonWidth = mix(0.24, 0.78, pow(1.0 - clamp(input.uv.x, 0.0, 1.0), 0.22));
    let ribbonCore = smoothstep(ribbonWidth + safeSoftness, ribbonWidth - safeSoftness, ribbonDistance);
    let ribbonFill =
      smoothstep(-0.08, 0.06, input.uv.x) *
      (1.0 - smoothstep(1.0, 1.03 + safeSoftness * 0.18, input.uv.x));
    let ribbonHighlight = smoothstep(0.22, 0.0, abs(input.uv.y - (ribbonCenter - 0.1))) * 0.32;
    edgeAlpha = 1.0;
    bodyAlpha = clamp((ribbonCore + ribbonHighlight) * ribbonFill, 0.0, 1.0);
    emission = 0.8 + tipBias * (0.5 + input.glow * 0.78);
  } else if (input.variant < 3.5) {
    // Liquid / filled mass.
    let bodyRadius = length(vec2f(input.uv.x * 1.72 - 0.86, input.uv.y * 0.94));
    let massTop = smoothstep(1.04 + safeSoftness, 0.38, bodyRadius);
    let forwardFill = smoothstep(-0.08, 0.04, input.uv.x);
    let liquidHighlight =
      smoothstep(0.24, 0.0, length(vec2f(input.uv.x * 1.5 - 0.48, input.uv.y + 0.22))) * 0.42;
    let meniscus = smoothstep(0.82, 0.08, abs(input.uv.y + 0.58)) * smoothstep(0.04, 0.34, input.uv.x) * 0.28;
    edgeAlpha = 1.0;
    bodyAlpha = clamp(massTop * forwardFill + liquidHighlight + meniscus, 0.0, 1.0);
    emission = 0.74 + tipBias * (0.36 + input.glow * 0.62);
  } else if (input.variant < 4.5) {
    // Flying glow / wing halo.
    let wingSoftness = max(0.0012, safeSoftness * 0.08);
    let wingWidth = mix(0.028, 0.84, pow(1.0 - clamp(input.uv.x, 0.0, 1.0), 0.8));
    let wingCore = smoothstep(wingWidth + wingSoftness, wingWidth - wingSoftness, side);
    let wingCenter = pow(clamp(1.0 - side / max(wingWidth, 0.0001), 0.0, 1.0), 2.4);
    let wingEnvelope =
      smoothstep(-0.001, 0.008, input.uv.x) *
      (1.0 - smoothstep(0.998, 1.0015 + wingSoftness * 0.03, input.uv.x));
    let wingSheen =
      smoothstep(0.12, 0.0, side / max(wingWidth, 0.0001)) *
      smoothstep(0.06, 0.52, input.uv.x) *
      0.035;
    edgeAlpha = 1.0;
    bodyAlpha = clamp((wingCore * 0.98 + wingCenter * 0.06 + wingSheen) * wingEnvelope, 0.0, 1.0);
    emission = 0.84 + tipBias * (0.34 + input.glow * 0.42);
  } else if (input.variant < 5.5) {
    // Halo stack / layered light hierarchy.
    let envelope =
      smoothstep(-0.04, 0.08, input.uv.x) *
      (1.0 - smoothstep(1.0, 1.1 + safeSoftness * 0.35, input.uv.x));
    let innerCore = smoothstep(0.18 + safeSoftness, 0.02, side);
    let midBand = smoothstep(0.46 + safeSoftness, 0.18, side);
    let auraBand = smoothstep(0.88 + safeSoftness, 0.4, side);
    let leadingBloom = smoothstep(0.28, 0.0, length(vec2f(input.uv.x - 0.78, input.uv.y))) * 0.24;
    edgeAlpha = 1.0;
    bodyAlpha = clamp((innerCore * 1.0 + midBand * 0.56 + auraBand * 0.28 + leadingBloom) * envelope, 0.0, 1.0);
    emission = 1.02 + tipBias * (1.0 + input.glow * 1.38);
  } else {
    // Straight bars / flagship premium linear columns.
    let envelope =
      smoothstep(0.0, 0.025, input.uv.x) *
      (1.0 - smoothstep(1.0, 1.02 + safeSoftness * 0.12, input.uv.x));
    let sideAlpha = smoothstep(1.0 + safeSoftness * 0.55, 1.0 - safeSoftness * 0.55, side);
    edgeAlpha = 1.0;
    bodyAlpha = clamp(sideAlpha * envelope, 0.0, 1.0);
    emission = 0.92 + tipBias * 0.06;
  }

  let alpha = clamp(input.color.a * edgeAlpha * bodyAlpha, 0.0, 1.0);
  return vec4f(resolvedColor * emission, alpha);
}
`

const BACKDROP_SHADER_CODE = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@group(0) @binding(0) var backdropSampler: sampler;
@group(0) @binding(1) var backdropTexture: texture_2d<f32>;

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  return textureSample(backdropTexture, backdropSampler, input.uv);
}
`

const PARTICLE_SHADER_CODE = /* wgsl */ `
struct Uniforms {
  viewport: vec2f,
  particleTimeReactive: vec2f,
  particleCenter: vec2f,
  particleDriftSwirl: vec2f,
  particleParams: vec4f,
  particleBaseColor: vec4f,
  particleReactColor: vec4f,
}

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
  @location(1) color: vec4f,
  @location(2) style: f32,
  @location(3) softness: f32,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

@vertex
fn vs_main(
  @builtin(vertex_index) vertexIndex: u32,
  @location(0) spawn: vec2f,
  @location(1) dir: vec2f,
  @location(2) halfExtent: vec2f,
  @location(3) motion: vec4f,
  @location(4) style: f32,
  @location(5) softness: f32,
  @location(6) noiseSeed: f32,
) -> VertexOutput {
  var quad = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );

  let local = quad[vertexIndex];
  let baseDir = select(vec2f(1.0, 0.0), normalize(dir), length(dir) > 0.0001);
  let speed = max(0.0, motion.x);
  let spawnSec = motion.y;
  let lifetimeSec = max(0.08, motion.z);
  let baseOpacity = clamp(motion.w, 0.0, 1.0);
  let ageSec = max(0.0, uniforms.particleTimeReactive.x - spawnSec);
  let alive = select(0.0, 1.0, ageSec < lifetimeSec);
  let lifeProgress = clamp(ageSec / lifetimeSec, 0.0, 1.0);
  let fadeIn = clamp(lifeProgress / 0.14, 0.0, 1.0);
  let fadeOut = clamp((1.0 - lifeProgress) / 0.36, 0.0, 1.0);
  let fade = fadeIn * fadeOut * alive;
  let reactiveEnv = clamp(uniforms.particleTimeReactive.y, 0.0, 1.0);
  let triggerEnv = clamp(uniforms.particleParams.x, 0.0, 1.0);
  let liveDrive = clamp(max(reactiveEnv * 1.75, triggerEnv * 2.2), 0.0, 1.0);
  let reactStrength = clamp(uniforms.particleParams.w, 0.0, 1.0);
  let colorDrive = clamp(max(reactiveEnv * 1.3, triggerEnv * 1.85), 0.0, 1.0);
  let colorMix = clamp(pow(colorDrive, 0.72) * reactStrength, 0.0, 1.0);
  let particleRgb = mix(uniforms.particleBaseColor.rgb, uniforms.particleReactColor.rgb, colorMix);
  let audioTravelBoost = max(0.0, uniforms.particleBaseColor.a);
  let audioMotionMode = max(0.0, uniforms.particleReactColor.a);
  let travelEnabled = select(0.0, 1.0, audioMotionMode > 0.5);
  let sizePulseEnabled = select(0.0, 1.0, (audioMotionMode < 0.5) || (audioMotionMode > 1.5));
  let travelDrive = liveDrive * travelEnabled;
  let sizePulseDrive = liveDrive * sizePulseEnabled;
  let motionBoost =
    1.0 +
    travelDrive *
      (0.95 + clamp(uniforms.particleParams.y, 0.0, 1.0) * 2.75) *
      audioTravelBoost;
  let radial = spawn - uniforms.particleCenter;
  let distance = max(1.0, length(radial));
  let tangent = vec2f(-radial.y, radial.x) / distance;
  var styleTravelGain = 1.0;
  var styleDriftGain = 1.0;
  var styleSwirlGain = 1.0;
  var styleLiftGain = 1.0;
  var orbitGain = 0.0;
  if (style < 0.5) {
    styleTravelGain = 1.32;
    styleDriftGain = 0.62;
    styleSwirlGain = 0.55;
    styleLiftGain = 0.9;
  } else if (style < 1.5) {
    styleTravelGain = 0.94;
    styleDriftGain = 1.35;
    styleSwirlGain = 0.82;
    styleLiftGain = 1.55;
  } else if (style < 2.5) {
    styleTravelGain = 0.86;
    styleDriftGain = 0.7;
    styleSwirlGain = 1.95;
    styleLiftGain = 1.24;
    orbitGain = 1.0;
  } else if (style < 3.5) {
    styleTravelGain = 2.6;
    styleDriftGain = 0.16;
    styleSwirlGain = 0.24;
    styleLiftGain = 0.48;
  } else {
    styleTravelGain = 0.78;
    styleDriftGain = 0.9;
    styleSwirlGain = 1.28;
    styleLiftGain = 1.08;
    orbitGain = 0.66;
  }
  let driftPhaseA = ageSec * (1.8 + noiseSeed * 2.6) + noiseSeed * 6.28318530718;
  let driftPhaseB = ageSec * (1.45 + noiseSeed * 2.1) + noiseSeed * 3.14159265359;
  let driftOffset =
    vec2f(sin(driftPhaseA), cos(driftPhaseB)) * uniforms.particleDriftSwirl.x * styleDriftGain * ageSec * 0.38;
  let swirlOffset =
    tangent * uniforms.particleDriftSwirl.y * styleSwirlGain * ageSec * (0.22 + ageSec * 0.12);
  let orbitOffset =
    tangent *
    orbitGain *
    6.0 *
    sin(ageSec * (1.4 + noiseSeed * 1.8) + noiseSeed * 6.28318530718) *
    lifeProgress;
  let liftOffset = vec2f(0.0, 0.0);
  let travelDistance =
    speed *
    ageSec *
    motionBoost *
    styleTravelGain *
    (1.0 + lifeProgress * (1.05 + travelDrive * 1.45));
  let travel = baseDir * travelDistance;
  let center = spawn + travel + driftOffset + swirlOffset + orbitOffset + liftOffset;
  let driftVelocity = vec2f(
    cos(driftPhaseA) * (1.8 + noiseSeed * 2.6),
    -sin(driftPhaseB) * (1.45 + noiseSeed * 2.1),
  ) * uniforms.particleDriftSwirl.x * 0.16;
  let swirlVelocity =
    tangent * uniforms.particleDriftSwirl.y * styleSwirlGain * (0.28 + ageSec * 0.16);
  let liftVelocity = vec2f(0.0, 0.0);
  let velocityDir = baseDir * speed * motionBoost + driftVelocity + swirlVelocity + liftVelocity;
  let safeDir = select(
    vec2f(1.0, 0.0),
    normalize(velocityDir),
    length(velocityDir) > 0.0001,
  );
  let perp = vec2f(-safeDir.y, safeDir.x);
  var extent = halfExtent;
  if (style < 0.5) {
    let roundPulse = 1.0 + sizePulseDrive * 0.2 + sin(ageSec * (1.8 + noiseSeed * 1.1)) * 0.05;
    extent = halfExtent * roundPulse;
  } else if (style < 1.5) {
    let hazePulse = 1.0 + sizePulseDrive * 0.22 + sin(ageSec * (1.6 + noiseSeed * 1.2)) * 0.06;
    extent = halfExtent * hazePulse;
  } else if (style < 2.5) {
    let ringBreath = 1.0 + sizePulseDrive * 0.18 + sin(ageSec * (2.2 + noiseSeed * 1.6)) * 0.08;
    extent = halfExtent * ringBreath;
  } else if (style < 3.5) {
    let streakStretch = 1.6 + sizePulseDrive * 1.35 + (1.0 - lifeProgress) * 0.9;
    extent = vec2f(halfExtent.x * streakStretch, halfExtent.y * (0.5 + sizePulseDrive * 0.1));
  } else {
    let bubbleBreath = 1.0 + sizePulseDrive * 0.22 + sin(ageSec * (1.4 + noiseSeed * 1.4)) * 0.1;
    extent = halfExtent * bubbleBreath;
  }
  let world = center + safeDir * extent.x * local.x + perp * extent.y * local.y;
  let clip = vec2f(
    (world.x / uniforms.viewport.x) * 2.0 - 1.0,
    1.0 - (world.y / uniforms.viewport.y) * 2.0,
  );

  var output: VertexOutput;
  output.position = vec4f(clip, 0.0, 1.0);
  output.uv = local;
  output.color = vec4f(
    particleRgb,
    clamp(
      baseOpacity * fade * clamp(uniforms.particleParams.z, 0.0, 1.0) * (0.72 + liveDrive * 0.52),
      0.0,
      1.0,
    ),
  );
  output.style = style;
  output.softness = softness;
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let uv = input.uv;
  let radius = length(uv);
  let safeSoftness = clamp(input.softness, 0.02, 1.0);
  var alphaShape = 0.0;
  var emission = 1.0;

  if (input.style < 0.5) {
    alphaShape = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, radius);
  } else if (input.style < 1.5) {
    alphaShape = smoothstep(1.0 + safeSoftness * 1.1, 1.0 - safeSoftness * 0.92, radius);
    emission = 1.48;
  } else if (input.style < 2.5) {
    let outer = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, radius);
    let inner = smoothstep(0.58 + safeSoftness * 0.5, 0.58 - safeSoftness * 0.5, radius);
    alphaShape = clamp(outer - inner, 0.0, 1.0);
    emission = 1.15;
  } else if (input.style < 3.5) {
    let longitudinal = smoothstep(1.0 + safeSoftness, 1.0 - safeSoftness, abs(uv.x));
    let transverse = smoothstep(0.45 + safeSoftness, 0.08, abs(uv.y));
    alphaShape = longitudinal * transverse;
    emission = 1.55;
  } else {
    let body = pow(max(0.0, 1.0 - radius), 1.8);
    let highlight = smoothstep(0.45, 0.0, length(uv - vec2f(-0.28, -0.28))) * 0.35;
    alphaShape = clamp(body + highlight, 0.0, 1.0);
    emission = 1.08;
  }

  let alpha = clamp(input.color.a * alphaShape, 0.0, 1.0);
  return vec4f(input.color.rgb * emission, alpha);
}
`

const ATMOSPHERE_SHADER_CODE = /* wgsl */ `
struct AtmosphereUniforms {
  viewportTime: vec4f,
  smokeParamsA: vec4f,
  smokeParamsB: vec4f,
  smokeColor: vec4f,
  vignetteParamsA: vec4f,
  vignetteColor: vec4f,
}

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@group(0) @binding(0) var<uniform> atmosphere: AtmosphereUniforms;

fn hash21(p: vec2f) -> f32 {
  return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453123);
}

fn noise2(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let a = hash21(i);
  let b = hash21(i + vec2f(1.0, 0.0));
  let c = hash21(i + vec2f(0.0, 1.0));
  let d = hash21(i + vec2f(1.0, 1.0));
  let u = f * f * (3.0 - 2.0 * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f) -> f32 {
  var value = 0.0;
  var amplitude = 0.5;
  var frequency = 1.0;
  for (var octave = 0; octave < 4; octave = octave + 1) {
    value += noise2(p * frequency) * amplitude;
    frequency *= 2.03;
    amplitude *= 0.5;
  }
  return value;
}

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

fn composite(base: vec4f, top: vec4f) -> vec4f {
  let alpha = top.a + base.a * (1.0 - top.a);
  let rgb = top.rgb * top.a + base.rgb * (1.0 - top.a);
  return vec4f(rgb, alpha);
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let viewport = max(atmosphere.viewportTime.xy, vec2f(1.0, 1.0));
  let timeSec = atmosphere.viewportTime.z;
  let aspect = viewport.x / viewport.y;
  let uv = input.uv;
  let aspectUv = vec2f((uv.x - 0.5) * aspect + 0.5, uv.y);
  var result = vec4f(0.0);

  if (atmosphere.smokeParamsA.x > 0.5) {
    let smokeOpacity = clamp(atmosphere.smokeParamsA.y, 0.0, 1.0);
    let smokeStrength = clamp(atmosphere.smokeParamsA.z, 0.0, 1.0);
    let smokeBlur = clamp(atmosphere.smokeParamsA.w, 0.0, 1.0);
    let smokeSpeed = max(0.2, atmosphere.smokeParamsB.x);
    let smokeNoise = clamp(atmosphere.smokeParamsB.y, 0.0, 1.0);
    let smokeColor = atmosphere.smokeColor.rgb;
    let driftA = vec2f(sin(timeSec * smokeSpeed * 0.35) * 0.04, -cos(timeSec * smokeSpeed * 0.28) * 0.03);
    let driftB = vec2f(-sin(timeSec * smokeSpeed * 0.35) * 0.05, cos(timeSec * smokeSpeed * 0.28) * 0.04);
    let centerA = vec2f((0.18 + driftA.x - 0.5) * aspect + 0.5, 0.82 + driftA.y);
    let centerB = vec2f((0.82 + driftB.x - 0.5) * aspect + 0.5, 0.18 + driftB.y);
    let noiseFieldA = fbm(aspectUv * (2.4 + smokeNoise * 3.2) + vec2f(timeSec * smokeSpeed * 0.05, -timeSec * smokeSpeed * 0.035));
    let noiseFieldB = fbm(aspectUv * (2.0 + smokeNoise * 2.7) + vec2f(-timeSec * smokeSpeed * 0.04, timeSec * smokeSpeed * 0.03));
    let distA = distance(aspectUv, centerA);
    let distB = distance(aspectUv, centerB);
    let radiusA = 0.28 * (1.0 + smokeNoise * (noiseFieldA - 0.5) * 0.42);
    let radiusB = 0.32 * (1.0 + smokeNoise * (noiseFieldB - 0.5) * 0.38);
    let softnessA = mix(0.12, 0.42, smokeBlur);
    let softnessB = mix(0.14, 0.46, smokeBlur);
    let cloudA =
      (1.0 - smoothstep(radiusA * 0.16, radiusA * (1.0 + softnessA), distA)) *
      mix(0.62, 1.08, noiseFieldA);
    let cloudB =
      (1.0 - smoothstep(radiusB * 0.14, radiusB * (1.0 + softnessB), distB)) *
      mix(0.58, 1.0, noiseFieldB);
    let smokeAlpha = clamp((cloudA * 0.38 + cloudB * 0.28) * smokeOpacity * (0.35 + smokeStrength * 0.55), 0.0, 0.8);
    result = composite(result, vec4f(smokeColor, smokeAlpha));
  }

  if (atmosphere.vignetteParamsA.x > 0.5) {
    let strength = clamp(atmosphere.vignetteParamsA.y, 0.0, 1.0);
    let feather = clamp(atmosphere.vignetteParamsA.z, 0.05, 1.0);
    let opacity = clamp(atmosphere.vignetteParamsA.w, 0.0, 1.0);
    let vignetteColor = atmosphere.vignetteColor.rgb;
    let centered = vec2f((uv.x - 0.5) * aspect, uv.y - 0.5);
    let radial = length(centered) * 2.0;
    let innerRadius = clamp(0.52 + (1.0 - strength) * 0.18, 0.2, 0.92);
    let outerRadius = clamp(innerRadius + feather * 0.42, 0.35, 1.0);
    let edge = smoothstep(innerRadius, outerRadius, radial);
    let ramp = clamp((radial - innerRadius) / max(0.0001, outerRadius - innerRadius), 0.0, 1.0);
    let vignetteAlpha = clamp(edge * mix(opacity * 0.45, opacity, ramp), 0.0, 1.0);
    result = composite(result, vec4f(vignetteColor, vignetteAlpha));
  }

  return result;
}
`

const POSTFX_BRIGHT_SHADER_CODE = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

struct PostFxUniforms {
  params0: vec4f,
  params1: vec4f,
}

@group(0) @binding(0) var postSampler: sampler;
@group(0) @binding(1) var sourceTexture: texture_2d<f32>;
@group(0) @binding(2) var<uniform> postFx: PostFxUniforms;

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

fn luminance(color: vec3f) -> f32 {
  return dot(color, vec3f(0.2126, 0.7152, 0.0722));
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let threshold = postFx.params0.x;
  let knee = max(0.0001, postFx.params0.y);
  let intensity = postFx.params0.z;
  let color = textureSample(sourceTexture, postSampler, input.uv).rgb;
  let luma = luminance(color);
  let soft = clamp((luma - threshold + knee) / (2.0 * knee), 0.0, 1.0);
  let highlight = max(luma - threshold, 0.0);
  let gain = max(highlight, soft * soft * knee) / max(luma, 0.0001);
  return vec4f(color * gain * intensity, clamp(gain, 0.0, 1.0));
}
`

const POSTFX_BLUR_SHADER_CODE = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

struct PostFxUniforms {
  params0: vec4f,
  params1: vec4f,
}

@group(0) @binding(0) var postSampler: sampler;
@group(0) @binding(1) var sourceTexture: texture_2d<f32>;
@group(0) @binding(2) var<uniform> postFx: PostFxUniforms;

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let texel = postFx.params0.xy;
  let direction = postFx.params0.zw;
  let radius = max(0.25, postFx.params1.x);
  let step = texel * direction * radius;
  let weights = array<f32, 5>(0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
  var sum = textureSample(sourceTexture, postSampler, input.uv) * weights[0];
  for (var index = 1; index < 5; index = index + 1) {
    let offset = f32(index);
    sum += textureSample(sourceTexture, postSampler, input.uv + step * offset) * weights[index];
    sum += textureSample(sourceTexture, postSampler, input.uv - step * offset) * weights[index];
  }
  return vec4f(sum.rgb, 1.0);
}
`

const POSTFX_COMPOSITE_SHADER_CODE = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

struct PostFxUniforms {
  params0: vec4f,
  params1: vec4f,
  params2: vec4f,
  params3: vec4f,
}

@group(0) @binding(0) var postSampler: sampler;
@group(0) @binding(1) var sceneTexture: texture_2d<f32>;
@group(0) @binding(2) var bloomTexture: texture_2d<f32>;
@group(0) @binding(3) var historyTexture: texture_2d<f32>;
@group(0) @binding(4) var<uniform> postFx: PostFxUniforms;

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let bloomStrength = postFx.params0.x;
  let reactiveEnergy = clamp(postFx.params1.x, 0.0, 1.0);
  let kickEnergy = clamp(postFx.params1.y, 0.0, 1.0);
  let styleMotionDrive = clamp(postFx.params1.z, 0.0, 1.0);
  let motionBlurStrength = clamp(postFx.params2.x, 0.0, 1.0);
  let historyMixBase = clamp(postFx.params2.y, 0.0, 1.0);
  let historyValid = clamp(postFx.params2.z, 0.0, 1.0);
  let scene = textureSample(sceneTexture, postSampler, input.uv);
  let bloom = textureSample(bloomTexture, postSampler, input.uv);
  let history = textureSample(historyTexture, postSampler, input.uv);
  let bloomGain = 1.0 + reactiveEnergy * 0.18 + kickEnergy * 0.24 + styleMotionDrive * 0.08;
  let bloomMix =
    bloom.rgb *
    bloomStrength *
    bloomGain *
    (1.0 - clamp(scene.rgb * 0.72, vec3f(0.0), vec3f(1.0)));
  let currentRgb = scene.rgb + bloomMix;
  let historyMix =
    motionBlurStrength *
    historyMixBase *
    historyValid *
    clamp(0.4 + reactiveEnergy * 0.28 + styleMotionDrive * 0.12, 0.0, 1.0);
  let rgb = mix(currentRgb, history.rgb, historyMix);
  return vec4f(rgb, clamp(scene.a, 0.0, 1.0));
}
`

const FALLBACK_SCENE_SHADER_CODE = /* wgsl */ `
struct Uniforms {
  viewport: vec2f,
  _padding: vec2f,
}

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

@vertex
fn vs_main(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
  var positions = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f(1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, -1.0),
    vec2f(1.0, 1.0),
    vec2f(-1.0, 1.0),
  );
  var uvs = array<vec2f, 6>(
    vec2f(0.0, 1.0),
    vec2f(1.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 1.0),
    vec2f(1.0, 0.0),
    vec2f(0.0, 0.0),
  );

  var output: VertexOutput;
  output.position = vec4f(positions[vertexIndex], 0.0, 1.0);
  output.uv = uvs[vertexIndex];
  return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4f {
  let aspect = uniforms.viewport.x / max(uniforms.viewport.y, 1.0);
  let uv = input.uv;
  let top = vec3f(0.07, 0.11, 0.21);
  let bottom = vec3f(0.01, 0.03, 0.08);
  let base = mix(top, bottom, uv.y);
  let centerUv = vec2f((uv.x - 0.5) * aspect, uv.y - 0.35);
  let glow = exp(-dot(centerUv, centerUv) * 7.5);
  let edgeUv = vec2f((uv.x - 0.5) * aspect, uv.y - 0.15);
  let halo = smoothstep(0.85, 0.1, length(edgeUv)) * 0.16;
  let accent = vec3f(0.85, 0.26, 0.94) * glow * 0.42 + vec3f(0.17, 0.86, 1.0) * halo;
  return vec4f(base + accent, 1.0);
}
`

export class WebGpuSpectrumRenderer {
  private canvas: HTMLCanvasElement | null = null
  private device: any = null
  private context: any = null
  private spectrumOpaquePipeline: any = null
  private spectrumAdditivePipeline: any = null
  private spectrumScreenPipeline: any = null
  private spectrumAlphaPipeline: any = null
  private particlePipeline: any = null
  private backdropPipeline: any = null
  private atmospherePipeline: any = null
  private uniformBuffer: any = null
  private atmosphereUniformBuffer: any = null
  private audioSignalBuffer: any = null
  private instanceBuffer: any = null
  private particleBuffer: any = null
  private spectrumBindGroup: any = null
  private spectrumGradientBindGroup: any = null
  private atmosphereBindGroup: any = null
  private spectrumGradientSampler: any = null
  private spectrumGradientTexture: any = null
  private spectrumGradientLayout: any = null
  private backdropSampler: any = null
  private backdropTexture: any = null
  private backdropBindGroup: any = null
  private overlayTexture: any = null
  private overlayBindGroup: any = null
  private postFxSampler: any = null
  private postFxUniformBuffer: any = null
  private postFxBrightPipeline: any = null
  private postFxBlurPipeline: any = null
  private postFxCompositePipeline: any = null
  private fallbackScenePipeline: any = null
  private postFxTextureLayout: any = null
  private postFxCompositeLayout: any = null
  private postFxBrightBindGroup: any = null
  private postFxBlurBindGroupA: any = null
  private postFxBlurBindGroupB: any = null
  private postFxCompositeBindGroupA: any = null
  private postFxCompositeBindGroupB: any = null
  private postFxHistoryBindGroupA: any = null
  private postFxHistoryBindGroupB: any = null
  private sceneTexture: any = null
  private bloomTextureA: any = null
  private bloomTextureB: any = null
  private historyTextureA: any = null
  private historyTextureB: any = null
  private postFxWidth = 0
  private postFxHeight = 0
  private bloomWidth = 0
  private bloomHeight = 0
  private activeHistoryIndex = 0
  private historyValid = false
  private textureFormat: string | null = null
  private readbackSlots: WebGpuReadbackSlot[] = [
    { buffer: null, busy: false },
    { buffer: null, busy: false },
  ]
  private readbackBytesPerRow = 0
  private readbackBufferSize = 0
  private readbackEnabled = false
  private latestReadbackFrame: Uint8Array | null = null
  private pendingReadbackPromise: Promise<Uint8Array> | null = null
  private instanceCapacity = 0
  private particleCapacity = 0
  private pixelWidth = 0
  private pixelHeight = 0
  private backdropWidth = 0
  private backdropHeight = 0
  private overlayWidth = 0
  private overlayHeight = 0
  private spectrumGradientWidth = 0
  private spectrumGradientHeight = 0
  private onDeviceLost: ((message: string) => void) | null = null
  private uniformScratch = new Float32Array(UNIFORM_STRIDE_FLOATS)
  private postFxScratch = new Float32Array(16)
  private atmosphereScratch = new Float32Array(ATMOSPHERE_UNIFORM_STRIDE_FLOATS)
  private audioSignalScratch = new Float32Array(AUDIO_SIGNAL_BUFFER_FLOATS)
  private instanceScratch: Float32Array | null = null
  private particleScratch: Float32Array | null = null

  async initialize(
    canvas: HTMLCanvasElement,
    options?: WebGpuInitializeOptions,
  ): Promise<WebGpuInitializeResult> {
    if (typeof navigator === 'undefined' || !('gpu' in navigator)) {
      throw new Error('WebGPU is not available in this renderer process.')
    }

    const gpu = (navigator as Navigator & { gpu?: GpuNavigator }).gpu
    if (!gpu) {
      throw new Error('WebGPU is not available in this renderer process.')
    }
    const adapter = await gpu.requestAdapter()
    if (!adapter) {
      throw new Error('No compatible WebGPU adapter was found.')
    }

    const device = await adapter.requestDevice()
    this.onDeviceLost = options?.onDeviceLost ?? null
    const deviceLost = device?.lost
    if (deviceLost && typeof deviceLost.then === 'function') {
      void deviceLost.then((info: { message?: string } | undefined) => {
        if (this.device !== device) {
          return
        }
        this.onDeviceLost?.(info?.message || 'The WebGPU device was lost.')
      })
    }
    const context = canvas.getContext('webgpu')
    if (!context) {
      throw new Error('Unable to create a WebGPU canvas context.')
    }

    const textureFormat = gpu.getPreferredCanvasFormat()
    const shaderModule = device.createShaderModule({ code: SHADER_CODE })
    const particleShaderModule = device.createShaderModule({ code: PARTICLE_SHADER_CODE })
    const backdropShaderModule = device.createShaderModule({ code: BACKDROP_SHADER_CODE })
    const atmosphereShaderModule = device.createShaderModule({ code: ATMOSPHERE_SHADER_CODE })
    const postFxBrightShaderModule = device.createShaderModule({ code: POSTFX_BRIGHT_SHADER_CODE })
    const postFxBlurShaderModule = device.createShaderModule({ code: POSTFX_BLUR_SHADER_CODE })
    const postFxCompositeShaderModule = device.createShaderModule({ code: POSTFX_COMPOSITE_SHADER_CODE })
    const fallbackSceneShaderModule = device.createShaderModule({ code: FALLBACK_SCENE_SHADER_CODE })
    const uniformBuffer = device.createBuffer({
      size: UNIFORM_STRIDE_BYTES,
      usage: GPU_BUFFER_USAGE_UNIFORM | GPU_BUFFER_USAGE_COPY_DST,
    })
    const atmosphereUniformBuffer = device.createBuffer({
      size: ATMOSPHERE_UNIFORM_STRIDE_BYTES,
      usage: GPU_BUFFER_USAGE_UNIFORM | GPU_BUFFER_USAGE_COPY_DST,
    })
    const audioSignalBuffer = device.createBuffer({
      size: AUDIO_SIGNAL_BUFFER_BYTES,
      usage: GPU_BUFFER_USAGE_STORAGE | GPU_BUFFER_USAGE_COPY_DST,
    })
    const postFxUniformBuffer = device.createBuffer({
      size: 64,
      usage: GPU_BUFFER_USAGE_UNIFORM | GPU_BUFFER_USAGE_COPY_DST,
    })
    const bindGroupLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_VERTEX | GPU_SHADER_STAGE_FRAGMENT,
          buffer: { type: 'uniform' },
        },
      ],
    })
    const spectrumGradientLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          sampler: { type: 'filtering' },
        },
        {
          binding: 1,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
      ],
    })
    const pipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [bindGroupLayout],
    })
    const spectrumPipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [bindGroupLayout, spectrumGradientLayout],
    })
    const atmosphereBindGroupLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          buffer: { type: 'uniform' },
        },
      ],
    })
    const atmospherePipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [atmosphereBindGroupLayout],
    })
    const backdropBindGroupLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          sampler: { type: 'filtering' },
        },
        {
          binding: 1,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
      ],
    })
    const backdropPipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [backdropBindGroupLayout],
    })
    const postFxTextureLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          sampler: { type: 'filtering' },
        },
        {
          binding: 1,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
        {
          binding: 2,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          buffer: { type: 'uniform' },
        },
      ],
    })
    const postFxCompositeLayout = device.createBindGroupLayout({
      entries: [
        {
          binding: 0,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          sampler: { type: 'filtering' },
        },
        {
          binding: 1,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
        {
          binding: 2,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
        {
          binding: 3,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          texture: { sampleType: 'float' },
        },
        {
          binding: 4,
          visibility: GPU_SHADER_STAGE_FRAGMENT,
          buffer: { type: 'uniform' },
        },
      ],
    })
    const postFxTexturePipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [postFxTextureLayout],
    })
    const postFxCompositePipelineLayout = device.createPipelineLayout({
      bindGroupLayouts: [postFxCompositeLayout],
    })

    const spectrumOpaquePipeline = device.createRenderPipeline({
      layout: spectrumPipelineLayout,
      vertex: {
        module: shaderModule,
        entryPoint: 'vs_main',
        buffers: [
          {
            arrayStride: INSTANCE_STRIDE_BYTES,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x2' },
              { shaderLocation: 2, offset: 16, format: 'float32' },
              { shaderLocation: 3, offset: 20, format: 'float32' },
              { shaderLocation: 4, offset: 24, format: 'float32x4' },
              { shaderLocation: 5, offset: 40, format: 'float32' },
              { shaderLocation: 6, offset: 44, format: 'float32' },
              { shaderLocation: 7, offset: 48, format: 'float32' },
              { shaderLocation: 8, offset: 52, format: 'float32x2' },
            ],
          },
        ],
      },
      fragment: {
        module: shaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const spectrumAdditivePipeline = device.createRenderPipeline({
      layout: spectrumPipelineLayout,
      vertex: {
        module: shaderModule,
        entryPoint: 'vs_main',
        buffers: [
          {
            arrayStride: INSTANCE_STRIDE_BYTES,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x2' },
              { shaderLocation: 2, offset: 16, format: 'float32' },
              { shaderLocation: 3, offset: 20, format: 'float32' },
              { shaderLocation: 4, offset: 24, format: 'float32x4' },
              { shaderLocation: 5, offset: 40, format: 'float32' },
              { shaderLocation: 6, offset: 44, format: 'float32' },
              { shaderLocation: 7, offset: 48, format: 'float32' },
              { shaderLocation: 8, offset: 52, format: 'float32x2' },
            ],
          },
        ],
      },
      fragment: {
        module: shaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const spectrumScreenPipeline = device.createRenderPipeline({
      layout: spectrumPipelineLayout,
      vertex: {
        module: shaderModule,
        entryPoint: 'vs_main',
        buffers: [
          {
            arrayStride: INSTANCE_STRIDE_BYTES,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x2' },
              { shaderLocation: 2, offset: 16, format: 'float32' },
              { shaderLocation: 3, offset: 20, format: 'float32' },
              { shaderLocation: 4, offset: 24, format: 'float32x4' },
              { shaderLocation: 5, offset: 40, format: 'float32' },
              { shaderLocation: 6, offset: 44, format: 'float32' },
              { shaderLocation: 7, offset: 48, format: 'float32' },
              { shaderLocation: 8, offset: 52, format: 'float32x2' },
            ],
          },
        ],
      },
      fragment: {
        module: shaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'one-minus-dst',
                dstFactor: 'one',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const spectrumAlphaPipeline = device.createRenderPipeline({
      layout: spectrumPipelineLayout,
      vertex: {
        module: shaderModule,
        entryPoint: 'vs_main',
        buffers: [
          {
            arrayStride: INSTANCE_STRIDE_BYTES,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x2' },
              { shaderLocation: 2, offset: 16, format: 'float32' },
              { shaderLocation: 3, offset: 20, format: 'float32' },
              { shaderLocation: 4, offset: 24, format: 'float32x4' },
              { shaderLocation: 5, offset: 40, format: 'float32' },
              { shaderLocation: 6, offset: 44, format: 'float32' },
              { shaderLocation: 7, offset: 48, format: 'float32' },
              { shaderLocation: 8, offset: 52, format: 'float32x2' },
            ],
          },
        ],
      },
      fragment: {
        module: shaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const particlePipeline = device.createRenderPipeline({
      layout: pipelineLayout,
      vertex: {
        module: particleShaderModule,
        entryPoint: 'vs_main',
        buffers: [
          {
            arrayStride: PARTICLE_INSTANCE_STRIDE_BYTES,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x2' },
              { shaderLocation: 2, offset: 16, format: 'float32x2' },
              { shaderLocation: 3, offset: 24, format: 'float32x4' },
              { shaderLocation: 4, offset: 40, format: 'float32' },
              { shaderLocation: 5, offset: 44, format: 'float32' },
              { shaderLocation: 6, offset: 48, format: 'float32' },
            ],
          },
        ],
      },
      fragment: {
        module: particleShaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const backdropPipeline = device.createRenderPipeline({
      layout: backdropPipelineLayout,
      vertex: {
        module: backdropShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: backdropShaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const atmospherePipeline = device.createRenderPipeline({
      layout: atmospherePipelineLayout,
      vertex: {
        module: atmosphereShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: atmosphereShaderModule,
        entryPoint: 'fs_main',
        targets: [
          {
            format: textureFormat,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
            writeMask: GPU_COLOR_WRITE_ALL,
          },
        ],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const postFxBrightPipeline = device.createRenderPipeline({
      layout: postFxTexturePipelineLayout,
      vertex: {
        module: postFxBrightShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: postFxBrightShaderModule,
        entryPoint: 'fs_main',
        targets: [{ format: textureFormat }],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const postFxBlurPipeline = device.createRenderPipeline({
      layout: postFxTexturePipelineLayout,
      vertex: {
        module: postFxBlurShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: postFxBlurShaderModule,
        entryPoint: 'fs_main',
        targets: [{ format: textureFormat }],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const postFxCompositePipeline = device.createRenderPipeline({
      layout: postFxCompositePipelineLayout,
      vertex: {
        module: postFxCompositeShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: postFxCompositeShaderModule,
        entryPoint: 'fs_main',
        targets: [{ format: textureFormat }],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })
    const fallbackScenePipeline = device.createRenderPipeline({
      layout: pipelineLayout,
      vertex: {
        module: fallbackSceneShaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: fallbackSceneShaderModule,
        entryPoint: 'fs_main',
        targets: [{ format: textureFormat }],
      },
      primitive: {
        topology: 'triangle-list',
      },
    })

    const spectrumBindGroup = device.createBindGroup({
      layout: bindGroupLayout,
      entries: [
        {
          binding: 0,
          resource: { buffer: uniformBuffer },
        },
      ],
    })
    const spectrumGradientSampler = device.createSampler({
      magFilter: 'linear',
      minFilter: 'linear',
    })
    const spectrumGradientTexture = device.createTexture({
      size: [1, 1, 1],
      format: 'rgba8unorm',
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_COPY_DST,
    })
    device.queue.writeTexture(
      { texture: spectrumGradientTexture },
      DEFAULT_GRADIENT_ATLAS_RGBA,
      {
        bytesPerRow: 4,
      },
      [1, 1, 1],
    )
    const spectrumGradientBindGroup = device.createBindGroup({
      layout: spectrumGradientLayout,
      entries: [
        { binding: 0, resource: spectrumGradientSampler },
        { binding: 1, resource: spectrumGradientTexture.createView() },
      ],
    })
    const backdropSampler = device.createSampler({
      magFilter: 'linear',
      minFilter: 'linear',
    })
    const postFxSampler = device.createSampler({
      magFilter: 'linear',
      minFilter: 'linear',
    })
    const atmosphereBindGroup = device.createBindGroup({
      layout: atmosphereBindGroupLayout,
      entries: [
        {
          binding: 0,
          resource: { buffer: atmosphereUniformBuffer },
        },
      ],
    })

    this.canvas = canvas
    this.device = device
    this.context = context
    this.spectrumOpaquePipeline = spectrumOpaquePipeline
    this.spectrumAdditivePipeline = spectrumAdditivePipeline
    this.spectrumScreenPipeline = spectrumScreenPipeline
    this.spectrumAlphaPipeline = spectrumAlphaPipeline
    this.particlePipeline = particlePipeline
    this.backdropPipeline = backdropPipeline
    this.atmospherePipeline = atmospherePipeline
    this.uniformBuffer = uniformBuffer
    this.atmosphereUniformBuffer = atmosphereUniformBuffer
    this.audioSignalBuffer = audioSignalBuffer
    this.spectrumGradientSampler = spectrumGradientSampler
    this.spectrumGradientTexture = spectrumGradientTexture
    this.spectrumGradientLayout = spectrumGradientLayout
    this.postFxSampler = postFxSampler
    this.postFxUniformBuffer = postFxUniformBuffer
    this.postFxBrightPipeline = postFxBrightPipeline
    this.postFxBlurPipeline = postFxBlurPipeline
    this.postFxCompositePipeline = postFxCompositePipeline
    this.fallbackScenePipeline = fallbackScenePipeline
    this.postFxTextureLayout = postFxTextureLayout
    this.postFxCompositeLayout = postFxCompositeLayout
    this.spectrumBindGroup = spectrumBindGroup
    this.spectrumGradientBindGroup = spectrumGradientBindGroup
    this.atmosphereBindGroup = atmosphereBindGroup
    this.backdropSampler = backdropSampler
    this.textureFormat = textureFormat
    this.instanceCapacity = 0
    this.particleCapacity = 0
    this.instanceBuffer = null
    this.particleBuffer = null
    this.spectrumGradientWidth = 1
    this.spectrumGradientHeight = 1
    this.ensureInstanceCapacity(INITIAL_INSTANCE_CAPACITY)
    this.ensureParticleCapacity(INITIAL_INSTANCE_CAPACITY)

    const capabilityProfile = buildPreviewGpuCapabilityProfile({
      rendererCapability: 'webgpu',
      preferredCanvasFormat: textureFormat,
      adapter,
      device,
    })
    const qualityPolicy = resolvePreviewQualityPolicy(capabilityProfile)

    return {
      capabilityProfile,
      qualityPolicy,
    }
  }

  resize(width: number, height: number, dpr: number): void {
    if (!this.canvas || !this.context || !this.device || !this.textureFormat) {
      return
    }

    const pixelWidth = Math.max(1, Math.round(width * dpr))
    const pixelHeight = Math.max(1, Math.round(height * dpr))
    if (pixelWidth === this.pixelWidth && pixelHeight === this.pixelHeight) {
      return
    }

    this.pixelWidth = pixelWidth
    this.pixelHeight = pixelHeight
    this.canvas.width = pixelWidth
    this.canvas.height = pixelHeight
    this.context.configure({
      device: this.device,
      format: this.textureFormat,
      alphaMode: 'premultiplied',
      usage: GPU_TEXTURE_USAGE_RENDER_ATTACHMENT | GPU_TEXTURE_USAGE_COPY_SRC,
    })
  }

  setReadbackEnabled(enabled: boolean): void {
    this.readbackEnabled = enabled
    if (!enabled) {
      this.latestReadbackFrame = null
    }
  }

  async readbackLatestFrame(): Promise<Uint8Array | null> {
    if (!this.latestReadbackFrame) {
      if (this.pendingReadbackPromise) {
        return this.pendingReadbackPromise.then((frame) => frame.slice())
      }
      return null
    }
    return this.latestReadbackFrame.slice()
  }

  render(frame: WebGpuSpectrumFrame): boolean {
    if (
      !this.device ||
      !this.context ||
      !this.spectrumOpaquePipeline ||
      !this.spectrumAdditivePipeline ||
      !this.spectrumScreenPipeline ||
      !this.spectrumAlphaPipeline ||
      !this.spectrumBindGroup ||
      !this.spectrumGradientBindGroup ||
      !this.uniformBuffer
    ) {
      return false
    }

    this.resize(frame.width, frame.height, frame.dpr)

    this.uniformScratch.fill(0)
    this.uniformScratch[0] = frame.width
    this.uniformScratch[1] = frame.height
    const particleSimulation = frame.particleSimulation ?? null
    if (particleSimulation) {
      this.uniformScratch[2] = particleSimulation.timeSec
      this.uniformScratch[3] = particleSimulation.reactiveEnv
      this.uniformScratch[4] = particleSimulation.centerX
      this.uniformScratch[5] = particleSimulation.centerY
      this.uniformScratch[6] = particleSimulation.driftStrength
      this.uniformScratch[7] = particleSimulation.swirlStrength
      this.uniformScratch[8] = particleSimulation.triggerEnv
      this.uniformScratch[9] = particleSimulation.reactivity
      this.uniformScratch[10] = particleSimulation.opacity
      this.uniformScratch[11] = particleSimulation.reactStrength
      this.uniformScratch[12] = particleSimulation.baseRed
      this.uniformScratch[13] = particleSimulation.baseGreen
      this.uniformScratch[14] = particleSimulation.baseBlue
      this.uniformScratch[15] = particleSimulation.audioTravelBoost
      this.uniformScratch[16] = particleSimulation.reactRed
      this.uniformScratch[17] = particleSimulation.reactGreen
      this.uniformScratch[18] = particleSimulation.reactBlue
      this.uniformScratch[19] = particleSimulation.audioMotionMode
    }
    if (particleSimulation) {
      const debugSecond = Math.floor(Math.max(0, particleSimulation.timeSec ?? 0))
      if (debugSecond !== lastParticleUniformDebugSecond) {
        // #region debug-point C:particle-uniform-pack
        sendParticleReactColorDebug({
          hypothesisId: 'C',
          location: 'webgpuSpectrumRenderer',
          msg: '[DEBUG] particle uniform packing snapshot',
          data: {
            uniformStrideFloats: UNIFORM_STRIDE_FLOATS,
            timeSec: Number((particleSimulation.timeSec ?? 0).toFixed(3)),
            reactiveEnv: Number((particleSimulation.reactiveEnv ?? 0).toFixed(4)),
            triggerEnv: Number((particleSimulation.triggerEnv ?? 0).toFixed(4)),
            reactivity: Number((particleSimulation.reactivity ?? 0).toFixed(4)),
            audioTravelBoost: Number((particleSimulation.audioTravelBoost ?? 0).toFixed(4)),
            audioMotionMode: Number((particleSimulation.audioMotionMode ?? 0).toFixed(4)),
            opacity: Number((particleSimulation.opacity ?? 0).toFixed(4)),
            reactStrength: Number((particleSimulation.reactStrength ?? 0).toFixed(4)),
            baseRgb: [
              Number((particleSimulation.baseRed ?? 0).toFixed(4)),
              Number((particleSimulation.baseGreen ?? 0).toFixed(4)),
              Number((particleSimulation.baseBlue ?? 0).toFixed(4)),
            ],
            reactRgb: [
              Number((particleSimulation.reactRed ?? 0).toFixed(4)),
              Number((particleSimulation.reactGreen ?? 0).toFixed(4)),
              Number((particleSimulation.reactBlue ?? 0).toFixed(4)),
            ],
            uniformScratchSlice: Array.from(this.uniformScratch.slice(0, 20)).map((value) =>
              Number(value.toFixed(4)),
            ),
          },
        })
        // #endregion
        // #region debug-point PM-B:particle-missing-uniform-pack
        sendParticleMissingDebug({
          hypothesisId: 'B',
          location: 'webgpuSpectrumRenderer',
          msg: '[DEBUG] particle missing uniform snapshot',
          data: {
            timeSec: Number((particleSimulation.timeSec ?? 0).toFixed(3)),
            reactiveEnv: Number((particleSimulation.reactiveEnv ?? 0).toFixed(4)),
            triggerEnv: Number((particleSimulation.triggerEnv ?? 0).toFixed(4)),
            driftStrength: Number((particleSimulation.driftStrength ?? 0).toFixed(4)),
            swirlStrength: Number((particleSimulation.swirlStrength ?? 0).toFixed(4)),
            reactivity: Number((particleSimulation.reactivity ?? 0).toFixed(4)),
            opacity: Number((particleSimulation.opacity ?? 0).toFixed(4)),
            audioTravelBoost: Number((particleSimulation.audioTravelBoost ?? 0).toFixed(4)),
            audioMotionMode: Number((particleSimulation.audioMotionMode ?? 0).toFixed(4)),
            uniformScratchSlice: Array.from(this.uniformScratch.slice(0, 20)).map((value) =>
              Number(value.toFixed(4)),
            ),
          },
        })
        // #endregion
        lastParticleUniformDebugSecond = debugSecond
      }
    }
    this.device.queue.writeBuffer(this.uniformBuffer, 0, this.uniformScratch)

    let opaqueInstanceCount = 0
    let alphaInstanceCount = 0
    let screenInstanceCount = 0
    let additiveInstanceCount = 0
    frame.instances.forEach((instance) => {
      const blendMode = instance.blendMode
      if (blendMode === 'opaque') {
        opaqueInstanceCount += 1
        return
      }
      if (blendMode === 'screen') {
        screenInstanceCount += 1
        return
      }
      if (blendMode === 'add') {
        additiveInstanceCount += 1
        return
      }
      alphaInstanceCount += 1
    })
    const instanceCount = opaqueInstanceCount + alphaInstanceCount + screenInstanceCount + additiveInstanceCount
    const particleCount = frame.particles?.length ?? 0
    this.ensureInstanceCapacity(Math.max(INITIAL_INSTANCE_CAPACITY, instanceCount))
    this.ensureParticleCapacity(Math.max(INITIAL_INSTANCE_CAPACITY, particleCount))

    if (!this.instanceBuffer || !this.particleBuffer) {
      return false
    }

    if (instanceCount > 0) {
      const scratchCapacity = Math.max(INSTANCE_STRIDE_FLOATS, this.instanceCapacity * INSTANCE_STRIDE_FLOATS)
      if (!this.instanceScratch || this.instanceScratch.length < scratchCapacity) {
        this.instanceScratch = new Float32Array(scratchCapacity)
      }

      let opaqueIndex = 0
      let alphaIndex = opaqueInstanceCount
      let screenIndex = opaqueInstanceCount + alphaInstanceCount
      let additiveIndex = opaqueInstanceCount + alphaInstanceCount + screenInstanceCount
      frame.instances.forEach((instance) => {
        let packedIndex = alphaIndex
        const blendMode = instance.blendMode
        if (blendMode === 'opaque') {
          packedIndex = opaqueIndex
          opaqueIndex += 1
        } else if (blendMode === 'screen') {
          packedIndex = screenIndex
          screenIndex += 1
        } else if (blendMode === 'add') {
          packedIndex = additiveIndex
          additiveIndex += 1
        } else {
          alphaIndex += 1
        }

        const offset = packedIndex * INSTANCE_STRIDE_FLOATS
        this.instanceScratch![offset] = instance.baseX
        this.instanceScratch![offset + 1] = instance.baseY
        this.instanceScratch![offset + 2] = instance.dirX
        this.instanceScratch![offset + 3] = instance.dirY
        this.instanceScratch![offset + 4] = instance.halfWidth
        this.instanceScratch![offset + 5] = instance.length
        this.instanceScratch![offset + 6] = instance.red
        this.instanceScratch![offset + 7] = instance.green
        this.instanceScratch![offset + 8] = instance.blue
        this.instanceScratch![offset + 9] = instance.alpha
        this.instanceScratch![offset + 10] = instance.softness
        this.instanceScratch![offset + 11] = instance.glow
        this.instanceScratch![offset + 12] = instance.variant
        this.instanceScratch![offset + 13] = instance.gradientU
        this.instanceScratch![offset + 14] = instance.gradientV
      })
      this.device.queue.writeBuffer(
        this.instanceBuffer,
        0,
        this.instanceScratch.subarray(0, instanceCount * INSTANCE_STRIDE_FLOATS),
      )
    }

    if (particleCount > 0) {
      const scratchCapacity = Math.max(PARTICLE_INSTANCE_STRIDE_FLOATS, this.particleCapacity * PARTICLE_INSTANCE_STRIDE_FLOATS)
      if (!this.particleScratch || this.particleScratch.length < scratchCapacity) {
        this.particleScratch = new Float32Array(scratchCapacity)
      }
      frame.particles?.forEach((particle, index) => {
        const offset = index * PARTICLE_INSTANCE_STRIDE_FLOATS
        this.particleScratch![offset] = particle.spawnX
        this.particleScratch![offset + 1] = particle.spawnY
        this.particleScratch![offset + 2] = particle.dirX
        this.particleScratch![offset + 3] = particle.dirY
        this.particleScratch![offset + 4] = particle.halfWidth
        this.particleScratch![offset + 5] = particle.halfHeight
        this.particleScratch![offset + 6] = particle.speed
        this.particleScratch![offset + 7] = particle.spawnSec
        this.particleScratch![offset + 8] = particle.lifetimeSec
        this.particleScratch![offset + 9] = particle.opacity
        this.particleScratch![offset + 10] = particle.style
        this.particleScratch![offset + 11] = particle.softness
        this.particleScratch![offset + 12] = particle.noiseSeed
      })
      this.device.queue.writeBuffer(
        this.particleBuffer,
        0,
        this.particleScratch.subarray(0, particleCount * PARTICLE_INSTANCE_STRIDE_FLOATS),
      )
      if (particleSimulation) {
        const debugSecond = Math.floor(Math.max(0, particleSimulation.timeSec ?? 0))
        if (debugSecond !== lastParticleInstanceDebugSecond) {
          // #region debug-point PM-C:particle-missing-instance-pack
          sendParticleMissingDebug({
            hypothesisId: 'C',
            location: 'webgpuSpectrumRenderer',
            msg: '[DEBUG] particle missing instance snapshot',
            data: {
              particleCount,
              firstParticleScratch: Array.from(this.particleScratch.subarray(0, PARTICLE_INSTANCE_STRIDE_FLOATS)).map(
                (value) => Number(value.toFixed(4)),
              ),
            },
          })
          // #endregion
          lastParticleInstanceDebugSecond = debugSecond
        }
      }
    }

    const atmosphere = frame.atmosphere ?? null
    if (atmosphere && this.atmosphereUniformBuffer) {
      this.atmosphereScratch.fill(0)
      this.atmosphereScratch[0] = frame.width
      this.atmosphereScratch[1] = frame.height
      this.atmosphereScratch[2] = atmosphere.timeSec
      this.atmosphereScratch[4] = atmosphere.smokeEnabled ? 1 : 0
      this.atmosphereScratch[5] = atmosphere.smokeOpacity
      this.atmosphereScratch[6] = atmosphere.smokeStrength
      this.atmosphereScratch[7] = atmosphere.smokeBlur
      this.atmosphereScratch[8] = atmosphere.smokeSpeed
      this.atmosphereScratch[9] = atmosphere.smokeNoise
      this.atmosphereScratch[12] = atmosphere.smokeRed
      this.atmosphereScratch[13] = atmosphere.smokeGreen
      this.atmosphereScratch[14] = atmosphere.smokeBlue
      this.atmosphereScratch[16] = atmosphere.vignetteEnabled ? 1 : 0
      this.atmosphereScratch[17] = atmosphere.vignetteStrength
      this.atmosphereScratch[18] = atmosphere.vignetteFeather
      this.atmosphereScratch[19] = atmosphere.vignetteOpacity
      this.atmosphereScratch[20] = atmosphere.vignetteRed
      this.atmosphereScratch[21] = atmosphere.vignetteGreen
      this.atmosphereScratch[22] = atmosphere.vignetteBlue
      this.device.queue.writeBuffer(this.atmosphereUniformBuffer, 0, this.atmosphereScratch)
    }

    const audioSignal = frame.audioSignal ?? null
    if (audioSignal && this.audioSignalBuffer) {
      this.audioSignalScratch.fill(0)
      this.audioSignalScratch[0] = audioSignal.timeSec
      this.audioSignalScratch[1] = audioSignal.reactiveEnergy
      this.audioSignalScratch[2] = audioSignal.kick
      this.audioSignalScratch[3] = audioSignal.drop
      this.audioSignalScratch[4] = audioSignal.averageEnergy
      this.audioSignalScratch[5] = audioSignal.averageTransient
      this.audioSignalScratch[6] = audioSignal.averageOnset
      this.audioSignalScratch[7] = audioSignal.styleMotionDrive
      this.audioSignalScratch[8] = audioSignal.styleTriggerDrive
      this.audioSignalScratch.set(audioSignal.energyBands, AUDIO_SIGNAL_HEADER_FLOATS)
      this.audioSignalScratch.set(
        audioSignal.peakHoldBands,
        AUDIO_SIGNAL_HEADER_FLOATS + AUDIO_SIGNAL_BAND_FLOATS,
      )
      this.audioSignalScratch.set(
        audioSignal.transientBands,
        AUDIO_SIGNAL_HEADER_FLOATS + AUDIO_SIGNAL_BAND_FLOATS * 2,
      )
      this.audioSignalScratch.set(
        audioSignal.onsetBands,
        AUDIO_SIGNAL_HEADER_FLOATS + AUDIO_SIGNAL_BAND_FLOATS * 3,
      )
      this.device.queue.writeBuffer(this.audioSignalBuffer, 0, this.audioSignalScratch)
    }

    if (frame.backdropSource) {
      this.updateTextureSource('backdrop', frame.backdropSource)
    }
    if (frame.overlaySource) {
      this.updateTextureSource('overlay', frame.overlaySource)
    }
    if (frame.spectrumGradientAtlas) {
      this.updateSpectrumGradientAtlas(frame.spectrumGradientAtlas)
    }

    const pixelWidth = this.pixelWidth
    const pixelHeight = this.pixelHeight
    const postFxReady = this.ensurePostFxResources(pixelWidth, pixelHeight)

    const commandEncoder = this.device.createCommandEncoder()
    const presentTexture = this.context.getCurrentTexture()

    const postFxSettings = frame.postFx ?? null
    const bloomEnabled =
      postFxSettings?.enabled ?? (!frame.fallbackScene && instanceCount + particleCount > 0)

    if (
      postFxReady &&
      bloomEnabled &&
      this.sceneTexture &&
      this.bloomTextureA &&
      this.bloomTextureB &&
      this.postFxUniformBuffer &&
      this.postFxBrightPipeline &&
      this.postFxBlurPipeline &&
      this.postFxCompositePipeline &&
      this.postFxBrightBindGroup &&
      this.postFxBlurBindGroupA &&
      this.postFxBlurBindGroupB &&
      this.postFxCompositeBindGroupA &&
      this.postFxCompositeBindGroupB
    ) {
      const scenePass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: this.sceneTexture.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })

      if (frame.fallbackScene && this.fallbackScenePipeline) {
        scenePass.setPipeline(this.fallbackScenePipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.draw(6, 1)
      } else if (frame.backdropSource && this.backdropPipeline && this.backdropBindGroup) {
        scenePass.setPipeline(this.backdropPipeline)
        scenePass.setBindGroup(0, this.backdropBindGroup)
        scenePass.draw(6, 1)
      }

      if (atmosphere && this.atmospherePipeline && this.atmosphereBindGroup) {
        scenePass.setPipeline(this.atmospherePipeline)
        scenePass.setBindGroup(0, this.atmosphereBindGroup)
        scenePass.draw(6, 1)
      }

      if (particleCount > 0 && this.particlePipeline) {
        scenePass.setPipeline(this.particlePipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.setVertexBuffer(0, this.particleBuffer)
        scenePass.draw(6, particleCount)
      }

      if (opaqueInstanceCount > 0) {
        scenePass.setPipeline(this.spectrumOpaquePipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.setBindGroup(1, this.spectrumGradientBindGroup)
        scenePass.setVertexBuffer(0, this.instanceBuffer)
        scenePass.draw(6, opaqueInstanceCount, 0, 0)
      }
      if (alphaInstanceCount > 0) {
        scenePass.setPipeline(this.spectrumAlphaPipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.setBindGroup(1, this.spectrumGradientBindGroup)
        scenePass.setVertexBuffer(0, this.instanceBuffer)
        scenePass.draw(6, alphaInstanceCount, 0, opaqueInstanceCount)
      }
      if (screenInstanceCount > 0) {
        scenePass.setPipeline(this.spectrumScreenPipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.setBindGroup(1, this.spectrumGradientBindGroup)
        scenePass.setVertexBuffer(0, this.instanceBuffer)
        scenePass.draw(6, screenInstanceCount, 0, opaqueInstanceCount + alphaInstanceCount)
      }
      if (additiveInstanceCount > 0) {
        scenePass.setPipeline(this.spectrumAdditivePipeline)
        scenePass.setBindGroup(0, this.spectrumBindGroup)
        scenePass.setBindGroup(1, this.spectrumGradientBindGroup)
        scenePass.setVertexBuffer(0, this.instanceBuffer)
        scenePass.draw(
          6,
          additiveInstanceCount,
          0,
          opaqueInstanceCount + alphaInstanceCount + screenInstanceCount,
        )
      }

      if (frame.overlaySource && this.backdropPipeline && this.overlayBindGroup) {
        scenePass.setPipeline(this.backdropPipeline)
        scenePass.setBindGroup(0, this.overlayBindGroup)
        scenePass.draw(6, 1)
      }
      scenePass.end()

      const threshold = clamp(postFxSettings?.threshold ?? 0.62, 0.1, 1.25)
      const knee = clamp(postFxSettings?.knee ?? 0.35, 0.01, 1.25)
      const intensity = clamp(postFxSettings?.intensity ?? 1.05, 0.0, 4.0)
      const blurScale = clamp(postFxSettings?.blurScale ?? 1.0, 0.25, 3.5)
      this.postFxScratch[0] = threshold
      this.postFxScratch[1] = knee
      this.postFxScratch[2] = intensity
      this.postFxScratch[3] = 0
      this.postFxScratch[4] = blurScale
      this.postFxScratch[5] = 0
      this.postFxScratch[6] = 0
      this.postFxScratch[7] = 0
      this.device.queue.writeBuffer(
        this.postFxUniformBuffer,
        0,
        this.postFxScratch,
      )
      const brightPass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: this.bloomTextureA.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })
      brightPass.setPipeline(this.postFxBrightPipeline)
      brightPass.setBindGroup(0, this.postFxBrightBindGroup)
      brightPass.draw(6, 1)
      brightPass.end()

      const texelX = 1 / Math.max(1, this.bloomWidth)
      const texelY = 1 / Math.max(1, this.bloomHeight)
      this.postFxScratch[0] = texelX
      this.postFxScratch[1] = texelY
      this.postFxScratch[2] = 1
      this.postFxScratch[3] = 0
      this.postFxScratch[4] = blurScale
      this.postFxScratch[5] = 0
      this.postFxScratch[6] = 0
      this.postFxScratch[7] = 0
      this.device.queue.writeBuffer(
        this.postFxUniformBuffer,
        0,
        this.postFxScratch,
      )
      const blurHPass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: this.bloomTextureB.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })
      blurHPass.setPipeline(this.postFxBlurPipeline)
      blurHPass.setBindGroup(0, this.postFxBlurBindGroupA)
      blurHPass.draw(6, 1)
      blurHPass.end()

      this.postFxScratch[0] = texelX
      this.postFxScratch[1] = texelY
      this.postFxScratch[2] = 0
      this.postFxScratch[3] = 1
      this.postFxScratch[4] = blurScale
      this.postFxScratch[5] = 0
      this.postFxScratch[6] = 0
      this.postFxScratch[7] = 0
      this.device.queue.writeBuffer(
        this.postFxUniformBuffer,
        0,
        this.postFxScratch,
      )
      const blurVPass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: this.bloomTextureA.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })
      blurVPass.setPipeline(this.postFxBlurPipeline)
      blurVPass.setBindGroup(0, this.postFxBlurBindGroupB)
      blurVPass.draw(6, 1)
      blurVPass.end()

      const bloomStrength = clamp(postFxSettings?.bloomStrength ?? 0.65, 0.0, 3.0)
      const motionBlurStrength = clamp(postFxSettings?.motionBlurStrength ?? 0, 0.0, 1.0)
      const motionBlurShutter = clamp(postFxSettings?.motionBlurShutterAngle ?? 0, 0.0, 360.0)
      const motionBlurSamples = Math.max(0, Math.round(postFxSettings?.motionBlurSamples ?? 0))
      const historyMixBase = clamp(
        motionBlurStrength * Math.min(1, motionBlurShutter / 240) * Math.min(1, motionBlurSamples / 8),
        0.0,
        0.96,
      )
      const historyTargetTexture = this.activeHistoryIndex === 0 ? this.historyTextureA : this.historyTextureB
      const compositeBindGroup =
        this.activeHistoryIndex === 0 ? this.postFxCompositeBindGroupB : this.postFxCompositeBindGroupA
      const historyBindGroup = this.activeHistoryIndex === 0 ? this.postFxHistoryBindGroupA : this.postFxHistoryBindGroupB
      this.postFxScratch[0] = bloomStrength
      this.postFxScratch[1] = 0
      this.postFxScratch[2] = 0
      this.postFxScratch[3] = 0
      this.postFxScratch[4] = audioSignal?.reactiveEnergy ?? 0
      this.postFxScratch[5] = audioSignal?.kick ?? 0
      this.postFxScratch[6] = audioSignal?.styleMotionDrive ?? 0
      this.postFxScratch[7] = 0
      this.postFxScratch[8] = motionBlurStrength
      this.postFxScratch[9] = historyMixBase
      this.postFxScratch[10] = this.historyValid ? 1 : 0
      this.postFxScratch[11] = motionBlurSamples
      this.postFxScratch[12] = motionBlurShutter
      this.postFxScratch[13] = 0
      this.postFxScratch[14] = 0
      this.postFxScratch[15] = 0
      this.device.queue.writeBuffer(
        this.postFxUniformBuffer,
        0,
        this.postFxScratch,
      )
      const compositePass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: historyTargetTexture.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })
      compositePass.setPipeline(this.postFxCompositePipeline)
      compositePass.setBindGroup(0, compositeBindGroup)
      compositePass.draw(6, 1)
      compositePass.end()

      const presentPass = commandEncoder.beginRenderPass({
        colorAttachments: [
          {
            view: presentTexture.createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })
      presentPass.setPipeline(this.backdropPipeline)
      presentPass.setBindGroup(0, historyBindGroup)
      presentPass.draw(6, 1)
      presentPass.end()

      this.scheduleReadback(commandEncoder, presentTexture, pixelWidth, pixelHeight)
      this.device.queue.submit([commandEncoder.finish()])
      this.historyValid = true
      this.activeHistoryIndex = (this.activeHistoryIndex + 1) % 2
      return true
    }

    this.historyValid = false

    const renderPass = commandEncoder.beginRenderPass({
      colorAttachments: [
        {
          view: presentTexture.createView(),
          clearValue: { r: 0, g: 0, b: 0, a: 0 },
          loadOp: 'clear',
          storeOp: 'store',
        },
      ],
    })

    if (frame.fallbackScene && this.fallbackScenePipeline) {
      renderPass.setPipeline(this.fallbackScenePipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.draw(6, 1)
    } else if (frame.backdropSource && this.backdropPipeline && this.backdropBindGroup) {
      renderPass.setPipeline(this.backdropPipeline)
      renderPass.setBindGroup(0, this.backdropBindGroup)
      renderPass.draw(6, 1)
    }

    if (atmosphere && this.atmospherePipeline && this.atmosphereBindGroup) {
      renderPass.setPipeline(this.atmospherePipeline)
      renderPass.setBindGroup(0, this.atmosphereBindGroup)
      renderPass.draw(6, 1)
    }

    if (particleCount > 0 && this.particlePipeline) {
      renderPass.setPipeline(this.particlePipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.setVertexBuffer(0, this.particleBuffer)
      renderPass.draw(6, particleCount)
    }

    if (opaqueInstanceCount > 0) {
      renderPass.setPipeline(this.spectrumOpaquePipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.setBindGroup(1, this.spectrumGradientBindGroup)
      renderPass.setVertexBuffer(0, this.instanceBuffer)
      renderPass.draw(6, opaqueInstanceCount, 0, 0)
    }
    if (alphaInstanceCount > 0) {
      renderPass.setPipeline(this.spectrumAlphaPipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.setBindGroup(1, this.spectrumGradientBindGroup)
      renderPass.setVertexBuffer(0, this.instanceBuffer)
      renderPass.draw(6, alphaInstanceCount, 0, opaqueInstanceCount)
    }
    if (screenInstanceCount > 0) {
      renderPass.setPipeline(this.spectrumScreenPipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.setBindGroup(1, this.spectrumGradientBindGroup)
      renderPass.setVertexBuffer(0, this.instanceBuffer)
      renderPass.draw(6, screenInstanceCount, 0, opaqueInstanceCount + alphaInstanceCount)
    }
    if (additiveInstanceCount > 0) {
      renderPass.setPipeline(this.spectrumAdditivePipeline)
      renderPass.setBindGroup(0, this.spectrumBindGroup)
      renderPass.setBindGroup(1, this.spectrumGradientBindGroup)
      renderPass.setVertexBuffer(0, this.instanceBuffer)
      renderPass.draw(
        6,
        additiveInstanceCount,
        0,
        opaqueInstanceCount + alphaInstanceCount + screenInstanceCount,
      )
    }

    if (frame.overlaySource && this.backdropPipeline && this.overlayBindGroup) {
      renderPass.setPipeline(this.backdropPipeline)
      renderPass.setBindGroup(0, this.overlayBindGroup)
      renderPass.draw(6, 1)
    }
    renderPass.end()

    this.scheduleReadback(commandEncoder, presentTexture, pixelWidth, pixelHeight)
    this.device.queue.submit([commandEncoder.finish()])
    return true
  }

  destroy(): void {
    this.instanceBuffer?.destroy()
    this.particleBuffer?.destroy()
    this.uniformBuffer?.destroy()
    this.atmosphereUniformBuffer?.destroy()
    this.audioSignalBuffer?.destroy()
    this.postFxUniformBuffer?.destroy()
    this.spectrumGradientTexture?.destroy()
    this.backdropTexture?.destroy()
    this.overlayTexture?.destroy()
    this.sceneTexture?.destroy()
    this.bloomTextureA?.destroy()
    this.bloomTextureB?.destroy()
    this.historyTextureA?.destroy()
    this.historyTextureB?.destroy()
    this.instanceBuffer = null
    this.particleBuffer = null
    this.uniformBuffer = null
    this.atmosphereUniformBuffer = null
    this.audioSignalBuffer = null
    this.postFxUniformBuffer = null
    this.spectrumGradientTexture = null
    this.backdropTexture = null
    this.overlayTexture = null
    this.sceneTexture = null
    this.bloomTextureA = null
    this.bloomTextureB = null
    this.historyTextureA = null
    this.historyTextureB = null
    this.backdropBindGroup = null
    this.overlayBindGroup = null
    this.backdropSampler = null
    this.spectrumBindGroup = null
    this.spectrumGradientBindGroup = null
    this.spectrumGradientSampler = null
    this.spectrumGradientLayout = null
    this.atmosphereBindGroup = null
    this.spectrumOpaquePipeline = null
    this.spectrumAdditivePipeline = null
    this.spectrumScreenPipeline = null
    this.spectrumAlphaPipeline = null
    this.particlePipeline = null
    this.backdropPipeline = null
    this.atmospherePipeline = null
    this.postFxSampler = null
    this.postFxBrightPipeline = null
    this.postFxBlurPipeline = null
    this.postFxCompositePipeline = null
    this.fallbackScenePipeline = null
    this.postFxTextureLayout = null
    this.postFxCompositeLayout = null
    this.postFxBrightBindGroup = null
    this.postFxBlurBindGroupA = null
    this.postFxBlurBindGroupB = null
    this.postFxCompositeBindGroupA = null
    this.postFxCompositeBindGroupB = null
    this.postFxHistoryBindGroupA = null
    this.postFxHistoryBindGroupB = null
    this.context = null
    this.device = null
    this.canvas = null
    this.textureFormat = null
    this.readbackSlots.forEach((slot) => {
      try {
        slot.buffer?.destroy?.()
      } catch {
        // ignore readback cleanup failures
      }
      slot.buffer = null
      slot.busy = false
    })
    this.readbackBytesPerRow = 0
    this.readbackBufferSize = 0
    this.readbackEnabled = false
    this.latestReadbackFrame = null
    this.pendingReadbackPromise = null
    this.instanceCapacity = 0
    this.particleCapacity = 0
    this.pixelWidth = 0
    this.pixelHeight = 0
    this.backdropWidth = 0
    this.backdropHeight = 0
    this.overlayWidth = 0
    this.overlayHeight = 0
    this.spectrumGradientWidth = 0
    this.spectrumGradientHeight = 0
    this.postFxWidth = 0
    this.postFxHeight = 0
    this.bloomWidth = 0
    this.bloomHeight = 0
    this.activeHistoryIndex = 0
    this.historyValid = false
    this.onDeviceLost = null
  }

  private scheduleReadback(
    commandEncoder: any,
    texture: any,
    pixelWidth: number,
    pixelHeight: number,
  ): void {
    if (!this.readbackEnabled || !this.device) {
      return
    }
    const slot = this.ensureReadbackSlot(pixelWidth, pixelHeight)
    if (!slot) {
      return
    }
    slot.busy = true
    const readbackStartedAt = Date.now()
    commandEncoder.copyTextureToBuffer(
      {
        texture,
      },
      {
        buffer: slot.buffer,
        bytesPerRow: this.readbackBytesPerRow,
        rowsPerImage: pixelHeight,
      },
      [pixelWidth, pixelHeight, 1],
    )
    const readbackPromise = slot.buffer
      .mapAsync(GPU_MAP_MODE_READ)
      .then(() => {
        const mapped = new Uint8Array(slot.buffer.getMappedRange())
        const rowBytes = pixelWidth * 4
        const frame = new Uint8Array(rowBytes * pixelHeight)
        if (this.readbackBytesPerRow === rowBytes) {
          frame.set(mapped.subarray(0, frame.byteLength))
        } else {
          for (let rowIndex = 0; rowIndex < pixelHeight; rowIndex += 1) {
            const sourceOffset = rowIndex * this.readbackBytesPerRow
            const targetOffset = rowIndex * rowBytes
            frame.set(mapped.subarray(sourceOffset, sourceOffset + rowBytes), targetOffset)
          }
        }
        this.latestReadbackFrame = frame
        // #region debug-point A:gpu-readback
        sendExportSpeedDebug({
          hypothesisId: 'A',
          location: 'webgpuSpectrumRenderer:scheduleReadback',
          msg: '[DEBUG] export GPU readback completed in renderer',
          data: {
            elapsedMs: Date.now() - readbackStartedAt,
            pixelWidth,
            pixelHeight,
            bytesPerRow: this.readbackBytesPerRow,
            frameBytes: frame.byteLength,
          },
        })
        // #endregion
        return frame
      })
      .finally(() => {
        try {
          slot.buffer.unmap()
        } catch {
          // ignore readback unmap failures
        }
        slot.busy = false
        if (this.pendingReadbackPromise === readbackPromise) {
          this.pendingReadbackPromise = null
        }
      })
    this.pendingReadbackPromise = readbackPromise
  }

  private ensureReadbackSlot(pixelWidth: number, pixelHeight: number): WebGpuReadbackSlot | null {
    if (!this.device) {
      return null
    }
    const bytesPerRow = Math.ceil((pixelWidth * 4) / 256) * 256
    const bufferSize = bytesPerRow * pixelHeight
    if (bufferSize <= 0) {
      return null
    }
    if (bufferSize !== this.readbackBufferSize || bytesPerRow !== this.readbackBytesPerRow) {
      // #region debug-point D:readback-buffer-config
      sendExportSpeedDebug({
        hypothesisId: 'D',
        location: 'webgpuSpectrumRenderer:ensureReadbackSlot',
        msg: '[DEBUG] export readback buffer resized',
        data: {
          pixelWidth,
          pixelHeight,
          bytesPerRow,
          bufferSize,
        },
      })
      // #endregion
      this.readbackSlots.forEach((slot) => {
        try {
          slot.buffer?.destroy?.()
        } catch {
          // ignore readback buffer cleanup failures
        }
        slot.buffer = this.device.createBuffer({
          size: bufferSize,
          usage: GPU_BUFFER_USAGE_COPY_DST | GPU_BUFFER_USAGE_MAP_READ,
        })
        slot.busy = false
      })
      this.readbackBufferSize = bufferSize
      this.readbackBytesPerRow = bytesPerRow
      this.latestReadbackFrame = null
    }
    return this.readbackSlots.find((slot) => !slot.busy) ?? null
  }

  private ensureInstanceCapacity(nextCapacity: number): void {
    if (!this.device || nextCapacity <= this.instanceCapacity) {
      return
    }

    this.instanceBuffer?.destroy()
    this.instanceBuffer = this.device.createBuffer({
      size: nextCapacity * INSTANCE_STRIDE_BYTES,
      usage: GPU_BUFFER_USAGE_VERTEX | GPU_BUFFER_USAGE_COPY_DST,
    })
    this.instanceCapacity = nextCapacity
  }

  private ensureParticleCapacity(nextCapacity: number): void {
    if (!this.device || nextCapacity <= this.particleCapacity) {
      return
    }

    this.particleBuffer?.destroy()
    this.particleBuffer = this.device.createBuffer({
      size: nextCapacity * PARTICLE_INSTANCE_STRIDE_BYTES,
      usage: GPU_BUFFER_USAGE_VERTEX | GPU_BUFFER_USAGE_COPY_DST,
    })
    this.particleCapacity = nextCapacity
  }

  private updateSpectrumGradientAtlas(gradientAtlas: WebGpuSpectrumGradientAtlas): void {
    if (
      !this.device ||
      !this.spectrumGradientSampler ||
      !this.spectrumGradientLayout ||
      gradientAtlas.width <= 0 ||
      gradientAtlas.height <= 0
    ) {
      return
    }

    if (
      !this.spectrumGradientTexture ||
      this.spectrumGradientWidth !== gradientAtlas.width ||
      this.spectrumGradientHeight !== gradientAtlas.height
    ) {
      this.spectrumGradientTexture?.destroy()
      this.spectrumGradientTexture = this.device.createTexture({
        size: [gradientAtlas.width, gradientAtlas.height, 1],
        format: 'rgba8unorm',
        usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_COPY_DST,
      })
      this.spectrumGradientWidth = gradientAtlas.width
      this.spectrumGradientHeight = gradientAtlas.height
      this.spectrumGradientBindGroup = this.device.createBindGroup({
        layout: this.spectrumGradientLayout,
        entries: [
          { binding: 0, resource: this.spectrumGradientSampler },
          { binding: 1, resource: this.spectrumGradientTexture.createView() },
        ],
      })
    }

    this.device.queue.writeTexture(
      { texture: this.spectrumGradientTexture },
      gradientAtlas.rgba,
      {
        bytesPerRow: gradientAtlas.width * 4,
      },
      [gradientAtlas.width, gradientAtlas.height, 1],
    )
  }

  private ensurePostFxResources(pixelWidth: number, pixelHeight: number): boolean {
    if (
      !this.device ||
      !this.textureFormat ||
      !this.postFxSampler ||
      !this.postFxUniformBuffer ||
      !this.postFxTextureLayout ||
      !this.postFxCompositeLayout
    ) {
      return false
    }

    const bloomWidth = Math.max(1, Math.floor(pixelWidth / 2))
    const bloomHeight = Math.max(1, Math.floor(pixelHeight / 2))
    if (
      this.sceneTexture &&
      this.bloomTextureA &&
      this.bloomTextureB &&
      this.historyTextureA &&
      this.historyTextureB &&
      pixelWidth === this.postFxWidth &&
      pixelHeight === this.postFxHeight &&
      bloomWidth === this.bloomWidth &&
      bloomHeight === this.bloomHeight
    ) {
      return true
    }

    this.sceneTexture?.destroy()
    this.bloomTextureA?.destroy()
    this.bloomTextureB?.destroy()
    this.historyTextureA?.destroy()
    this.historyTextureB?.destroy()
    this.sceneTexture = this.device.createTexture({
      size: [pixelWidth, pixelHeight, 1],
      format: this.textureFormat,
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_RENDER_ATTACHMENT,
    })
    this.bloomTextureA = this.device.createTexture({
      size: [bloomWidth, bloomHeight, 1],
      format: this.textureFormat,
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_RENDER_ATTACHMENT,
    })
    this.bloomTextureB = this.device.createTexture({
      size: [bloomWidth, bloomHeight, 1],
      format: this.textureFormat,
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_RENDER_ATTACHMENT,
    })
    this.historyTextureA = this.device.createTexture({
      size: [pixelWidth, pixelHeight, 1],
      format: this.textureFormat,
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_RENDER_ATTACHMENT,
    })
    this.historyTextureB = this.device.createTexture({
      size: [pixelWidth, pixelHeight, 1],
      format: this.textureFormat,
      usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_RENDER_ATTACHMENT,
    })
    this.postFxWidth = pixelWidth
    this.postFxHeight = pixelHeight
    this.bloomWidth = bloomWidth
    this.bloomHeight = bloomHeight
    this.activeHistoryIndex = 0
    this.historyValid = false

    this.postFxBrightBindGroup = this.device.createBindGroup({
      layout: this.postFxTextureLayout,
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.sceneTexture.createView() },
        { binding: 2, resource: { buffer: this.postFxUniformBuffer } },
      ],
    })
    this.postFxBlurBindGroupA = this.device.createBindGroup({
      layout: this.postFxTextureLayout,
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.bloomTextureA.createView() },
        { binding: 2, resource: { buffer: this.postFxUniformBuffer } },
      ],
    })
    this.postFxBlurBindGroupB = this.device.createBindGroup({
      layout: this.postFxTextureLayout,
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.bloomTextureB.createView() },
        { binding: 2, resource: { buffer: this.postFxUniformBuffer } },
      ],
    })
    this.postFxCompositeBindGroupA = this.device.createBindGroup({
      layout: this.postFxCompositeLayout,
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.sceneTexture.createView() },
        { binding: 2, resource: this.bloomTextureA.createView() },
        { binding: 3, resource: this.historyTextureA.createView() },
        { binding: 4, resource: { buffer: this.postFxUniformBuffer } },
      ],
    })
    this.postFxCompositeBindGroupB = this.device.createBindGroup({
      layout: this.postFxCompositeLayout,
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.sceneTexture.createView() },
        { binding: 2, resource: this.bloomTextureA.createView() },
        { binding: 3, resource: this.historyTextureB.createView() },
        { binding: 4, resource: { buffer: this.postFxUniformBuffer } },
      ],
    })
    this.postFxHistoryBindGroupA = this.device.createBindGroup({
      layout: this.backdropPipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.historyTextureA.createView() },
      ],
    })
    this.postFxHistoryBindGroupB = this.device.createBindGroup({
      layout: this.backdropPipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: this.postFxSampler },
        { binding: 1, resource: this.historyTextureB.createView() },
      ],
    })
    return true
  }

  private updateTextureSource(kind: 'backdrop' | 'overlay', source: CanvasImageSource): void {
    if (!this.device || !this.backdropSampler) {
      return
    }

    const width = this.getSourceWidth(source)
    const height = this.getSourceHeight(source)
    if (width <= 0 || height <= 0) {
      return
    }

    const isBackdrop = kind === 'backdrop'
    const activeTexture = isBackdrop ? this.backdropTexture : this.overlayTexture
    const activeWidth = isBackdrop ? this.backdropWidth : this.overlayWidth
    const activeHeight = isBackdrop ? this.backdropHeight : this.overlayHeight

    if (!activeTexture || width !== activeWidth || height !== activeHeight) {
      activeTexture?.destroy()
      const nextTexture = this.device.createTexture({
        size: [width, height, 1],
        format: 'rgba8unorm',
        usage: GPU_TEXTURE_USAGE_TEXTURE_BINDING | GPU_TEXTURE_USAGE_COPY_DST,
      })
      const nextBindGroup = this.device.createBindGroup({
        layout: this.backdropPipeline.getBindGroupLayout(0),
        entries: [
          {
            binding: 0,
            resource: this.backdropSampler,
          },
          {
            binding: 1,
            resource: nextTexture.createView(),
          },
        ],
      })
      if (isBackdrop) {
        this.backdropTexture = nextTexture
        this.backdropWidth = width
        this.backdropHeight = height
        this.backdropBindGroup = nextBindGroup
      } else {
        this.overlayTexture = nextTexture
        this.overlayWidth = width
        this.overlayHeight = height
        this.overlayBindGroup = nextBindGroup
      }
    }

    const targetTexture = isBackdrop ? this.backdropTexture : this.overlayTexture
    if (!targetTexture) {
      return
    }
    this.device.queue.copyExternalImageToTexture(
      { source },
      { texture: targetTexture },
      [width, height],
    )
  }

  private getSourceWidth(source: CanvasImageSource): number {
    if ('videoWidth' in source && typeof source.videoWidth === 'number') {
      return source.videoWidth
    }
    if ('naturalWidth' in source && typeof source.naturalWidth === 'number') {
      return source.naturalWidth
    }
    if ('displayWidth' in source && typeof source.displayWidth === 'number') {
      return source.displayWidth
    }
    if ('codedWidth' in source && typeof source.codedWidth === 'number') {
      return source.codedWidth
    }
    if ('width' in source) {
      const width = (source as { width?: unknown }).width
      return typeof width === 'number' ? width : 0
    }
    return 0
  }

  private getSourceHeight(source: CanvasImageSource): number {
    if ('videoHeight' in source && typeof source.videoHeight === 'number') {
      return source.videoHeight
    }
    if ('naturalHeight' in source && typeof source.naturalHeight === 'number') {
      return source.naturalHeight
    }
    if ('displayHeight' in source && typeof source.displayHeight === 'number') {
      return source.displayHeight
    }
    if ('codedHeight' in source && typeof source.codedHeight === 'number') {
      return source.codedHeight
    }
    if ('height' in source) {
      const height = (source as { height?: unknown }).height
      return typeof height === 'number' ? height : 0
    }
    return 0
  }
}
