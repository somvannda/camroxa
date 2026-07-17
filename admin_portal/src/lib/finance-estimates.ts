import type { CreditPricing, ModelCost, UsageOperationSummary } from '@/types/models';

export type RoutingAssignmentHint = {
  provider: string;
  sub_model: string | null;
};

export type OperationFinanceRow = {
  operation: string;
  provider: string | null;
  model: string | null;
  /** Where provider/model display came from. */
  providerSource: 'metadata' | 'routing' | 'none';
  events: number;
  walletCharged: number;
  planIncludedList: number;
  estimatedCogsCredits: number | null;
  estimatedCogsUsd: number | null;
  coverage: 'pricing' | 'model_cost' | 'none';
};

function norm(value: string | null | undefined): string {
  return (value ?? '').trim();
}

/** Music ops share pricing rows under either name. */
function operationAliases(operation: string): string[] {
  const op = norm(operation);
  if (!op) return [];
  if (op === 'music' || op === 'music_generation' || op === 'suno') {
    return ['music', 'music_generation'];
  }
  return [op];
}

function pricingMatches(
  row: CreditPricing,
  operation: string,
  provider: string,
  model: string,
): boolean {
  if (!operationAliases(operation).includes(norm(row.operation_type))) return false;
  if (provider && norm(row.ai_service) !== provider) return false;
  if (model) {
    const rowModel = norm(row.sub_model);
    return !rowModel || rowModel === model;
  }
  return true;
}

/**
 * Look up cost-credits for a specific provider/model/operation.
 * Never averages unrelated providers (that was the channel_cover $0.50 bug).
 */
export function resolveCostCredits(
  pricing: CreditPricing[],
  operation: string,
  provider: string | null,
  model: string | null,
): number | null {
  const op = norm(operation);
  const prov = norm(provider);
  const mod = norm(model);
  if (!op) return null;

  const candidates = pricing.filter(
    (row) =>
      row.external_cost_cents != null &&
      row.external_cost_cents >= 0 &&
      pricingMatches(row, op, prov, mod),
  );
  if (candidates.length === 0) return null;

  // Prefer exact model match when a model is known.
  if (mod) {
    const exact = candidates.filter((row) => norm(row.sub_model) === mod);
    if (exact.length > 0) {
      return average(exact.map((row) => row.external_cost_cents as number));
    }
    const defaults = candidates.filter((row) => !norm(row.sub_model));
    if (defaults.length > 0) {
      return average(defaults.map((row) => row.external_cost_cents as number));
    }
  }

  // Provider known, model unknown: average only that provider's rows for the op.
  if (prov) {
    return average(candidates.map((row) => row.external_cost_cents as number));
  }

  // No provider: only use if a single distinct cost exists across matches.
  const values = candidates.map((row) => row.external_cost_cents as number);
  const unique = new Set(values.map((v) => Number(v.toFixed(6))));
  if (unique.size === 1) return values[0] ?? null;
  return null;
}

export function resolveModelCostUsd(
  modelCosts: ModelCost[],
  operation: string,
  provider: string | null,
  model: string | null,
): number | null {
  const op = norm(operation);
  const prov = norm(provider);
  const mod = norm(model);
  if (!op || !prov) return null;

  const aliases = operationAliases(op);
  const forProvider = modelCosts.filter(
    (row) =>
      Number.isFinite(row.cost_usd) &&
      row.cost_usd >= 0 &&
      aliases.includes(norm(row.operation_type)) &&
      norm(row.ai_service) === prov,
  );
  if (forProvider.length === 0) return null;

  if (mod) {
    const exact = forProvider.filter((row) => norm(row.sub_model) === mod);
    if (exact.length > 0) return average(exact.map((row) => row.cost_usd));
    const defaults = forProvider.filter((row) => !norm(row.sub_model));
    if (defaults.length > 0) return average(defaults.map((row) => row.cost_usd));
  }

  return average(forProvider.map((row) => row.cost_usd));
}

function average(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function resolveProviderModel(
  row: UsageOperationSummary,
  routingByOperation: Map<string, RoutingAssignmentHint>,
): {
  provider: string | null;
  model: string | null;
  providerSource: 'metadata' | 'routing' | 'none';
} {
  const metaProvider = norm(row.provider) || null;
  const metaModel = norm(row.model) || null;
  if (metaProvider || metaModel) {
    return {
      provider: metaProvider,
      model: metaModel,
      providerSource: 'metadata',
    };
  }

  const hint = routingByOperation.get(norm(row.operation));
  if (hint?.provider) {
    return {
      provider: norm(hint.provider) || null,
      model: norm(hint.sub_model) || null,
      providerSource: 'routing',
    };
  }

  return { provider: null, model: null, providerSource: 'none' };
}

export function buildRoutingHintMap(
  assignments: Record<string, RoutingAssignmentHint | undefined> | null | undefined,
): Map<string, RoutingAssignmentHint> {
  const map = new Map<string, RoutingAssignmentHint>();
  if (!assignments) return map;
  for (const [operation, hint] of Object.entries(assignments)) {
    if (!hint?.provider) continue;
    map.set(norm(operation), {
      provider: hint.provider,
      sub_model: hint.sub_model ?? null,
    });
  }
  return map;
}

export function flattenRoutingAssignments(data: {
  text_generation?: Record<string, RoutingAssignmentHint | undefined>;
  image_generation?: Record<string, RoutingAssignmentHint | undefined>;
  music_generation?: Record<string, RoutingAssignmentHint | undefined>;
} | null | undefined): Record<string, RoutingAssignmentHint> {
  const out: Record<string, RoutingAssignmentHint> = {};
  for (const group of [data?.text_generation, data?.image_generation, data?.music_generation]) {
    if (!group) continue;
    for (const [op, hint] of Object.entries(group)) {
      if (hint?.provider) out[op] = hint;
    }
  }
  return out;
}

export function buildOperationFinanceRows(
  byOperation: UsageOperationSummary[],
  pricing: CreditPricing[],
  modelCosts: ModelCost[],
  gcv: number | null,
  routingByOperation: Map<string, RoutingAssignmentHint> = new Map(),
): OperationFinanceRow[] {
  return byOperation.map((row) => {
    const resolved = resolveProviderModel(row, routingByOperation);
    const costCredits = resolveCostCredits(
      pricing,
      row.operation,
      resolved.provider,
      resolved.model,
    );

    if (costCredits != null) {
      const estimatedCogsCredits = row.events * costCredits;
      return {
        operation: row.operation,
        provider: resolved.provider,
        model: resolved.model,
        providerSource: resolved.providerSource,
        events: row.events,
        walletCharged: row.wallet_charged,
        planIncludedList: row.plan_included_list,
        estimatedCogsCredits,
        estimatedCogsUsd: gcv != null ? estimatedCogsCredits * gcv : null,
        coverage: 'pricing' as const,
      };
    }

    const costUsd = resolveModelCostUsd(
      modelCosts,
      row.operation,
      resolved.provider,
      resolved.model,
    );
    if (costUsd != null) {
      const estimatedCogsUsd = row.events * costUsd;
      return {
        operation: row.operation,
        provider: resolved.provider,
        model: resolved.model,
        providerSource: resolved.providerSource,
        events: row.events,
        walletCharged: row.wallet_charged,
        planIncludedList: row.plan_included_list,
        estimatedCogsCredits: gcv != null && gcv > 0 ? estimatedCogsUsd / gcv : null,
        estimatedCogsUsd,
        coverage: 'model_cost' as const,
      };
    }

    return {
      operation: row.operation,
      provider: resolved.provider,
      model: resolved.model,
      providerSource: resolved.providerSource,
      events: row.events,
      walletCharged: row.wallet_charged,
      planIncludedList: row.plan_included_list,
      estimatedCogsCredits: null,
      estimatedCogsUsd: null,
      coverage: 'none' as const,
    };
  });
}
