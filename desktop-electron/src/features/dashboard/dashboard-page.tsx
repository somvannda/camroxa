import { useMemo } from "react";
import { PageHeader } from "../../components/page-header";
import { Badge } from "../../components/status";
import {
  activityRows,
  buildWeeklySeries,
  creditPosition,
  kpiValues,
} from "./dashboard-format";
import { CreditBalanceCard } from "./credit-balance-card";
import { DashboardErrorBanner } from "./dashboard-error-banner";
import { KpiCard } from "./kpi-card";
import { RecentActivityCard } from "./recent-activity-card";
import { useAccountOverview } from "./use-account-overview";
import { WeeklyUsageCard } from "./weekly-usage-card";

export function DashboardPage() {
  const query = useAccountOverview();
  const data = query.data;
  const loading = query.isLoading;
  const stale = query.isError && Boolean(data);

  const kpis = useMemo(() => kpiValues(data?.stats, data?.me), [data?.stats, data?.me]);
  const series = useMemo(
    () => buildWeeklySeries(data?.stats?.usage_by_day),
    [data?.stats?.usage_by_day],
  );
  const position = useMemo(
    () => creditPosition(data?.stats, data?.me),
    [data?.stats, data?.me],
  );
  const activity = useMemo(() => activityRows(data?.stats), [data?.stats]);

  return (
    <div className="pb-6">
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Credits, generation output and account activity at a glance."
        actions={stale ? <Badge tone="warning">Stale</Badge> : undefined}
      />

      <div className="space-y-5 p-6">
        {query.isError ? <DashboardErrorBanner /> : null}

        <div className="grid grid-cols-2 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          {kpis.map((item) => (
            <KpiCard key={item.key} item={item} />
          ))}
        </div>

        <div className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
          <WeeklyUsageCard series={series} loading={loading} hasError={query.isError} />
          <CreditBalanceCard position={position} />
        </div>

        <RecentActivityCard rows={activity} loading={loading} />
      </div>
    </div>
  );
}
