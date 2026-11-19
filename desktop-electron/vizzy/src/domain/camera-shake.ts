/**
 * Camera Shake transform generator, ported from Vizzy module 582.
 *
 * The reference computes two simplex-noise channels and a rotation, then passes
 * `(x, y, angle, scale)` to the shake shader. Its phase is not the playhead: the
 * effect accumulates `1/fps * frequency` per rendered frame (module 582's
 * `cumulativeTime`). We evaluate that accumulator on the 60 Hz frame grid: a
 * contiguous frame advances it, a repeated frame (the reference's rerender) does
 * not, and a jump re-anchors to the target frame so captures are reproducible.
 */

const GRAD3 = new Float32Array([
  1, 1, 0, -1, 1, 0, 1, -1, 0, -1, -1, 0,
  1, 0, 1, -1, 0, 1, 1, 0, -1, -1, 0, -1,
  0, 1, 1, 0, -1, 1, 0, 1, -1, 0, -1, -1,
]);

const F2 = 0.5 * (Math.sqrt(3) - 1);
const G2 = (3 - Math.sqrt(3)) / 6;
const PI = Math.PI;

/**
 * Phase step rate. Module 582 advances its accumulator by
 * `1 / (e.fps === 1000 ? 60 : e.fps) * frequency` on every `renderEffect` call
 * that is not a `rerender`. `e.fps` is the editor FPS setting
 * (`editor.setting.fps`, default 60), not a measured rate. Captures replay at a
 * fixed 60 Hz, so using a literal 60 here makes the phase a function of the
 * frame the replay is on; a session configured for another editor FPS advances
 * at a different rate, which is a documented divergence rather than a source of
 * capture-to-capture noise.
 */
const SHAKE_PHASE_FPS = 60;

let seedCounter = 1;
function randomSeed(): number {
  const value = 10000 * Math.sin(seedCounter++);
  return value - Math.floor(value);
}

/**
 * Restart the seeded sequence at the beginning of a project import.
 *
 * The reference seeds its simplex table from a module-global counter
 * (`let a = 1; … 1e4*sin(a++)`), so the table an effect gets depends on how many
 * shake instances were constructed before it. A reused preview tab kept
 * importing templates, which advanced the counter and gave the *same* template a
 * different whole-frame offset on every capture (equinox swung 20.5 ↔ 38.2).
 * Resetting at import reproduces what a fresh browser session sees.
 */
export function resetCameraShakeSeed(): void {
  seedCounter = 1;
}

export interface ShakeSettings {
  amplitudeX: number;
  amplitudeY: number;
  rotation: number;
  frequency: number;
  octaves: number;
  autoScale: boolean;
  preScale: number;
}

export interface ShakeTransform {
  x: number;
  y: number;
  angle: number;
  scale: number;
}

export class CameraShakeTransform {
  private readonly perm = new Uint8Array(512);
  private readonly permMod12 = new Uint8Array(512);
  private initialized = false;
  private settings: ShakeSettings = {
    amplitudeX: 8,
    amplitudeY: 8,
    rotation: 2,
    frequency: 1.5,
    octaves: 1,
    autoScale: true,
    preScale: 1,
  };
  private maxScale = 1;
  /**
   * Phase cache for module 582's `cumulativeTime`. The reference advances it by
   * `1/fps * frequency` per `renderEffect` call that is not a rerender. Our
   * renderer interleaves background RAF passes with the capture/replay passes,
   * so a raw per-call counter is not reproducible; the playhead quantised to the
   * 60 Hz frame grid is. A contiguous frame advances the accumulator by one
   * step; a repeated frame (our rerender equivalent) does nothing; a jump
   * re-anchors to the target frame, i.e. the value continuous playback from 0
   * would have reached.
   */
  private cumulativeTime = 0;
  private lastFrame: number | null = null;

  constructor() {
    this.initializeSimplex();
    this.calcMax();
  }

  setSettings(settings: Partial<ShakeSettings>): void {
    this.settings = { ...this.settings, ...settings };
    this.calcMax();
  }

  private initializeSimplex(): void {
    if (this.initialized) return;
    const source = new Uint8Array(256);
    for (let i = 0; i < 256; i += 1) source[i] = 256 * randomSeed();
    for (let i = 0; i < 512; i += 1) {
      this.perm[i] = source[i & 255];
      this.permMod12[i] = this.perm[i] % 12;
    }
    this.initialized = true;
  }

  private calcScale(amplitudeX: number, amplitudeY: number, rotation: number): number {
    let scale = 1;
    let angle = rotation - PI * Math.floor(rotation / PI);
    if (angle) {
      const sin = Math.sin(angle);
      const cos = Math.sqrt(1 - sin * sin);
      let o = 1, r = 1;
      let a = Math.abs(o * cos - 1 * sin);
      let l = Math.abs(o * sin + 1 * cos);
      o = -o;
      const i = Math.abs(o * cos - 1 * sin);
      const c = Math.abs(o * sin + 1 * cos);
      scale = 2 * Math.max(a / 2, i / 2, l / 2, c / 2);
      void r;
    }
    return scale * Math.max((2 * Math.abs(amplitudeX) + 2) / 2, (2 * Math.abs(amplitudeY) + 2) / 2);
  }

  private noise2D(x: number, y: number): number {
    let n0 = 0, n1 = 0, n2 = 0;
    const s = (x + y) * F2;
    const i = Math.floor(x + s);
    const j = Math.floor(y + s);
    const t = (i + j) * G2;
    const x0 = x - (i - t);
    const y0 = y - (j - t);
    const i1 = x0 > y0 ? 1 : 0;
    const j1 = x0 > y0 ? 0 : 1;
    const x1 = x0 - i1 + G2;
    const y1 = y0 - j1 + G2;
    const x2 = x0 - 1 + 2 * G2;
    const y2 = y0 - 1 + 2 * G2;
    const ii = i & 255;
    const jj = j & 255;

    let t0 = 0.5 - x0 * x0 - y0 * y0;
    if (t0 >= 0) {
      const gi0 = this.permMod12[ii + this.perm[jj]] * 3;
      t0 *= t0;
      n0 = t0 * t0 * (GRAD3[gi0] * x0 + GRAD3[gi0 + 1] * y0);
    }
    let t1 = 0.5 - x1 * x1 - y1 * y1;
    if (t1 >= 0) {
      const gi1 = this.permMod12[ii + i1 + this.perm[jj + j1]] * 3;
      t1 *= t1;
      n1 = t1 * t1 * (GRAD3[gi1] * x1 + GRAD3[gi1 + 1] * y1);
    }
    let t2 = 0.5 - x2 * x2 - y2 * y2;
    if (t2 >= 0) {
      const gi2 = this.permMod12[ii + 1 + this.perm[jj + 1]] * 3;
      t2 *= t2;
      n2 = t2 * t2 * (GRAD3[gi2] * x2 + GRAD3[gi2 + 1] * y2);
    }
    return 70 * (n0 + n1 + n2);
  }

  private calcMax(): void {
    this.maxScale = this.calcScale(
      this.settings.amplitudeX / 100,
      this.settings.amplitudeY / 100,
      (this.settings.rotation * PI) / 180,
    );
  }

  transform(time: number): ShakeTransform {
    const { amplitudeX, amplitudeY, rotation, frequency, octaves, autoScale, preScale } =
      this.settings;
    const frame = Math.round(time * SHAKE_PHASE_FPS);
    if (this.lastFrame === null) {
      // A fresh effect starts wherever its first frame is; frame 0 is already
      // one step in because module 582 increments before sampling.
      this.cumulativeTime = ((frame + 1) / SHAKE_PHASE_FPS) * frequency;
    } else if (frame === this.lastFrame + 1) {
      // A contiguous playback frame adds exactly one step.
      this.cumulativeTime += frequency / SHAKE_PHASE_FPS;
    } else if (frame !== this.lastFrame) {
      // A seek or replay jump. The reference keeps its accumulator (a seek does
      // not rewind it); we re-anchor to the frame's continuous-playback value so
      // a capture is a function of its playhead, not of how many background
      // renders happened before it.
      this.cumulativeTime = ((frame + 1) / SHAKE_PHASE_FPS) * frequency;
    }
    if (this.lastFrame !== frame) this.lastFrame = frame;
    const u = this.cumulativeTime;
    let totalAmplitude = 0;
    let angle = 0;
    let x = 0;
    let y = 0;
    for (let octave = 0; octave < Math.max(1, octaves); octave += 1) {
      const frequencyScale = Math.pow(2, octave);
      const amplitudeScale = Math.pow(0.5, octave);
      totalAmplitude += amplitudeScale;
      if (rotation) angle += this.noise2D(u * frequencyScale, 7 * frequencyScale) * amplitudeScale;
      if (amplitudeX) x += this.noise2D(u * frequencyScale, 11 * frequencyScale) * amplitudeScale;
      if (amplitudeY) y += this.noise2D(u * frequencyScale, 13 * frequencyScale) * amplitudeScale;
    }
    angle *= rotation / (totalAmplitude * 1);
    x *= amplitudeX / (totalAmplitude * 100);
    y *= amplitudeY / (totalAmplitude * 100);
    const radians = (angle * PI) / 180;
    let scale = 1;
    if (autoScale) {
      scale =
        preScale === 1
          ? this.maxScale
          : preScale * this.maxScale + (1 - preScale) * this.calcScale(x, y, radians);
    }
    return { x, y, angle: radians, scale };
  }
}
