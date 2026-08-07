import { useMemo } from 'react';
import { Users, UserCheck, UserPlus, UserMinus } from 'lucide-react';

import { MoneyGlanceStrip } from '@/components/dashboard/money-glance-strip';
import { OperationsStatusHero } from '@/components/dashboard/operations-status-hero';
import { ProviderKeyBalancesPanel } from '@/components/dashboard/provider-key-balances-panel';
import {
  TopSpendersTable,
  useTopSpendSort,
} from '@/components/dashboard/top-spenders-table';
import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAIRoutingAssignments } from '@/hooks/use-ai-routing';
import {
  useGlobalCreditValue,
  useModelCosts,
  usePricing,
} from '@/hooks/use-credits';
import {
  useAdminOverview,
  useHealthStatus,
} from '@/hooks/use-dashboard';
import { useJobQueueMetrics } from '@/hooks/use-job-queue';
import { useUsage } from '@/hooks/use-usage';
import { useUserSpend } from '@/hooks/use-user-spend';
import {
  buildOperationFinanceRows,
  buildRoutingHintMap,
  computeFinanceGlance,
  flattenRoutingAssignments,
  lastDaysFromIso,
} from '@/lib/finance-estimates';

const DASHBOARD_WINDOW_DAYS = 30;

export default function DashboardPage() {
  const fromDate = useMemo(() => lastDaysFromIso(DASHBOARD_WINDOW_DAYS), []);
  const windowLabel = `Last ${DASHBOARD_WINDOW_DAYS} days`;

  const healthQuery = useHealthStatus();
  const jobQueueQuery = useJobQueueMetrics();
  const overviewQuery = useAdminOverview();

  const [spendSort, setSpendSort] = useTopSpendSort('cogs_desc');
  const spendQuery = useUserSpend({
    page: 1,
    page_size: 10,
    sort: spendSort,
    from_date: fromDate,
  });

  const usageQuery = useUsage({
    page: 1,
    page_size: 1,
    from_date: fromDate,
  });
  const pricingQuery = usePricing();
  const modelCostsQuery = useModelCosts();
  const gcvQuery = useGlobalCreditValue();
  const routingQuery = useAIRoutingAssignments();

  const gcv = gcvQuery.data?.global_credit_value ?? null;
  const routingByOperation = useMemo(
    () => buildRoutingHintMap(flattenRoutingAssignments(routingQuery.data)),
    [routingQuery.data],
  );
  const operationRows = useMemo(
    () =>
      buildOperationFinanceRows(
        usageQuery.data?.summary?.by_operation ?? [],
        pricingQuery.data ?? [],
        modelCostsQuery.data ?? [],
        gcv,
        routingByOperation,
      ),
    [
      usageQuery.data?.summary?.by_operation,
      pricingQuery.data,
      modelCostsQuery.data,
      gcv,
      routingByOperation,
    ],
  );
  const financeGlance = useMemo(
    () => computeFinanceGlance(usageQuery.data?.summary, operationRows, gcv),
    [usageQuery.data?.summary, operationRows, gcv],
  );

  const moneyLoading =
    usageQuery.isLoading ||
    pricingQuery.isLoading ||
    modelCostsQuery.isLoading ||
    gcvQuery.isLoading;
  const moneyError =
    usageQuery.isError ||
    pricingQuery.isError ||
    modelCostsQuery.isError ||
    gcvQuery.isError;
  const moneyErrorMessage =
    (usageQuery.error as Error | null)?.message ||
    (pricingQuery.error as Error | null)?.message ||
    (modelCostsQuery.error as Error | null)?.message ||
    (gcvQuery.error as Error | null)?.message;

  const overview = overviewQuery.data;
  const userStrip = [
    {
      title: 'Total users',
      value: overview?.total_users?.toLocaleString() ?? '—',
      icon: Users,
    },
    {
      title: 'Active',
      value: overview?.active_users?.toLocaleString() ?? '—',
      icon: UserCheck,
    },
    {
      title: 'New (7d)',
      value: overview?.new_users_7d?.toLocaleString() ?? '—',
      icon: UserPlus,
    },
    {
      title: 'Suspended',
      value: overview?.suspended_users?.toLocaleString() ?? '—',
      icon: UserMinus,
    },
  ];

  return (
    <div className="space-y-8 p-6">
      <PageHeader
        eyebrow="Operations overview"
        title="Dashboard"
        description="Live health, provider credits, money, and top spenders — the signals that matter first."
      />

      <OperationsStatusHero
        healthQuery={healthQuery}
        jobQueueQuery={jobQueueQuery}
      />

      <ProviderKeyBalancesPanel />

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Accounts</h2>
            <p className="text-sm text-slate-400">Quick user snapshot</p>
          </div>
          {overview?.new_users_30d != null ? (
            <Badge
              variant="outline"
              className="border-violet-400/20 bg-violet-500/10 text-violet-200"
            >
              Last 30 days: {overview.new_users_30d.toLocaleString()} new
            </Badge>
          ) : null}
        </div>
        {overviewQuery.isLoading ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-2xl" />
            ))}
          </div>
        ) : overviewQuery.isError ? (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {(overviewQuery.error as Error)?.message || 'Failed to load account overview'}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {userStrip.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.title}
                  className="rounded-2xl border border-slate-800/80 bg-slate-900/40 px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {stat.title}
                    </div>
                    <Icon className="h-3.5 w-3.5 text-slate-500" />
                  </div>
                  <div className="mt-2 text-xl font-semibold text-slate-100 tabular-nums">
                    {stat.value}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <MoneyGlanceStrip
        glance={moneyLoading ? null : financeGlance}
        isLoading={moneyLoading}
        isError={moneyError}
        errorMessage={moneyErrorMessage}
        windowLabel={windowLabel}
      />

      <TopSpendersTable
        items={spendQuery.data?.items ?? []}
        sort={spendSort}
        onSortChange={setSpendSort}
        isLoading={spendQuery.isLoading}
        isError={spendQuery.isError}
        errorMessage={(spendQuery.error as Error | null)?.message}
        windowLabel={windowLabel}
      />
    </div>
  );
}
