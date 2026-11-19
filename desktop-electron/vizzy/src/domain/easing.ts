/** Easing catalogue and functions, decompiled from Vizzy module 57. */
export const EASING_OPTIONS = [
  "linear",
  "easeInQuad",
  "easeOutQuad",
  "easeInOutQuad",
  "easeInCubic",
  "easeOutCubic",
  "easeInOutCubic",
  "easeInQuart",
  "easeOutQuart",
  "easeInOutQuart",
  "easeInQuint",
  "easeOutQuint",
  "easeInOutQuint",
  "easeInSine",
  "easeOutSine",
  "easeInOutSine",
  "easeInCirc",
  "easeOutCirc",
  "easeInOutCirc",
  "easeInExpo",
  "easeOutExpo",
  "easeInOutExpo",
  "easeInBack",
  "easeOutBack",
  "easeInOutBack",
  "easeInElastic",
  "easeOutElastic",
  "easeInOutElastic",
  "easeInBounce",
  "easeOutBounce",
  "easeInOutBounce",
] as const;

export type EasingName = (typeof EASING_OPTIONS)[number];

const sqrt = Math.sqrt;
const pow = Math.pow;
const cos = Math.cos;
const sin = Math.sin;
const PI = Math.PI;

function bounceOut(value: number): number {
  const n = 7.5625;
  const d = 2.75;
  if (value < 1 / d) return n * value * value;
  if (value < 2 / d) return n * (value -= 1.5 / d) * value + 0.75;
  if (value < 2.5 / d) return n * (value -= 2.25 / d) * value + 0.9375;
  return n * (value -= 2.625 / d) * value + 0.984375;
}

export const EASING_FUNCTIONS: Record<EasingName, (value: number) => number> = {
  linear: (t) => t,
  easeInQuad: (t) => t * t,
  easeOutQuad: (t) => 1 - (1 - t) * (1 - t),
  easeInOutQuad: (t) => (t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2),
  easeInCubic: (t) => t * t * t,
  easeOutCubic: (t) => 1 - pow(1 - t, 3),
  easeInOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2),
  easeInQuart: (t) => t * t * t * t,
  easeOutQuart: (t) => 1 - pow(1 - t, 4),
  easeInOutQuart: (t) => (t < 0.5 ? 8 * t * t * t * t : 1 - pow(-2 * t + 2, 4) / 2),
  easeInQuint: (t) => t * t * t * t * t,
  easeOutQuint: (t) => 1 - pow(1 - t, 5),
  easeInOutQuint: (t) => (t < 0.5 ? 16 * t * t * t * t * t : 1 - pow(-2 * t + 2, 5) / 2),
  easeInSine: (t) => 1 - cos((t * PI) / 2),
  easeOutSine: (t) => sin((t * PI) / 2),
  easeInOutSine: (t) => -(cos(PI * t) - 1) / 2,
  easeInCirc: (t) => 1 - sqrt(1 - pow(t, 2)),
  easeOutCirc: (t) => sqrt(1 - pow(t - 1, 2)),
  easeInOutCirc: (t) =>
    t < 0.5 ? (1 - sqrt(1 - pow(2 * t, 2))) / 2 : (sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2,
  easeInExpo: (t) => (t === 0 ? 0 : pow(2, 10 * t - 10)),
  easeOutExpo: (t) => (t === 1 ? 1 : 1 - pow(2, -10 * t)),
  easeInOutExpo: (t) =>
    t === 0 ? 0 : t === 1 ? 1 : t < 0.5 ? pow(2, 20 * t - 10) / 2 : (2 - pow(2, -20 * t + 10)) / 2,
  easeInBack: (t) => 2.70158 * t * t * t - 1.70158 * t * t,
  easeOutBack: (t) => 1 + 2.70158 * pow(t - 1, 3) + 1.70158 * pow(t - 1, 2),
  easeInOutBack: (t) => {
    const c = 2.5949095;
    return t < 0.5
      ? (pow(2 * t, 2) * (7.189819 * t - c)) / 2
      : (pow(2 * t - 2, 2) * ((c + 1) * (2 * t - 2) + c) + 2) / 2;
  },
  easeInElastic: (t) => {
    const c = (2 * PI) / 3;
    return t === 0 ? 0 : t === 1 ? 1 : -pow(2, 10 * t - 10) * sin((10 * t - 10.75) * c);
  },
  easeOutElastic: (t) => {
    const c = (2 * PI) / 3;
    return t === 0 ? 0 : t === 1 ? 1 : pow(2, -10 * t) * sin((10 * t - 0.75) * c) + 1;
  },
  easeInOutElastic: (t) => {
    const c = (2 * PI) / 4.5;
    return t === 0
      ? 0
      : t === 1
        ? 1
        : t < 0.5
          ? (-pow(2, 20 * t - 10) * sin((20 * t - 11.125) * c)) / 2
          : (pow(2, -20 * t + 10) * sin((20 * t - 11.125) * c)) / 2 + 1;
  },
  easeInBounce: (t) => 1 - bounceOut(1 - t),
  easeOutBounce: bounceOut,
  easeInOutBounce: (t) =>
    t < 0.5 ? (1 - bounceOut(1 - 2 * t)) / 2 : (1 + bounceOut(2 * t - 1)) / 2,
};

export function ease(name: string, value: number): number {
  return (EASING_FUNCTIONS[name as EasingName] ?? EASING_FUNCTIONS.linear)(value);
}
