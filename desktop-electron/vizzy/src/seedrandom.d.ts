// Minimal typings for the `seedrandom` package, which has no bundled types.
// The reference lays out its particle instances with `seedrandom(seed).double()`,
// so we use the same PRNG rather than approximating the distribution.
declare module "seedrandom" {
  export interface SeedRandom {
    double(): number;
    quick(): number;
    int32(): number;
    state(): unknown;
  }
  export default function seedrandom(seed?: string): SeedRandom;
}
