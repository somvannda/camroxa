/**
 * Spectrum path geometry, decompiled from the reference's `drawSpectrumPoints`
 * and its point helpers (webpack modules 194/198).
 *
 * The reference draws in a 1000×1000 item canvas with `curRad = 120`; every
 * update resets it to 120. Band values arrive in the analyser's units and are
 * scaled by `layer.multiplier * spectrumHeight` before downsampling.
 *
 * This module returns path commands rather than polylines so quadratic curves,
 * arcs, dots and fill holes survive the port. The Canvas2D renderer consumes
 * them directly.
 */

export interface SpectrumPathSettings {
  /** "Bars" | "Circle" | "Custom" | "Image" */
  spectrumType: string;
  /** "Line" | "Curve" | "Plexus" | "Point" */
  drawType: string;
  fillStyle: string;
  mirrorHorizontal: boolean;
  stretchToEnd: boolean;
  repeatPointsOnPath: boolean;
  closeLine: boolean;
  moveBack: boolean;
  /** Gap between bars, in item-space units. */
  spacing: number;
  /** Dot radius, in item-space units. */
  dotSize: number;
  /** Spectrum band stride (the reference's `downSample` string). */
  downsample?: number;
  /** Serialized custom path (`lineTo/quadTo/arcTo` commands). */
  customPath?: string;
  smoothStartAndEnd?: boolean;
  smoothingWidth?: number;
  smoothingPasses?: number;
  clipCircle: boolean;
  clipSize: number;
}

export type PathCommand =
  | { type: "move"; x: number; y: number }
  | { type: "line"; x: number; y: number }
  | { type: "quad"; cx: number; cy: number; x: number; y: number }
  | { type: "arc"; x: number; y: number; r: number; start: number; end: number; ccw?: boolean }
  | { type: "close" };

export interface SpectrumDrawing {
  commands: PathCommand[];
  /** Dots are also appended as arc subpaths; this list is for hit-testing/debug. */
  dots: PathPoint[];
}

export interface PathPoint {
  x: number;
  y: number;
}

/** The reference resets `curRad` to this on every update. */
export const CUR_RAD = 120;

/**
 * Scale, average-downsample and stride the band series exactly like module 198.
 * `downsample` is the spectrum's string stride (1/2/4/8).
 */
export function spectrumPoints(
  bands: ArrayLike<number>,
  downsample: number,
  multiplier: number,
): Float32Array {
  let points = Float32Array.from(bands);
  const scale = Number.isFinite(multiplier) ? multiplier : 1;
  if (scale !== 1) {
    for (let index = 0; index < points.length; index += 1) points[index] *= scale;
  }

  const stride = Math.max(1, Math.floor(downsample));
  if (stride !== 1) {
    const count = Math.ceil(points.length / stride);
    const reduced = new Float32Array(count);
    for (let index = 0; index < points.length; index += stride) {
      let sum = 0;
      const start = Math.max(index - stride / 2, 0);
      const end = Math.min(points.length, index + stride / 2);
      for (let cursor = start; cursor < end; cursor += 1) sum += points[cursor];
      reduced[index / stride] = sum / (end - start);
    }
    points = reduced;
  }
  return points;
}

/** Build every path command the reference would stroke/fill for these bands. */
export function buildSpectrumDrawing(
  bands: ArrayLike<number>,
  settings: SpectrumPathSettings,
  multiplier = 1,
): SpectrumDrawing {
  const points = spectrumPoints(bands, settings.downsample ?? 1, multiplier);
  if (String(settings.spectrumType).toLowerCase() === "custom") {
    return buildCustomFromPoints(points, settings);
  }
  return buildFromPoints(points, settings);
}

/** Same, when the caller already ran the point pipeline. */
export function buildFromPoints(
  points: ArrayLike<number>,
  settings: SpectrumPathSettings,
): SpectrumDrawing {
  if (points.length <= 4 || points.length > 1000) return { commands: [], dots: [] };

  const drawing: SpectrumDrawing = { commands: [], dots: [] };
  const bars = String(settings.spectrumType).toLowerCase() === "bars";
  // The reference appends the mirrored pass to the same path after the primary.
  appendPass(drawing, points, settings, bars, false);
  if (settings.mirrorHorizontal) {
    appendPass(drawing, Array.from(points).reverse(), settings, bars, true);
  }
  return drawing;
}

function appendPass(
  drawing: SpectrumDrawing,
  values: ArrayLike<number>,
  settings: SpectrumPathSettings,
  bars: boolean,
  mirrored: boolean,
): void {
  const commands = drawing.commands;
  const count = values.length;
  const last = count - 1;
  const sign = mirrored ? -1 : 1;
  const angleOffset = mirrored ? Math.PI : 0;
  const fullCircle = !settings.mirrorHorizontal && settings.stretchToEnd && !bars;
  const sweep = fullCircle ? Math.PI * 2 : Math.PI;
  const n = CUR_RAD + (bars ? (settings.spacing * last) / 2 : 0);
  const dot = Math.max(0, settings.dotSize);
  const curve = String(settings.drawType).toLowerCase();
  const filled = String(settings.fillStyle).toLowerCase() === "fill";

  if (bars) {
    if (settings.closeLine) {
      commands.push({ type: "move", x: 0, y: -n * sign });
      commands.push({ type: "line", x: (values[0] ?? 0) * sign, y: -n * sign });
    } else {
      commands.push({ type: "move", x: (values[0] ?? 0) * sign, y: -n * sign });
    }
  } else {
    commands.push({ type: "move", x: 0, y: -(n + (values[0] ?? 0)) * sign });
  }

  for (let index = 0; index < last; index += 1) {
    const v = index / last;
    const g = (index + 1) / last;
    const current = Math.max(0, values[index] ?? 0);
    const next =
      index === last - 1 ? Math.max(0, values[values.length - 1] ?? 0) : Math.max(0, values[index + 1] ?? 0);

    let x0: number;
    let y0: number;
    let x1: number;
    let y1: number;
    if (bars) {
      const from = v * n * 2;
      const to = g * n * 2;
      x0 = current * sign;
      y0 = mirrored ? n - from : from - n;
      x1 = next * sign;
      y1 = mirrored ? n - to : to - n;
    } else {
      const from = sweep * v - Math.PI / 2 + angleOffset;
      const to = sweep * g - Math.PI / 2 + angleOffset;
      x0 = (current + CUR_RAD) * Math.cos(from);
      y0 = (current + CUR_RAD) * Math.sin(from);
      x1 = (next + CUR_RAD) * Math.cos(to);
      y1 = (next + CUR_RAD) * Math.sin(to);
    }
    const midX = (x0 + x1) / 2;
    const midY = (y0 + y1) / 2;

    if (settings.moveBack) {
      if (bars) {
        const from = v * n * 2;
        commands.push({ type: "move", x: 0, y: mirrored ? n - from : from - n });
      } else {
        const angle = sweep * v - Math.PI / 2 + angleOffset;
        commands.push({
          type: "move",
          x: Math.cos(angle) * CUR_RAD,
          y: Math.sin(angle) * CUR_RAD,
        });
      }
    }

    if (index === last - 1) {
      const endValue = Math.max(0, values[values.length - 1] ?? 0);
      let endX: number;
      let endY: number;
      // `h` in the reference is `!mirror && stretchToEnd && !bars`, i.e. a
      // full-circle sweep closes back on the first band. Every other case
      // falls back to the axis (bars) or the circle's top/bottom pole.
      if (fullCircle && !bars) {
        if (settings.closeLine) {
          const angle = -Math.PI / 2 + angleOffset;
          endX = (values[0] + CUR_RAD) * Math.cos(angle);
          endY = (values[0] + CUR_RAD) * Math.sin(angle);
        } else {
          endX = x1;
          endY = y1;
        }
      } else {
        endX = (bars ? endValue : 0) * sign;
        endY = (n + (bars ? 0 : endValue)) * sign;
      }

      if (settings.moveBack) {
        if (curve !== "point") {
          commands.push({ type: "line", x: x0, y: y0 });
          commands.push({ type: "move", x: 0, y: endY });
          commands.push({ type: "line", x: endX, y: endY });
        }
      } else if (curve === "curve") {
        if (fullCircle && settings.closeLine) {
          commands.push({ type: "quad", cx: x0, cy: y0, x: endX, y: endY });
        } else if (fullCircle && !settings.closeLine) {
          commands.push({ type: "quad", cx: x0, cy: y0, x: x1, y: y1 });
        } else {
          commands.push({ type: "quad", cx: x0, cy: y0, x: endX, y: endY });
          if (bars && settings.closeLine) {
            commands.push({ type: "line", x: 0, y: endY });
          }
        }
      } else if (curve === "line" || curve === "plexus") {
        if (fullCircle && settings.closeLine) {
          commands.push({ type: "line", x: endX, y: endY });
        } else if (fullCircle && !settings.closeLine) {
          commands.push({ type: "line", x: x1, y: y1 });
        } else {
          commands.push({ type: "line", x: endX, y: endY });
          if (bars && settings.closeLine) commands.push({ type: "line", x: 0, y: endY });
        }
      }
    } else if (curve === "curve" || filled) {
      commands.push({ type: "quad", cx: x0, cy: y0, x: midX, y: midY });
    } else if (curve === "line" || curve === "plexus") {
      commands.push({ type: "line", x: x0, y: y0 });
    }

    if (curve === "plexus" || curve === "point") {
      drawing.dots.push({ x: x0, y: y0 });
      commands.push({ type: "move", x: x0 + dot / 2, y: y0 });
      commands.push({ type: "arc", x: x0, y: y0, r: dot / 2, start: 0, end: Math.PI * 2 });
    }
  }

  // The reference carves a hole for a filled circle when Clip circle is on.
  if (!bars && filled && settings.clipCircle) {
    const radius = CUR_RAD * settings.clipSize;
    commands.push({ type: "move", x: 0, y: -CUR_RAD });
    commands.push({
      type: "arc",
      x: 0,
      y: 0,
      r: radius,
      start: -Math.PI / 2,
      end: -Math.PI * 1.5,
      ccw: false,
    });
    commands.push({
      type: "arc",
      x: 0,
      y: 0,
      r: radius,
      start: -Math.PI * 1.5,
      end: -Math.PI * 2.5,
      ccw: false,
    });
    commands.push({ type: "close" });
  }
}

/* ------------------------------------------------------------------ */
/* Custom paths                                                        */
/* ------------------------------------------------------------------ */

interface CustomCommand {
  type: "lineTo" | "quadTo" | "arcTo";
  invert: boolean;
  reverse: boolean;
  /** Normalised end point (×500 applied later). */
  x: number;
  y: number;
  /** Normalised control point / arc bulge. */
  cx: number;
  cy: number;
}

interface CustomPoint {
  kind: "line" | "curve" | "move";
  bx: number;
  by: number;
  x: number;
  y: number;
}

function parseCustomPath(raw: string): CustomCommand[] {
  return raw
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const fields = part.split(/\s+/);
      if (fields.length < 5) return null;
      const type = fields[0];
      if (type !== "lineTo" && type !== "quadTo" && type !== "arcTo") return null;
      return {
        type,
        invert: fields[1] === "I",
        reverse: fields[2] === "R",
        x: Number(fields[3]),
        y: Number(fields[4]),
        cx: fields.length > 5 ? Number(fields[5]) : 0,
        cy: fields.length > 6 ? Number(fields[6]) : 0,
      } satisfies CustomCommand;
    })
    .filter((command): command is CustomCommand => command !== null);
}

function smoothCustomEnds(
  points: number[],
  smoothingWidth: number,
  smoothingPasses: number,
): void {
  const width = Math.floor(smoothingWidth);
  if (width < 1) return;
  const last = points.length - 1;
  for (let pass = 0; pass < smoothingPasses; pass += 1) {
    const span = Math.max(3, Math.floor(points.length / width + 5 * pass));
    // Real projects use 100 passes/width, which overruns a 64-band array. The
    // reference's loop indexes past the ends; here that would write NaN into
    // the path, so clamp to the points we actually have.
    const limit = Math.min(span, points.length - 1);
    for (let index = 0; index < limit; index += 1) {
      const left = (points.length - index) % points.length;
      const right = (points.length - 1 + index) % points.length;
      const weight = Math.pow((1 - index / span) / 2, 2);
      points[last - index] = points[left] * weight + (1 - weight) * points[last - index];
      points[index] = points[right] * weight + (1 - weight) * points[index];
    }
  }
  points[last] = points[0];
}

function buildCustomFromPoints(
  values: ArrayLike<number>,
  settings: SpectrumPathSettings,
): SpectrumDrawing {
  const commands = parseCustomPath(settings.customPath ?? "");
  if (commands.length === 0) return { commands: [], dots: [] };

  let bands = Array.from(values);
  const lastIndex = bands.length - 1;
  if (settings.smoothStartAndEnd !== false) {
    smoothCustomEnds(bands, settings.smoothingWidth ?? 10, settings.smoothingPasses ?? 4);
  }

  const half = 500;
  const repeat = settings.repeatPointsOnPath !== false;
  const curve = String(settings.drawType).toLowerCase() === "curve";
  const points: CustomPoint[] = [];

  let currentX = commands[0].x * half;
  let currentY = commands[0].y * half;

  for (let index = 1; index < commands.length; index += 1) {
    const command = commands[index];
    const endX = command.x * half;
    const endY = command.y * half;
    const controlX = (Number.isFinite(command.cx) ? command.cx : command.x) * half;
    const controlY = (Number.isFinite(command.cy) ? command.cy : command.y) * half;
    let commandBands = bands.slice();
    if (command.reverse) commandBands = commandBands.reverse();

    const segmentStart = index - 1;
    const segmentEnd = index;
    const from = repeat ? 0 : Math.floor(lastIndex * (segmentStart / (commands.length - 1)));
    const to = repeat
      ? lastIndex
      : Math.floor(lastIndex * (segmentEnd / (commands.length - 1)));
    const span = Math.max(1, to - from);

    if (command.type === "lineTo") {
      points.push({ kind: "move", bx: 0, by: 0, x: currentX, y: currentY });
      const dx = endX - currentX;
      const dy = endY - currentY;
      let nx = -dy;
      let ny = dx;
      if (command.invert) {
        nx = dy;
        ny = -dx;
      }
      const length = Math.hypot(nx, ny) || 1;
      nx /= length;
      ny /= length;
      for (let band = from; band < to; band += 1) {
        const ratio = (band - from) / span;
        const baseX = currentX + ratio * dx;
        const baseY = currentY + ratio * dy;
        const value = commandBands[band] ?? 0;
        points.push({
          kind: "line",
          bx: baseX,
          by: baseY,
          x: baseX + nx * value,
          y: baseY + ny * value,
        });
      }
      points.push({ kind: "move", bx: 0, by: 0, x: endX, y: endY });
    } else if (command.type === "quadTo") {
      for (let band = from; band < to; band += 1) {
        const ratio = (band - from) / Math.max(1, to - from - 1);
        const base = quadPoint(
          ratio,
          { x: currentX, y: currentY },
          { x: controlX, y: controlY },
          { x: endX, y: endY },
        );
        const normal = quadNormal(
          ratio,
          { x: currentX, y: currentY },
          { x: controlX, y: controlY },
          { x: endX, y: endY },
          command.invert,
        );
        const value = commandBands[band] ?? 0;
        points.push({
          kind: "curve",
          bx: base.x,
          by: base.y,
          x: base.x + normal.x * value,
          y: base.y + normal.y * value,
        });
      }
      points.push({ kind: "move", bx: 0, by: 0, x: endX, y: endY });
    } else {
      const arc = arcFromBulge(
        endX,
        endY,
        currentX,
        currentY,
        Number.isFinite(command.cx) ? command.cx : 0,
        Number.isFinite(command.cy) ? command.cy : 0,
      );
      let startAngle = arc.startAngle;
      let endAngle = arc.endAngle;
      if (command.cy === -1 && startAngle > endAngle) {
        [startAngle, endAngle] = [endAngle, startAngle];
      }
      // Reference loop: `for (a = m; a < x + 1; a++)` with the ratio
      // `(a - m) / (x - m)`. It divides by the last index, not by last+1, so
      // the final band lands exactly on the arc's end; dividing by last+1
      // compressed the sweep (rainbow-circle's arc ended ~3 deg short).
      const arcFrom = from;
      const arcTo = to + 1;
      const arcSpan = Math.max(1, to - from);
      for (let band = arcFrom; band < arcTo; band += 1) {
        const ratio = (band - arcFrom) / arcSpan;
        const angle = (1 - ratio) * startAngle + ratio * endAngle;
        const baseX = arc.centerX + arc.radius * Math.cos(angle);
        const baseY = arc.centerY + arc.radius * Math.sin(angle);
        const value = (commandBands[band] ?? 0) * (command.invert ? -1 : 1);
        points.push({
          kind: "line",
          bx: baseX,
          by: baseY,
          x: baseX + Math.cos(angle) * value,
          y: baseY + Math.sin(angle) * value,
        });
      }
    }
    currentX = endX;
    currentY = endY;
  }

  const drawing: SpectrumDrawing = { commands: [], dots: [] };
  if (points.length === 0) return drawing;
  const result = drawing.commands;
  result.push({ type: "move", x: points[0].x, y: points[0].y });
  for (let index = 0; index < points.length; index += 1) {
    const point = points[index];
    const next = points[index + 1];
    if (!next) {
      if (settings.closeLine !== false && !settings.moveBack) {
        result.push({ type: "line", x: point.x, y: point.y });
      } else if (!settings.moveBack) {
        result.push({ type: "line", x: point.x, y: point.y });
      }
      continue;
    }
    const midX = (point.x + next.x) / 2;
    const midY = (point.y + next.y) / 2;
    if (point.kind === "line" || point.kind === "curve") {
      if (index === 0 && !settings.moveBack) {
        result.push({ type: "move", x: point.x, y: point.y });
        continue;
      }
      if (settings.moveBack) result.push({ type: "move", x: point.bx, y: point.by });
      if (curve) result.push({ type: "quad", cx: point.x, cy: point.y, x: midX, y: midY });
      else result.push({ type: "line", x: point.x, y: point.y });
    } else if (point.kind === "move") {
      if (!settings.moveBack) {
        if (settings.closeLine !== false) result.push({ type: "line", x: next.x, y: next.y });
        else result.push({ type: "line", x: point.x, y: point.y });
      }
    }
  }
  return drawing;
}

/**
 * Quadratic point/normal helpers, kept for custom paths and future callers.
 * Ported from module 198.
 */
export function quadPoint(
  t: number,
  start: PathPoint,
  control: PathPoint,
  end: PathPoint,
): PathPoint {
  const u = 1 - t;
  return {
    x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
    y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
  };
}

export function quadNormal(
  t: number,
  start: PathPoint,
  control: PathPoint,
  end: PathPoint,
  invert = false,
): PathPoint {
  const dx = 2 * (control.x - start.x);
  const dy = 2 * (control.y - start.y);
  const dx2 = (1 - t) * dx + t * (2 * (end.x - control.x));
  const dy2 = (1 - t) * dy + t * (2 * (end.y - control.y));
  const length = Math.hypot(dx2, dy2) || 1;
  const nx = -dy2 / length;
  const ny = dx2 / length;
  return invert ? { x: -nx, y: -ny } : { x: nx, y: ny };
}

/**
 * Arc centre/angles for the reference's `arcTo` command. `bulge` is the serialized
 * `cx` field; `direction` is the serialized `cy` field (-1/0/1).
 */
export function arcFromBulge(
  endX: number,
  endY: number,
  startX: number,
  startY: number,
  bulge: number,
  direction: number,
): { startAngle: number; endAngle: number; centerX: number; centerY: number; radius: number } {
  const dx = endX - startX;
  const dy = endY - startY;
  let nx = -dy;
  let ny = dx;
  if (direction) {
    nx = dy;
    ny = -dx;
  }
  const length = Math.hypot(nx, ny) || 1;
  const centerX = startX + dx / 2 + (bulge / 10) * (nx / length);
  const centerY = startY + dy / 2 + (bulge / 10) * (ny / length);
  const radius = Math.hypot(startX - centerX, startY - centerY);
  let startAngle = Math.atan2(startY - centerY, startX - centerX);
  let endAngle = Math.atan2(endY - centerY, endX - centerX);
  if (direction === -1) {
    const swap = startAngle;
    startAngle = endAngle;
    endAngle = swap;
  }
  const tau = Math.PI * 2;
  let normalised = startAngle % tau;
  if (normalised < 0) normalised += tau;
  const delta = normalised - startAngle;
  startAngle = normalised;
  endAngle += delta;
  if (startAngle - endAngle >= tau) endAngle = startAngle - tau;
  else if (startAngle < endAngle) endAngle = startAngle - (tau - ((endAngle - startAngle) % tau));
  return { startAngle, endAngle, centerX, centerY, radius };
}

/** A simple polyline representation, kept for legacy callers/tests. */
export function buildSpectrumPath(
  bands: readonly number[],
  settings: SpectrumPathSettings,
): PathPoint[] {
  const drawing = buildSpectrumDrawing(bands, settings, 1);
  return drawing.commands
    .filter((command): command is Extract<PathCommand, { type: "line" }> => command.type === "line")
    .map((command) => ({ x: command.x, y: command.y }));
}
