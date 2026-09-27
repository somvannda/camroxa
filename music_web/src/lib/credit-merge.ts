/**
 * Pure helpers that map the V3 wallet view onto the shared `CreditBalance` shape.
 *
 * Kept free of imports so it can be unit-tested with `node --test`.
 */

export type CreditSplit = {
  /** Daily free credits still available (these expire at midnight). */
  dailyFree: number;
  /** Size of the monthly grant pot. */
  monthlyPool: number;
  /** Monthly grant credits still available. */
  monthlyRemaining: number;
  /** Monthly grant credits already spent. */
  monthlyUsed: number;
  /** Everything left once the daily and monthly pots are accounted for. */
  topup: number;
};

/**
 * Split a wallet balance into the daily, monthly and top-up pots.
 *
 * Wallet lot `remaining_credits` is only zeroed on expiry, never on spend
 * (charging only debits `credit_wallets`), so lots report the granted amount
 * rather than a remainder. Splitting the authoritative wallet balance instead
 * keeps the usage figures correct. The expiring daily grant is consumed first,
 * then the monthly grant, then top-ups.
 */
export function splitCreditBalance(
  total: number,
  dailyLimit: number,
  monthlyPool: number,
): CreditSplit {
  const dailyFree = Math.min(Math.max(0, total), dailyLimit);
  const monthlyRemaining = Math.min(Math.max(0, total - dailyFree), monthlyPool);
  const topup = Math.max(0, total - dailyFree - monthlyRemaining);

  return {
    dailyFree,
    monthlyPool,
    monthlyRemaining,
    monthlyUsed: Math.max(0, monthlyPool - monthlyRemaining),
    topup,
  };
}
