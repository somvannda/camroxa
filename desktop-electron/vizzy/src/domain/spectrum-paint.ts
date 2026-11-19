/**
 * GPU colour texture for a Spectrum `Shader` layer.
 *
 * The reference uses the SkSL runtime effect as a Skia paint: the shader supplies
 * colour, the path supplies coverage. We render the shader to a small transparent
 * canvas on the GPU, then the Canvas2D renderer masks that colour with the exact
 * decompiled path.
 *
 * All layers share **one** WebGL context. The reference also has one Skia GPU
 * context; creating a context per layer exhausted the browser's ~16 context
 * limit after a few preset changes and left later shaders blank.
 */
import * as THREE from "three";
import {
  getShaderValidation,
  requestShaderValidation,
  SPECTRUM_VERTEX_SHADER,
  wrapSpectrumFragment,
} from "./spectrum-shader";
import type { SpectrumLayer } from "./spectrum-layers";

const SIZE = 512;

class SharedShaderStage {
  readonly canvas: HTMLCanvasElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly camera: THREE.OrthographicCamera;
  private readonly mesh: THREE.Mesh;
  private material: THREE.ShaderMaterial | null = null;
  private source: string | null = null;

  constructor() {
    this.canvas = document.createElement("canvas");
    this.canvas.width = SIZE;
    this.canvas.height = SIZE;
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: false,
      preserveDrawingBuffer: true,
      premultipliedAlpha: false,
    });
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(SIZE, SIZE, false);
    this.renderer.setClearColor(0x000000, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial());
    this.scene.add(this.mesh);
  }

  render(
    source: string,
    layer: Pick<SpectrumLayer, "colorFrom" | "colorTo">,
    time: number,
    cumulative: number,
    current: number,
    resolution: { x: number; y: number },
  ): void {
    if (source !== this.source) {
      this.material?.dispose();
      this.material = new THREE.ShaderMaterial({
        transparent: true,
        depthTest: false,
        depthWrite: false,
        vertexShader: SPECTRUM_VERTEX_SHADER,
        fragmentShader: source,
        uniforms: {
          u_resolution: { value: new THREE.Vector2(SIZE, SIZE) },
          u_itemSize: { value: 1000 },
          u_time: { value: 0 },
          u_audio_cumulative: { value: 0 },
          u_audio_current: { value: 0 },
          u_col1: { value: new THREE.Vector4(1, 1, 1, 1) },
          u_col2: { value: new THREE.Vector4(0, 0, 0, 1) },
        },
      });
      this.material.blending = THREE.NormalBlending;
      this.mesh.material = this.material;
      this.source = source;
    }
    if (!this.material) return;
    const uniforms = this.material.uniforms;
    // The reference builds the runtime-effect shader with the editor's render
    // size (`getRenderSize()`), not the item texture size.
    (uniforms.u_resolution.value as THREE.Vector2).set(resolution.x, resolution.y);
    uniforms.u_time.value = time;
    uniforms.u_audio_cumulative.value = cumulative;
    uniforms.u_audio_current.value = current;
    (uniforms.u_col1.value as THREE.Vector4).set(...hexRgb(layer.colorFrom), 1);
    (uniforms.u_col2.value as THREE.Vector4).set(...hexRgb(layer.colorTo), 1);
    this.renderer.render(this.scene, this.camera);
  }
}

let sharedStage: SharedShaderStage | null = null;

function stage(): SharedShaderStage {
  sharedStage ??= new SharedShaderStage();
  return sharedStage;
}

export class SpectrumShaderPaint {
  readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;

  constructor() {
    this.canvas = document.createElement("canvas");
    this.canvas.width = SIZE;
    this.canvas.height = SIZE;
    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas2D is unavailable");
    this.ctx = ctx;
  }

  /** Renders one frame; returns false when the shader has no usable source. */
  render(
    layer: Pick<SpectrumLayer, "shaderSrc" | "colorFrom" | "colorTo">,
    time: number,
    cumulative: number,
    current: number,
    resolution: { x: number; y: number },
  ): boolean {
    // Build the paint source immediately. Waiting for the asynchronous GPU
    // validation made the first click on a shader preset fall back to the solid
    // colour, so the same tile worked or not depending on what had been clicked
    // before. Validation still runs in the background and rejects a bad source
    // on the next frame.
    const wrapped = wrapSpectrumFragment(layer.shaderSrc, false, true);
    if (!wrapped.source) return false;
    const verdict = getShaderValidation(wrapped.source);
    if (verdict === undefined) void requestShaderValidation(wrapped.source);
    else if (verdict !== null) return false;
    const shared = stage();
    shared.render(wrapped.source, layer, time, cumulative, current, resolution);
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, SIZE, SIZE);
    this.ctx.drawImage(shared.canvas, 0, 0);
    return true;
  }

  dispose(): void {
    this.ctx.clearRect(0, 0, SIZE, SIZE);
    this.canvas.width = 0;
    this.canvas.height = 0;
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
