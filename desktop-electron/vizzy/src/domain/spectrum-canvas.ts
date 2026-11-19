/**
 * Canvas2D path renderer for Spectrum items.
 *
 * The reference draws spectra as Skia paths on a 1000×1000 item canvas and maps
 * that canvas with `preScaling`. This module reproduces the same path commands
 * with Canvas2D and uploads the result as a Three.js texture, so it can sit on
 * the existing Spectrum plane.
 *
 * It is used for the sourced presets whose layers are Solid/From-to; Shader
 * layers stay on the GPU fragment path until the SkSL runtime is wired in.
 */
import * as THREE from "three";
import {
  buildSpectrumDrawing,
  CUR_RAD,
  type PathCommand,
  type SpectrumPathSettings,
} from "./spectrum-path";
import type { SpectrumLayer } from "./spectrum-layers";
import { SpectrumShaderPaint } from "./spectrum-paint";

const ITEM_SIZE = 1000;
/**
 * Reference module 22 `o()`: `e ? e / 900 : getRenderSize().height / 900`.
 * Both the per-layer blur and the global shadow sigma are multiplied by it.
 */
const REFERENCE_BLUR_SCALE = 900;

export interface PathSettings extends SpectrumPathSettings {
  height: number; // percent
  lineWidth: number;
  lineCap: string;
  pathEffect: string;
  dashOffset: number;
  opacity: number;
  positionX: number;
  positionY: number;
  scaleX: number;
  scaleY: number;
  rotation: number;
  scaleMultiplier: number;
  globalShadow: boolean;
  globalShadowScale: number;
  globalShadowAlpha: number;
  globalShadowSigmaX: number;
  globalShadowSigmaY: number;
  /** Editor render size, passed to custom SkSL shaders as `u_resolution`. */
  renderWidth: number;
  renderHeight: number;
  /** Circle image disc (reference `drawCircleImage`). */
  fillCircle: boolean;
  circleSize: number;
  circleColor: string;
  circularImage: boolean;
  imageSize: number;
}

interface PathLayer extends Pick<
  SpectrumLayer,
  | "id"
  | "shaderSrc"
  | "colorType"
  | "color"
  | "colorFrom"
  | "colorTo"
  | "colorMix"
  | "baseOn"
  | "colorGradient"
  | "alpha"
  | "multiplier"
  | "ceiling"
  | "rotation"
  | "scale"
  | "blurAmount"
  | "shadowAlpha"
  | "shadowColor"
  | "shadowScale"
  | "enabled"
> {
  bands: Float32Array;
}

export class SpectrumCanvasRenderer {
  readonly canvas: HTMLCanvasElement;
  readonly texture: THREE.CanvasTexture;
  private readonly content: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private readonly contentCtx: CanvasRenderingContext2D;
  private readonly shaderPaints = new Map<string, SpectrumShaderPaint>();
  private scratch: HTMLCanvasElement | null = null;
  private scratchCtx: CanvasRenderingContext2D | null = null;
  private shadow: HTMLCanvasElement | null = null;
  private shadowCtx: CanvasRenderingContext2D | null = null;
  /** Texture rasterisation scale (1 = project resolution). */
  private renderScale = 1;

  // The reference draws spectra on the project's render surface. The node calls
  // `setSize` with the current drawing-buffer size, so a 614x345 preview does
  // not pay for a 1920x853 Canvas2D surface and 20px blur every frame (software
  // Canvas2D made that ~4fps); audit/export runs still use the project size.
  constructor(width = 1920, height = 853) {
    this.canvas = document.createElement("canvas");
    this.canvas.width = width;
    this.canvas.height = height;
    this.content = document.createElement("canvas");
    this.content.width = width;
    this.content.height = height;
    const ctx = this.canvas.getContext("2d");
    const contentCtx = this.content.getContext("2d");
    if (!ctx || !contentCtx) throw new Error("Canvas2D is unavailable");
    this.ctx = ctx;
    this.contentCtx = contentCtx;
    this.texture = new THREE.CanvasTexture(this.canvas);
    // Same reason as SkiaText: the 2D context paints the layer's authored sRGB
    // hexes and the frame is composited without an output encode, so an sRGB
    // tag decoded the bars to linear - `#FFC24A` measured (255,154,26) and the
    // gold-to-magenta ramp read as an orange-to-pink one.
    this.texture.colorSpace = THREE.NoColorSpace;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;
  }

  /** Match the project's render surface (preview pane or full project size). */
  setSize(width: number, height: number): void {
    const nextWidth = Math.max(1, Math.round(width * this.renderScale));
    const nextHeight = Math.max(1, Math.round(height * this.renderScale));
    if (this.canvas.width === nextWidth && this.canvas.height === nextHeight) return;
    // three allocates a canvas texture with immutable `texStorage2D` storage, so
    // uploading a resized canvas into it is rejected and the texture stays the
    // blank allocation. Drop the allocation whenever the surface changes (pane
    // -> full resolution); the next draw re-allocates at the new size.
    // Trade-off: a feedback chain that samples the spectrum in the same frame
    // (monochromatic-bloom's Transform loop) sees one empty allocation, which
    // costs that row ~10 points; reallocating without a blank frame is an open
    // refinement, not something to guess at here.
    this.texture.dispose();
    this.canvas.width = nextWidth;
    this.canvas.height = nextHeight;
    this.content.width = nextWidth;
    this.content.height = nextHeight;
    // Scratch/shadow canvases are rebuilt lazily at the new size.
    this.scratch = null;
    this.scratchCtx = null;
    this.shadow = null;
    this.shadowCtx = null;
    this.texture.needsUpdate = true;
  }

  /**
   * Rasterisation scale for the uploaded texture. A Spectrum item repaints and
   * re-uploads its whole surface every frame; at 1920x1080 that upload is the
   * dominant per-frame cost (measured on an RTX 3060: 2 nodes at 1.0 = 10 fps,
   * the same two at 0.5 = 30 fps). 1 keeps the reference's project-resolution
   * surface; templates opt into a smaller raster for frame rate.
   */
  setRenderScale(scale: number): void {
    const next = Math.min(1, Math.max(0.25, scale));
    if (next === this.renderScale) return;
    this.renderScale = next;
    this.canvas.width = 0;
  }

  draw(
    settings: PathSettings,
    layers: readonly PathLayer[],
    image: CanvasImageSource | null = null,
    time = 0,
    cumulative = 0,
    current = 0,
  ): void {
    const scale = this.renderScale;
    const width = this.canvas.width / scale;
    const height = this.canvas.height / scale;
    this.contentCtx.setTransform(scale, 0, 0, scale, 0, 0);
    this.contentCtx.clearRect(0, 0, width, height);
    this.contentCtx.save();
    this.applyItemTransform(this.contentCtx, settings, width, height);

    for (const layer of layers) {
      if (!layer.enabled || layer.bands.length <= 4) continue;
      this.drawLayer(this.contentCtx, layer, settings, height, width, time, cumulative, current);
    }
    if (["circle", "image"].includes(String(settings.spectrumType).toLowerCase())) {
      // Reference drawCircleImage runs after the layers: the black disc masks
      // the centre, leaving the audio-displaced ring outside it. Image items
      // use the same circle-backed rendering, with the supplied artwork as the
      // centre cover.
      this.drawCircleFill(this.contentCtx, settings);
      this.drawCircleImage(this.contentCtx, settings, image);
    }
    this.contentCtx.restore();

    const deviceWidth = this.canvas.width;
    const deviceHeight = this.canvas.height;
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, deviceWidth, deviceHeight);
    if (settings.globalShadow) {
      // `MakeBlur(sigmaX * o(), sigmaY * o())` where `o()` is height / 900.
      const sigmaX = Math.max(0, settings.globalShadowSigmaX) * (height / REFERENCE_BLUR_SCALE);
      const sigmaY = Math.max(0, settings.globalShadowSigmaY) * (height / REFERENCE_BLUR_SCALE);
      const shadowScale = Math.max(0.01, settings.globalShadowScale / 100);
      const alpha = Math.min(1, Math.max(0, settings.globalShadowAlpha / 100));
      const blurred = this.blurCopy(deviceWidth, deviceHeight, sigmaX, sigmaY);
      this.ctx.save();
      this.ctx.globalAlpha = alpha;
      // `translate(-w*(o-1)/2); scale(o)` scales about the item centre.
      this.ctx.translate(deviceWidth / 2, deviceHeight / 2);
      this.ctx.scale(shadowScale, shadowScale);
      this.ctx.translate(-deviceWidth / 2, -deviceHeight / 2);
      if (blurred) {
        this.ctx.save();
        this.ctx.scale(blurred.scaleX, blurred.scaleY);
        this.ctx.drawImage(blurred.canvas, 0, 0);
        this.ctx.restore();
      }
      this.ctx.restore();
    }
    this.ctx.drawImage(this.content, 0, 0);
    // A mirrored spectrum is a reflection: the template draws the same bars with
    // `scaleY: -1` under the waterline, and the reference's artwork fades that
    // copy with depth instead of ending it on a hard edge. Without the fade the
    // mirrored copy read as a smear when its raster is upscaled (top-pop: a flat
    // mauve band 58 px deep, alpha 0.45, no bar shapes). Mask the item with a
    // vertical gradient anchored on the mirror axis - one alpha ramp from the
    // bars' foot to their deepest tip - so the same geometry reads as water.
    this.fadeMirroredReflection(settings, layers, deviceWidth, deviceHeight);
    this.texture.needsUpdate = true;
  }

  /** Vertical alpha falloff for a `scaleY < 0` (reflection) spectrum. */
  private fadeMirroredReflection(
    settings: PathSettings,
    layers: readonly PathLayer[],
    deviceWidth: number,
    deviceHeight: number,
  ): void {
    if (!(settings.scaleY < 0)) return;
    // Bars grow from the item's origin; the origin's row on the stage is the
    // waterline. Same mapping as `applyItemTransform`: the y scale is height/1000.
    const axis = ((ITEM_SIZE / 2 + settings.positionY) / ITEM_SIZE) * deviceHeight;
    // Deepest mirrored tip, in device pixels: the tallest band (200 reference
    // units) scaled by the layer multiplier and the item's height percentage.
    const heightFactor = settings.height / 100;
    const pxPerUnit = deviceHeight / ITEM_SIZE;
    let deepest = 0;
    for (const layer of layers) {
      if (!layer.enabled) continue;
      const ceiling = layer.ceiling > 0 ? Math.min(200, layer.ceiling) : 200;
      deepest = Math.max(deepest, ceiling * layer.multiplier * heightFactor * pxPerUnit);
    }
    const fade = Math.max(12, deepest * 1.15);
    const gradient = this.ctx.createLinearGradient(0, axis, 0, axis + fade);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.45, "rgba(255,255,255,0.85)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    this.ctx.save();
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.globalCompositeOperation = "destination-in";
    this.ctx.fillStyle = gradient;
    this.ctx.fillRect(0, 0, deviceWidth, deviceHeight);
    this.ctx.restore();
  }

  /**
   * Drop GPU paints for layers that are no longer Shader layers. Without this,
   * a layer id reused by the next preset kept a paint (and its shader) alive,
   * so results depended on which presets had been applied before.
   */
  retainShaderLayers(active: ReadonlySet<string>): void {
    for (const [id, paint] of this.shaderPaints) {
      if (active.has(id)) continue;
      paint.dispose();
      this.shaderPaints.delete(id);
    }
  }

  dispose(): void {
    this.retainShaderLayers(new Set());
    this.texture.dispose();
    this.canvas.width = 0;
    this.canvas.height = 0;
    this.content.width = 0;
    this.content.height = 0;
    this.scratch = null;
    this.scratchCtx = null;
    this.shadow = null;
    this.shadowCtx = null;
  }

  private ensureScratch(width: number, height: number): CanvasRenderingContext2D {
    if (!this.scratch || this.scratch.width !== width || this.scratch.height !== height) {
      this.scratch = document.createElement("canvas");
      this.scratch.width = width;
      this.scratch.height = height;
      this.scratchCtx = this.scratch.getContext("2d");
    }
    if (!this.scratchCtx) throw new Error("Canvas2D is unavailable");
    return this.scratchCtx;
  }

  private ensureShadow(width: number, height: number): CanvasRenderingContext2D {
    if (!this.shadow || this.shadow.width !== width || this.shadow.height !== height) {
      this.shadow = document.createElement("canvas");
      this.shadow.width = width;
      this.shadow.height = height;
      this.shadowCtx = this.shadow.getContext("2d");
    }
    if (!this.shadowCtx) throw new Error("Canvas2D is unavailable");
    this.shadowCtx.setTransform(1, 0, 0, 1, 0, 0);
    return this.shadowCtx;
  }

  /**
   * Reference global shadow: `ImageFilter.MakeBlur(sigmaX, sigmaY)` over a
   * copy of the whole item, drawn behind the sharp copy. Canvas2D only exposes
   * one blur radius, so when the axes differ the wider axis is shrunk before
   * the blur and restored at composite time.
   */
  private blurCopy(
    width: number,
    height: number,
    sigmaX: number,
    sigmaY: number,
  ): { canvas: HTMLCanvasElement; scaleX: number; scaleY: number } | null {
    // A zero sigma still composites an unblurred copy in the reference
    // (`MakeBlur(0, 0)` returns no filter), so keep the shadow pass.
    const sx = Math.max(0.01, sigmaX);
    const sy = Math.max(0.01, sigmaY);
    const base = Math.min(sx, sy);
    const kx = base / sx;
    const ky = base / sy;
    const uniform = kx === 1 && ky === 1;
    let source: HTMLCanvasElement = this.content;
    if (!uniform) {
      const scaled = this.ensureScratch(width, height);
      scaled.clearRect(0, 0, width, height);
      scaled.setTransform(kx, 0, 0, ky, 0, 0);
      scaled.drawImage(this.content, 0, 0);
      scaled.setTransform(1, 0, 0, 1, 0, 0);
      source = this.scratch as HTMLCanvasElement;
    }
    const shadow = this.ensureShadow(width, height);
    shadow.clearRect(0, 0, width, height);
    shadow.filter = `blur(${base}px)`;
    shadow.drawImage(source, 0, 0);
    shadow.filter = "none";
    return { canvas: this.shadow as HTMLCanvasElement, scaleX: 1 / kx, scaleY: 1 / ky };
  }

  /**
   * Compose a GPU shader colour through the decompiled path coverage. The
   * reference uses the SkSL as a Skia paint; this is the same relationship.
   */
  private paintShaderLayer(
    ctx: CanvasRenderingContext2D,
    layer: PathLayer,
    settings: PathSettings,
    path: Path2D,
    fill: boolean,
    width: number,
    height: number,
    time: number,
    cumulative: number,
    current: number,
  ): boolean {
    let paint = this.shaderPaints.get(layer.id);
    if (!paint) {
      paint = new SpectrumShaderPaint();
      this.shaderPaints.set(layer.id, paint);
    }
    if (
      !paint.render(layer, time, cumulative, current, {
        x: settings.renderWidth,
        y: settings.renderHeight,
      })
    ) {
      return false;
    }

    const bars = String(settings.spectrumType).toLowerCase() === "bars";
    const deviceWidth = this.canvas.width;
    const deviceHeight = this.canvas.height;
    const scratch = this.ensureScratch(deviceWidth, deviceHeight);
    scratch.setTransform(1, 0, 0, 1, 0, 0);
    scratch.clearRect(0, 0, deviceWidth, deviceHeight);
    scratch.setTransform(this.renderScale, 0, 0, this.renderScale, 0, 0);
    scratch.save();
    this.applyItemTransform(scratch, settings, width, height);
    // `drawSpectrumPoints` rotates the canvas before the path is built and
    // `drawPath` scales it, so the paint's local space rotates/scales too.
    scratch.rotate(((layer.rotation - (bars ? 90 : 0)) / 180) * Math.PI);
    scratch.scale(layer.scale, layer.scale);
    scratch.drawImage(paint.canvas, -ITEM_SIZE / 2, -ITEM_SIZE / 2, ITEM_SIZE, ITEM_SIZE);
    scratch.restore();

    scratch.save();
    this.applyItemTransform(scratch, settings, width, height);
    scratch.rotate(((layer.rotation - (bars ? 90 : 0)) / 180) * Math.PI);
    scratch.scale(layer.scale, layer.scale);
    scratch.globalCompositeOperation = "destination-in";
    scratch.fillStyle = "#ffffff";
    scratch.strokeStyle = "#ffffff";
    scratch.lineWidth = settings.lineWidth;
    scratch.lineCap = settings.lineCap as CanvasLineCap;
    scratch.lineJoin = "round";
    applyPathEffect(scratch, settings);
    if (fill) scratch.fill(path, settings.clipCircle ? "evenodd" : "nonzero");
    else scratch.stroke(path);
    scratch.restore();

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    // A paint shader replaces the paint's colour, alpha included: the reference's
    // Skia `paint.setShader` means the layer's `alpha` does not modulate it.
    ctx.globalAlpha = Math.min(1, Math.max(0, settings.opacity / 100));
    ctx.drawImage(scratch.canvas, 0, 0);
    ctx.restore();
    return true;
  }

  /**
   * Alpha mask for a Shader layer. The reference uses a Skia paint shader, so
   * its custom SkSL only colours pixels inside the spectrum path; this mask is
   * what clips the GPU shader output to the decompiled path geometry.
   */
  drawMask(settings: PathSettings, layer: PathLayer): void {
    const width = this.canvas.width / this.renderScale;
    const height = this.canvas.height / this.renderScale;
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.ctx.setTransform(this.renderScale, 0, 0, this.renderScale, 0, 0);
    if (!layer.enabled || layer.bands.length <= 4) {
      this.texture.needsUpdate = true;
      return;
    }
    const drawing = buildSpectrumDrawing(
      layer.bands,
      settings,
      layer.multiplier * (settings.height / 100),
    );
    if (drawing.commands.length === 0) {
      this.texture.needsUpdate = true;
      return;
    }
    const bars = String(settings.spectrumType).toLowerCase() === "bars";
    this.ctx.save();
    this.applyItemTransform(this.ctx, settings, width, height);
    this.ctx.rotate(((layer.rotation - (bars ? 90 : 0)) / 180) * Math.PI);
    this.ctx.scale(layer.scale, layer.scale);
    this.ctx.fillStyle = "#ffffff";
    this.ctx.strokeStyle = "#ffffff";
    this.ctx.lineWidth = settings.lineWidth;
    this.ctx.lineCap = settings.lineCap as CanvasLineCap;
    this.ctx.lineJoin = "round";
    applyPathEffect(this.ctx, settings);
    const path = pathFromCommands(drawing.commands);
    if (String(settings.fillStyle).toLowerCase() === "fill") {
      this.ctx.fill(path, settings.clipCircle ? "evenodd" : "nonzero");
    } else {
      this.ctx.stroke(path);
    }
    this.ctx.restore();
    this.texture.needsUpdate = true;
  }

  /** Background disc for a Circle spectrum (`fillCircle` + `circleColor`). */
  private drawCircleFill(ctx: CanvasRenderingContext2D, settings: PathSettings): void {
    const radius = CUR_RAD * settings.circleSize;
    if (!settings.fillCircle || radius <= 0) return;
    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fillStyle = settings.circleColor;
    ctx.fill();
    ctx.restore();
  }

  /** Reference `drawCircleImage`: the image square, clipped when circular. */
  private drawCircleImage(
    ctx: CanvasRenderingContext2D,
    settings: PathSettings,
    image: CanvasImageSource | null,
  ): void {
    if (!image) return;
    const size = Math.max(1, settings.imageSize * CUR_RAD * 1.96);
    ctx.save();
    if (settings.circularImage) {
      ctx.beginPath();
      ctx.arc(0, 0, size / 2, 0, Math.PI * 2);
      ctx.clip();
    }
    ctx.drawImage(image, -size / 2, -size / 2, size, size);
    ctx.restore();
  }

  private applyItemTransform(
    ctx: CanvasRenderingContext2D,
    settings: PathSettings,
    width: number,
    height: number,
  ): void {
    const aspect = width / height;
    ctx.scale(width / ITEM_SIZE, height / ITEM_SIZE);
    ctx.translate(ITEM_SIZE / 2 + settings.positionX, ITEM_SIZE / 2 + settings.positionY);
    ctx.scale(settings.scaleX * settings.scaleMultiplier, settings.scaleY * settings.scaleMultiplier);
    if (Math.abs(aspect - 1) > 1e-6) ctx.scale(1 / aspect, 1);
    ctx.rotate((settings.rotation / 180) * Math.PI);
  }

  private drawLayer(
    ctx: CanvasRenderingContext2D,
    layer: PathLayer,
    settings: PathSettings,
    height: number,
    width: number,
    time: number,
    cumulative: number,
    current: number,
  ): void {
    const bars = String(settings.spectrumType).toLowerCase() === "bars";
    const drawing = buildSpectrumDrawing(
      layer.bands,
      settings,
      layer.multiplier * (settings.height / 100),
    );
    if (drawing.commands.length === 0) return;

    ctx.save();
    ctx.rotate(((layer.rotation - (bars ? 90 : 0)) / 180) * Math.PI);
    ctx.scale(layer.scale, layer.scale);
    ctx.globalAlpha = Math.min(
      1,
      Math.max(0, layer.alpha * (settings.opacity / 100)),
    );

    const path = pathFromCommands(drawing.commands);
    const fill = String(settings.fillStyle).toLowerCase() === "fill";

    if (layer.colorType === "Shader") {
      if (this.paintShaderLayer(ctx, layer, settings, path, fill, width, height, time, cumulative, current)) {
        ctx.restore();
        return;
      }
    }

    const style = this.layerStyle(ctx, layer, settings, bars);

    if (layer.shadowAlpha > 0 && layer.blurAmount > 0) {
      ctx.save();
      ctx.filter = `blur(${layer.blurAmount * (height / REFERENCE_BLUR_SCALE)}px)`;
      ctx.globalAlpha *= Math.min(1, layer.shadowAlpha);
      ctx.fillStyle = layer.shadowColor;
      ctx.strokeStyle = layer.shadowColor;
      ctx.lineWidth = settings.lineWidth;
      ctx.scale(layer.shadowScale, layer.shadowScale);
      if (fill) ctx.fill(path);
      else ctx.stroke(path);
      ctx.restore();
    }

    if (fill) {
      ctx.fillStyle = style;
      // clipCircle appends an inner arc as a hole; even-odd is the reliable
      // winding-independent way to keep it open.
      ctx.fill(path, settings.clipCircle ? "evenodd" : "nonzero");
    } else {
      ctx.strokeStyle = style;
      ctx.lineWidth = settings.lineWidth;
      ctx.lineCap = settings.lineCap as CanvasLineCap;
      ctx.lineJoin = "round";
      applyPathEffect(ctx, settings);
      ctx.stroke(path);
    }
    ctx.restore();
  }

  private layerStyle(
    ctx: CanvasRenderingContext2D,
    layer: PathLayer,
    settings: PathSettings,
    bars: boolean,
  ): string | CanvasGradient {
    if (layer.colorType === "From-to") {
      const mix = Math.min(1, Math.max(0.001, layer.colorMix));
      if (layer.baseOn === "Value") {
        return mixHex(layer.colorFrom, layer.colorTo, mix);
      }
      if (layer.baseOn === "Distance from center") {
        const radius = 750 * mix;
        const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
        gradient.addColorStop(0, layer.colorFrom);
        gradient.addColorStop(1, layer.colorTo);
        return gradient;
      }
      const radius = 750 * mix;
      const gradient = ctx.createLinearGradient(-radius, 0, radius, 0);
      gradient.addColorStop(0, layer.colorTo);
      gradient.addColorStop(0.5, layer.colorFrom);
      gradient.addColorStop(1, layer.colorTo);
      if (layer.baseOn === "Y-Position") {
        const vertical = ctx.createLinearGradient(0, -radius, 0, radius);
        vertical.addColorStop(0, layer.colorTo);
        vertical.addColorStop(0.5, layer.colorFrom);
        vertical.addColorStop(1, layer.colorTo);
        return vertical;
      }
      return gradient;
    }

    if (layer.colorType === "Gradient") {
      const stops = [
        layer.colorFrom,
        ...layer.colorGradient.split(/[:|,]/).filter(Boolean),
        layer.colorTo,
      ];
      const gradient = ctx.createLinearGradient(-CUR_RAD, 0, CUR_RAD, 0);
      stops.forEach((color, index) => {
        gradient.addColorStop(stops.length === 1 ? 0 : index / (stops.length - 1), color);
      });
      return gradient;
    }

    return layer.color;
  }
}

function pathFromCommands(commands: readonly PathCommand[]): Path2D {
  const path = new Path2D();
  for (const command of commands) {
    switch (command.type) {
      case "move":
        path.moveTo(command.x, command.y);
        break;
      case "line":
        path.lineTo(command.x, command.y);
        break;
      case "quad":
        path.quadraticCurveTo(command.cx, command.cy, command.x, command.y);
        break;
      case "arc":
        path.arc(command.x, command.y, command.r, command.start, command.end, command.ccw);
        break;
      case "close":
        path.closePath();
        break;
    }
  }
  return path;
}

function applyPathEffect(ctx: CanvasRenderingContext2D, settings: PathSettings): void {
  // `PathEffect.MakeDash([t, t], 1)` / `MakeDiscrete(3, 2, 1)`: both use phase 1.
  ctx.lineDashOffset = 1;
  if (settings.pathEffect === "dash") {
    ctx.setLineDash([settings.dashOffset, settings.dashOffset]);
  } else if (settings.pathEffect === "discrete") {
    ctx.setLineDash([3, 2]);
  } else {
    ctx.setLineDash([]);
  }
}

function mixHex(from: string, to: string, t: number): string {
  const a = parseHex(from);
  const b = parseHex(to);
  if (!a || !b) return from;
  const mix = (index: number): number => Math.round(a[index] + (b[index] - a[index]) * t);
  return `rgb(${mix(0)}, ${mix(1)}, ${mix(2)})`;
}

function parseHex(hex: string): [number, number, number] | null {
  const raw = hex.trim().replace(/^#/, "");
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((char) => char + char)
          .join("")
      : raw;
  if (!/^[0-9a-f]{6}$/i.test(full)) return null;
  return [0, 2, 4].map((offset) => parseInt(full.slice(offset, offset + 2), 16)) as [
    number,
    number,
    number,
  ];
}
