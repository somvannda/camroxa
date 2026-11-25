import * as THREE from "three";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
import type { AnyNode, NodeContext } from "../domain/nodes";
import type { AssetStore, CompositionLayer, Project } from "../domain/project";
import { affectsGlobal, effectOrder, GLOBAL_TARGET, type EffectInstance } from "../domain/effects";
import {
  analyzerGain,
  frequencyScaleIndex,
  perBandWeightingIndex,
  sampleProviderIndex,
  windowFunctionIndex,
  type Analyzer,
} from "../domain/analyzers";
import { AnalyzerBank } from "../audio/analyzer-bank";
import { AnalyserManager, type AnalyserHandle } from "../audio/vizzy-analyzer";
import { PostProcessingManager } from "./post-processing";
import { resetCameraShakeSeed } from "../domain/camera-shake";
import type { SpectrumAnalyser } from "../audio/spectrum";

/** Analysis window in samples for a duration, in the source's sample rate. */
function analyzerWindow(durationMs: number, sampleRate: number): number {
  return Math.round((Math.max(1, durationMs) / 1000) * sampleRate);
}

/**
 * Stage renderer.
 *
 * The project is treated as a fixed-size stage (1920x1080 by default) mapped to
 * an orthographic camera, so element coordinates are stable regardless of the
 * preview size. Node meshes live in their own groups and are ordered by `z`.
 */
const REFERENCE_UNIT_3D = new Set([
  "Particles",
  "Spherical Field",
  "Model",
  "Ground",
  "Line Bed",
  "Particle Lines",
  "Confetti",
  "Particle System",
  "Instanced Particle System",
  "Timeline",
  "Shader Item",
]);

/**
 * Primitives are authored in the reference's 1000-unit stage (a 1024 plane is
 * 2.05 world units and `position:z` is raw). A perspective layer holding one
 * therefore needs its camera in that same 2/1000 unit; a project-pixel unit
 * made the camera 2.8x too far away on 360-tall projects.
 *
 * Noise is the same kind of item: `NoiseNode` builds a 1024-unit plane scaled
 * by `2/1000`, so a Noise layer's camera has to use that unit too (`code-286`'s
 * dot wall sat at 91% of the reference's width/height with the project-pixel
 * camera).
 */
const REFERENCE_STAGE_PRIMITIVES = new Set(["Plane", "Cube", "Square", "Point Light", "Noise"]);

/** Scratch matrix for folding a layer camera's authored scale into its projection. */
const cameraScaleMatrix = new THREE.Matrix4();

/**
 * Which frame context `render()` hands the effect chain.
 *
 * `auto` is the reference's own rule: a render whose playhead equals the
 * previous one is a repeat (`rerender`) frame and carries the initial
 * `time: 0`. `playback` declares a live playback step even when the playhead
 * repeats, which is what a capture needs when it is reproducing a frame the
 * reference rendered while playing (see `render()`).
 */
export type FrameClock = "auto" | "playback";

export class StageRenderer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  private background = new THREE.Color("#000000");
  readonly camera: THREE.OrthographicCamera;
  private perspectiveCamera: THREE.PerspectiveCamera | null = null;
  private readonly drawBuffer = new THREE.Vector2();
  private readonly analyzerBank = new AnalyzerBank();
  private readonly engineCache = new Map<string, { time: number; slots: Float32Array }>();
  private analyserManager: AnalyserManager | null = null;
  private analyserManagerPending = false;
  private readonly analyserContexts = new Map<
    string,
    { signature: string; handle: AnalyserHandle }
  >();
  private readonly wasmResults = new Map<string, Float32Array>();
  private wasmFrameTime = Number.NaN;
  private sharedFrame: { time: number; buffer: Float32Array } | null = null;
  private frameTime = 0;
  private lastFrameTime: number | null = null;
  /**
   * The reference hands every `renderEffect` a frame context
   * (`{time, fps, frameIndex, rerender}`) and a seek or paused re-render falls
   * back to the *initial* context `{time: 0, fps: 60, frameIndex: 0,
   * rerender: true}` (`docs/camera-shake-phase.md` §2: "renders with no
   * argument, which falls back to that initial frame info"). Passes that read
   * the context clock (`uTime`) therefore see **0**, not the playhead, whenever
   * the frame is not a playback step. `render()` flags that case here.
   */
  private frameRerender = false;
  private lastRenderedTime: number | null = null;
  private use3D = false;
  private fullResolution = false;
  /** Explicit framebuffer while an export owns the renderer. */
  private exportSize: { width: number; height: number } | null = null;
  private playing = false;
  private resizeObserver: ResizeObserver;
  private context: NodeContext;

  private readonly postProcessing = new PostProcessingManager();
  /** One composer per composition layer, as the reference gives each Layer one. */
  private readonly layerPostProcessing = new Map<string, PostProcessingManager>();
  /** Finished frames for layers that other layer effects can sample. */
  private readonly layerTargets = new Map<string, THREE.WebGLRenderTarget>();
  private readonly layerCompositor = new PostProcessingManager();
  /** Perspective camera for 3D layers (the reference uses fov 45, near 1, far 1000). */
  private readonly particleCamera = new THREE.PerspectiveCamera(45, 16 / 9, 1, 100000);
  /** One reference camera per composition layer (Layer.position/rotation/scale). */
  private readonly layerOrthoCameras = new Map<string, THREE.OrthographicCamera>();
  /** Which camera each node's layer resolved to on the last render. */
  private readonly nodeOrthoLayer = new Map<string, boolean>();
  private readonly layerPerspectiveCameras = new Map<string, THREE.PerspectiveCamera>();

  /** Reference transform gizmo (I toggles, W/E/R switch modes). */
  private transformControls: TransformControls | null = null;
  private transformHelper: THREE.Object3D | null = null;
  private transformTarget: AnyNode | null = null;
  private transformEnabled = false;
  private transformMode: "translate" | "rotate" | "scale" = "translate";
  private gizmoSuppressed = false;
  /** Reference Ctrl+H state: shy objects are hidden while this is on. */
  private hideShyLayers = true;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly project: Project,
    private readonly assets: AssetStore,
    private readonly spectrum: SpectrumAnalyser,
  ) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x0e0e12, 1);

    const aspect = project.width / project.height;
    this.camera = new THREE.OrthographicCamera(-aspect, aspect, 1, -1, -100, 100);
    this.camera.position.z = 10;

    this.context = {
      spectrum: () => spectrum.value(),
      waveform: () => spectrum.waveform(),
      waveformWindow: (samples, time) => spectrum.windowFor(samples, time),
      waveformWindowChannels: (samples, time) => [
        spectrum.windowForChannel(samples, time, 0),
        spectrum.windowForChannel(samples, time, 1),
      ],
      sampleRate: () => spectrum.sampleRate,
      texture: (assetId) => this.assets.get(assetId),
      analyzerBands: (analyzerId) =>
        this.project.analyzers.find((analyzer) => analyzer.id === analyzerId)?.sampleOutCount ??
        null,
      analyzerGain: (analyzerId) => {
        const analyzer = this.project.analyzers.find((item) => item.id === analyzerId);
        return analyzer ? analyzerGain(analyzer) : null;
      },
      spectrumScanFor: (analyzerId) => {
        // Single-context analysis for the audio-impact scan: results are
        // identical to `spectrumFor` (same shared frame, same `_analyse`), but
        // the other open analysers are not recomputed.
        const analyzer = this.project.analyzers.find((item) => item.id === analyzerId);
        if (!analyzer) return null;
        const handle = this.ensureAnalyserHandle(analyzer);
        const manager = this.analyserManager;
        if (!handle || !manager) return this.context.spectrumFor?.(analyzerId) ?? null;
        const frame = this.analysisFrame();
        manager.analyseOne(handle, frame, this.spectrum.sampleRate);
        const values = manager.result(handle, analyzer.sampleOutCount);
        return values.length ? this.analyzerBank.fromValues(values, analyzer.id) : null;
      },
      spectrumBandsFor: (analyzerId) => {
        // Native `sampleOutCount` series: the reference feeds exactly these
        // values to the spectrum path, while the 256-slot array only exists for
        // the shader's fixed-size texture. Running the normal spectrum lookup
        // first fills the native series (and drives the analyser).
        const analyzer = this.project.analyzers.find((item) => item.id === analyzerId);
        if (!analyzer) return null;
        this.context.spectrumFor?.(analyzerId);
        return this.analyzerBank.nativeValues(analyzer.id);
      },
      defaultAnalyzerId: () => {
        // The reference's Default analyzer object is permanent and is what an
        // unbound spectrum layer reads; imported projects export it as
        // `analyzer:default`, a fresh project creates it as `analyzer_default`.
        const analyzers = this.project.analyzers;
        const preferred = analyzers.find(
          (analyzer) => analyzer.id === "analyzer:default" || analyzer.name === "Default",
        );
        return (preferred ?? analyzers[0])?.id ?? null;
      },
      maxAudioImpact: () => this.project.audioImpactMax,
      spectrumFor: (analyzerId) => {
        const analyzer = this.project.analyzers.find((item) => item.id === analyzerId);
        if (!analyzer) return null;

        // Prefer the reference's own analyser; fall back to our engines until
        // the wasm manager finishes loading.
        const handle = this.ensureAnalyserHandle(analyzer);
        if (handle) {
          // The reference manager analyses one shared frame per update; each
          // analyser selects its own window inside it.
          this.analyseWasmFrame();
          const values = this.wasmResults.get(analyzer.id);
          if (values) return this.analyzerBank.fromValues(values, analyzer.id);
        }

        // Each analyser transforms a window sized to its own analysis duration.
        // Both providers have exact pre-wasm ports: the constant-Q filter bank
        // and the Goertzel bank.
        const size = analyzerWindow(analyzer.audioDuration, spectrum.sampleRate);
        const cached = this.engineCache.get(analyzer.id);
        if (cached && cached.time === this.frameTime) return cached.slots;
        const clamped = Math.max(128, Math.min(32768, size + (size % 4)));
        const slots = this.analyzerBank.bandsFromEngine(
          this.analysisFrame(),
          {
            id: analyzer.id,
            provider:
              sampleProviderIndex(analyzer.sampleProvider) === 0
                ? "filter bank"
                : "goertzel",
            smoothingTimeConstant: analyzer.smoothingTimeConstant ?? 0,
            perBandFrequencyTilt: analyzer.perBandFrequencyTilt ?? 0,
            perBandWeightingIndex: perBandWeightingIndex(analyzer.perBandWeighting ?? "a"),
            perBandWeightingAmount: analyzer.perBandWeightingAmount ?? 0,
            cqt: {
              sampleRate: spectrum.sampleRate,
              sampleInCount: clamped,
              sampleOutCount: analyzer.sampleOutCount,
              minHz: analyzer.frequencyRange[0],
              maxHz: analyzer.frequencyRange[1],
              frequencyScale: analyzer.frequencyScale ?? "linear",
              hzLinearFactor: analyzer.hzLinearFactor ?? 0.5,
              windowIndex: windowFunctionIndex(analyzer.windowFunction),
              windowParameter: analyzer.windowParameter ?? 1,
              windowSkew: analyzer.windowSkew ?? 0,
              cqtResolution: analyzer.cqtResolution ?? 7,
              cqtBandwidth: analyzer.cqtBandwidth ?? 8,
              cqtWindowIndex: windowFunctionIndex(analyzer.cqtWindowFunction ?? "hann"),
              cqtWindowParameter: analyzer.cqtWindowParameter ?? 1,
              cqtWindowSkew: analyzer.cqtWindowSkew ?? 0,
              spectrumConstantQ: analyzer.spectrumConstantQ ?? false,
              outputMultiplier: analyzer.outputMultiplier,
              downSample: analyzer.downSample ? 1 : 0,
              audioOffset: analyzer.audioOffset,
              audioReactionAlignment: analyzer.audioReactionAlignment,
            },
          },
        );
        this.engineCache.set(analyzer.id, { time: this.frameTime, slots });
        return slots;
      },
      resolution: () => {
        this.renderer.getDrawingBufferSize(this.drawBuffer);
        return { x: this.drawBuffer.x, y: this.drawBuffer.y };
      },
      projectDuration: () => this.project.duration,
      projectName: () => this.project.name,
      globalVar: (index) => this.project.globals[index] ?? 0,
      audioName: () => "",
      layerTexture: (layerId) => this.layerTargets.get(layerId)?.texture ?? null,
      // Before a layer has been drawn once this frame, fall back to its declared
      // camera so an import's very first frame is not 500x off; afterwards the
      // resolved camera from `layerCameraFor` is authoritative (a layer can be
      // implicitly perspective through its 3D items).
      orthographicLayer: (nodeId) => {
        const resolved = this.nodeOrthoLayer.get(nodeId);
        if (resolved !== undefined) return resolved;
        const layer = this.project.layers.find((item) => item.nodeIds.includes(nodeId));
        return layer?.camera?.type !== "Perspective";
      },
      playing: () => this.playing,
    };

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement ?? canvas);
    this.resize();
  }

  makeContext(): NodeContext {
    return this.context;
  }

  /* ------------------------------------------------------------------ */
  /* Transform gizmo (reference I / W / E / R)                           */
  /* ------------------------------------------------------------------ */

  private ensureTransformControls(): TransformControls {
    if (this.transformControls) return this.transformControls;
    const controls = new TransformControls(this.particleCamera, this.canvas);
    controls.setSize(0.8);
    controls.mode = this.transformMode;
    controls.addEventListener("objectChange", () => {
      this.transformTarget?.applyGizmoDelta();
    });
    this.transformControls = controls;
    this.transformHelper = controls.getHelper();
    this.transformHelper.visible = false;
    this.scene.add(this.transformHelper);
    return controls;
  }

  /** Target the gizmo at a 3D item, or clear it. */
  setGizmoTarget(node: AnyNode | null): void {
    const target = node && node.is3D ? node : null;
    this.transformTarget = target;
    if (!target) {
      if (this.transformHelper) this.transformHelper.visible = false;
      this.transformControls?.detach();
      return;
    }
    const controls = this.ensureTransformControls();
    controls.attach(target.group);
    target.captureGizmoBase();
  }

  setGizmoEnabled(enabled: boolean): void {
    this.transformEnabled = enabled;
    if (this.transformHelper) this.transformHelper.visible = false;
  }

  setPlaying(playing: boolean): void {
    this.playing = playing;
  }

  setHideShyLayers(hidden: boolean): void {
    this.hideShyLayers = hidden;
  }

  /** Exports and screenshots must never include the editor gizmo. */
  setGizmoSuppressed(suppressed: boolean): void {
    this.gizmoSuppressed = suppressed;
    if (suppressed && this.transformHelper) this.transformHelper.visible = false;
  }

  setGizmoMode(mode: "translate" | "rotate" | "scale"): void {
    this.transformMode = mode;
    if (this.transformControls) this.transformControls.mode = mode;
  }

  gizmoState(): { enabled: boolean; mode: string; target: string | null; attached: boolean } {
    return {
      enabled: this.transformEnabled,
      mode: this.transformMode,
      target: this.transformTarget?.id ?? null,
      attached: Boolean(this.transformControls?.object),
    };
  }

  /** Shows the gizmo only in the pass that renders the target's layer. */
  private updateGizmoForLayer(layer: CompositionLayer, camera: THREE.Camera): void {
    if (!this.transformHelper) return;
    const target = this.transformTarget;
    const perspective = layer.camera
      ? layer.camera.type === "Perspective"
      : this.project.nodes.some((node) => node.is3D && layer.nodeIds.includes(node.id));
    const visible =
      !this.gizmoSuppressed &&
      this.transformEnabled &&
      Boolean(target) &&
      perspective &&
      layer.nodeIds.includes(target?.id ?? "");
    this.transformHelper.visible = visible;
    if (visible && this.transformControls) this.transformControls.camera = camera;
  }

  attach(node: AnyNode): void {
    node.group.userData.node = node;
    this.scene.add(node.group);
  }

  detach(node: AnyNode): void {
    this.scene.remove(node.group);
  }

  /** Permanently remove a node and release its GPU/Canvas resources. */
  disposeNode(node: AnyNode): void {
    this.scene.remove(node.group);
    (node as AnyNode & { dispose?: () => void }).dispose?.();
  }

  /**
   * Drop every per-layer render target and effect buffer. Layer ids are
   * project-scoped, and a project import reuses this renderer, so keeping the
   * old targets would leak two full-resolution buffers per layer on every
   * import; a 90-template run then runs out of GPU memory and loses the WebGL
   * context (all later frames become blank).
   */
  resetLayers(): void {
    resetCameraShakeSeed();
    for (const target of this.layerTargets.values()) target.dispose();
    this.layerTargets.clear();
    for (const manager of this.layerPostProcessing.values()) manager.dispose();
    this.layerPostProcessing.clear();
  }

  /**
   * Drop cached wasm analysers and band filters for analyzers that no longer
   * belong to the project. Presets create new analyzers on every apply, exactly
   * like the reference, so without pruning the old instances would retain wasm
   * memory and make later presets slower or fail to initialize.
   */
  retainAnalyzers(ids: Iterable<string>): void {
    const keep = new Set(ids);
    let removed = false;
    for (const [id, entry] of this.analyserContexts) {
      if (keep.has(id)) continue;
      removed = true;
      this.analyserManager?.close(entry.handle);
      this.analyserContexts.delete(id);
      this.wasmResults.delete(id);
    }
    // Closing a context frees its slot on the shared heap, and re-initialising on
    // the same module returned stale bands for the low layer after a template
    // replacement. Drop the module and rebuild it, like the reference manager's
    // `clear()`, so every new context starts on a clean heap.
    if (removed) {
      for (const entry of this.analyserContexts.values()) {
        this.analyserManager?.close(entry.handle);
      }
      this.analyserContexts.clear();
      this.wasmResults.clear();
      this.analyserManager = null;
      this.analyserManagerPending = false;
      this.wasmFrameTime = Number.NaN;
    }
    for (const id of this.engineCache.keys()) {
      if (!keep.has(id)) this.engineCache.delete(id);
    }
    this.analyzerBank.retain(keep);
  }

  reorder(nodes: AnyNode[]): void {
    nodes.forEach((node, index) => {
      node.group.renderOrder = index;
      // Node order composes with the order inside the node: a Spectrum's layer
      // passes must still paint 0..6 even though the whole node has its own rank.
      node.group.children.forEach((child, childIndex) => {
        child.renderOrder = index * 100 + childIndex;
      });
    });
  }

  /** Render at the project resolution instead of the on-screen pane size. */
  setFullResolution(enabled: boolean): void {
    this.fullResolution = enabled;
    this.resize();
  }

  get fullResolutionEnabled(): boolean {
    return this.fullResolution;
  }

  resize(): void {
    // During an export the renderer owns an explicit framebuffer size. A shell
    // panel resize must not shrink it mid-render or frames use the wrong stride.
    if (this.exportSize) {
      this.renderer.setPixelRatio(1);
      this.renderer.setSize(this.exportSize.width, this.exportSize.height, false);
      return;
    }

    const parent = this.canvas.parentElement;
    if (!parent) return;

    // The stage keeps the project's aspect inside the pane instead of filling
    // it: a stretched canvas made circles into ellipses and clipped the sides.
    const paneWidth = Math.max(1, parent.clientWidth);
    const paneHeight = Math.max(1, parent.clientHeight);
    const aspect = this.project.width / this.project.height;
    let width = paneWidth;
    let height = width / aspect;
    if (height > paneHeight) {
      height = paneHeight;
      width = height * aspect;
    }

    // The reference WebGLManager renders at the project resolution and lets CSS
    // scale the canvas down to the stage pane, so full-quality passes use that
    // size. The interactive preview stays at the displayed size (times the
    // device pixel ratio, capped at the project): rendering a 1920x1080 project
    // into a 614px pane multiplied every layer/effect pass by ~10 and made the
    // refreshed studio feel laggy.
    this.renderer.setPixelRatio(1);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const bufferWidth = this.fullResolution
      ? this.project.width
      : Math.min(this.project.width, Math.max(1, Math.round(width * dpr)));
    const bufferHeight = this.fullResolution
      ? this.project.height
      : Math.min(this.project.height, Math.max(1, Math.round(height * dpr)));
    this.renderer.setSize(bufferWidth, bufferHeight, false);
    this.canvas.style.width = `${Math.round(width)}px`;
    this.canvas.style.height = `${Math.round(height)}px`;

    this.camera.left = -aspect;
    this.camera.right = aspect;
    this.camera.top = 1;
    this.camera.bottom = -1;
    this.camera.updateProjectionMatrix();
  }

  /** Toggle the reference's 3D mode: perspective view instead of flat ortho. */
  set3D(on: boolean): boolean {
    this.use3D = on;
    if (on && !this.perspectiveCamera) {
      const aspect = this.project.width / this.project.height;
      this.perspectiveCamera = new THREE.PerspectiveCamera(50, aspect, 0.1, 100);
      this.perspectiveCamera.position.set(0, 0, 3.4);
    }
    if (on && this.perspectiveCamera) {
      this.perspectiveCamera.aspect = this.project.width / this.project.height;
      this.perspectiveCamera.updateProjectionMatrix();
    }
    return this.use3D;
  }

  /** The reference's shared analysis frame, rebuilt once per rendered frame. */
  private analysisFrame(): Float32Array {
    if (!this.sharedFrame || this.sharedFrame.time !== this.frameTime) {
      this.sharedFrame = {
        time: this.frameTime,
        buffer: this.spectrum.analysisFrame(this.frameTime),
      };
    }
    return this.sharedFrame.buffer;
  }

  /** Settings the reference analyser expects for one analyzer. */
  private analyserSettings(analyzer: Analyzer) {
    return {
      sampleRate: this.spectrum.sampleRate,
      sampleInCount: Math.round((analyzer.audioDuration / 1000) * this.spectrum.sampleRate),
      sampleOutCount: analyzer.sampleOutCount,
      minHz: analyzer.frequencyRange[0],
      maxHz: analyzer.frequencyRange[1],
      windowIndex: windowFunctionIndex(analyzer.windowFunction),
      providerIndex: sampleProviderIndex(analyzer.sampleProvider),
      outputMultiplier: analyzer.outputMultiplier,
      audioOffset: analyzer.audioOffset,
      smoothingTimeConstant: analyzer.smoothingTimeConstant,
      audioReactionAlignment: analyzer.audioReactionAlignment,
      windowParameter: analyzer.windowParameter,
      windowSkew: analyzer.windowSkew,
      frequencyScaleIndex: frequencyScaleIndex(analyzer.frequencyScale ?? "linear"),
      hzLinearFactor: analyzer.hzLinearFactor,
      cqtResolution: analyzer.cqtResolution,
      cqtBandwidth: analyzer.cqtBandwidth,
      cqtWindowIndex: windowFunctionIndex(analyzer.cqtWindowFunction ?? "hann"),
      cqtWindowParameter: analyzer.cqtWindowParameter,
      cqtWindowSkew: analyzer.cqtWindowSkew,
      spectrumConstantQ: analyzer.spectrumConstantQ ?? false,
      downSample: analyzer.downSample ? 1 : 0,
      perBandWeightingIndex: perBandWeightingIndex(analyzer.perBandWeighting ?? "a"),
      perBandWeightingAmount: analyzer.perBandWeightingAmount ?? 0,
      perBandFrequencyTilt: analyzer.perBandFrequencyTilt ?? 0,
    };
  }

  /**
   * Lazily opens the reference analyser context for one analyzer; null until the
   * shared manager is ready. Like the reference, every analyzer lives in one
   * module and is analysed in a single `_analyse_multiple` batch per frame.
   */
  private ensureAnalyserHandle(analyzer: Analyzer): AnalyserHandle | null {
    const settings = this.analyserSettings(analyzer);
    const signature = JSON.stringify(settings);

    const existing = this.analyserContexts.get(analyzer.id);
    if (existing) {
      if (existing.signature === signature) return existing.handle;
      // The inspector can edit an analyser in place; never reuse a context built
      // with the old window/range.
      this.analyserManager?.close(existing.handle);
      this.analyserContexts.delete(analyzer.id);
    }
    if (!this.analyserManager) {
      if (!this.analyserManagerPending) {
        this.analyserManagerPending = true;
        void AnalyserManager.create().then((manager) => {
          this.analyserManagerPending = false;
          this.analyserManager = manager;
        });
      }
      return null;
    }
    const handle = this.analyserManager.open(settings);
    if (!handle) return null;
    this.analyserContexts.set(analyzer.id, { signature, handle });
    // A context opened mid-frame needs a fresh batch.
    this.wasmFrameTime = Number.NaN;
    return handle;
  }

  /** Reference manager batch: one shared frame, one call, cached band values. */
  private analyseWasmFrame(): void {
    if (this.wasmFrameTime === this.frameTime) return;
    this.wasmFrameTime = this.frameTime;
    this.wasmResults.clear();
    const manager = this.analyserManager;
    if (!manager) return;
    manager.analyse(this.analysisFrame(), this.spectrum.sampleRate);
    for (const [id, entry] of this.analyserContexts) {
      const analyzer = this.project.analyzers.find((item) => item.id === id);
      if (!analyzer) continue;
      this.wasmResults.set(id, manager.result(entry.handle, analyzer.sampleOutCount));
    }
  }

  /**
   * Reference `resetAnalysers` (the exporter calls it when it starts): forget the
   * smoothing history so exported frames begin from a clean state instead of
   * inheriting whatever the preview had converged to.
   */
  resetAnalysers(): void {
    this.analyserManager?.reset();
    this.analyzerBank.reset();
    this.wasmResults.clear();
    this.wasmFrameTime = Number.NaN;
    this.sharedFrame = null;
  }

  /**
   * Point the analysis caches at a frame time before automations are evaluated.
   * `render()` repeats this; exports need it earlier because audio-impact and
   * math automations read `spectrumFor` before the frame is drawn.
   */
  setFrameTime(time: number): void {
    this.frameTime = time;
    this.lastFrameTime = time;
    this.sharedFrame = null;
    this.wasmFrameTime = Number.NaN;
  }

  render(time: number, clock: FrameClock = "auto"): void {
    // A repeat render of the same playhead is the reference's `rerender` (a
    // paused/seeked render), whose frame context carries `time: 0`. Capture
    // pipelines replay the timeline and then re-render the target frame, so the
    // captured frame uses that context - see `frameRerender`.
    //
    // `clock: "playback"` exists for the opposite provenance: a reference
    // captured *during play-through* is a live playback step at that playhead,
    // and its effects saw the playhead clock. A capture reproducing it must
    // sample with that clock even though its own pipeline re-renders the same
    // time (scripts/capture-frame.mjs `REA_CAPTURE_CLOCK=playhead`). The default
    // stays `auto`, so the live editor and all exports keep the reference rule.
    //
    // Reference module (playback component, `138-153.3372d016.chunk.js`,
    // `_update()`), quoted in docs/camera-shake-phase.md §2:
    //
    //   this.projectManager.update({time:this.time,
    //     frameIndex:this.frameIndex, fps:this.props.fps, rerender:!1})
    //
    // i.e. a played frame is `rerender:false` at the playhead, while the
    // initial/paused context is `{time:0,fps:60,frameIndex:0,rerender:true}`.
    this.frameRerender = clock === "playback" ? false : this.lastRenderedTime === time;
    this.lastRenderedTime = time;
    this.lastFrameTime = time;
    this.frameTime = time;
    this.background.set(this.project.background || "#000000");
    this.scene.background = this.background;
    const anySolo = this.project.nodes.some((node) => node.solo);
    for (const child of this.scene.children) {
      const node = child.userData.node as AnyNode | undefined;
      if (!node) continue;
      node.sync(time);
      child.visible =
        node.visible &&
        (!this.hideShyLayers || !node.shy) &&
        (!anySolo || node.solo) &&
        (node.ignoreTimeSpan || (time >= node.start && time <= node.start + node.duration));
    }

    // Effects run where they were connected: the composition root sees the
    // whole frame, while a layer's chain sees only that layer's items and is
    // composited back over the frame.
    const enabled = this.project.effects.filter(
      (effect) =>
        effect.enabled &&
        (effect.ignoreTimeSpan ||
          !effect.time ||
          (this.frameTime >= effect.time[0] &&
            this.frameTime <= effect.time[1])),
    );
    const globalEffects = enabled
      .filter((effect) => affectsGlobal(effect))
      .sort((a, b) => effectOrder(a, GLOBAL_TARGET) - effectOrder(b, GLOBAL_TARGET));
    const layerEffects = new Map<string, EffectInstance[]>();
    for (const effect of enabled) {
      if (affectsGlobal(effect)) continue;
      for (const layer of this.project.layers) {
        if (!layer.enabled) continue;
        if (!effect.targets.includes(layer.id)) continue;
        const chain = layerEffects.get(layer.id) ?? [];
        chain.push(effect);
        layerEffects.set(layer.id, chain);
      }
      // An item-targeted effect is a separate render-target chain in the
      // reference. Do not silently widen it to the whole frame: that made an
      // Alpha on Spectrum/Particles fade everything.
    }
    // A Transform into another layer mutates that layer's buffer in place
    // (module 361). The reference gets away with it because each layer's items
    // are re-rendered in row order, before the later mask runs. Our raw pass
    // fills every layer first, so a target already consumed by an *earlier*
    // row would keep the masked-away content on the next frame. For those
    // targets the effect draws into a scratch copy instead; the persisted
    // buffer stays what the earlier row sampled. `equinox`'s `background src`
    // (row 0) is sampled by `background base` (row 1) and masked at row 6.
    const references = (layerId: string): Set<string> => {
      const ids = new Set<string>();
      const layer = this.project.layers.find((item) => item.id === layerId);
      if (!layer) return ids;
      for (const nodeId of layer.nodeIds) {
        const node = this.project.nodes.find((item) => item.id === nodeId) as
          | { useLayerAsImage?: boolean; layerSource?: string }
          | undefined;
        if (node?.useLayerAsImage && node.layerSource) ids.add(node.layerSource);
      }
      for (const effect of layerEffects.get(layerId) ?? []) {
        if (effect.type === "transform") continue;
        const target = effect.params?.targetLayer;
        if (typeof target === "string" && target !== "Screen") ids.add(target);
      }
      return ids;
    };
    const preserveTransformTargets = new Map<string, Set<string>>();
    const referencedByEarlier = new Set<string>();
    for (const layer of this.project.layers) {
      preserveTransformTargets.set(layer.id, new Set(referencedByEarlier));
      for (const id of references(layer.id)) referencedByEarlier.add(id);
    }

    // Reference `Layer.addEffect` + module 53 `getBlendingParams`: the factors
    // used when a layer's finished buffer reaches the frame come from the
    // layer's camera, never from the last effect in its chain. Orthographic
    // layers use premultiplied `ONE / ONE_MINUS_SRC_ALPHA`; perspective layers
    // use `ONE / ONE` (additive). The Bloom pass's `SrcAlpha / One` final
    // material only blends inside the layer's own buffer, so a chain ending in
    // Bloom does not change how the layer composites.
    const additiveLayers = new Set<string>();
    for (const [layerId, chain] of layerEffects) {
      chain.sort((a, b) => effectOrder(a, layerId) - effectOrder(b, layerId));
      if (
        this.project.layers.find((layer) => layer.id === layerId)?.camera
          ?.type === "Perspective"
      ) {
        // Layer.addEffect uses dst ONE for perspective cameras, so the final
        // effect pass adds to the frame instead of alpha-covering it.
        additiveLayers.add(layerId);
      }
    }

    // The reference `Layer.getRenderTarget` returns the layer's own buffer when
    // `renderToBuffer` is set, and `Layer.render` then skips
    // `setRenderTargetScreen`: such a layer is never drawn straight to the
    // frame, it only feeds effects (Blending, Transform, masks) on other
    // layers. Mask sources and full-frame white/black helper planes are all
    // buffers in the corpus; a mask source that is also the main visual
    // (yidhari-anime's video) has the flag off and composites normally.
    // A Transform whose destination is Screen renders its final quad with the
    // effect's own blend factors in the reference. Compositing its buffer with
    // the default alpha-over instead made black letterbox/overlay planes cover
    // the frame (glass-3d).
    const terminalBlends = new Map<
      string,
      { equation: string; src: string; dst: string }
    >();
    // Layers whose chain ends in a Bloom pass that draws an opaque
    // `vec4(bloom, 1.0)` into a non-buffer layer. The reference sends that pass
    // to the composition with the pass's own `AdditiveBlending`, so the buffer
    // must be *added*, not alpha-covered (see `compositeBloomAdditive`).
    const bloomScreenLayers = new Set<string>();
    for (const [layerId, chain] of layerEffects) {
      const last = chain[chain.length - 1];
      if (!last) continue;
      if (last.type !== "bloom" && last.type !== "glow-bloom") continue;
      const layer = this.project.layers.find((item) => item.id === layerId);
      if (!layer || layer.renderToBuffer) continue;
      // Only when the pass is the opaque `vec4(bloom, 1.0)` branch: no base
      // texture. That is the case that alpha-over turns into an opaque card;
      // every other combination keeps the base (or its alpha) and the existing
      // composite already approximates the frame.
      //
      // The shipped Bloom forces the additive branch off whenever the base is
      // not rendered - module 1287 `renderEffect`:
      //   `this.finalShadermaterial.uniforms.renderBaseAdditive.value =
      //      !!this.renderBaseTexture && this.renderBaseAdditive`
      // so an authored `additive: true` with `renderBaseTexture: false` still
      // takes the `else { color = vec4(bloom, 1.0); }` branch of the final
      // shader. Gating on the authored flag skipped exactly those chains: the
      // Spherical Field rows (`manga-phonk`, `neon-drink`, `orbital`,
      // `yidhari-anime`) all end in base-less additive Bloom, and alpha-covering
      // their buffer turned a dense dot sheet into an opaque dark veil
      // (`neon-drink` @15: layer buffer mean RGB 23 / alpha 216, frame 55.25
      // against a 16.0 field-free floor).
      if (Number(last.params.renderBaseTexture ?? 0) > 0.5) continue;
      bloomScreenLayers.add(layerId);
    }
    // A layer whose chain ends in a Transform into another layer does *not*
    // paint its own quad on the composition. Reference `Transform.renderEffect`
    // (`main~053e68a9` module 361) draws the source into the target layer's
    // buffer with the authored factors, then binds the composer target and
    // draws `blendResultFSQuad` with `u.texture` - the **target layer's** buffer:
    //
    //   u = Instance.tryGetLayerTarget(this.targetLayer)
    //   u && (t.setRenderTarget(u), this.fsQuad.render(t, !0),
    //         this.setTarget(n, time, r), ...
    //         this.blendResultMat.uniforms.tDiffuse.value = u.texture,
    //         this.blendResultFSQuad.render(t))
    //
    // so the target layer reaches the screen at this layer's turn. Our chain
    // writes that same buffer into the layer's output (`post-processing.ts`),
    // which means the normal composite is the reference's second pass and must
    // run. The earlier `redirectedLayers` rule skipped it for `dstBlending:
    // SrcColor` chains: glass-3d's Theme Changer targets `2 Final` (whose Image
    // items sample `Background-S-2`), so the whole yellow theme was dropped and
    // only the night-city `S-1` layers remained.
    for (const [layerId, chain] of layerEffects) {
      const last = chain[chain.length - 1];
      if (
        last?.type === "transform" &&
        String(last.params.targetLayer ?? "Screen") === "Screen"
      ) {
        terminalBlends.set(layerId, {
          equation: String(last.params.blendEquation ?? "Add"),
          src: String(last.params.srcBlending ?? "One"),
          dst: String(last.params.dstBlending ?? "OneMinusSrcAlpha"),
        });
      }
    }
    const compositeLayer = (
      layer: CompositionLayer,
      target: THREE.WebGLRenderTarget | null,
    ): void => {
      const layerTarget = this.layerTargets.get(layer.id);
      if (!layerTarget) return;
      if (bloomScreenLayers.has(layer.id)) {
        // Reference `PostProcessingManager.render`: a non-buffer layer's last
        // effect pass writes to the composition with its own material blending,
        // and Bloom's final quad is `AdditiveBlending` (`SrcAlpha / One`). With
        // `renderBaseTexture` off the pass is `vec4(bloom, 1.0)` — opaque black
        // plus the glow — so alpha-over covers the frame with that black and the
        // scene disappears (`utopia` @30).
        this.layerCompositor.compositeBloomAdditive(
          this.renderer,
          layerTarget.texture,
          target,
        );
        return;
      }
      const custom = terminalBlends.get(layer.id);
      if (custom) {
        this.layerCompositor.compositeBlend(
          this.renderer,
          layerTarget.texture,
          target,
          custom.equation,
          custom.src,
          custom.dst,
        );
      } else if (target) {
        this.layerCompositor.compositeTo(
          this.renderer,
          layerTarget.texture,
          target,
          true,
          additiveLayers.has(layer.id),
        );
      } else {
        this.layerCompositor.composite(
          this.renderer,
          layerTarget.texture,
          true,
          additiveLayers.has(layer.id),
        );
      }
    };

    // A layer that holds particle items owns a perspective camera in the
    // reference (cameraType "perspective", fov 45, near 1, far 1000), so it is
    // isolated from the 2D pass even when it has no effect chain. Particles that
    // sit in no layer at all are drawn by the overlay pass instead.
    const perspectiveIds = new Set(
      this.project.nodes.filter((node) => node.is3D).map((node) => node.id),
    );
    const perspectiveLayerIds = new Set<string>();
    const layeredPerspective = new Set<string>();
    for (const layer of this.project.layers) {
      const members = layer.nodeIds.filter((id) => perspectiveIds.has(id));
      // Layered items are never drawn by the loose overlay, even when their
      // layer is disabled: the reference skips the whole layer, not just its
      // camera pass (`Layer.render`: `if (!this.enabled) return;`).
      for (const id of members) layeredPerspective.add(id);
      if (!layer.enabled || members.length === 0) continue;
      perspectiveLayerIds.add(layer.id);
    }
    const loosePerspective = new Set(
      [...perspectiveIds].filter((id) => !layeredPerspective.has(id)),
    );

    // Base visibility, before a layer pass or the particle overlay changes it.
    const baseVisible = new Map<string, boolean>();
    for (const child of this.scene.children) {
      const node = child.userData.node as AnyNode | undefined;
      if (node) baseVisible.set(node.id, child.visible);
    }
    const hideLooseParticles = (): void => {
      for (const child of this.scene.children) {
        const node = child.userData.node as AnyNode | undefined;
        if (node && loosePerspective.has(node.id)) child.visible = false;
      }
    };
    const applyVisibility = (keep: (node: AnyNode) => boolean): void => {
      for (const child of this.scene.children) {
        const node = child.userData.node as AnyNode | undefined;
        if (!node) continue;
        child.visible = (baseVisible.get(node.id) ?? false) && keep(node);
      }
    };

    // Every layered item is drawn only by its layer's pass. A disabled layer
    // keeps its items out of the frame entirely: the reference manager still
    // calls `preRender` for each layer, but `Layer.render` starts with
    // `if (!this.enabled) return;`, so neither the layer nor its items reach the
    // screen. Listing only *enabled* layers here made a disabled layer's items
    // fall through to the loose pass and paint over the frame (spageton @30: the
    // graffiti skin over the black lyric card).
    const isolated = new Set<string>();
    for (const layer of this.project.layers) {
      for (const id of layer.nodeIds) isolated.add(id);
    }

    if (
      layerEffects.size === 0 &&
      perspectiveLayerIds.size === 0 &&
      !this.project.layers.some((layer) => layer.enabled && layer.nodeIds.length > 0)
    ) {
      hideLooseParticles();
      applyVisibility((node) => !isolated.has(node.id));
      this.drawScene(globalEffects);
      applyVisibility(() => true);
      this.drawLooseParticles(loosePerspective, baseVisible);
      return;
    }

    // The reference composites layer by layer, in the composition's own order
    // ("Background Layer", "3D Visualizers", "2D Visualizers"), so an item's
    // layer decides what covers what: the particles belong to the 3D layer and
    // the spectrum to the 2D one, which draws over them.
    const drawOrder = this.project.layers.filter(
      (layer) =>
        layer.enabled &&
        (layer.nodeIds.length > 0 || layerEffects.has(layer.id)),
    );

    // Pre-render every visible layer into its own target. A layer's finished
    // frame is then available to effects on other layers (Blending, Transform's
    // blend-with) through the reference's renderToBuffer flag.
    // A layer with no items can still be the composition's output: several
    // templates ("This empty layer makes it work?!", "Compose") run their whole
    // Render-layer/Transform chain on an empty layer.
    const visibleLayers = drawOrder.filter(
      (layer) =>
        layer.nodeIds.some((id) => baseVisible.get(id)) ||
        layerEffects.has(layer.id),
    );
    const size = this.renderer.getDrawingBufferSize(this.drawBuffer);
    const rawTextures = new Map<string, THREE.Texture>();
    const finalized = new Set<string>();
    const previousBackground: THREE.Color | THREE.Texture | null = this.scene.background;
    const previousAlpha = this.renderer.getClearAlpha();
    this.scene.background = null;
    this.renderer.setClearAlpha(0);

    // The reference walks the layers in composition order, and a layer's
    // Transform-into-another-layer pass mutates the target's buffer in place
    // (`main~053e68a9` module 361: `t.setRenderTarget(u)`). A target that an
    // *earlier* row already sampled would therefore lose what that row read.
    // Those targets are resolved to a scratch copy here; `preserveTargets`
    // (see `render()`) names them.
    for (const layer of visibleLayers) {
      const members = new Set(layer.nodeIds);
      applyVisibility((node) => members.has(node.id));
      const manager = this.layerManager(layer.id);
      manager.setSize(size.x, size.y);
      const input = manager.inputTarget;
      if (!input) continue;
      const camera = this.layerCameraFor(layer, perspectiveLayerIds);
      this.updateGizmoForLayer(layer, camera);
      this.renderer.setRenderTarget(input);
      this.renderer.render(this.scene, camera);
      rawTextures.set(layer.id, input.texture);
    }
    if (this.transformHelper) this.transformHelper.visible = false;

    // Compose in layer order. Blending's "Screen" target must sample the frame
    // built *so far* (background plus earlier layers), not just the empty base,
    // so each layer is rendered, then immediately composited into this target.
    const compositionTarget = this.ensureLayerTarget("__composition", size.x, size.y);
    const opaqueForGlobal = globalEffects.length > 0;
    // God rays / Streak Glow with `renderInputOnTop` scale their accumulation by
    // `1 - inputColor.a` (decompiled module 1300/1313). The reference's
    // composition buffer carries the layer stack's *coverage* in alpha
    // (`main~053e68a9` module 361 clears with `clearAlpha 0`); ours is opaque so
    // that term reads 1 and zeroes every ray. Compose over a transparent base
    // only to obtain that coverage and flatten the RGB back to opaque for the
    // chain - the opaque path itself is untouched, because a transparent base
    // changes every alpha-sensitive pass (`glass-3d` cost 1.66 on `cb71ac2`).
    const coverageForGlobal =
      opaqueForGlobal &&
      globalEffects.some(
        (effect) =>
          (effect.type === "god-rays" || effect.type === "streak-glow") &&
          Number(effect.params?.renderInputOnTop) > 0.5,
      );
    applyVisibility((node) => !isolated.has(node.id));
    this.scene.background = coverageForGlobal
      ? null
      : opaqueForGlobal
        ? new THREE.Color("#000000")
        : previousBackground;
    this.renderer.setClearAlpha(coverageForGlobal ? 0 : opaqueForGlobal ? 1 : previousAlpha);
    this.renderer.setRenderTarget(compositionTarget);
    this.renderer.render(this.scene, this.camera);
    this.scene.background = null;
    this.renderer.setClearAlpha(0);

    for (const layer of visibleLayers) {
      const raw = rawTextures.get(layer.id);
      if (!raw) continue;
      const manager = this.layerManager(layer.id);
      const target = this.ensureLayerTarget(layer.id, size.x, size.y);
      const chain = layerEffects.get(layer.id) ?? [];
      // A Transform that writes into another layer's buffer normally targets
      // that layer's *finished* output, so masking chains stay exact. Only a
      // reciprocal chain (A's Transform targets B, B's chain targets A) is a
      // feedback loop: the reference writes that pass into B's current content
      // (`getBuffer()` -> readBuffer) without clearing, which is what bounds the
      // SrcColor/DstColor accumulation. Resolve exactly those targets to the
      // readBuffer; everything else keeps the output target.
      const feedbackTargets = this.feedbackTransformTargets(layer.id, layerEffects);
      const rendered =
        chain.length > 0 &&
        manager.render(this.renderer, chain, {
          time: this.frameTime,
          rerender: this.frameRerender,
          output: target,
          layerTexture: (otherId, preferRaw, selfTexture) => {
            // A self-targeting effect reads the layer's *own* buffer, not its
            // finished output. Reference `WebGLManager.tryGetLayerTarget`
            // (`main~8b8da8bb` @17186):
            //
            //   tryGetLayerTarget(e) {
            //     const t = this.children.find(t => t._id === e);
            //     return t ? t.getBuffer(this.previousPlaybackInfo.time) : null;
            //   }
            //
            // and `PostProcessingManager.getBuffer` (`main~053e68a9` @4250)
            // returns `this.readBuffer` - the buffer the chain is reading at
            // this pass, which `render()` swaps after every effect. Resolving
            // it to `layerTargets` (the output target, cleared by this frame's
            // final copy) fed the pass an empty texture: `code-286`'s
            // "Unnasdas" layer (Alpha -> Two pass blur -> Displacement into
            // itself) rendered nothing at all, so the reference's smoke band
            // was missing.
            if (otherId === layer.id) return selfTexture ?? raw;
            return this.layerTextureFor(otherId, rawTextures, finalized, preferRaw);
          },
          layerTarget: (otherId) =>
            feedbackTargets.has(otherId)
              ? this.layerManager(otherId).inputTarget ??
                this.layerTargets.get(otherId) ??
                null
              : this.layerTargetFor(otherId),
          // Module 591 `Layer.getRenderTarget`: a layer is a buffer source when
          // it has an active effect or `renderToBuffer`; only those keep a
          // Transform's authored factor pair (see the Transform branch in
          // post-processing).
          authoredTransformBlending: layer.renderToBuffer,
          screenTexture: compositionTarget.texture,
          preserveTargets: preserveTransformTargets.get(layer.id),
        });
      if (!rendered) manager.copyTo(this.renderer, raw, target);
      finalized.add(layer.id);
      // `renderToBuffer` stops the default screen pass. The effect's
      // `targetLayer: "Screen"` means "blend with the current destination"
      // (`setTarget(n, …)`), which is still the layer buffer here - not a
      // forced screen draw. Compositing these made white mask planes cover
      // the frame (nebula-staff), so only unbuffered layers use this pass.
      if (!layer.renderToBuffer) {
        compositeLayer(layer, compositionTarget);
      }
    }

    this.scene.background = previousBackground;
    this.renderer.setClearAlpha(previousAlpha);

    applyVisibility((node) => !isolated.has(node.id));
    // Loose particles belong to no layer, so they are drawn by the perspective
    // overlay below rather than by the orthographic pass.
    for (const child of this.scene.children) {
      const node = child.userData.node as AnyNode | undefined;
      if (node && loosePerspective.has(node.id)) child.visible = false;
    }

    if (globalEffects.length === 0) {
      this.layerCompositor.composite(
        this.renderer,
        compositionTarget.texture,
        false,
      );
    } else {
      this.postProcessing.setSize(size.x, size.y);
      const target = this.postProcessing.inputTarget;
      if (target) {
        if (coverageForGlobal) {
          this.layerCompositor.copyOpaque(
            this.renderer,
            compositionTarget.texture,
            target,
          );
        } else {
          this.layerCompositor.compositeTo(
            this.renderer,
            compositionTarget.texture,
            target,
            false,
          );
        }
        this.postProcessing.render(this.renderer, globalEffects, {
          time: this.frameTime,
          rerender: this.frameRerender,
          coverageTexture: coverageForGlobal ? compositionTarget.texture : null,
        });
      } else {
        this.layerCompositor.composite(
          this.renderer,
          compositionTarget.texture,
          false,
        );
      }
    }
    applyVisibility(() => true);
    this.drawLooseParticles(loosePerspective, baseVisible);
  }

  /**
   * Draw particles that belong to no layer through the perspective camera, over
   * the finished frame. `scene.background` is nulled for the pass because three
   * force-clears for a colour background even when autoClear is off.
   */
  private drawLooseParticles(particles: Set<string>, baseVisible: Map<string, boolean>): void {
    if (particles.size === 0) return;
    const previous = new Map<string, boolean>();
    let visible = false;
    for (const child of this.scene.children) {
      const node = child.userData.node as AnyNode | undefined;
      if (!node) continue;
      previous.set(node.id, child.visible);
      const keep = particles.has(node.id) && (baseVisible.get(node.id) ?? false);
      if (keep) visible = true;
      child.visible = keep;
    }
    if (visible) {
      const background = this.scene.background;
      this.scene.background = null;
      const camera = this.layerCamera(true);
      this.renderer.setRenderTarget(null);
      const autoClear = this.renderer.autoClear;
      this.renderer.autoClear = false;
      // The reference draws a layer into a fresh buffer, so its points never test
      // against the 2D pass's depth. Our overlay shares that buffer; clearing
      // depth reproduces the reference's starting state without touching colour.
      this.renderer.clearDepth();
      this.renderer.render(this.scene, camera);
      this.renderer.autoClear = autoClear;
      this.scene.background = background;
    }
    for (const child of this.scene.children) {
      const node = child.userData.node as AnyNode | undefined;
      if (node) child.visible = baseVisible.get(node.id) ?? previous.get(node.id) ?? child.visible;
    }
  }

  private layerManager(layerId: string): PostProcessingManager {
    let manager = this.layerPostProcessing.get(layerId);
    if (!manager) {
      manager = new PostProcessingManager();
      this.layerPostProcessing.set(layerId, manager);
    }
    return manager;
  }

  private ensureLayerTarget(
    layerId: string,
    width: number,
    height: number,
  ): THREE.WebGLRenderTarget {
    let target = this.layerTargets.get(layerId);
    if (!target) {
      target = new THREE.WebGLRenderTarget(Math.max(1, width), Math.max(1, height));
      this.layerTargets.set(layerId, target);
    } else if (target.width !== width || target.height !== height) {
      target.setSize(Math.max(1, width), Math.max(1, height));
    }
    return target;
  }

  /**
   * Resolve another layer as a render target. Every layer is rendered into a
   * target each frame; `renderToBuffer` controls whether the reference keeps
   * that frame for direct compositing (it skips the screen pass), but it never
   * gates sampling - Blending and Transform routinely consume layers whose flag
   * is off.
   */
  private layerTargetFor(layerId: string): THREE.WebGLRenderTarget | null {
    return this.layerTargets.get(layerId) ?? null;
  }

  /**
   * Target layers that participate in a Transform feedback cycle with
   * `sourceId`. Only those are resolved to the layer's current readBuffer; a
   * one-way masking Transform keeps its finished output target.
   */
  private feedbackTransformTargets(
    sourceId: string,
    layerEffects: Map<string, EffectInstance[]>,
  ): Set<string> {
    const transformTargets = (layerId: string): string[] =>
      (layerEffects.get(layerId) ?? [])
        .filter((effect) => effect.enabled && effect.type === "transform")
        .map((effect) => String(effect.params?.targetLayer ?? "Screen"))
        .filter((target) => target !== "Screen");
    const reachesSource = (layerId: string, seen: Set<string>): boolean => {
      if (layerId === sourceId) return true;
      if (seen.has(layerId)) return false;
      const nextSeen = new Set(seen);
      nextSeen.add(layerId);
      return transformTargets(layerId).some((next) =>
        reachesSource(next, nextSeen),
      );
    };
    const feedback = new Set<string>();
    for (const target of transformTargets(sourceId)) {
      if (reachesSource(target, new Set())) feedback.add(target);
    }
    return feedback;
  }

  private layerTextureFor(
    layerId: string,
    rawTextures: Map<string, THREE.Texture>,
    finalized: Set<string>,
    preferRaw = false,
  ): THREE.Texture | null {
    if (finalized.has(layerId)) {
      return this.layerTargets.get(layerId)?.texture ?? rawTextures.get(layerId) ?? null;
    }
    // The reference resolves a layer through `getBuffer(previousPlaybackInfo.time)`,
    // i.e. the layer's finished buffer from the previous frame. That is what a
    // forward reference (void-sea's reverse motion render-layer) needs. Blending
    // is the exception: it must see the other layer's current content even when
    // that layer is composed later, otherwise a forward blend settles to black
    // (eternal-pulse's Background against Noise).
    if (preferRaw) {
      return (
        rawTextures.get(layerId) ??
        this.layerTargets.get(layerId)?.texture ??
        null
      );
    }
    return (
      this.layerTargets.get(layerId)?.texture ??
      rawTextures.get(layerId) ??
      null
    );
  }

  /** The reference gives 3D layers a perspective camera and 2D layers an ortho one. */
  private layerCamera(perspective: boolean): THREE.Camera {
    if (!perspective) return this.camera;
    this.particleCamera.aspect = this.project.width / this.project.height;
    this.particleCamera.updateProjectionMatrix();
    return this.particleCamera;
  }

  /**
   * Layer camera, ported from the shipped `Layer.createCamera()`: a layer is a
   * camera whose position/rotation/scale come from its transform, with an
   * orthographic projection unless the reference says perspective (or the layer
   * contains 3D items). Non-3D content is authored in reference pixels, so the
   * camera pose and near/far are mapped through the project resolution; 3D
   * items already live in reference pixel units.
   */
  private layerCameraFor(layer: CompositionLayer, perspectiveIds: Set<string>): THREE.Camera {
    const aspect = this.project.width / this.project.height;
    const has3D = perspectiveIds.has(layer.id);
    const explicit = layer.camera;
    const transform0 = layer.transform;
    const explicit3D =
      explicit?.type === "Perspective" &&
      Boolean(
        transform0 &&
          (Math.abs(transform0.position[2]) > 0.0001 ||
            transform0.rotation[0] !== 0 ||
            transform0.rotation[1] !== 0),
      );
    // An explicit camera type wins over the items' own dimension. A layer can
    // contain a 3D primitive (e.g. a white mask plane) while still declaring an
    // orthographic camera; forcing perspective clipped that plane at z=0.
    // A render-layer quad is authored in the reference's 1000-unit world and its
    // layer can take the declared perspective camera even when the layer has no
    // 3D pose of its own (`dubstep-riddim-3d`'s sticker layers sit at z=0 with
    // content 750 units behind, which the reference projects at fov 45).
    const hasRenderLayer = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      return Boolean(node && "useLayerAsImage" in node && (node as { useLayerAsImage?: boolean }).useLayerAsImage);
    });
    // A Media item's `position:z` is a real camera distance, not a paint-order
    // offset: the reference Image plane lives in the 1000-unit stage world and
    // its depth (plus its X/Y rotation) is projected by the layer's camera.
    // `dubstep-riddim-3d`'s background photo is at z=-350 and is rotated about X
    // and Y by its automations, yet its layer declares no pose of its own, so
    // the ortho stage ignored the depth and drew the photo filled to the frame;
    // the reference shows the closer, rotated view (49.9 -> 19.1 mean against
    // the live frame at t=15).
    const hasStagePosedMedia = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      if (!node || !("useLayerAsImage" in node)) return false;
      return (
        Math.abs(node.readNumber("transform.z")) > 0.0001 ||
        Math.abs(node.readNumber("transform.rotX")) > 0.0001 ||
        Math.abs(node.readNumber("transform.rotY")) > 0.0001
      );
    });
    // The shipped Layer.createCamera picks the camera purely from `cameraType`.
    // A stage primitive (Noise, Plane, Cube, …) is authored at a real reference
    // depth, so a layer that declares Perspective must project it even when the
    // layer itself has no 3D pose. Without this the camera fell back to ortho and
    // `eternal-pulse`'s full-frame Noise quad covered only 2 of the 3.55 stage
    // units, so every layer blended through its rotated silhouette.
    const hasStageDepth = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      if (!node || !REFERENCE_STAGE_PRIMITIVES.has(node.typeLabel)) return false;
      return Math.abs(node.readNumber("transform.z")) > 0.001;
    });
    const perspective = explicit
      ? explicit.type === "Perspective" &&
        (has3D ||
          explicit3D ||
          hasRenderLayer ||
          hasStagePosedMedia ||
          // A buffer-only layer is never drawn to the screen; giving it the
          // perspective stage camera as well made foliage's full-frame Noise
          // cover the frame and saturate the downstream Bloom to white.
          (hasStageDepth && !layer.renderToBuffer))
      : has3D;
    const perspectiveCamera = explicit?.type === "Perspective" ? explicit : undefined;
    const transform = layer.transform;
    const degrees = Math.PI / 180;
    // Shader Items are authored in the reference's 1000-unit stage; the node
    // maps that to the 2-unit stage only when its layer uses the orthographic
    // camera (see ShaderItemNode.sync).
    for (const id of layer.nodeIds) this.nodeOrthoLayer.set(id, !perspective);

    if (!perspective) {
      let camera = this.layerOrthoCameras.get(layer.id);
      if (!camera) {
        camera = new THREE.OrthographicCamera(-aspect, aspect, 1, -1, -1000, 1000);
        this.layerOrthoCameras.set(layer.id, camera);
      }
      // Layer positions are in the reference's 1000-unit world (`position:x`
      // reaches ±2000), exactly like items and perspective layers; using the
      // project-pixel unit put `blobs-cubiq`'s background plane mostly
      // off-frame. `f(x, y, true)` gives x the aspect in landscape.
      const unit = 2 / 1000;
      const landscape = aspect > 1;
      camera.left = -aspect;
      camera.right = aspect;
      camera.top = 1;
      camera.bottom = -1;
      camera.position.set(
        (transform?.position[0] ?? 0) * unit * (landscape ? aspect : 1),
        (transform?.position[1] ?? 0) * unit * (landscape ? 1 : aspect),
        10,
      );
      camera.rotation.set(
        (transform?.rotation[0] ?? 0) * degrees,
        (transform?.rotation[1] ?? 0) * degrees,
        (transform?.rotation[2] ?? 0) * degrees,
      );
      camera.scale.set(transform?.scale[0] ?? 1, transform?.scale[1] ?? 1, 1);
      camera.updateProjectionMatrix();
      camera.updateMatrixWorld();
      return camera;
    }

    let camera = this.layerPerspectiveCameras.get(layer.id);
    if (!camera) {
      camera = new THREE.PerspectiveCamera(45, aspect, 1, 100000);
      this.layerPerspectiveCameras.set(layer.id, camera);
    }
    // Primitive planes/cubes are authored in the same 2-unit stage as 2D
    // content; only particle-style items keep reference-pixel units.
    const hasReference3D = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      return Boolean(node && REFERENCE_UNIT_3D.has(node.typeLabel));
    });
    const hasStagePrimitive = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      return Boolean(node && REFERENCE_STAGE_PRIMITIVES.has(node.typeLabel));
    });
    // A render-layer quad (`useLayerTexture`) is a Media item, and Media places
    // itself in the reference's 1000-unit world (`position` -> 2/1000 in
    // MediaNode.sync). Its layer camera must use the same unit: the
    // project-pixel unit put a 360-tall project's camera ~2.8x too far away and
    // shrank every card in `music-player-list`'s fan to ~40% of the reference
    // size. Layers whose items are authored in pixels (lyrics/text) keep it.
    // Any Media item lives in that stage, not only a `useLayerTexture` quad:
    // `candy-wave`'s Cover layer holds one plain Image, so the pixel unit put
    // its camera 2.8x too far away and slid the portrait off the right edge
    // (raw bbox x 602..639 against its mask at x 409..558, i.e. masked to
    // nothing).
    const hasMediaItem = layer.nodeIds.some((id) => {
      const node = this.project.nodes.find((item) => item.id === id);
      return Boolean(node && "useLayerAsImage" in node);
    });
    const stageSpace = hasStagePrimitive || hasMediaItem;
    const unit = hasReference3D
      ? 1
      : stageSpace
        ? 2 / 1000
        : 2 / Math.max(1, this.project.height);
    const stageAxis = stageSpace && aspect > 1;
    const positionX = (transform?.position[0] ?? 0) * unit * (stageAxis ? aspect : 1);
    const positionY =
      (transform?.position[1] ?? 0) * unit * (stageSpace && !stageAxis ? aspect : 1);
    camera.aspect = aspect;
    camera.fov = perspectiveCamera?.fov ?? 45;
    // A layer can mix reference-unit items with stage primitives: `koharu`'s
    // "Particles & Planes" layer has a particle system authored at z=-500
    // (reference units, so the camera keeps `unit` 1) *and* the two dark 70%
    // Planes that fill its song-info and subscribe panels. Those planes live in
    // the 2-unit stage at z=-0.97, and the reference's `nearPlane` of 1 is in
    // reference units ΓÇö a literal `1 * unit` is 512x too near and clipped both
    // panels, leaving only their ProgressBar outlines. Measure the near plane in
    // the primitives' unit whenever the layer has one.
    const nearUnit = hasStagePrimitive ? 2 / 1000 : unit;
    const near = (perspectiveCamera?.near ?? 1) * nearUnit;
    // 2D layers mix project-unit positions with primitive z values expressed in
    // the /100 stage, so a literal farPlane * unit would clip them. Keep a deep
    // far plane for non-reference layers.
    const far = hasReference3D
      ? (perspectiveCamera?.far ?? 100000) * unit
      : 100000 * unit;
    camera.near = Math.max(0.0001, near);
    camera.far = Math.max(camera.near + 0.001, far);
    camera.position.set(
      positionX,
      positionY,
      (transform?.position[2] ?? 0) * unit,
    );
    camera.rotation.set(
      (transform?.rotation[0] ?? 0) * degrees,
      (transform?.rotation[1] ?? 0) * degrees,
      (transform?.rotation[2] ?? 0) * degrees,
    );
    camera.scale.set(transform?.scale[0] ?? 1, transform?.scale[1] ?? 1, 1);
    camera.updateProjectionMatrix();
    // three r186 deliberately drops a camera's scale from its view matrix
    // ("exclude scale from view matrix to be glTF conform", `Camera.updateMatrixWorld`),
    // but the shipped three r116 does not:
    //
    //   updateMatrixWorld: function (t) {
    //     Tr.prototype.updateMatrixWorld.call(this, t),
    //     this.matrixWorldInverse.getInverse(this.matrixWorld)
    //   }
    //
    // (`vendor~bd29b17b.581d8b80.chunk.js`). `Layer.createCamera` puts the
    // layer's authored `scale:x`/`scale:y` on the camera, so the reference
    // stretches such a layer by the reciprocal of that scale - `code-286`'s
    // card (scale:y 0.9) is 11% taller there, its lyric layer (0.4) 2.5x. Fold
    // the same factors into the projection, which is where r116's inverse view
    // applied them; the camera object keeps its scale for anything reading it.
    const cameraScaleX = transform?.scale[0] ?? 1;
    const cameraScaleY = transform?.scale[1] ?? 1;
    if (
      Number.isFinite(cameraScaleX) &&
      Number.isFinite(cameraScaleY) &&
      cameraScaleX !== 0 &&
      cameraScaleY !== 0 &&
      (cameraScaleX !== 1 || cameraScaleY !== 1)
    ) {
      camera.projectionMatrix.multiply(
        cameraScaleMatrix.makeScale(1 / cameraScaleX, 1 / cameraScaleY, 1),
      );
      camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    }
    camera.updateMatrixWorld();
    return camera;
  }

  /** Render the whole scene, then the given effect chain, to the screen. */
  private drawScene(effects: EffectInstance[]): void {
    const size = this.renderer.getDrawingBufferSize(this.drawBuffer);

    if (effects.length === 0) {
      this.renderer.setRenderTarget(null);
      this.renderer.render(this.scene, this.camera);
      return;
    }

    this.postProcessing.setSize(size.x, size.y);
    const target = this.postProcessing.inputTarget;
    if (!target) {
      this.renderer.setRenderTarget(null);
      this.renderer.render(this.scene, this.camera);
      return;
    }

    this.renderer.setRenderTarget(target);
    this.renderer.render(this.scene, this.camera);
    this.postProcessing.render(this.renderer, effects, {
      time: this.frameTime,
      rerender: this.frameRerender,
    });
  }



  /**
   * Read the frame that is already on screen as top-down RGBA.
   *
   * Encoding a frame (`toBlob`) costs seconds at export resolution because it
   * reads the drawing buffer back *and* runs a PNG encoder on the main thread,
   * while a raw readback of the same buffer takes milliseconds. The exporter
   * feeds these bytes straight to ffmpeg as rawvideo instead.
   */
  /**
   * Read the drawing buffer. Video encoders expect top-down rows, while the
   * reference WASM encoder consumes the raw bottom-up OpenGL buffer.
   */
  readFrame(flip = true): Uint8Array {
    const gl = this.renderer.getContext();
    const width = this.renderer.domElement.width;
    const height = this.renderer.domElement.height;
    const source = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, source);
    if (!flip) return source;

    // OpenGL's origin is bottom-left; video frames are top-down.
    const rowBytes = width * 4;
    const flipped = new Uint8Array(source.length);
    for (let row = 0; row < height; row += 1) {
      const from = (height - 1 - row) * rowBytes;
      flipped.set(source.subarray(from, from + rowBytes), row * rowBytes);
    }
    return flipped;
  }

  /** The live WebGL canvas, used by the WebCodecs export source. */
  get canvasElement(): HTMLCanvasElement {
    return this.canvas;
  }

  /** Drawing buffer size, in pixels, of the frame `readFrame` returns. */
  get frameSize(): { width: number; height: number } {
    const size = this.renderer.getDrawingBufferSize(new THREE.Vector2());
    return { width: size.x, height: size.y };
  }

  /**
   * Capture the canvas as a blob. By default a raw scene render is drawn first
   * (used by "Save preview as PNG"); pass `renderScene = false` immediately
   * after `render(time)` in the export pipeline so the captured frame keeps the
   * global/layer effect composite instead of being overwritten by the raw scene.
   */
  async frameBlob(
    type = "image/png",
    quality = 0.95,
    renderScene = true,
  ): Promise<Blob> {
    if (renderScene) this.renderer.render(this.scene, this.camera);
    return new Promise((resolve, reject) => {
      this.canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("frame capture failed"))),
        type,
        quality,
      );
    });
  }

  /**
   * Temporarily renders at an explicit resolution, e.g. 1280x720 for export,
   * regardless of the preview size. Returns a restore function.
   */
  setExportSize(width: number, height: number): () => void {
    const previousRatio = this.renderer.getPixelRatio();
    this.exportSize = { width, height };
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height, false);
    return () => {
      this.exportSize = null;
      this.renderer.setPixelRatio(previousRatio);
      this.resize();
    };
  }

  dispose(): void {
    this.resizeObserver.disconnect();
    this.renderer.dispose();
  }
}
