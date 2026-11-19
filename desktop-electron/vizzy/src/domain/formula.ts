/**
 * Formula evaluator for `math` automations.
 *
 * The reference lets a math automation drive any controller with a formula.
 * Its help text lists the keywords `t`, `p`, `a`, `m`, `d`, `u1`-`u5`,
 * `g1`-`g5`, `rx`, `ry`, and states that angles are in degrees
 * (`cos(90) = 0`), so the evaluator below works in degrees for every
 * trigonometric function.
 *
 * The grammar is a small recursive-descent expression parser; no `eval`, so a
 * saved project can never execute arbitrary code.
 */

import { formulaNoise } from "./formula-noise";

export interface FormulaVariables {
  /** Time in seconds. */
  t: number;
  /** Previous value of the controller (last frame). */
  p: number;
  /** Audio impact (sum of every frequency bin). */
  a: number;
  /** Maximum audio impact for the loaded song. */
  m: number;
  /** Song duration in seconds. */
  d: number;
  u1: number;
  u2: number;
  u3: number;
  u4: number;
  u5: number;
  g1: number;
  g2: number;
  g3: number;
  g4: number;
  g5: number;
  /** Render resolution. */
  rx: number;
  ry: number;
}

export const EMPTY_FORMULA_VARIABLES: FormulaVariables = {
  t: 0,
  p: 0,
  a: 0,
  m: 0,
  d: 0,
  u1: 0,
  u2: 0,
  u3: 0,
  u4: 0,
  u5: 0,
  g1: 0,
  g2: 0,
  g3: 0,
  g4: 0,
  g5: 0,
  rx: 1920,
  ry: 1080,
};

const DEG = Math.PI / 180;

// `noise(x, seed)` is the shipped SimplexNoise field sampled at `(x, 50)` with a
// field seeded from the second argument - see `formula-noise.ts` for the module
// quote and the port. The previous implementation used one globally seeded field
// and ignored the seed, which shifted every formula-driven position.

type FunctionName = keyof typeof FUNCTIONS;

const FUNCTIONS = {
  sin: (x: number) => Math.sin(x * DEG),
  cos: (x: number) => Math.cos(x * DEG),
  tan: (x: number) => Math.tan(x * DEG),
  asin: (x: number) => Math.asin(x) / DEG,
  acos: (x: number) => Math.acos(x) / DEG,
  atan: (x: number) => Math.atan(x) / DEG,
  atan2: (y: number, x: number) => Math.atan2(y, x) / DEG,
  sqrt: Math.sqrt,
  abs: Math.abs,
  exp: Math.exp,
  ln: Math.log,
  log: Math.log10,
  floor: Math.floor,
  ceil: Math.ceil,
  round: Math.round,
  sign: Math.sign,
  // The reference's formula editor spells this `sgn` (exports use both).
  sgn: Math.sign,
  pow: Math.pow,
  min: Math.min,
  max: Math.max,
  tanh: Math.tanh,
  clamp: (value: number, low: number, high: number) => Math.min(high, Math.max(low, value)),
  // The reference's remap helper, used by 266 exported formulas. The shipped
  // token is `Object(f.t)(value, inMin, inMax, outMin, outMax)`, and the only
  // five-argument function of that shape in the bundle is three's
  // `mapLinear: (t,e,n,r,i) => r + (t-e)*(i-r)/(n-e)` - with **no clamp**. Ours
  // clamped to the output range, which only differs where the input is outside
  // its window and the result drives something unclamped (a position rather than
  // an alpha); the intro/outro remaps `linear(t, d-0.1, d-g1/2, 0, 1)` are the
  // ones to watch.
  linear: (value: number, inMin: number, inMax: number, outMin: number, outMax: number) => {
    const span = inMax - inMin;
    const t = span === 0 ? 1 : (value - inMin) / span;
    return outMin + (outMax - outMin) * t;
  },
  noise: (x: number, y = 0) => formulaNoise(x, y),
} as const;

const CONSTANTS: Record<string, number> = {
  pi: Math.PI,
  e: Math.E,
};

class FormulaError extends Error {}

export class Formula {
  private readonly tokens: string[];
  private at = 0;

  constructor(
    readonly source: string,
    private readonly variables: FormulaVariables,
  ) {
    this.tokens = tokenize(source);
    if (this.tokens.length === 0) throw new FormulaError("empty formula");
  }

  static evaluate(source: string, variables: Partial<FormulaVariables> = {}): number {
    return new Formula(source, { ...EMPTY_FORMULA_VARIABLES, ...variables }).run();
  }

  /** True when `source` parses; used to gate the Add automation button. */
  static isValid(source: string, variables: Partial<FormulaVariables> = {}): boolean {
    try {
      const value = Formula.evaluate(source, variables);
      return Number.isFinite(value);
    } catch {
      return false;
    }
  }

  run(): number {
    const value = this.parseExpression();
    if (this.at !== this.tokens.length) {
      throw new FormulaError(`unexpected "${this.tokens[this.at]}"`);
    }
    if (!Number.isFinite(value)) throw new FormulaError("not a finite number");
    return value;
  }

  private peek(): string | undefined {
    return this.tokens[this.at];
  }

  private next(): string {
    const token = this.tokens[this.at];
    if (token === undefined) throw new FormulaError("unexpected end of formula");
    this.at += 1;
    return token;
  }

  private parseExpression(): number {
    let value = this.parseTerm();
    for (;;) {
      const token = this.peek();
      if (token !== "+" && token !== "-") return value;
      this.next();
      const right = this.parseTerm();
      value = token === "+" ? value + right : value - right;
    }
  }

  private parseTerm(): number {
    let value = this.parseUnary();
    for (;;) {
      const token = this.peek();
      const modulo = token === "Mod" || token === "mod";
      if (token !== "*" && token !== "/" && token !== "%" && !modulo) return value;
      this.next();
      const right = this.parseUnary();
      if (modulo) {
        // mathjs-style modulo (sign follows the divisor), which is what the
        // reference's `Mod` produces; JS `%` keeps the dividend's sign.
        value = right === 0 ? value : value - right * Math.floor(value / right);
      } else if (token === "*") {
        value *= right;
      } else if (token === "/") {
        value /= right;
      } else {
        value %= right;
      }
    }
  }

  private parseUnary(): number {
    const token = this.peek();
    if (token === "-") {
      this.next();
      return -this.parseUnary();
    }
    if (token === "+") {
      this.next();
      return this.parseUnary();
    }
    return this.parsePower();
  }

  private parsePower(): number {
    const base = this.parsePrimary();
    if (this.peek() !== "^") return base;
    this.next();
    // Right-associative, like every other `^`.
    return Math.pow(base, this.parseUnary());
  }

  private parsePrimary(): number {
    const token = this.next();
    if (token === "(") {
      const value = this.parseExpression();
      if (this.next() !== ")") throw new FormulaError('expected ")"');
      return value;
    }
    if (/^\d/.test(token) || token.startsWith(".")) return Number(token);
    if (token in CONSTANTS) return CONSTANTS[token];
    if (token in this.variables) return this.variables[token as keyof FormulaVariables];
    if (token in FUNCTIONS) {
      if (this.peek() !== "(") throw new FormulaError(`expected "(" after ${token}`);
      this.next();
      const args: number[] = [];
      if (this.peek() !== ")") {
        for (;;) {
          args.push(this.parseExpression());
          if (this.peek() !== ",") break;
          this.next();
        }
      }
      if (this.next() !== ")") throw new FormulaError('expected ")"');
      const fn = FUNCTIONS[token as FunctionName] as (...values: number[]) => number;
      return fn(...args);
    }
    throw new FormulaError(`unknown name "${token}"`);
  }
}

function tokenize(source: string): string[] {
  const tokens: string[] = [];
  let index = 0;
  while (index < source.length) {
    const char = source[index];
    if (/\s/.test(char)) {
      index += 1;
      continue;
    }
    if (/[0-9.]/.test(char)) {
      let end = index;
      while (end < source.length && /[0-9.]/.test(source[end])) end += 1;
      // Exponent form: 1e-3
      if (source[end] === "e" || source[end] === "E") {
        let probe = end + 1;
        if (source[probe] === "+" || source[probe] === "-") probe += 1;
        if (/[0-9]/.test(source[probe] ?? "")) {
          end = probe;
          while (end < source.length && /[0-9]/.test(source[end])) end += 1;
        }
      }
      tokens.push(source.slice(index, end));
      index = end;
      continue;
    }
    if (/[a-zA-Z_]/.test(char)) {
      let end = index;
      while (end < source.length && /[a-zA-Z0-9_]/.test(source[end])) end += 1;
      tokens.push(source.slice(index, end));
      index = end;
      continue;
    }
    if ("+-*/%^(),".includes(char)) {
      tokens.push(char);
      index += 1;
      continue;
    }
    throw new FormulaError(`unexpected "${char}"`);
  }
  return tokens;
}
