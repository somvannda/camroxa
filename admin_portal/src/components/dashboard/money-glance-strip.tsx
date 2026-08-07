import { Link } from 'react-router-dom';
import { ArrowRight, Coins, DollarSign, PiggyBank, TrendingUp } from 'lucide-react';

import { StatCard } from '@/components/shared/stat-card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDollars } from '@/lib/credit-format';
import type { FinanceGlance } from '@/lib/finance-estimates';

type MoneyGlanceStripProps = {
  glance: FinanceGlance | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  windowLabel?: string;
};

export function MoneyGlanceStrip({
  glance,
  isLoading,
  isError,
  errorMessage,
  windowLabel = 'Last 30 days',
}: MoneyGlanceStripProps) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Money glance</h2>
          <p className="text-sm text-slate-400">
            {windowLabel} · income, COGS, profit, and credit pack purchases
          </p>
        </div>
        <Link
          to="/finance"
          className="inline-flex items-center text-xs font-medium text-violet-300 hover:text-violet-200"
        >
          Open finance
          <ArrowRight className="ml-1 h-3.5 w-3.5" />
        </Link>
      </div>

      {isError ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {errorMessage || 'Failed to load finance summary'}
        </div>
      ) : isLoading || !glance ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total income"
            value={formatDollars(glance.cashRevenueUsd)}
            hint="Subscriptions + wallet spend (est. USD)"
            icon={DollarSign}
          />
          <StatCard
            label="Est. COGS"
            value={formatDollars(glance.estimatedCogsUsd)}
            hint={
              glance.totalEvents > 0 && glance.cogsCoverageEvents < glance.totalEvents
                ? `Partial · ${glance.cogsCoverageEvents}/${glance.totalEvents} events`
                : 'Provider cost estimate'
            }
            icon={PiggyBank}
            tone="warning"
          />
          <StatCard
            label="Profit"
            value={formatDollars(glance.profitUsd)}
            hint="Income − est. COGS"
            icon={TrendingUp}
            tone={
              glance.profitUsd == null
                ? 'default'
                : glance.profitUsd >= 0
                  ? 'success'
                  : 'danger'
            }
          />
          <StatCard
            label="Credits purchased"
            value={formatDollars(glance.creditPackRevenueUsd)}
            hint={
              glance.creditPackPaymentCount > 0
                ? `${glance.creditPackPaymentCount} credit pack payment${
                    glance.creditPackPaymentCount === 1 ? '' : 's'
                  }`
                : 'Credit pack checkout cash'
            }
            icon={Coins}
            tone="success"
          />
        </div>
      )}
    </section>
  );
}
