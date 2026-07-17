import React from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  Coins,
  DollarSign,
  Info,
  PiggyBank,
  RefreshCw,
  Search,
  TrendingUp,
} from 'lucide-react';

import { DateRangePicker, type DateRangeValue } from '@/components/shared/date-range-picker';
import { ErrorState } from '@/components/shared/error-state';
import { StatCard } from '@/components/shared/stat-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAIRoutingAssignments } from '@/hooks/use-ai-routing';
import {
  useGlobalCreditValue,
  useModelCosts,
  usePricing,
} from '@/hooks/use-credits';
import { useUsage, useUsageFilters } from '@/hooks/use-usage';
import { formatCredits, formatDollars } from '@/lib/credit-format';
import {
  buildOperationFinanceRows,
  buildRoutingHintMap,
  flattenRoutingAssignments,
} from '@/lib/finance-estimates';
import { formatOperationLabel } from '@/lib/usage-labels';
import type { UsageListParams } from '@/types/api';

interface FinanceFiltersState {
  operation: string;
  dateRange: DateRangeValue;
}

const EMPTY_FILTERS: FinanceFiltersState = {
  operation: 'all',
  dateRange: {},
};

function filtersToParams(filters: FinanceFiltersState): UsageListParams {
  return {
    page: 1,
    page_size: 1,
    ...(filters.operation !== 'all' && { operation: filters.operation }),
    ...(filters.dateRange.from && { from_date: filters.dateRange.from }),
    ...(filters.dateRange.to && { to_date: `${filters.dateRange.to}T23:59:59` }),
  };
}

function formatProviderModel(provider: string | null, model: string | null): string {
  if (provider && model) return `${provider} / ${model}`;
  if (provider) return provider;
  if (model) return model;
  return '—';
}

export default function FinancePage() {
  const [draftFilters, setDraftFilters] = React.useState<FinanceFiltersState>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = React.useState<FinanceFiltersState>(EMPTY_FILTERS);

  const params = React.useMemo(() => filtersToParams(appliedFilters), [appliedFilters]);
  const { data, isLoading, isError, error, refetch, isFetching } = useUsage(params);
  const filtersQuery = useUsageFilters();
  const pricingQuery = usePricing();
  const modelCostsQuery = useModelCosts();
  const gcvQuery = useGlobalCreditValue();
  const routingQuery = useAIRoutingAssignments();

  const operationOptions = filtersQuery.data?.operations ?? [];
  const gcv = gcvQuery.data?.global_credit_value ?? null;
  const summary = data?.summary;

  const routingByOperation = React.useMemo(
    () => buildRoutingHintMap(flattenRoutingAssignments(routingQuery.data)),
    [routingQuery.data],
  );

  const operationRows = React.useMemo(
    () =>
      buildOperationFinanceRows(
        summary?.by_operation ?? [],
        pricingQuery.data ?? [],
        modelCostsQuery.data ?? [],
        gcv,
        routingByOperation,
      ),
    [summary?.by_operation, pricingQuery.data, modelCostsQuery.data, gcv, routingByOperation],
  );

  const estimatedCogsCredits = operationRows.reduce(
    (sum, row) => sum + (row.estimatedCogsCredits ?? 0),
    0,
  );
  const estimatedCogsUsd = operationRows.reduce(
    (sum, row) => sum + (row.estimatedCogsUsd ?? 0),
    0,
  );
  const cogsCoverageEvents = operationRows
    .filter((row) => row.coverage !== 'none')
    .reduce((sum, row) => sum + row.events, 0);
  const totalEvents = operationRows.reduce((sum, row) => sum + row.events, 0);
  const cogsPartial = totalEvents > 0 && cogsCoverageEvents < totalEvents;

  const walletRevenueUsd =
    gcv != null && summary ? (summary.wallet_charged ?? 0) * gcv : null;
  const planListUsd =
    gcv != null && summary ? (summary.plan_included_list ?? 0) * gcv : null;
  const planDraftListUsd =
    gcv != null && summary ? (summary.plan_draft_list ?? 0) * gcv : null;
  const planSongListUsd =
    gcv != null && summary ? (summary.plan_song_list ?? 0) * gcv : null;
  const planImageListUsd =
    gcv != null && summary ? (summary.plan_image_list ?? 0) * gcv : null;
  const absorbListUsd =
    gcv != null && summary ? (summary.platform_absorb_list ?? 0) * gcv : null;
  const subscriptionRevenueUsd =
    summary != null ? (summary.subscription_revenue_cents ?? 0) / 100 : null;
  const cashRevenueUsd =
    walletRevenueUsd != null && subscriptionRevenueUsd != null
      ? walletRevenueUsd + subscriptionRevenueUsd
      : walletRevenueUsd ?? subscriptionRevenueUsd;
  const profitUsd =
    cashRevenueUsd != null ? cashRevenueUsd - estimatedCogsUsd : null;

  const applyFilters = () => setAppliedFilters(draftFilters);
  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  };

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load finance summary'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.08),transparent_35%),linear-gradient(180deg,#020617_0%,#030712_100%)] p-8">
      <div className="mx-auto max-w-[1400px] space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-400/80">
              Finance
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
              Profit & revenue estimate
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
              Subscription cash, wallet charges, plan-included list value (draft / song /
              image), platform absorb, estimated provider COGS, and contribution margin —
              filtered by operation and date range.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              asChild
            >
              <Link to="/usage">Open usage ledger</Link>
            </Button>
            <Button
              variant="outline"
              className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-slate-300">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            <div className="space-y-2">
              <div className="font-medium text-slate-100">Assumptions</div>
              <ul className="list-disc space-y-1 pl-4 text-slate-400">
                <li>
                  <span className="text-slate-300">Wallet charged revenue</span> = wallet debit
                  credits × global credit value (GCV). List-price wallet consumption, not
                  necessarily cash collected.
                </li>
                <li>
                  <span className="text-slate-300">Subscription revenue</span> = sum of{' '}
                  <span className="font-mono text-slate-300">billing_payments.amount_cents</span>{' '}
                  where status is paid and fulfilled (cash collected).
                </li>
                <li>
                  <span className="text-slate-300">Plan-included list value</span> sums{' '}
                  <span className="font-mono text-slate-300">list_credit_units</span> on{' '}
                  <span className="font-mono text-slate-300">plan_allowance</span> rows × GCV,
                  split by meter coverage (draft / song package / image).
                </li>
                <li>
                  <span className="text-slate-300">Platform absorb</span> = owner-paid failed /
                  unbillable list units (
                  <span className="font-mono text-slate-300">billing=platform_absorb</span>).
                </li>
                <li>
                  <span className="text-slate-300">Estimated COGS</span> uses each row&apos;s
                  provider/model (from transaction metadata, else current AI routing). Cost is
                  that row&apos;s Credits pricing{' '}
                  <span className="font-mono text-slate-300">external_cost_cents</span> (display
                  cost credits) × events × GCV — not an average across unrelated providers. Falls
                  back to{' '}
                  <span className="font-mono text-slate-300">ai_model_costs.cost_usd</span> when
                  pricing cost is missing.
                </li>
                <li>
                  <span className="text-slate-300">Example</span>: SLAI channel cover at 1 cost
                  credit × GCV $0.01 = $0.01/event. Music list 7.5 cr / cost 6 cr → $0.075 / $0.06
                  at GCV $0.01.
                </li>
                <li>
                  <span className="text-slate-300">Profit estimate</span> = (subscription cash +
                  wallet charged revenue) − estimated COGS.
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-5 shadow-xl shadow-black/20">
          <div className="mb-4 text-sm font-medium text-slate-200">Filters</div>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={draftFilters.operation}
              onValueChange={(value) => setDraftFilters((prev) => ({ ...prev, operation: value }))}
            >
              <SelectTrigger className="w-[220px] border-slate-700/80 bg-slate-900/70 text-slate-100">
                <SelectValue placeholder="Operation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All operations</SelectItem>
                {operationOptions.map((operation) => (
                  <SelectItem key={operation} value={operation}>
                    {formatOperationLabel(operation)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <DateRangePicker
              value={draftFilters.dateRange}
              onChange={(dateRange) => setDraftFilters((prev) => ({ ...prev, dateRange }))}
            />
            <Button onClick={applyFilters} className="bg-emerald-600 hover:bg-emerald-500">
              <Search className="mr-2 h-4 w-4" />
              Apply
            </Button>
            <Button
              variant="outline"
              className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-900"
              onClick={clearFilters}
            >
              Clear
            </Button>
            {isLoading ? <span className="text-xs text-slate-500">Loading…</span> : null}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <StatCard
            label="Subscription revenue"
            value={
              subscriptionRevenueUsd != null
                ? formatDollars(subscriptionRevenueUsd)
                : '—'
            }
            tone="success"
            icon={PiggyBank}
            hint={
              summary
                ? `${summary.subscription_payment_count ?? 0} paid+fulfilled checkouts`
                : undefined
            }
          />
          <StatCard
            label="Wallet charged revenue"
            value={walletRevenueUsd != null ? formatDollars(walletRevenueUsd) : '—'}
            tone="success"
            icon={DollarSign}
            hint={
              summary
                ? `${formatCredits(summary.wallet_charged ?? 0)} cr · GCV ${
                    gcv != null ? formatDollars(gcv) : 'not set'
                  }`
                : undefined
            }
          />
          <StatCard
            label="Plan included (list)"
            value={planListUsd != null ? formatDollars(planListUsd) : '—'}
            icon={Coins}
            hint={
              summary
                ? [
                    `Draft ${formatDollars(planDraftListUsd ?? 0)}`,
                    `Song ${formatDollars(planSongListUsd ?? 0)}`,
                    `Image ${formatDollars(planImageListUsd ?? 0)}`,
                    `${summary.plan_allowance_events ?? 0} plan rows`,
                  ].join(' · ')
                : undefined
            }
          />
          <StatCard
            label="Platform absorb"
            value={absorbListUsd != null ? formatDollars(absorbListUsd) : '—'}
            tone="warning"
            icon={AlertCircle}
            hint={
              summary
                ? `${summary.platform_absorb_events ?? 0} absorb rows · ${formatCredits(
                    summary.platform_absorb_list ?? 0,
                  )} list cr`
                : undefined
            }
          />
          <StatCard
            label="Estimated COGS"
            value={
              estimatedCogsUsd > 0 || cogsCoverageEvents > 0
                ? formatDollars(estimatedCogsUsd)
                : '—'
            }
            tone="danger"
            icon={AlertCircle}
            hint={
              cogsPartial
                ? `Partial · ${cogsCoverageEvents}/${totalEvents} events have cost data`
                : estimatedCogsCredits > 0
                  ? `${formatCredits(estimatedCogsCredits)} cost credits`
                  : 'Configure pricing costs or model costs'
            }
          />
          <StatCard
            label="Profit estimate"
            value={profitUsd != null ? formatDollars(profitUsd) : '—'}
            tone={profitUsd != null && profitUsd >= 0 ? 'success' : 'warning'}
            icon={TrendingUp}
            hint="(Sub cash + wallet) − estimated COGS"
          />
          <StatCard
            label="Billable events"
            value={summary?.billable_events ?? '—'}
            icon={Coins}
            hint={`${summary?.refund_events ?? 0} refunds in range · see licenses for active subs`}
          />
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-5 shadow-xl shadow-black/20">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-medium text-slate-200">Breakdown by operation</div>
            <Badge className="border-transparent bg-slate-800 text-slate-300 hover:bg-slate-800">
              Filters apply to totals and rows
            </Badge>
          </div>
          {operationRows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                    <th className="pb-2 font-medium">Operation</th>
                    <th className="pb-2 font-medium">Provider / Model</th>
                    <th className="pb-2 font-medium">Events</th>
                    <th className="pb-2 font-medium">Wallet charged</th>
                    <th className="pb-2 font-medium">Plan included</th>
                    <th className="pb-2 font-medium">Est. COGS</th>
                    <th className="pb-2 font-medium">Cost source</th>
                  </tr>
                </thead>
                <tbody>
                  {operationRows.map((row) => (
                    <tr
                      key={`${row.operation}|${row.provider ?? ''}|${row.model ?? ''}`}
                      className="border-b border-slate-900/80 text-slate-300"
                    >
                      <td className="py-2.5 pr-4 font-medium text-slate-200">
                        {formatOperationLabel(row.operation)}
                      </td>
                      <td className="py-2.5 pr-4">
                        <div className="font-mono text-sm text-slate-200">
                          {formatProviderModel(row.provider, row.model)}
                        </div>
                        {row.providerSource === 'routing' ? (
                          <div className="text-[11px] text-slate-500">from current routing</div>
                        ) : null}
                      </td>
                      <td className="py-2.5 pr-4 font-mono">{row.events}</td>
                      <td className="py-2.5 pr-4 font-mono text-red-300/90">
                        {formatCredits(row.walletCharged)}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-sky-300/90">
                        {formatCredits(row.planIncludedList)}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-amber-300/90">
                        {row.estimatedCogsUsd != null ? formatDollars(row.estimatedCogsUsd) : '—'}
                      </td>
                      <td className="py-2.5 text-xs text-slate-500">
                        {row.coverage === 'pricing'
                          ? 'Credit pricing cost'
                          : row.coverage === 'model_cost'
                            ? 'Model cost USD'
                            : 'No cost data'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              No operation breakdown for the current filters.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
