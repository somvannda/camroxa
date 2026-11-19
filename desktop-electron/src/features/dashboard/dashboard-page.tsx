import { useMemo } from "react";
import { PageHeader } from "../../components/page-header";
import { Badge } from "../../components/status";
import {
  activityRows,
  buildWeeklySeries,
  kpiValues,
  planBadge,
  quotaRows,
  quotaSummary,
} from "./dashboard-format";
import { DashboardErrorBanner } from "./dashboard-error-banner";
import { KpiCard } from "./kpi-card";
import { RecentActivityCard } from "./recent-activity-card";
import { RemainingMonthCard } from "./remaining-month-card";
import { useAccountOverview } from "./use-account-overview";
import { WeeklyUsageCard } from "./weekly-usage-card";

export function DashboardPage() {
  const query = useAccountOverview();
  const data = query.data;
  const loading = query.isLoading;
  const stale = query.isError && Boolean(data);

  const kpis = useMemo(() => kpiValues(data?.stats), [data?.stats]);
  const series = useMemo(() => buildWeeklySeries(data?.stats?.usage_by_day), [data?.stats?.usage_by_day]);
  const plan = useMemo(() => planBadge(data?.me, data?.license), [data?.me, data?.license]);
  const rows = useMemo(() => quotaRows(data?.stats, data?.license), [data?.stats, data?.license]);
  const summary = useMemo(
    () => quotaSummary(data?.me, data?.stats, data?.license),
    [data?.me, data?.stats, data?.license],
  );
  const activity = useMemo(() => activityRows(data?.stats), [data?.stats]);

  return (
    <div className="pb-6">
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Usage, quota and recent activity at a glance."
        actions={stale ? <Badge tone="warning">Stale</Badge> : undefined}
      />

      <div className="space-y-6 p-6">
        {query.isError ? <DashboardErrorBanner /> : null}

        <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
          {kpis.map((item) => (
            <KpiCard key={item.key} item={item} />
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[59fr_41fr]">
          <WeeklyUsageCard
            series={series}
            plan={plan.plan}
            expiry={plan.expiry}
            loading={loading}
            hasError={query.isError}
          />
          <RemainingMonthCard rows={rows} summary={summary} />
        </div>

        <RecentActivityCard rows={activity} plan={plan} loading={loading} />
      </div>
    </div>
  );
}
