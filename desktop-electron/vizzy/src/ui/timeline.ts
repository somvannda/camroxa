import type { AnyNode } from "../domain/nodes";
import type { Project } from "../domain/project";
import type { Automation, Keyframe } from "../domain/types";

const ROW_HEIGHT = 35;
const LAYER_HEIGHT = 24;
const HEADER = 40;
const KEY_RADIUS = 5;
/** Accent per item kind, used as a low-alpha clip tint. */
const CLIP_TINTS: Record<string, string> = {
  Spectrum: "#a855f7",
  Particles: "#c084fc",
  Media: "#60a5fa",
  Image: "#60a5fa",
  Text: "#f0abfc",
  SkiaText: "#f0abfc",
  AnimatedText: "#f0abfc",
  AudioWave: "#67e8f9",
  BasicSpectrumBars: "#a855f7",
  ParticleLines: "#c084fc",
  Model: "#c4b5fd",
  SphericalField: "#c4b5fd",
  LineBed: "#67e8f9",
  ShaderItem: "#f0abfc",
  Butterchurn: "#f0abfc",
};
const SNAP_PX = 6;
const AUDIO_HEIGHT = 44;
/** Expanded automation rows double as a small value graph. */
const AUTOMATION_ROW_HEIGHT = 56;
const GRAPH_PADDING = 8;

function tint(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface TimelineRow {
  y: number;
  height: number;
  index: number;
  kind: "layer" | "clips" | "automation";
  layerId?: string;
  layerName?: string;
  visible?: boolean;
  automationIndex?: number;
  nodes: AnyNode[];
}

export interface TimelineCallbacks {
  onSelect(nodeId: string | null): void;
  onSeek(time: number): void;
  onMoveStart(nodeId: string, start: number): void;
  onResize(nodeId: string, start: number, duration: number, edge: "start" | "end"): void;
  /** Move a set of keyframes; called continuously during a key drag. */
  onMoveKeyframes?(moves: {
    automation: Automation;
    key: Keyframe;
    time: number;
    value?: number;
  }[]): void;
  /** Finish a key drag: sort the affected rows and push one history step. */
  onCommitKeyframes?(): void;
  onSeekKeyframeSelect?(nodeId: string, propertyId: string): void;
  /** Right-click on a clip: open the item menu at the pointer. */
  onContextMenu?(nodeId: string, x: number, y: number): void;
  /** Right-click a ruler marker. */
  onMarkerMenu?(index: number, x: number, y: number): void;
  /** Slip a clip's source by a delta in seconds, keeping its timeline span. */
  onSlip?(nodeId: string, delta: number): void;
  /** Finish a slip drag. */
  onSlipEnd?(): void;
  /** Move a ruler marker; called continuously while dragging its flag. */
  onMoveMarker?(marker: { id: string; time: number; name: string }, time: number): void;
  /** Finish a marker drag (sort/history step). */
  onMoveMarkerEnd?(): void;
  /** Toggle a clip in the timeline selection. */
  onSelectMany?(ids: string[]): void;
  /** Move several clips by the same delta. */
  onMoveMany?(moves: { id: string; start: number }[]): void;
  /** Razor: split a clip at a clicked time. */
  onSplitAt?(nodeId: string, time: number): void;
  /** Select a composition layer from its timeline header. */
  onSelectLayer?(layerId: string): void;
  /** Toggle a layer's visibility from its timeline header. */
  onToggleLayer?(layerId: string): void;
}

type Drag =
  | { kind: "playhead" }
  | { kind: "loop"; anchor: number }
  | { kind: "pan"; startX: number; startView: number }
  | {
      kind: "marquee";
      x0: number;
      y0: number;
      x1: number;
      y1: number;
      additive: boolean;
      base: string[];
      keyBase: Keyframe[];
    }
  | { kind: "move"; nodeId: string; offset: number }
  | {
      kind: "slip";
      nodeId: string;
      startX: number;
      startSource: number;
      hasSource: boolean;
    }
  | {
      kind: "marker";
      marker: { id: string; time: number; name: string };
      startX: number;
      moved: boolean;
    }
  | { kind: "loop-edge"; edge: "start" | "end" }
  | {
      kind: "resize";
      nodeId: string;
      edge: "start" | "end";
      start: number;
      duration: number;
    }
  | {
      kind: "keys";
      anchorTime: number;
      anchorY: number;
      entries: {
        automation: Automation;
        key: Keyframe;
        originalTime: number;
        originalValue: number;
        lane: { rowY: number; height: number; range: { min: number; max: number } } | null;
      }[];
    };

/**
 * Canvas timeline.
 *
 * Rows are drawn from the node list; automation tracks for the selected node are
 * rendered beneath it as keyframe diamonds. All hit testing is in the same
 * coordinate space the canvas draws in, so there is no DOM/canvas drift.
 */
export class TimelineView {
  private drag: Drag | null = null;
  private hoverNode: string | null = null;
  private dpr = Math.min(window.devicePixelRatio, 2);
  private zoom = 1;
  /** First visible second at the current zoom; `0` shows the project start. */
  private viewStart = 0;
  /** Time highlighted by the snap guide while dragging, or null. */
  private snapGuide: number | null = null;
  /** Span readout drawn while moving or trimming a clip. */
  private dragReadout: { nodeId: string; start: number; end: number } | null = null;
  /** Source-position readout drawn while slipping a clip. */
  private slipReadout: { nodeId: string; source: number; delta: number } | null = null;
  /** Last rendered playhead, used as a snap target. */
  private time = 0;
  /** Peak amplitudes across the project, shown in the audio band. */
  private waveform: Float32Array | null = null;
  private audioLabel = "";
  /** Optional loop span created by Shift-dragging the ruler. */
  private loopRange: { start: number; end: number } | null = null;
  private snapEnabled = true;
  private tool: "select" | "hand" | "razor" | "slip" = "select";
  private selection = new Set<string>();
  /** Layers whose automation rows are expanded. */
  private expandedLayers = new Set<string>();
  /** Keyframes selected by click/shift-click or a lane marquee. */
  private selectedKeys = new Set<Keyframe>();
  /** Value ranges frozen for the duration of a key drag. */
  private frozenRanges = new Map<string, { min: number; max: number }>();
  /** Cached static timeline (everything but playhead/transient overlays). */
  private cache: HTMLCanvasElement | null = null;
  private cacheCtx: CanvasRenderingContext2D | null = null;
  private cacheKey = "";
  private renderStats = { full: 0, cached: 0 };
  /** Horizontal scrollbar elements (below the canvas, above the a11y list). */
  private hTrack: HTMLElement | null = null;
  private hThumb: HTMLElement | null = null;
  private scrollbarGrab: { x: number; start: number } | null = null;

  /** Static/cached frame counts, for the performance check. */
  getRenderStats(): { full: number; cached: number } {
    return { ...this.renderStats };
  }

  setTool(tool: "select" | "hand" | "razor" | "slip"): void {
    this.tool = tool;
    this.canvas.style.cursor =
      tool === "hand"
        ? "grab"
        : tool === "razor"
          ? "crosshair"
          : tool === "slip"
            ? "ew-resize"
            : "default";
  }

  getTool(): "select" | "hand" | "razor" | "slip" {
    return this.tool;
  }

  setSelection(ids: readonly string[]): void {
    this.selection = new Set(ids);
    this.selectedId = ids[0] ?? null;
    this.render(this.time, this.selectedId);
  }

  getSelection(): string[] {
    return [...this.selection];
  }

  /** Keep the snapping target in step with an immediate seek. */
  setPlayhead(time: number): void {
    this.time = time;
    this.render(time, this.selectedId);
  }

  setSnapEnabled(enabled: boolean): void {
    this.snapEnabled = enabled;
  }

  getSnapEnabled(): boolean {
    return this.snapEnabled;
  }

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly project: Project,
    private readonly callbacks: TimelineCallbacks,
  ) {
    this.canvas.addEventListener("pointerdown", this.onPointerDown);
    this.canvas.addEventListener("pointermove", this.onPointerMove);
    this.canvas.addEventListener("pointerup", this.onPointerUp);
    this.canvas.addEventListener("contextmenu", this.onContextMenu);
    this.canvas.addEventListener("wheel", this.onWheel, { passive: false });
    this.canvas.addEventListener("dblclick", this.onDoubleClick);
    this.canvas.addEventListener("pointerleave", () => {
      this.hoverNode = null;
    });
    this.hTrack = document.getElementById("timeline-hscroll");
    this.hThumb = document.getElementById("timeline-hthumb");
    this.hTrack?.addEventListener("pointerdown", this.onScrollbarDown);
    new ResizeObserver(() => this.render(this.time, this.selectedId)).observe(this.canvas);
  }

  /** Position/size the horizontal scrollbar to mirror the visible span. */
  private syncScrollbar(): void {
    if (!this.hTrack || !this.hThumb) return;
    const track = this.hTrack.clientWidth;
    if (track <= 0) return;
    const total = Math.max(1e-6, this.project.duration);
    const visible = Math.min(total, Math.max(0.001, this.visibleDuration));
    const width = Math.max(24, Math.min(track, (visible / total) * track));
    const maxStart = Math.max(1e-6, total - visible);
    const left = (this.viewStart / maxStart) * Math.max(0, track - width);
    this.hThumb.style.width = `${width}px`;
    this.hThumb.style.left = `${Math.max(0, Math.min(track - width, left))}px`;
  }

  private scrollbarStart(event: PointerEvent): void {
    if (!this.hTrack || !this.hThumb) return;
    event.preventDefault();
    const rect = this.hTrack.getBoundingClientRect();
    if (event.target !== this.hThumb) {
      // Click on the track centres the visible span on the pointer.
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
      this.viewStart = Math.max(0, Math.min(this.maxViewStart, ratio * this.project.duration - this.visibleDuration / 2));
      this.render(this.time, this.selectedId);
    }
    this.scrollbarGrab = { x: event.clientX, start: this.viewStart };
    this.hTrack.classList.add("dragging");
    window.addEventListener("pointermove", this.onScrollbarMove);
    window.addEventListener("pointerup", this.onScrollbarUp, { once: true });
  }

  private onScrollbarDown = (event: PointerEvent): void => this.scrollbarStart(event);

  private onScrollbarMove = (event: PointerEvent): void => {
    if (!this.scrollbarGrab || !this.hTrack) return;
    const track = Math.max(1, this.hTrack.getBoundingClientRect().width);
    const total = Math.max(1e-6, this.project.duration);
    const delta = ((event.clientX - this.scrollbarGrab.x) / track) * total;
    this.viewStart = Math.max(0, Math.min(this.maxViewStart, this.scrollbarGrab.start + delta));
    this.render(this.time, this.selectedId);
  };

  private onScrollbarUp = (): void => {
    this.scrollbarGrab = null;
    this.hTrack?.classList.remove("dragging");
    window.removeEventListener("pointermove", this.onScrollbarMove);
  };

  private get ctx(): CanvasRenderingContext2D {
    return this.canvas.getContext("2d")!;
  }

  private get width(): number {
    return this.canvas.clientWidth;
  }

  private get trackWidth(): number {
    return Math.max(1, this.width);
  }

  setZoom(zoom: number, anchorTime?: number): void {
    const previous = this.visibleDuration;
    const anchor = anchorTime ?? this.viewStart + previous / 2;
    const fraction = previous > 0 ? (anchor - this.viewStart) / previous : 0;
    this.zoom = Math.max(0.25, Math.min(8, zoom));
    const next = this.visibleDuration;
    this.viewStart = Math.max(
      0,
      Math.min(this.maxViewStart, anchor - fraction * next),
    );
    this.render(this.time, this.selectedId);
  }

  /** Show the whole project from zero. */
  fit(): void {
    this.zoom = 1;
    this.viewStart = 0;
    this.render(this.time, this.selectedId);
  }

  /** Frame the selected clips with a small margin. */
  zoomToSelection(): boolean {
    const ids =
      this.selection.size > 0
        ? [...this.selection]
        : this.selectedId
          ? [this.selectedId]
          : [];
    const nodes = ids
      .map((id) => this.project.nodes.find((node) => node.id === id))
      .filter((node): node is AnyNode => Boolean(node));
    if (nodes.length === 0) return false;
    const min = Math.min(...nodes.map((node) => node.start));
    const max = Math.max(...nodes.map((node) => node.start + node.duration));
    const span = Math.max(0.5, max - min);
    const pad = Math.max(0.2, span * 0.1);
    const start = Math.max(0, min - pad);
    const end = Math.min(this.project.duration, max + pad);
    const visible = Math.max(0.5, end - start);
    this.zoom = Math.max(0.25, Math.min(8, this.project.duration / visible));
    this.viewStart = Math.max(0, Math.min(this.maxViewStart, start));
    this.render(this.time, this.selectedId);
    return true;
  }

  /** Read-only state used by checks and the shell. */
  getViewState(): { zoom: number; viewStart: number; visible: number; playhead: number } {
    return {
      zoom: this.zoom,
      viewStart: this.viewStart,
      visible: this.visibleDuration,
      playhead: this.time,
    };
  }

  /** Supply the audio peak envelope drawn under the item rows. */
  setWaveform(peaks: Float32Array | null, label = ""): void {
    this.waveform = peaks;
    this.audioLabel = label;
    this.cacheKey = "";
    this.render(this.time, this.selectedId);
  }

  getWaveformState(): { length: number; label: string } {
    return { length: this.waveform?.length ?? 0, label: this.audioLabel };
  }

  setLoopRange(range: { start: number; end: number } | null): void {
    this.loopRange = range;
    this.render(this.time, this.selectedId);
  }

  getLoopRange(): { start: number; end: number } | null {
    return this.loopRange;
  }

  /** Clip-row geometry for a node, used by checks and keyboard focus. */
  getRowForNode(nodeId: string): { y: number; height: number } | null {
    for (const row of this.layout().rows) {
      if (row.kind === "clips" && row.nodes.some((node) => node.id === nodeId)) {
        return { y: row.y, height: row.height };
      }
    }
    return null;
  }

  /** Flat clip list for the hidden screen-reader mirror. */
  getAccessibilityItems(): {
    id: string;
    name: string;
    layer: string;
    start: number;
    duration: number;
  }[] {
    const items: { id: string; name: string; layer: string; start: number; duration: number }[] = [];
    for (const row of this.layout().rows) {
      if (row.kind !== "clips") continue;
      for (const node of row.nodes) {
        items.push({
          id: node.id,
          name: node.name,
          layer: row.layerName ?? "",
          start: node.start,
          duration: node.duration,
        });
      }
    }
    return items.sort((a, b) => a.start - b.start);
  }

  /** Expanded automation rows, for checks. */
  getAutomationRows(): { layer: string; index: number; label: string }[] {
    return this.layout()
      .rows.filter((row) => row.kind === "automation" && row.automationIndex !== undefined)
      .map((row) => ({
        layer: row.layerName ?? "",
        index: row.automationIndex as number,
        label: this.automationLaneLabel(this.project.automations[row.automationIndex as number]),
      }));
  }

  /** Layer headers in display order, for checks and keyboard navigation. */
  getLayerRows(): { id?: string; name: string; y: number; height: number; visible: boolean }[] {
    return this.layout()
      .rows.filter((row) => row.kind === "layer")
      .map((row) => ({
        id: row.layerId,
        name: row.layerName ?? "",
        y: row.y,
        height: row.height,
        visible: row.visible !== false,
      }));
  }

  /** Geometry of the optional audio band and the effect lanes below it. */
  private audioBand(bottom: number): { y: number; effectsY: number } {
    if (!this.waveform) return { y: bottom + 4, effectsY: bottom + 4 };
    return { y: bottom + 6, effectsY: bottom + 6 + AUDIO_HEIGHT + 4 };
  }

  /** Seconds visible across the track area at the current zoom. */
  private get visibleDuration(): number {
    return this.project.duration / this.zoom;
  }

  private get maxViewStart(): number {
    return Math.max(0, this.project.duration - this.visibleDuration);
  }

  private timeToX(time: number): number {
    return ((time - this.viewStart) / this.visibleDuration) * this.trackWidth;
  }

  private xToTime(x: number): number {
    const t = this.viewStart + (x / this.trackWidth) * this.visibleDuration;
    return Math.max(0, Math.min(this.project.duration, t));
  }

  /**
   * Snap a dragged edge to the project ends, the playhead, or another clip's
   * edges. Returns the (possibly unchanged) time and records the guide.
   */
  private snapTime(time: number, excludeNodeId?: string, bypass = false): number {
    if (!this.snapEnabled || bypass) {
      this.snapGuide = null;
      return time;
    }
    const threshold = (SNAP_PX / Math.max(1, this.width)) * this.visibleDuration;
    let best = time;
    let distance = threshold;
    const consider = (target: number): void => {
      const delta = Math.abs(target - time);
      if (delta <= distance) {
        distance = delta;
        best = target;
      }
    };
    consider(0);
    consider(this.project.duration);
    for (const marker of this.project.markers) consider(marker.time);
    consider(this.time);
    if (this.loopRange) {
      consider(this.loopRange.start);
      consider(this.loopRange.end);
    }
    // Beats are only useful when they are far enough apart to target.
    const beat = 60 / Math.max(1, this.project.bpm || 120);
    const beatPx = (beat / this.visibleDuration) * this.width;
    if (beatPx >= 6) consider(Math.round(time / beat) * beat);
    for (const node of this.project.nodes) {
      if (node.id === excludeNodeId) continue;
      consider(node.start);
      consider(node.start + node.duration);
    }
    this.snapGuide = best === time ? null : best;
    return best;
  }

  private onWheel = (event: WheelEvent): void => {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const anchor = this.xToTime(event.clientX - rect.left);
      const factor = Math.exp(-event.deltaY * 0.002);
      this.setZoom(this.zoom * factor, anchor);
      return;
    }
    // Plain wheel scrolls the track vertically (the rows live in a scroll
    // container now). Shift+wheel, or a horizontal trackpad gesture, pans time.
    const horizontal = event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY);
    if (!horizontal) return;
    event.preventDefault();
    const delta = event.deltaX !== 0 ? event.deltaX : event.deltaY;
    this.viewStart = Math.max(
      0,
      Math.min(this.maxViewStart, this.viewStart + (delta / Math.max(1, this.width)) * this.visibleDuration),
    );
    this.render(this.time, this.selectedId);
  };

  private rowAt(y: number): TimelineRow | null {
    return (
      this.layout().rows.find((row) => y >= row.y && y < row.y + row.height) ?? null
    );
  }

  private markerAt(x: number): number {
    let found = -1;
    let distance = 6;
    this.project.markers.forEach((marker, index) => {
      const delta = Math.abs(this.timeToX(marker.time) - x);
      if (delta <= distance) {
        distance = delta;
        found = index;
      }
    });
    return found;
  }

  /** True when a point is within the resize handle of a clip. */
  private edgeAt(x: number, y: number): boolean {
    const node = this.nodeAt(x, y);
    if (!node) return false;
    const x0 = this.timeToX(node.start);
    const x1 = this.timeToX(node.start + node.duration);
    return Math.abs(x - x0) <= 4 || Math.abs(x - x1) <= 4;
  }

  /** The clip under a point, searching the row that owns that y. */
  private nodeAt(x: number, y: number): AnyNode | null {
    const row = this.rowAt(y);
    if (!row) return null;
    for (const node of row.nodes) {
      const x0 = this.timeToX(node.start);
      const x1 = this.timeToX(node.start + node.duration);
      if (x >= x0 - 3 && x <= x1 + 3) return node;
    }
    return null;
  }

  private automationLaneLabel(automation: Automation): string {
    const target =
      automation.propertyId || Object.values(automation.connections).flat().join(", ");
    const name =
      automation.name ??
      (automation.type === "audioImpact"
        ? "Audio Impact"
        : automation.type === "math"
          ? "Math"
          : "Keyframes");
    return target ? `${name} \u00b7 ${target}` : name;
  }

  /** Span readout for the active move/trim drag, for checks. */
  getDragReadout(): { start: number; end: number; duration: number; label: string } | null {
    if (!this.dragReadout) return null;
    const { start, end } = this.dragReadout;
    return {
      start,
      end,
      duration: end - start,
      label: this.readoutLabel(start, end),
    };
  }

  /** `mm:ss.ff` plus musical `bar.beat` for the drag tooltip. */
  private readoutLabel(start: number, end: number): string {
    const fps = Math.max(1, Math.round(this.project.fps || 30));
    const format = (seconds: number): string => {
      const whole = Math.max(0, seconds);
      const mm = Math.floor(whole / 60);
      const ss = Math.floor(whole % 60);
      const ff = Math.floor((whole % 1) * fps);
      return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}.${String(ff).padStart(2, "0")}`;
    };
    const beat = 60 / Math.max(1, this.project.bpm || 120);
    const beats = Math.max(0, start) / beat;
    const bar = Math.floor(beats / 4) + 1;
    const beatInBar = Math.floor(beats % 4) + 1;
    return `${format(start)} \u2192 ${format(end)}  (${format(end - start)})  \u00b7  ${bar}.${beatInBar}`;
  }

  /** Source readout for the active slip drag, for checks. */
  getSlipReadout(): { source: number; delta: number } | null {
    if (!this.slipReadout) return null;
    return { source: this.slipReadout.source, delta: this.slipReadout.delta };
  }

  /** Draw the source tooltip above the slipped clip. */
  private drawSlipReadout(ctx: CanvasRenderingContext2D): void {
    if (!this.slipReadout) return;
    const { rows } = this.layout();
    const row = rows.find((entry) =>
      entry.nodes.some((node) => node.id === this.slipReadout?.nodeId),
    );
    if (!row) return;
    const { source, delta } = this.slipReadout;
    const label = `Slip ${delta >= 0 ? "+" : ""}${delta.toFixed(2)}s  \u00b7  source ${source.toFixed(2)}s`;
    const node = this.project.nodes.find((entry) => entry.id === this.slipReadout?.nodeId);
    ctx.save();
    ctx.font = "11px ui-monospace, monospace";
    const width = ctx.measureText(label).width + 16;
    const height = 22;
    const anchor = node ? this.timeToX(node.start) : 0;
    const x = Math.max(4, Math.min(this.width - width - 4, anchor));
    let y = row.y - height - 4;
    if (y < HEADER) y = Math.min(this.canvas.clientHeight - height - 4, row.y + row.height + 4);
    ctx.fillStyle = "rgba(12, 12, 18, 0.94)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 255, 255, 0.86)";
    ctx.textAlign = "start";
    ctx.fillText(label, x + 8, y + 15);
    ctx.restore();
  }

  /** Draw the span tooltip above (or below) the dragged clip. */
  private drawDragReadout(ctx: CanvasRenderingContext2D): void {
    if (!this.dragReadout) return;
    const { rows } = this.layout();
    const row = rows.find((entry) => entry.nodes.some((node) => node.id === this.dragReadout?.nodeId));
    if (!row) return;
    const label = this.readoutLabel(this.dragReadout.start, this.dragReadout.end);
    ctx.font = "11px ui-monospace, monospace";
    const width = ctx.measureText(label).width + 16;
    const height = 22;
    const anchor = this.timeToX(this.dragReadout.start);
    const x = Math.max(4, Math.min(this.width - width - 4, anchor));
    let y = row.y - height - 4;
    if (y < HEADER) y = Math.min(this.canvas.clientHeight - height - 4, row.y + row.height + 4);
    ctx.save();
    ctx.fillStyle = "rgba(12, 12, 18, 0.94)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 255, 255, 0.86)";
    ctx.textAlign = "start";
    ctx.fillText(label, x + 8, y + 15);
    ctx.restore();
  }

  private tracksFor(node: AnyNode): { automation: Automation; index: number }[] {
    const out: { automation: Automation; index: number }[] = [];
    this.project.automations.forEach((automation, index) => {
      if (automation.nodeId === node.id) out.push({ automation, index });
    });
    return out;
  }

  /** Value span drawn by an expanded automation lane. */
  private laneRange(automation: Automation): { min: number; max: number } {
    const frozen = this.drag?.kind === "keys" ? this.frozenRanges.get(automation.id) : undefined;
    if (frozen) return frozen;
    const values = automation.keyframes
      .map((key) => key.value)
      .filter((value) => Number.isFinite(value));
    if (values.length === 0) return { min: 0, max: 1 };
    let min = Math.min(...values);
    let max = Math.max(...values);
    const span = max - min;
    if (span < 1e-6) {
      const pad = Math.max(1, Math.abs(min) * 0.1);
      min -= pad;
      max += pad;
    } else {
      min -= span * 0.1;
      max += span * 0.1;
    }
    return { min, max };
  }

  /** Graph Y for a value inside an automation row. */
  private valueToLaneY(
    value: number,
    rowY: number,
    height: number,
    range: { min: number; max: number },
  ): number {
    const usable = Math.max(1, height - GRAPH_PADDING * 2);
    const norm = (range.max - value) / Math.max(1e-6, range.max - range.min);
    return rowY + GRAPH_PADDING + Math.max(0, Math.min(1, norm)) * usable;
  }

  /** Value for a graph Y inside an automation row. */
  private laneYToValue(
    y: number,
    rowY: number,
    height: number,
    range: { min: number; max: number },
  ): number {
    const usable = Math.max(1, height - GRAPH_PADDING * 2);
    const norm = Math.max(0, Math.min(1, (y - rowY - GRAPH_PADDING) / usable));
    return range.max - norm * (range.max - range.min);
  }

  /** Tracks that drive effect parameters rather than an item property. */
  private effectTracks(): { automation: Automation; index: number }[] {
    const out: { automation: Automation; index: number }[] = [];
    this.project.automations.forEach((automation, index) => {
      if (!automation.nodeId) out.push({ automation, index });
    });
    return out;
  }

  private effectTrackLabel(automation: Automation): string {
    const [effectId, params] = Object.entries(automation.connections)[0] ?? [];
    const effect = this.project.effects.find((item) => item.id === effectId);
    return `${effect?.name ?? "Effect"} \u00b7 ${params?.[0] ?? "param"}`;
  }

  /**
   * Reference timeline layout: clips sit at `rowIndex × rowHeight`, so a lane
   * can hold several clips. Empty lanes between occupied rows are still drawn.
   */
  private layout(): { rows: TimelineRow[]; bottom: number } {
    const byId = new Map(this.project.nodes.map((node) => [node.id, node]));
    const rows: TimelineRow[] = [];
    let y = HEADER;
    let index = 0;
    const assigned = new Set(this.project.layers.flatMap((layer) => layer.nodeIds));
    const groups: {
      id?: string;
      name: string;
      visible: boolean;
      nodes: AnyNode[];
    }[] = [];
    for (const layer of this.project.layers) {
      groups.push({
        id: layer.id,
        name: layer.name,
        visible: layer.enabled,
        nodes: layer.nodeIds
          .map((id) => byId.get(id))
          .filter((node): node is AnyNode => Boolean(node)),
      });
    }
    const orphans = this.project.nodes.filter((node) => !assigned.has(node.id));
    if (orphans.length > 0) {
      groups.push({ name: "Unassigned", visible: true, nodes: orphans });
    }

    for (const group of groups) {
      rows.push({
        y,
        height: LAYER_HEIGHT,
        index: index++,
        kind: "layer",
        layerId: group.id,
        layerName: group.name,
        visible: group.visible,
        nodes: [],
      });
      y += LAYER_HEIGHT;

      // Pack overlapping clips into sub-lanes under their layer.
      const lanes: { end: number; nodes: AnyNode[] }[] = [];
      const ordered = [...group.nodes].sort(
        (a, b) => a.start - b.start || a.duration - b.duration,
      );
      for (const node of ordered) {
        let lane = lanes.find((entry) => entry.end <= node.start + 1e-3);
        if (!lane) {
          lane = { end: 0, nodes: [] };
          lanes.push(lane);
        }
        lane.nodes.push(node);
        lane.end = Math.max(lane.end, node.start + node.duration);
      }
      for (const lane of lanes) {
        rows.push({
          y,
          height: ROW_HEIGHT,
          index: index++,
          kind: "clips",
          layerId: group.id,
          layerName: group.name,
          nodes: lane.nodes,
        });
        y += ROW_HEIGHT;
      }

      if (group.id && this.expandedLayers.has(group.id)) {
        const members = new Set(group.nodes.map((node) => node.id));
        this.project.automations.forEach((automation, automationIndex) => {
          if (!automation.nodeId || !members.has(automation.nodeId)) return;
          rows.push({
            y,
            height: AUTOMATION_ROW_HEIGHT,
            index: index++,
            kind: "automation",
            layerId: group.id,
            layerName: group.name,
            automationIndex,
            nodes: [],
          });
          y += AUTOMATION_ROW_HEIGHT;
        });
      }
    }
    return { rows, bottom: y };
  }

  /** Keyframe diamonds can be hidden, like the reference's "Hide keyframes". */
  showKeyframes = true;

  render(time: number, selectedId: string | null, follow = false): void {
    this.time = time;
    this.viewStart = Math.max(0, Math.min(this.maxViewStart, this.viewStart));
    if (follow) {
      if (time < this.viewStart || time > this.viewStart + this.visibleDuration * 0.9) {
        this.viewStart = Math.max(
          0,
          Math.min(this.maxViewStart, time - this.visibleDuration * 0.2),
        );
      }
    }
    const dpr = this.dpr;
    const effectTracks = this.showKeyframes ? this.effectTracks() : [];
    const effectHeight = effectTracks.length > 0 ? 16 + effectTracks.length * 18 : 0;
    const { rows, bottom } = this.layout();
    const band = this.audioBand(bottom);
    const audioSpace = this.waveform ? AUDIO_HEIGHT + 10 : 0;
    const height = bottom + audioSpace + 120 + effectHeight;
    const pixelWidth = Math.max(1, Math.floor(this.width * dpr));
    const pixelHeight = Math.max(1, Math.floor(height * dpr));
    if (this.canvas.width !== pixelWidth || this.canvas.height !== pixelHeight) {
      this.canvas.width = pixelWidth;
      this.canvas.height = pixelHeight;
      this.cacheKey = "";
    }
    this.canvas.style.height = `${height}px`;

    const ctx = this.ctx;
    const key = this.staticKey(height);
    // Playback changes only the playhead, so reuse the cached static layer and
    // redraw just the transient overlays.
    if (this.cache && this.cacheCtx && this.cacheKey === key) {
      this.renderStats.cached += 1;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, pixelWidth, pixelHeight);
      ctx.drawImage(this.cache, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.drawOverlays(ctx, time, height);
      this.syncScrollbar();
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, this.width, height);
    this.renderStats.full += 1;

    ctx.fillStyle = "#141419";
    ctx.fillRect(0, 0, this.width, height);

    // Ruler.
    ctx.fillStyle = "#0f0f13";
    ctx.fillRect(0, 0, this.width, HEADER);
    ctx.font = "11px ui-monospace, monospace";
    ctx.fillStyle = "#6f7080";
    const visible = this.visibleDuration;
    const step = visible <= 15 ? 1 : Math.ceil(visible / 12);
    const first = Math.max(0, Math.floor(this.viewStart / step) * step);
    for (let t = first; t <= this.viewStart + visible + 0.001; t += step) {
      const x = this.timeToX(t);
      ctx.fillRect(x, 0, 1, HEADER);
      ctx.fillText(`${t.toFixed(0)}s`, x + 3, 14);
    }

    // Ruler markers.
    for (const marker of this.project.markers) {
      const mx = this.timeToX(marker.time);
      if (mx < -10 || mx > this.width + 10) continue;
      ctx.fillStyle = "rgba(240, 180, 41, 0.14)";
      ctx.fillRect(mx, HEADER, 1, height - HEADER);
      ctx.fillStyle = "#f0b429";
      ctx.fillRect(mx, 0, 1, HEADER);
      ctx.beginPath();
      ctx.moveTo(mx, 0);
      ctx.lineTo(mx + 8, 0);
      ctx.lineTo(mx + 8, 5);
      ctx.lineTo(mx, 5);
      ctx.closePath();
      ctx.fill();
    }

    // Loop region (Shift-drag the ruler).
    if (this.loopRange) {
      const left = this.timeToX(this.loopRange.start);
      const right = this.timeToX(this.loopRange.end);
      ctx.fillStyle = "rgba(139, 156, 255, 0.18)";
      ctx.fillRect(left, 0, Math.max(1, right - left), HEADER);
      ctx.fillStyle = "rgba(139, 156, 255, 0.9)";
      ctx.fillRect(left, 0, 2, HEADER);
      ctx.fillRect(Math.max(left, right - 2), 0, 2, HEADER);
    }

    // Rows. The reference clips span the full row width and carry their label
    // inside; there is no separate gutter column.
    ctx.textBaseline = "middle";
    for (const row of rows) {
      const y = row.y;
      if (row.kind === "layer") {
        ctx.fillStyle = "#101116";
        ctx.fillRect(0, y, this.width, row.height);
        ctx.fillStyle = "rgba(139, 156, 255, 0.8)";
        ctx.fillRect(0, y, 2, row.height);
        // Visibility checkbox.
        ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
        ctx.lineWidth = 1;
        ctx.strokeRect(10.5, y + 6.5, 11, 11);
        if (row.visible) {
          ctx.fillStyle = "rgba(139, 156, 255, 0.92)";
          ctx.fillRect(13, y + 9, 6, 6);
        }
        ctx.fillStyle = "rgba(255, 255, 255, 0.72)";
        ctx.font = "12px system-ui, sans-serif";
        ctx.fillText(row.layerName ?? "", 44, y + row.height / 2);
        // Automation disclosure.
        const expanded = row.layerId ? this.expandedLayers.has(row.layerId) : false;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.6)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        if (expanded) {
          ctx.moveTo(27, y + 9);
          ctx.lineTo(33, y + 15);
          ctx.lineTo(39, y + 9);
        } else {
          ctx.moveTo(29, y + 9);
          ctx.lineTo(35, y + 12);
          ctx.lineTo(29, y + 15);
        }
        ctx.stroke();
        const count =
          this.project.layers.find((layer) => layer.id === row.layerId)?.nodeIds.length ?? 0;
        ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
        ctx.font = "10px ui-monospace, monospace";
        ctx.textAlign = "right";
        ctx.fillText(String(count), this.width - 10, y + row.height / 2);
        ctx.textAlign = "start";
        ctx.fillStyle = "rgba(255, 255, 255, 0.06)";
        ctx.fillRect(0, y + row.height - 1, this.width, 1);
        continue;
      }

      if (row.kind === "automation" && row.automationIndex !== undefined) {
        const automation = this.project.automations[row.automationIndex];
        const range = this.laneRange(automation);
        ctx.fillStyle = "#0b0b10";
        ctx.fillRect(0, y, this.width, row.height);
        ctx.fillStyle = "rgba(255, 255, 255, 0.035)";
        ctx.fillRect(0, y + row.height - 1, this.width, 1);
        ctx.fillStyle = "rgba(255, 255, 255, 0.62)";
        ctx.font = "10px system-ui, sans-serif";
        ctx.fillText(this.automationLaneLabel(automation), 44, y + 9);
        ctx.fillStyle = "rgba(255, 255, 255, 0.28)";
        ctx.textAlign = "right";
        ctx.fillText(String(Number(range.max.toFixed(2))), this.width - 8, y + 9);
        ctx.fillText(String(Number(range.min.toFixed(2))), this.width - 8, y + row.height - 9);
        ctx.textAlign = "start";
        const color =
          automation.type === "audioImpact"
            ? "#f0b429"
            : automation.type === "math"
              ? "#8b9cff"
              : "#c08f2a";
        const sorted = [...automation.keyframes].sort((a, b) => a.t - b.t);
        if (sorted.length > 0) {
          ctx.beginPath();
          sorted.forEach((key, index) => {
            const kx = this.timeToX(key.t);
            const ky = this.valueToLaneY(key.value, y, row.height, range);
            if (index === 0) ctx.moveTo(kx, ky);
            else ctx.lineTo(kx, ky);
          });
          ctx.strokeStyle = tint(color, 0.75);
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        for (const key of sorted) {
          const kx = this.timeToX(key.t);
          const ky = this.valueToLaneY(key.value, y, row.height, range);
          ctx.beginPath();
          ctx.moveTo(kx, ky - KEY_RADIUS);
          ctx.lineTo(kx + KEY_RADIUS, ky);
          ctx.lineTo(kx, ky + KEY_RADIUS);
          ctx.lineTo(kx - KEY_RADIUS, ky);
          ctx.closePath();
          ctx.fillStyle = this.selectedKeys.has(key) ? "#ffffff" : color;
          ctx.fill();
        }
        continue;
      }

      const rowSelected = row.nodes.some((node) => this.selection.has(node.id));
      const rowHovered = row.nodes.some((node) => node.id === this.hoverNode);

      ctx.fillStyle = rowSelected ? "#16161d" : rowHovered ? "#16161d" : "#141419";
      ctx.fillRect(0, y, this.width, row.height);

      // The selected clip draws last, like the reference's z-index.
      const ordered = [...row.nodes].sort((a, b) => {
        const sa = this.selection.has(a.id) ? 1 : 0;
        const sb = this.selection.has(b.id) ? 1 : 0;
        return sa - sb;
      });
      for (const node of ordered) {
        const selected = this.selection.has(node.id);
        const hovered = node.id === this.hoverNode;
        const x0 = this.timeToX(node.start);
        const x1 = this.timeToX(node.start + node.duration);
        const width = Math.max(2, x1 - x0);
        const accent = CLIP_TINTS[node.typeLabel] ?? "#8b9cff";
        const alpha = selected ? 0.22 : hovered ? 0.16 : 0.1 + Math.min(0.04, row.index * 0.01);
        ctx.fillStyle = tint(accent, alpha);
        ctx.fillRect(x0, y, width, row.height);
        // Thin accent header gives each item kind an identity without a loud bar.
        ctx.fillStyle = tint(accent, selected ? 0.95 : 0.7);
        ctx.fillRect(x0, y, width, 2);
        // Reference clip handles: a white 2px marker at each end.
        ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
        ctx.fillRect(x0, y, 2, row.height);
        ctx.fillRect(Math.max(x0, x1 - 2), y, 2, row.height);
        // Hover/selection reveals wider trim grips.
        if (hovered || selected) {
          ctx.fillStyle = "rgba(255, 255, 255, 0.32)";
          ctx.fillRect(x0, y + 6, 4, row.height - 12);
          ctx.fillRect(Math.max(x0, x1 - 4), y + 6, 4, row.height - 12);
        }

        // Clip name inside the bar.
        if (width > 24) {
          ctx.save();
          ctx.beginPath();
          ctx.rect(x0, y, width, row.height);
          ctx.clip();
          ctx.fillStyle = selected ? "#ffffff" : "rgba(255, 255, 255, 0.82)";
          ctx.font = "14.4px system-ui, sans-serif";
          ctx.fillText(node.name, x0 + 17, y + row.height / 2);
          ctx.restore();
        }

        // A note badge marks clips with a comment.
        if ((node as AnyNode & { note?: string }).note) {
          ctx.fillStyle = "#f0b429";
          ctx.beginPath();
          ctx.arc(Math.max(x0 + 8, x1 - 10), y + 10, 3, 0, Math.PI * 2);
          ctx.fill();
        }

        // Automation keyframes live on the clip row, like the reference's
        // keyframe dots. Multiple tracks stack a few pixels apart.
        if (this.showKeyframes) {
          const tracks = this.tracksFor(node);
          const base = y + row.height - 6;
          tracks.forEach(({ automation }, trackIndex) => {
            const ky = base - (tracks.length - 1 - trackIndex) * 3;
            for (const key of automation.keyframes) {
              const kx = this.timeToX(key.t);
              ctx.beginPath();
              ctx.moveTo(kx, ky - KEY_RADIUS);
              ctx.lineTo(kx + KEY_RADIUS, ky);
              ctx.lineTo(kx, ky + KEY_RADIUS);
              ctx.lineTo(kx - KEY_RADIUS, ky);
              ctx.closePath();
              ctx.fillStyle = this.selectedKeys.has(key)
                ? "#ffffff"
                : selected
                  ? "#f0b429"
                  : "#c08f2a";
              ctx.fill();
            }
          });
        }
      }
    }

    // Audio band: peak envelope under the item rows.
    if (this.waveform) {
      const y = band.y;
      ctx.fillStyle = "#101116";
      ctx.fillRect(0, y, this.width, AUDIO_HEIGHT);
      ctx.fillStyle = "#181922";
      ctx.fillRect(0, y + AUDIO_HEIGHT - 1, this.width, 1);
      const mid = y + AUDIO_HEIGHT / 2 + 4;
      const half = (AUDIO_HEIGHT - 16) / 2;
      const peaks = this.waveform;
      ctx.beginPath();
      for (let x = 0; x <= this.width; x += 1) {
        const t = this.viewStart + (x / Math.max(1, this.width)) * this.visibleDuration;
        const index = Math.max(0, Math.min(peaks.length - 1, Math.floor((t / Math.max(0.001, this.project.duration)) * peaks.length)));
        const yy = mid - peaks[index] * half;
        if (x === 0) ctx.moveTo(x, yy);
        else ctx.lineTo(x, yy);
      }
      for (let x = this.width; x >= 0; x -= 1) {
        const t = this.viewStart + (x / Math.max(1, this.width)) * this.visibleDuration;
        const index = Math.max(0, Math.min(peaks.length - 1, Math.floor((t / Math.max(0.001, this.project.duration)) * peaks.length)));
        ctx.lineTo(x, mid + peaks[index] * half);
      }
      ctx.closePath();
      ctx.fillStyle = "rgba(139, 156, 255, 0.42)";
      ctx.fill();
      ctx.fillStyle = "#101116";
      ctx.fillRect(0, y, Math.min(200, this.width), 18);
      ctx.fillStyle = "rgba(255, 255, 255, 0.68)";
      ctx.font = "12px system-ui, sans-serif";
      ctx.fillText(this.audioLabel || "Audio", 17, y + 9);
    }

    // Effect-parameter tracks sit below the item rows, since effects are not
    // rows themselves. Keys are draggable exactly like item keys.
    if (effectTracks.length > 0) {
      let ty = band.effectsY;
      ctx.fillStyle = "#0f0f13";
      ctx.fillRect(0, ty, this.width, 16);
      ctx.fillStyle = "#6f7080";
      ctx.font = "10px ui-monospace, monospace";
      ctx.fillText("EFFECTS", 10, ty + 8);
      ty += 16;

      for (const { automation } of effectTracks) {
        ctx.fillStyle = "#111117";
        ctx.fillRect(0, ty, this.width, 18);
        ctx.fillStyle = "#4a4a58";
        ctx.fillText(this.effectTrackLabel(automation), 10, ty + 9);
        for (const key of automation.keyframes) {
          const kx = this.timeToX(key.t);
          const ky = ty + 9;
          ctx.beginPath();
          ctx.moveTo(kx, ky - KEY_RADIUS);
          ctx.lineTo(kx + KEY_RADIUS, ky);
          ctx.lineTo(kx, ky + KEY_RADIUS);
          ctx.lineTo(kx - KEY_RADIUS, ky);
          ctx.closePath();
          ctx.fillStyle = this.selectedKeys.has(key) ? "#ffffff" : "#f0b429";
          ctx.fill();
        }
        ty += 18;
      }
    }

    // Beat grid from the project tempo: bars are stronger than beats, and the
    // density is dropped when lines would be too close to read.
    {
      const beat = 60 / Math.max(1, this.project.bpm || 120);
      const beatPx = (beat / this.visibleDuration) * this.width;
      const barPx = beatPx * 4;
      if (barPx >= 6) {
        const bar = beat * 4;
        const firstBar = Math.floor(this.viewStart / bar) * bar;
        for (let t = firstBar; t <= this.viewStart + this.visibleDuration; t += bar) {
          const gx = this.timeToX(t);
          ctx.fillStyle = "rgba(255, 255, 255, 0.06)";
          ctx.fillRect(gx, HEADER, 1, height - HEADER);
        }
        if (beatPx >= 6) {
          const firstBeat = Math.floor(this.viewStart / beat) * beat;
          for (let t = firstBeat; t <= this.viewStart + this.visibleDuration; t += beat) {
            if (Math.abs(t / bar - Math.round(t / bar)) < 1e-6) continue;
            const gx = this.timeToX(t);
            ctx.fillStyle = "rgba(255, 255, 255, 0.028)";
            ctx.fillRect(gx, HEADER, 1, height - HEADER);
          }
        }
      }
    }

    if (this.project.nodes.length === 0) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
      ctx.font = "13px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Add an item to a layer, or choose audio to begin", this.width / 2, height / 2);
      ctx.textAlign = "start";
    }

    this.captureStatic(key);
    this.drawOverlays(ctx, time, height);
    this.syncScrollbar();
  }

  /** Everything that changes with playback or an in-progress gesture. */
  private drawOverlays(
    ctx: CanvasRenderingContext2D,
    time: number,
    height: number,
  ): void {
    // Marquee selection.
    if (this.drag?.kind === "marquee") {
      const left = Math.min(this.drag.x0, this.drag.x1);
      const top = Math.min(this.drag.y0, this.drag.y1);
      const width = Math.abs(this.drag.x1 - this.drag.x0);
      const boxHeight = Math.abs(this.drag.y1 - this.drag.y0);
      ctx.fillStyle = "rgba(139, 156, 255, 0.12)";
      ctx.fillRect(left, top, width, boxHeight);
      ctx.strokeStyle = "rgba(139, 156, 255, 0.8)";
      ctx.lineWidth = 1;
      ctx.strokeRect(
        left + 0.5,
        top + 0.5,
        Math.max(0, width - 1),
        Math.max(0, boxHeight - 1),
      );
    }

    // Snap guide while dragging an edge.
    if (this.snapGuide !== null) {
      const gx = this.timeToX(this.snapGuide);
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(gx, HEADER);
      ctx.lineTo(gx, height);
      ctx.stroke();
      ctx.restore();
    }

    this.drawDragReadout(ctx);
    this.drawSlipReadout(ctx);

    // Playhead: the reference uses a translucent indigo 2px line with a grey
    // down-pointing handle at the top of the ruler.
    const px = this.timeToX(time);
    ctx.fillStyle = "rgba(100, 100, 255, 0.3)";
    ctx.fillRect(px, 7, 2, height - 7);
    ctx.beginPath();
    ctx.moveTo(px - 5, 0);
    ctx.lineTo(px + 5, 0);
    ctx.lineTo(px, 7);
    ctx.closePath();
    ctx.fillStyle = "#999999";
    ctx.fill();
  }

  /**
   * Copy the finished static frame into an offscreen canvas. Playback then
   * redraws only the playhead instead of every clip, key and grid line.
   */
  private captureStatic(key: string): void {
    if (!this.cache) {
      this.cache = document.createElement("canvas");
      this.cacheCtx = this.cache.getContext("2d");
    }
    if (!this.cacheCtx) return;
    if (this.cache.width !== this.canvas.width || this.cache.height !== this.canvas.height) {
      this.cache.width = this.canvas.width;
      this.cache.height = this.canvas.height;
    }
    this.cacheCtx.setTransform(1, 0, 0, 1, 0, 0);
    this.cacheCtx.clearRect(0, 0, this.cache.width, this.cache.height);
    this.cacheCtx.drawImage(this.canvas, 0, 0);
    this.cacheKey = key;
  }

  /** State that affects the static frame; when it changes the cache is redrawn. */
  private staticKey(height: number): string {
    const nodes = this.project.nodes
      .map((node) => {
        const note = (node as AnyNode & { note?: string }).note ?? "";
        return [
          node.id,
          node.start.toFixed(4),
          node.duration.toFixed(4),
          node.name,
          node.typeLabel,
          node.visible ? 1 : 0,
          node.solo ? 1 : 0,
          node.shy ? 1 : 0,
          note,
        ].join(":");
      })
      .join("|");
    const layers = this.project.layers
      .map((layer) => `${layer.id}:${layer.name}:${layer.enabled ? 1 : 0}:${layer.nodeIds.join(",")}`)
      .join("|");
    const automations = this.project.automations
      .map((automation) =>
        [
          automation.id,
          automation.type,
          automation.nodeId ?? "",
          automation.propertyId ?? "",
          automation.name ?? "",
          automation.keyframes
            .map((key) => `${key.t.toFixed(4)}:${key.value.toFixed(4)}`)
            .join(","),
        ].join(":"),
      )
      .join("|");
    const effects = this.project.effects
      .map((effect) => `${effect.id}:${effect.name}:${effect.enabled ? 1 : 0}`)
      .join("|");
    const markers = this.project.markers
      .map((marker) => `${marker.id}:${marker.time.toFixed(4)}:${marker.name}`)
      .join("|");
    const keys = this.getSelectedKeys()
      .map(
        (entry) => `${entry.automationId}:${entry.time.toFixed(4)}:${entry.value.toFixed(4)}`,
      )
      .join(",");
    return [
      this.width,
      height,
      this.dpr,
      this.viewStart.toFixed(4),
      this.visibleDuration.toFixed(4),
      this.showKeyframes ? 1 : 0,
      this.project.duration,
      this.project.bpm,
      this.project.fps,
      this.loopRange ? `${this.loopRange.start}:${this.loopRange.end}` : "",
      markers,
      nodes,
      layers,
      automations,
      effects,
      [...this.expandedLayers].join(","),
      this.hoverNode ?? "",
      [...this.selection].join(","),
      this.selectedId ?? "",
      keys,
      this.waveform?.length ?? 0,
      this.audioLabel,
    ].join("~");
  }

  private keyPositions(): {
    automationIndex: number;
    automation: Automation;
    key: Keyframe;
    x: number;
    y: number;
    kind: "lane" | "clip" | "effect";
    lane: { rowY: number; height: number; range: { min: number; max: number } } | null;
  }[] {
    const out: {
      automationIndex: number;
      automation: Automation;
      key: Keyframe;
      x: number;
      y: number;
      kind: "lane" | "clip" | "effect";
      lane: { rowY: number; height: number; range: { min: number; max: number } } | null;
    }[] = [];
    const { rows, bottom } = this.layout();
    for (const entry of rows) {
      if (entry.kind === "automation" && entry.automationIndex !== undefined) {
        const automation = this.project.automations[entry.automationIndex];
        const lane = { rowY: entry.y, height: entry.height, range: this.laneRange(automation) };
        for (const key of automation.keyframes) {
          out.push({
            automationIndex: entry.automationIndex,
            automation,
            key,
            x: this.timeToX(key.t),
            y: this.valueToLaneY(key.value, lane.rowY, lane.height, lane.range),
            kind: "lane",
            lane,
          });
        }
        continue;
      }
      for (const node of entry.nodes) {
        const tracks = this.tracksFor(node);
        const base = entry.y + entry.height - 6;
        tracks.forEach(({ automation, index }, trackIndex) => {
          const y = base - (tracks.length - 1 - trackIndex) * 3;
          for (const key of automation.keyframes) {
            out.push({
              automationIndex: index,
              automation,
              key,
              x: this.timeToX(key.t),
              y,
              kind: "clip",
              lane: null,
            });
          }
        });
      }
    }
    if (this.showKeyframes) {
      const band = this.audioBand(bottom);
      let ty = band.effectsY + 16;
      for (const { automation, index } of this.effectTracks()) {
        for (const key of automation.keyframes) {
          out.push({
            automationIndex: index,
            automation,
            key,
            x: this.timeToX(key.t),
            y: ty + 9,
            kind: "effect",
            lane: null,
          });
        }
        ty += 18;
      }
    }
    return out;
  }

  private hitKeyframe(
    x: number,
    y: number,
  ): { automationIndex: number; keyIndex: number; automation: Automation; key: Keyframe } | null {
    let hit: { automationIndex: number; keyIndex: number; automation: Automation; key: Keyframe } | null =
      null;
    for (const entry of this.keyPositions()) {
      if (Math.abs(entry.x - x) <= KEY_RADIUS + 3 && Math.abs(entry.y - y) <= 9) {
        hit = {
          automationIndex: entry.automationIndex,
          keyIndex: entry.automation.keyframes.indexOf(entry.key),
          automation: entry.automation,
          key: entry.key,
        };
      }
    }
    return hit;
  }

  /** Visible key positions, for marquee/checks. */
  getKeyPositions(): {
    automationId: string;
    automationIndex: number;
    keyIndex: number;
    time: number;
    value: number;
    kind: "lane" | "clip" | "effect";
    x: number;
    y: number;
    selected: boolean;
  }[] {
    return this.keyPositions().map((entry) => ({
      automationId: entry.automation.id,
      automationIndex: entry.automationIndex,
      keyIndex: entry.automation.keyframes.indexOf(entry.key),
      time: entry.key.t,
      value: entry.key.value,
      kind: entry.kind,
      x: entry.x,
      y: entry.y,
      selected: this.selectedKeys.has(entry.key),
    }));
  }

  getSelectedKeys(): { automationId: string; time: number; value: number }[] {
    const out: { automationId: string; time: number; value: number }[] = [];
    for (const automation of this.project.automations) {
      for (const key of automation.keyframes) {
        if (this.selectedKeys.has(key)) {
          out.push({ automationId: automation.id, time: key.t, value: key.value });
        }
      }
    }
    return out;
  }

  private selectedId: string | null = null;

  private onPointerDown = (event: PointerEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    // Synthetic pointer events (tests) have no active pointer to capture.
    try {
      this.canvas.setPointerCapture(event.pointerId);
    } catch {
      /* untrusted event */
    }

    if (y <= HEADER) {
      if (event.shiftKey) {
        const anchor = this.xToTime(x);
        this.loopRange = { start: anchor, end: anchor };
        this.drag = { kind: "loop", anchor };
        this.render(this.time, this.selectedId);
        return;
      }
      if (this.loopRange) {
        const startX = this.timeToX(this.loopRange.start);
        const endX = this.timeToX(this.loopRange.end);
        if (Math.abs(x - startX) <= 4) {
          this.drag = { kind: "loop-edge", edge: "start" };
          return;
        }
        if (Math.abs(x - endX) <= 4) {
          this.drag = { kind: "loop-edge", edge: "end" };
          return;
        }
      }
      const marker = this.markerAt(x);
      if (marker >= 0) {
        this.drag = {
          kind: "marker",
          marker: this.project.markers[marker],
          startX: x,
          moved: false,
        };
        return;
      }
      this.callbacks.onSeek(this.xToTime(x));
      this.drag = { kind: "playhead" };
      return;
    }

    if (this.tool === "hand") {
      this.drag = { kind: "pan", startX: x, startView: this.viewStart };
      this.canvas.style.cursor = "grabbing";
      return;
    }

    if (this.tool === "slip") {
      const target = this.nodeAt(x, y);
      if (target) {
        this.selection = new Set([target.id]);
        this.selectedId = target.id;
        this.callbacks.onSelectMany?.([target.id]);
        this.callbacks.onSelect?.(target.id);
        const sourceIn = (target as AnyNode & { sourceIn?: number }).sourceIn;
        const hasSource = typeof sourceIn === "number";
        this.slipReadout = hasSource
          ? { nodeId: target.id, source: sourceIn, delta: 0 }
          : null;
        this.drag = {
          kind: "slip",
          nodeId: target.id,
          startX: x,
          startSource: hasSource ? sourceIn : 0,
          hasSource,
        };
        this.render(this.time, this.selectedId);
      }
      return;
    }

    if (this.tool === "razor") {
      const target = this.nodeAt(x, y);
      if (target) this.callbacks.onSplitAt?.(target.id, this.xToTime(x));
      return;
    }

    const key = this.hitKeyframe(x, y);
    if (key) {
      const additive = event.ctrlKey || event.metaKey || event.shiftKey;
      if (additive) {
        if (this.selectedKeys.has(key.key)) this.selectedKeys.delete(key.key);
        else this.selectedKeys.add(key.key);
      } else if (!this.selectedKeys.has(key.key)) {
        this.selectedKeys = new Set([key.key]);
      }
      if (this.selectedKeys.has(key.key)) {
        const lanes = new Map<
          string,
          { rowY: number; height: number; range: { min: number; max: number } }
        >();
        for (const row of this.layout().rows) {
          if (row.kind !== "automation" || row.automationIndex === undefined) continue;
          const automation = this.project.automations[row.automationIndex];
          lanes.set(automation.id, {
            rowY: row.y,
            height: row.height,
            range: this.laneRange(automation),
          });
        }
        const entries = [...this.selectedKeys]
          .map((entry) => {
            const automation = this.project.automations.find((row) =>
              row.keyframes.includes(entry),
            );
            if (!automation) return null;
            return {
              automation,
              key: entry,
              originalTime: entry.t,
              originalValue: entry.value,
              lane: lanes.get(automation.id) ?? null,
            };
          })
          .filter(
            (
              entry,
            ): entry is {
              automation: Automation;
              key: Keyframe;
              originalTime: number;
              originalValue: number;
              lane: { rowY: number; height: number; range: { min: number; max: number } } | null;
            } => Boolean(entry),
          );
        this.frozenRanges.clear();
        for (const [id, lane] of lanes) this.frozenRanges.set(id, lane.range);
        this.drag = {
          kind: "keys",
          anchorTime: this.xToTime(x),
          anchorY: y,
          entries,
        };
      }
      this.render(this.time, this.selectedId);
      return;
    }

    const row = this.rowAt(y);
    if (row?.kind === "layer") {
      if (!row.layerId) return;
      if (x < 24) {
        this.callbacks.onToggleLayer?.(row.layerId);
      } else if (x < 42) {
        if (this.expandedLayers.has(row.layerId)) this.expandedLayers.delete(row.layerId);
        else this.expandedLayers.add(row.layerId);
        this.render(this.time, this.selectedId);
      } else {
        this.callbacks.onSelectLayer?.(row.layerId);
      }
      return;
    }

    const node = this.nodeAt(x, y);
    if (node) {
      const additive = event.ctrlKey || event.metaKey || event.shiftKey;
      if (!additive && this.selectedKeys.size > 0) this.selectedKeys.clear();
      if (additive) {
        if (this.selection.has(node.id)) this.selection.delete(node.id);
        else this.selection.add(node.id);
        this.selectedId = this.selection.has(node.id)
          ? node.id
          : (this.selection.values().next().value ?? null);
        this.callbacks.onSelectMany?.([...this.selection]);
        if (this.selectedId) this.callbacks.onSelect(this.selectedId);
        this.render(this.time, this.selectedId);
        return;
      }
      if (!this.selection.has(node.id)) {
        this.selection = new Set([node.id]);
        this.callbacks.onSelectMany?.([node.id]);
      }
      this.selectedId = node.id;
      this.callbacks.onSelect(node.id);
      const x0 = this.timeToX(node.start);
      const x1 = this.timeToX(node.start + node.duration);
      const edge = 4;
      if (this.selection.size <= 1 && (Math.abs(x - x0) <= edge || Math.abs(x - x1) <= edge)) {
        this.drag = {
          kind: "resize",
          nodeId: node.id,
          edge: Math.abs(x - x0) <= edge ? "start" : "end",
          start: node.start,
          duration: node.duration,
        };
      } else if (x >= x0 - 3 && x <= x1 + 3) {
        this.drag = { kind: "move", nodeId: node.id, offset: this.xToTime(x) - node.start };
      } else {
        this.callbacks.onSeek(this.xToTime(x));
        this.drag = { kind: "playhead" };
      }
      return;
    }

    // Empty track space (or below the rows): a click seeks, a drag creates a
    // marquee selection.
    const additive = event.ctrlKey || event.metaKey || event.shiftKey;
    const base = additive ? [...this.selection] : [];
    const keyBase = additive ? [...this.selectedKeys] : [];
    if (!additive) {
      this.selection.clear();
      this.selectedKeys.clear();
      this.selectedId = null;
      this.callbacks.onSelectMany?.([]);
      this.callbacks.onSelect(null);
    }
    this.drag = {
      kind: "marquee",
      x0: x,
      y0: y,
      x1: x,
      y1: y,
      additive,
      base,
      keyBase,
    };
    this.render(this.time, this.selectedId);
  };

  private onPointerMove = (event: PointerEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    if (!this.drag) {
      if (this.tool === "hand") {
        this.hoverNode = null;
        this.canvas.style.cursor = "grab";
        return;
      }
      if (this.tool === "slip") {
        this.hoverNode = this.nodeAt(x, y)?.id ?? null;
        this.canvas.style.cursor = "ew-resize";
        return;
      }
      if (this.tool === "razor") {
        this.hoverNode = this.nodeAt(x, y)?.id ?? null;
        this.canvas.style.cursor = "crosshair";
        return;
      }
      this.hoverNode = this.nodeAt(x, y)?.id ?? null;
      const loopEdge =
        y <= HEADER &&
        this.loopRange !== null &&
        (Math.abs(x - this.timeToX(this.loopRange.start)) <= 4 ||
          Math.abs(x - this.timeToX(this.loopRange.end)) <= 4);
      this.canvas.style.cursor = loopEdge
        ? "col-resize"
        : this.edgeAt(x, y)
          ? "col-resize"
          : this.hoverNode
            ? "grab"
            : "default";
      return;
    }

    if (this.drag.kind === "pan") {
      const dx = x - this.drag.startX;
      this.viewStart = Math.max(
        0,
        Math.min(
          this.maxViewStart,
          this.drag.startView - (dx / Math.max(1, this.width)) * this.visibleDuration,
        ),
      );
      this.render(this.time, this.selectedId);
      return;
    }
    if (this.drag.kind === "marquee") {
      this.drag.x1 = x;
      this.drag.y1 = y;
      this.render(this.time, this.selectedId);
      return;
    }

    if (this.drag.kind === "playhead") {
      this.callbacks.onSeek(this.xToTime(x));
      return;
    }
    if (this.drag.kind === "loop") {
      const time = this.xToTime(x);
      const start = Math.min(this.drag.anchor, time);
      const end = Math.max(this.drag.anchor, time);
      this.loopRange = end - start >= 0.02 ? { start, end } : null;
      this.render(this.time, this.selectedId);
      return;
    }
    if (this.drag.kind === "loop-edge" && this.loopRange) {
      const time = this.snapTime(this.xToTime(x), undefined, event.altKey);
      if (this.drag.edge === "start") {
        const end = this.loopRange.end;
        this.loopRange = { start: Math.max(0, Math.min(time, end - 0.02)), end };
      } else {
        const start = this.loopRange.start;
        this.loopRange = {
          start,
          end: Math.max(start + 0.02, Math.min(this.project.duration, time)),
        };
      }
      this.render(this.time, this.selectedId);
      return;
    }
    if (this.drag.kind === "marker") {
      if (Math.abs(x - this.drag.startX) > 2) this.drag.moved = true;
      if (this.drag.moved) {
        const time = Math.max(
          0,
          Math.min(this.project.duration, this.snapTime(this.xToTime(x), undefined, event.altKey)),
        );
        this.callbacks.onMoveMarker?.(
          this.drag.marker,
          Math.round(time * 100) / 100,
        );
      }
      return;
    }
    if (this.drag.kind === "slip") {
      const delta =
        ((x - this.drag.startX) / Math.max(1, this.width)) * this.visibleDuration;
      const clamped = this.drag.hasSource
        ? Math.max(delta, -this.drag.startSource)
        : delta;
      this.callbacks.onSlip?.(this.drag.nodeId, Math.round(clamped * 1000) / 1000);
      if (this.drag.hasSource) {
        this.slipReadout = {
          nodeId: this.drag.nodeId,
          source: Math.max(0, this.drag.startSource + clamped),
          delta: clamped,
        };
      }
      return;
    }
    if (this.drag.kind === "resize") {
      const time = this.snapTime(this.xToTime(x), this.drag.nodeId, event.altKey);
      let start = this.drag.start;
      let duration = this.drag.duration;
      if (this.drag.edge === "end") {
        duration = Math.max(0.1, time - start);
      } else {
        const end = start + duration;
        start = Math.max(0, Math.min(time, end - 0.1));
        duration = end - start;
      }
      this.callbacks.onResize(
        this.drag.nodeId,
        Math.round(start * 100) / 100,
        Math.round(duration * 100) / 100,
        this.drag.edge,
      );
      const roundedStart = Math.round(start * 100) / 100;
      const roundedDuration = Math.round(duration * 100) / 100;
      this.dragReadout = {
        nodeId: this.drag.nodeId,
        start: roundedStart,
        end: roundedStart + roundedDuration,
      };
      return;
    }
    if (this.drag.kind === "move") {
      const source = this.project.nodes.find((node) => node.id === (this.drag as { nodeId: string }).nodeId);
      if (!source) return;
      const snapped = this.snapTime(
        this.xToTime(x) - (this.drag as { offset: number }).offset,
        source.id,
        event.altKey,
      );
      if (this.selection.size > 1) {
        const delta = snapped - source.start;
        const moves = [...this.selection]
          .map((id) => {
            const node = this.project.nodes.find((entry) => entry.id === id);
            if (!node) return null;
            return {
              id,
              start: Math.max(0, Math.min(this.project.duration, node.start + delta)),
            };
          })
          .filter((entry): entry is { id: string; start: number } => Boolean(entry));
        this.callbacks.onMoveMany?.(moves);
        const primary = moves.find((entry) => entry.id === source.id) ?? moves[0];
        if (primary) {
          this.dragReadout = {
            nodeId: primary.id,
            start: primary.start,
            end: primary.start + source.duration,
          };
        }
      } else {
        const start = Math.max(0, Math.min(this.project.duration, snapped));
        const rounded = Math.round(start * 100) / 100;
        this.callbacks.onMoveStart(source.id, rounded);
        this.dragReadout = { nodeId: source.id, start: rounded, end: rounded + source.duration };
      }
      return;
    }
    if (this.drag.kind === "keys") {
      const target = this.snapTime(this.xToTime(x), undefined, event.altKey);
      let delta = target - this.drag.anchorTime;
      const earliest = Math.min(...this.drag.entries.map((entry) => entry.originalTime));
      if (earliest + delta < 0) delta = -earliest;
      const dy = this.drag.anchorY - y;
      this.callbacks.onMoveKeyframes?.(
        this.drag.entries.map((entry) => {
          let value = entry.originalValue;
          if (entry.lane) {
            const usable = Math.max(1, entry.lane.height - GRAPH_PADDING * 2);
            value =
              entry.originalValue +
              dy * ((entry.lane.range.max - entry.lane.range.min) / usable);
          }
          return {
            automation: entry.automation,
            key: entry.key,
            time: Math.round((entry.originalTime + delta) * 100) / 100,
            value: Math.round(value * 10000) / 10000,
          };
        }),
      );
      return;
    }
  };

  private onPointerUp = (): void => {
    if (this.drag?.kind === "marker") {
      if (!this.drag.moved) this.callbacks.onSeek(this.drag.marker.time);
      else this.callbacks.onMoveMarkerEnd?.();
    }
    if (this.drag?.kind === "slip") {
      this.callbacks.onSlipEnd?.();
    }
    if (this.drag?.kind === "keys") {
      this.frozenRanges.clear();
      this.callbacks.onCommitKeyframes?.();
      this.render(this.time, this.selectedId);
    }
    if (this.drag?.kind === "loop" && this.loopRange) {
      if (this.loopRange.end - this.loopRange.start < 0.05) this.loopRange = null;
      this.render(this.time, this.selectedId);
    }
    if (this.drag?.kind === "marquee") {
      const { x0, y0, x1, y1, base } = this.drag;
      if (Math.abs(x1 - x0) < 3 && Math.abs(y1 - y0) < 3) {
        this.callbacks.onSeek(this.xToTime(x1));
      } else {
        const left = Math.min(x0, x1);
        const right = Math.max(x0, x1);
        const top = Math.min(y0, y1);
        const bottom = Math.max(y0, y1);
        const selected = new Set(base);
        for (const row of this.layout().rows) {
          if (row.kind !== "clips") continue;
          if (row.y + row.height < top || row.y > bottom) continue;
          for (const node of row.nodes) {
            const nx0 = this.timeToX(node.start);
            const nx1 = this.timeToX(node.start + node.duration);
            if (nx1 >= left && nx0 <= right) selected.add(node.id);
          }
        }
        this.selection = selected;
        this.selectedId = selected.values().next().value ?? null;
        this.selectedKeys = new Set(this.drag.keyBase);
        for (const entry of this.keyPositions()) {
          if (
            entry.x >= left &&
            entry.x <= right &&
            entry.y >= top &&
            entry.y <= bottom
          ) {
            this.selectedKeys.add(entry.key);
          }
        }
        this.callbacks.onSelectMany?.([...selected]);
        if (this.selectedId) this.callbacks.onSelect(this.selectedId);
        this.render(this.time, this.selectedId);
      }
    }
    this.drag = null;
    this.snapGuide = null;
    const hadReadout = this.dragReadout !== null;
    const hadSlip = this.slipReadout !== null;
    this.dragReadout = null;
    this.slipReadout = null;
    if (hadReadout || hadSlip) this.render(this.time, this.selectedId);
    this.canvas.style.cursor =
      this.tool === "hand" ? "grab" : this.tool === "slip" ? "ew-resize" : "default";
  };

  private onDoubleClick = (event: MouseEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    if (event.clientY - rect.top > HEADER) return;
    if (!this.loopRange) return;
    this.loopRange = null;
    this.render(this.time, this.selectedId);
  };

  private onContextMenu = (event: MouseEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (y <= HEADER) {
      const marker = this.markerAt(x);
      if (marker >= 0) {
        event.preventDefault();
        this.callbacks.onMarkerMenu?.(marker, event.clientX, event.clientY);
      }
      return;
    }
    const node = this.nodeAt(x, y);
    if (!node) return;
    event.preventDefault();
    this.selectedId = node.id;
    this.callbacks.onSelect(node.id);
    this.callbacks.onContextMenu?.(node.id, event.clientX, event.clientY);
  };
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const radius = Math.min(r, h / 2, w / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}
