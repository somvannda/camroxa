/**
 * The reference's custom-path model and sampler.
 *
 * Recovered from the shipped bundle:
 * - `parse`/`serialize` are module `194` (`d`/`e`). Rows are serialized as
 *   `type I|N R|N x y [cx cy]`, joined with `;` and a trailing `;`. The parser
 *   rejects paths from the older format (token 3 is not `N`/`R`) and coerces
 *   every non-`lineTo`/`arcTo` row into `quadTo` — `moveTo` is not a real type.
 * - `sample` is the base item's `getPoints`/`getPosition`, including the arc
 *   solver from module `198` and the shipped build's empty `QUAD_TO` case.
 */

export type CustomPathType = "lineTo" | "quadTo" | "arcTo";

export interface CustomPathPoint {
  type: CustomPathType;
  /** Inverts the segment (editor "Invert"). */
  invert: boolean;
  /** Editor "Quad to": draws the segment as a curve. */
  reverse: boolean;
  x: number;
  y: number;
  /** Arc bulge (`r`) for `arcTo`; control point for `quadTo`. */
  cx: number;
  /** Arc flip flag (-1 flips the sweep). */
  cy: number;
}

export interface PathSample {
  x: number;
  y: number;
}

const LINE_TO = "lineTo" as const;
const QUAD_TO = "quadTo" as const;
const ARC_TO = "arcTo" as const;

/** Module `194` export `d`. Returns an empty list for the old path format. */
export function parseCustomPath(value: string): CustomPathPoint[] {
  const parts = value.split(";").filter((part) => part !== "");
  const points: CustomPathPoint[] = [];
  for (const part of parts) {
    const tokens = part.split(" ");
    if (tokens[2] !== "R" && tokens[2] !== "N") return [];
    const invert = tokens[1] === "I";
    const reverse = tokens[2] === "R";
    const x = Number(tokens[3]);
    const y = Number(tokens[4]);
    if (tokens[0] === LINE_TO) {
      points.push({ type: LINE_TO, invert, reverse, x, y, cx: 0, cy: 0 });
    } else if (tokens[0] === ARC_TO) {
      points.push({ type: ARC_TO, invert, reverse, x, y, cx: Number(tokens[5]), cy: Number(tokens[6]) });
    } else {
      points.push({ type: QUAD_TO, invert, reverse, x, y, cx: Number(tokens[5]), cy: Number(tokens[6]) });
    }
  }
  return points;
}

/** Module `194` export `e`. */
export function serializeCustomPath(points: readonly CustomPathPoint[]): string {
  return (
    points
      .map((point) => {
        const invert = point.invert ? "I" : "N";
        const reverse = point.reverse ? "R" : "N";
        const base = `${point.type} ${invert} ${reverse} ${point.x} ${point.y}`;
        return point.type === LINE_TO ? base : `${base} ${point.cx} ${point.cy}`;
      })
      .join(";") + ";"
  );
}

/**
 * Arc centre, angles, and radius for `arcTo` (module `198`, export `a`).
 * `bulge` is the row's `r`; `flip` is its `cy` sign.
 */
export function arcFromPoints(
  ex: number,
  ey: number,
  sx: number,
  sy: number,
  bulge: number,
  flip: number,
): { offset: number; startAngle: number; endAngle: number; x: number; y: number; radius: number } {
  const dx = ex - sx;
  const dy = ey - sy;
  let nx = -dy;
  let ny = dx;
  if (flip) {
    nx = dy;
    ny = -dx;
  }
  const length = Math.hypot(nx, ny) || 1;
  const cx = sx + dx / 2 + (bulge / 10) * (nx / length);
  const cy = sy + dy / 2 + (bulge / 10) * (ny / length);
  const h = sx - cx;
  const f = sy - cy;
  const radius = Math.hypot(h, f);

  let start = Math.atan2(f, h);
  let end = Math.atan2(ey - cy, ex - cx);
  if (flip === -1) {
    const swap = start;
    start = end;
    end = swap;
  }
  const tau = 2 * Math.PI;
  let wrapped = start % tau;
  if (wrapped < 0) wrapped += tau;
  end += wrapped - start;
  start = wrapped;
  if (start - end >= tau) end = start - tau;
  else if (start < end) end = start - (tau - ((end - start) % tau));
  return { offset: 0, startAngle: start, endAngle: end, x: cx, y: cy, radius };
}

/**
 * Position of one particle at `time`: the base item's `getPoints` picks a
 * segment from `offset` and `t` (`distanceDone`), then `getPosition` resolves it.
 */
export function sampleCustomPath(
  time: number,
  points: readonly CustomPathPoint[],
  offset: number,
  distanceDone: number,
): PathSample {
  if (points.length < 2) return { x: 0, y: 0 };
  const step = 1 / (points.length - 1);
  const progress = step + ((offset + time / 8) % (distanceDone + 1e-4));
  const index = Math.floor(progress / step);
  const start = points[index - 1];
  const end = points[index];
  if (!start || !end) return { x: 0, y: 0 };
  const t = (progress % step) / step;

  if (end.type === ARC_TO) {
    const arc = arcFromPoints(end.x, end.y, start.x, start.y, end.cx, end.cy);
    const angle =
      (1 - t) * arc.startAngle + t * arc.endAngle + arc.offset + (end.cy === -1 ? Math.PI : 0);
    return { x: arc.x + arc.radius * Math.cos(angle), y: arc.y + arc.radius * Math.sin(angle) };
  }
  if (end.type === QUAD_TO) {
    // The shipped `QUAD_TO` switch case is empty, so the segment resolves to the
    // origin rather than interpolating toward its control point.
    return { x: 0, y: 0 };
  }
  return { x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t };
}
