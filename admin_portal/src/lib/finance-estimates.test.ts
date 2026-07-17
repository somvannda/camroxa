import { describe, expect, it } from 'vitest';

import {
  buildOperationFinanceRows,
  resolveCostCredits,
  resolveModelCostUsd,
} from '@/lib/finance-estimates';
import type { CreditPricing, ModelCost, UsageOperationSummary } from '@/types/models';

function pricing(
  partial: Partial<CreditPricing> &
    Pick<CreditPricing, 'ai_service' | 'operation_type' | 'external_cost_cents'>,
): CreditPricing {
  return {
    id: '1',
    model_identifier: partial.ai_service,
    sub_model: '',
    credits_per_operation: 1,
    sell_price_cents: null,
    profit_margin_cents: null,
    profit_margin_percent: null,
    needs_review: false,
    created_at: '',
    updated_at: '',
    ...partial,
  };
}

describe('resolveCostCredits', () => {
  const rows: CreditPricing[] = [
    pricing({
      ai_service: 'fal',
      sub_model: 'flux-pro',
      operation_type: 'channel_cover',
      external_cost_cents: 20,
    }),
    pricing({
      ai_service: 'openai',
      sub_model: 'gpt-image-1',
      operation_type: 'channel_cover',
      external_cost_cents: 4,
    }),
    pricing({
      ai_service: 'slai',
      sub_model: 'slai/gpt-image-2',
      operation_type: 'channel_cover',
      external_cost_cents: 1,
    }),
  ];

  it('does not average unrelated providers for the same operation', () => {
    // Old bug: (20+4+1)/3 = 8.333 → $0.50 for 6 events
    expect(resolveCostCredits(rows, 'channel_cover', null, null)).toBeNull();
  });

  it('resolves SLAI channel cover cost credits', () => {
    expect(resolveCostCredits(rows, 'channel_cover', 'slai', 'slai/gpt-image-2')).toBe(1);
  });
});

describe('buildOperationFinanceRows', () => {
  const pricingRows: CreditPricing[] = [
    pricing({
      ai_service: 'fal',
      sub_model: 'flux-pro',
      operation_type: 'channel_cover',
      external_cost_cents: 20,
    }),
    pricing({
      ai_service: 'openai',
      sub_model: 'gpt-image-1',
      operation_type: 'channel_cover',
      external_cost_cents: 4,
    }),
    pricing({
      ai_service: 'slai',
      sub_model: 'slai/gpt-image-2',
      operation_type: 'channel_cover',
      external_cost_cents: 1,
    }),
  ];

  const usage: UsageOperationSummary[] = [
    {
      operation: 'channel_cover',
      provider: 'slai',
      model: 'slai/gpt-image-2',
      events: 6,
      wallet_charged: 0,
      plan_included_list: 0,
    },
  ];

  it('estimates channel_cover COGS at $0.06 for 6 SLAI events', () => {
    const rows = buildOperationFinanceRows(usage, pricingRows, [], 0.01);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.estimatedCogsUsd).toBeCloseTo(0.06, 6);
    expect(rows[0]?.coverage).toBe('pricing');
    expect(rows[0]?.provider).toBe('slai');
    expect(rows[0]?.model).toBe('slai/gpt-image-2');
  });

  it('falls back to model cost USD for the same provider/model', () => {
    const modelCosts: ModelCost[] = [
      {
        id: '1',
        ai_service: 'slai',
        sub_model: 'slai/gpt-image-2',
        operation_type: 'channel_cover',
        cost_usd: 0.01,
        notes: null,
        source: 'registry',
        created_at: '',
        updated_at: '',
      },
    ];
    const rows = buildOperationFinanceRows(usage, [], modelCosts, 0.01);
    expect(rows[0]?.estimatedCogsUsd).toBeCloseTo(0.06, 6);
    expect(rows[0]?.coverage).toBe('model_cost');
  });

  it('uses routing hint when metadata provider is missing', () => {
    const orphan: UsageOperationSummary[] = [
      {
        operation: 'channel_cover',
        provider: '',
        model: '',
        events: 6,
        wallet_charged: 0,
        plan_included_list: 0,
      },
    ];
    const routing = new Map([
      ['channel_cover', { provider: 'slai', sub_model: 'slai/gpt-image-2' }],
    ]);
    const rows = buildOperationFinanceRows(orphan, pricingRows, [], 0.01, routing);
    expect(rows[0]?.providerSource).toBe('routing');
    expect(rows[0]?.estimatedCogsUsd).toBeCloseTo(0.06, 6);
  });
});

describe('resolveModelCostUsd', () => {
  it('requires a provider so it never mixes Fal/OpenAI/SLAI', () => {
    const costs: ModelCost[] = [
      {
        id: '1',
        ai_service: 'fal',
        sub_model: 'flux-pro',
        operation_type: 'channel_cover',
        cost_usd: 0.05,
        notes: null,
        source: 'registry',
        created_at: '',
        updated_at: '',
      },
      {
        id: '2',
        ai_service: 'slai',
        sub_model: 'slai/gpt-image-2',
        operation_type: 'channel_cover',
        cost_usd: 0.01,
        notes: null,
        source: 'registry',
        created_at: '',
        updated_at: '',
      },
    ];
    expect(resolveModelCostUsd(costs, 'channel_cover', null, null)).toBeNull();
    expect(resolveModelCostUsd(costs, 'channel_cover', 'slai', 'slai/gpt-image-2')).toBe(0.01);
  });
});
