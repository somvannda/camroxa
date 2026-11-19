/**
 * Port of the shipped formula `noise(x, seed)` field.
 *
 * The math node registers a two-argument token whose implementation is a
 * SimplexNoise class seeded from the second argument and sampled on a fixed row:
 *
 *   {type:8, token:"noise", show:"noise", numberOfArguments:2,
 *    value: function (e, t) { return new u.a(t).simplex2(e, 50) }, precedence:0}
 *
 * (token table in `main~412a0a1c`; the class is module 456 of `main~427b64a5`,
 * whose `seed` method and `simplex2` are ported below verbatim).
 *
 * We previously approximated this with one globally seeded 2D field and ignored
 * the per-call seed. Sixteen templates drive positions and scales from
 * `linear(noise(t/2, 200), -1, 1, -u1, u1)` style formulas, so every one of them
 * evaluated the wrong value (`terminal` sat 9 px off because of it).
 */

const GRAD3: ReadonlyArray<readonly [number, number, number]> = [
  [1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
  [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1],
];

const BASE_PERMUTATION: ReadonlyArray<number> = [
  151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
  140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
  247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
  57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
  74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
  60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
  65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
  200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
  52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
  207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
  119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
  129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
  218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
  81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
  184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
  222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
];

const F2 = 0.5 * (Math.sqrt(3) - 1);
const G2 = (3 - Math.sqrt(3)) / 6;
/** The shipped token evaluates every seed on this row: `simplex2(e, 50)`. */
const NOISE_ROW = 50;

function dot2(grad: readonly [number, number, number], x: number, y: number): number {
  return grad[0] * x + grad[1] * y;
}

class SimplexField {
  private readonly perm = new Array<number>(512).fill(0);
  private readonly gradP = new Array<readonly [number, number, number]>(512).fill(GRAD3[0]);

  constructor(seed: number) {
    // Exact port of the shipped `seed` method, including the 0 < seed < 1 fold
    // (multiply by 65536) and the < 256 fold (`seed |= seed << 8`).
    let value = seed;
    if (value > 0 && value < 1) value *= 65536;
    value = Math.floor(value);
    if (value < 256) value |= value << 8;
    for (let index = 0; index < 256; index += 1) {
      const base = BASE_PERMUTATION[index] ?? 0;
      const next = 1 & index ? base ^ (255 & value) : base ^ ((value >> 8) & 255);
      this.perm[index] = next;
      this.perm[index + 256] = next;
      const grad = GRAD3[next % 12] ?? GRAD3[0];
      this.gradP[index] = grad;
      this.gradP[index + 256] = grad;
    }
  }

  /** `simplex2` from the shipped class, verbatim. */
  simplex2(xin: number, yin: number): number {
    const s = (xin + yin) * F2;
    let i = Math.floor(xin + s);
    let j = Math.floor(yin + s);
    const t = (i + j) * G2;
    const x0 = xin - (i - t);
    const y0 = yin - (j - t);
    let i1 = 0;
    let j1 = 1;
    if (x0 > y0) {
      i1 = 1;
      j1 = 0;
    }
    const x1 = x0 - i1 + G2;
    const y1 = y0 - j1 + G2;
    const x2 = x0 - 1 + 2 * G2;
    const y2 = y0 - 1 + 2 * G2;
    i &= 255;
    j &= 255;
    const p = this.perm;
    const g = this.gradP;
    const gi0 = g[i + p[j]] ?? GRAD3[0];
    const gi1 = g[i + i1 + p[j + j1]] ?? GRAD3[0];
    const gi2 = g[i + 1 + p[j + 1]] ?? GRAD3[0];
    let n0 = 0;
    let n1 = 0;
    let n2 = 0;
    let t0 = 0.5 - x0 * x0 - y0 * y0;
    if (t0 >= 0) {
      t0 *= t0;
      n0 = t0 * t0 * dot2(gi0, x0, y0);
    }
    let t1 = 0.5 - x1 * x1 - y1 * y1;
    if (t1 >= 0) {
      t1 *= t1;
      n1 = t1 * t1 * dot2(gi1, x1, y1);
    }
    let t2 = 0.5 - x2 * x2 - y2 * y2;
    if (t2 >= 0) {
      t2 *= t2;
      n2 = t2 * t2 * dot2(gi2, x2, y2);
    }
    return 70 * (n0 + n1 + n2);
  }
}

const fields = new Map<number, SimplexField>();

/** `noise(x, seed)` exactly as the shipped math node evaluates it. */
export function formulaNoise(x: number, seed: number): number {
  const key = Number.isFinite(seed) ? seed : 0;
  let field = fields.get(key);
  if (!field) {
    field = new SimplexField(key);
    fields.set(key, field);
  }
  return field.simplex2(x, NOISE_ROW);
}
