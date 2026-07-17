import { describe, expect, it } from 'vitest';

import { formatDollars } from './credit-format';

describe('formatDollars', () => {
  it('shows sub-cent amounts for micro-credit pricing', () => {
    expect(formatDollars(0.0016 * 0.01)).toBe('$0.000016');
    expect(formatDollars(0.0032 * 0.01)).toBe('$0.000032');
    expect(formatDollars((0.0032 - 0.0016) * 0.01)).toBe('$0.000016');
  });

  it('keeps normal precision for larger amounts', () => {
    expect(formatDollars(0.02)).toBe('$0.02');
    expect(formatDollars(1.5)).toBe('$1.5');
  });
});
