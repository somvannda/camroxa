import {
  Users,
  KeyRound,
  Coins,
  Activity,
  Music,
  Image,
  Shield,
  UserCheck,
  UserMinus,
  UserPlus,
  FolderKanban,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingSkeleton } from '@/components/shared/loading-skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { HealthSummary } from '@/components/key-pool/health-summary';
import { ProviderKeyBalancesPanel } from '@/components/dashboard/provider-key-balances-panel';
import { PageHeader } from '@/components/shared/page-header';
import { useHealthStatus, useSunoBalance, useAdminOverview, useProviderKeyBalances } from '@/hooks/use-dashboard';
import { cn } from '@/lib/utils';
import type { HealthStatus, ServiceHealth } from '@/types/models';

type StatusLevel = HealthStatus['status'];

const STATUS_COLORS: Record<StatusLevel, string> = {
  healthy: 'bg-green-500/10 text-green-500 border-green-500/20',
  degraded: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  unhealthy: 'bg-red-500/10 text-red-500 border-red-500/20',
};

const STATUS_DOT_COLORS: Record<StatusLevel, string> = {
  healthy: 'bg-green-500',
  degraded: 'bg-yellow-500',
  unhealthy: 'bg-red-500',
};

function getStatusLabel(status: StatusLevel | undefined): string {
  if (!status) return 'Unknown';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function getAffectedServices(
  services: Record<string, ServiceHealth | boolean> | null | undefined,
): Array<{ name: string; status: StatusLevel; message?: string }> {
  if (!services || typeof services !== 'object') {
    return [];
  }

  return Object.entries(services)
    .filter(([, svc]) => {
      if (typeof svc === 'boolean') return !svc;
      return svc?.status !== 'healthy';
    })
    .map(([name, svc]) => ({
      name,
      status: typeof svc === 'boolean'
        ? ((svc ? 'healthy' : 'unhealthy') as StatusLevel)
        : (svc?.status ?? 'unhealthy'),
      message: typeof svc === 'boolean' ? undefined : svc?.message,
    }));
}

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

export default function DashboardPage() {
  const healthQuery = useHealthStatus();
  const balanceQuery = useSunoBalance();
  const overviewQuery = useAdminOverview();
  const providerBalancesQuery = useProviderKeyBalances();

  const isLoading = healthQuery.isLoading || balanceQuery.isLoading || overviewQuery.isLoading;
  const isError = healthQuery.isError || balanceQuery.isError || overviewQuery.isError;
  const errorMessage =
    healthQuery.error?.message || balanceQuery.error?.message || overviewQuery.error?.message || 'Failed to load dashboard data';

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (isError) {
    return (
      <ErrorState
        message={errorMessage}
        onRetry={() => {
          healthQuery.refetch();
          balanceQuery.refetch();
          overviewQuery.refetch();
          providerBalancesQuery.refetch();
        }}
      />
    );
  }

  const health = healthQuery.data;
  const balance = balanceQuery.data?.credits ?? 0;
  const overview = overviewQuery.data;
  const affectedServices = getAffectedServices(health?.services);
  const totalUsers = overview?.total_users ?? 0;
  const activeRate = totalUsers > 0 ? (overview?.active_users ?? 0) / totalUsers * 100 : 0;
  const profileCoverage = totalUsers > 0 ? (overview?.users_with_profiles ?? 0) / totalUsers * 100 : 0;
  const licenseCoverage = totalUsers > 0 ? (overview?.users_with_active_license ?? 0) / totalUsers * 100 : 0;

  const primaryStats = [
    {
      title: 'Total Users',
      value: overview?.total_users?.toLocaleString() ?? '—',
      description: 'All registered accounts',
      icon: Users,
    },
    {
      title: 'Active Accounts',
      value: overview?.active_users?.toLocaleString() ?? '—',
      description: `${formatPercent(activeRate)} of users are active`,
      icon: UserCheck,
    },
    {
      title: 'New Users (7d)',
      value: overview?.new_users_7d?.toLocaleString() ?? '—',
      description: 'Recently created accounts',
      icon: UserPlus,
    },
    {
      title: 'Suspended Users',
      value: overview?.suspended_users?.toLocaleString() ?? '—',
      description: 'Accounts currently blocked',
      icon: UserMinus,
    },
    {
      title: 'Users With Profiles',
      value: overview?.users_with_profiles?.toLocaleString() ?? '—',
      description: `${formatPercent(profileCoverage)} have channel setup`,
      icon: FolderKanban,
    },
    {
      title: 'Users With License',
      value: overview?.users_with_active_license?.toLocaleString() ?? '—',
      description: `${formatPercent(licenseCoverage)} have active access`,
      icon: KeyRound,
    },
  ];

  const platformStats = [
    {
      title: 'Admin Accounts',
      value: overview?.total_admins?.toLocaleString() ?? '—',
      description: 'Internal operators with admin access',
      icon: Shield,
    },
    {
      title: 'Active Licenses',
      value: overview?.active_licenses?.toLocaleString() ?? '—',
      description: 'Currently assigned and active',
      icon: KeyRound,
    },
    {
      title: 'Total Songs',
      value: overview?.total_songs?.toLocaleString() ?? '—',
      description: 'Generated across the platform',
      icon: Music,
    },
    {
      title: 'Total Images',
      value: overview?.total_images?.toLocaleString() ?? '—',
      description: 'Image jobs created so far',
      icon: Image,
    },
    {
      title: 'Suno Balance',
      value: balance.toLocaleString(),
      description: 'External API credits',
      icon: Coins,
    },
    {
      title: 'System Health',
      value: health ? getStatusLabel(health.status) : 'Unknown',
      description: 'Platform API status',
      icon: Activity,
      accent: health ? STATUS_COLORS[health.status] : '',
      dot: health ? STATUS_DOT_COLORS[health.status] : 'bg-slate-500',
    },
  ];

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Operations overview"
        title="Dashboard"
        description="Monitor system health, provider readiness, platform usage, and your current operating posture from one place."
      />

      <ProviderKeyBalancesPanel />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">User Statistics</h2>
            <p className="text-sm text-slate-400">
              Track account growth, adoption, and operational account status.
            </p>
          </div>
          <Badge variant="outline" className="border-violet-400/20 bg-violet-500/10 text-violet-200">
            Last 30 days: {overview?.new_users_30d?.toLocaleString() ?? '—'} new users
          </Badge>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {primaryStats.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.title} className="border-slate-800 bg-slate-900/50">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-slate-400">
                    {stat.title}
                  </CardTitle>
                  <Icon className="h-4 w-4 text-slate-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-slate-100">{stat.value}</div>
                  <p className="text-xs text-slate-500">{stat.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-slate-100">
              Account Coverage
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {[
              {
                label: 'Accounts with channel profiles',
                value: overview?.users_with_profiles ?? 0,
                total: totalUsers,
                percent: profileCoverage,
              },
              {
                label: 'Accounts with active license access',
                value: overview?.users_with_active_license ?? 0,
                total: totalUsers,
                percent: licenseCoverage,
              },
              {
                label: 'Active account health',
                value: overview?.active_users ?? 0,
                total: totalUsers,
                percent: activeRate,
              },
            ].map((item) => (
              <div key={item.label} className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm text-slate-300">{item.label}</div>
                  <div className="text-sm font-medium text-white">
                    {item.value.toLocaleString()} / {item.total.toLocaleString()} ({formatPercent(item.percent)})
                  </div>
                </div>
                <div className="h-2 rounded-full bg-slate-800/90">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500"
                    style={{ width: `${Math.max(6, Math.min(100, item.percent))}%` }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-slate-100">
              Platform Snapshot
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {platformStats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.title}
                  className="rounded-2xl border border-white/8 bg-slate-950/45 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                        {stat.title}
                      </div>
                      {stat.dot ? (
                        <div className="mt-2 flex items-center gap-2">
                          <span className={cn('h-2.5 w-2.5 rounded-full', stat.dot)} />
                          <Badge className={cn('text-xs', stat.accent)}>{stat.value}</Badge>
                        </div>
                      ) : (
                        <div className="mt-2 text-xl font-semibold text-white">{stat.value}</div>
                      )}
                      <div className="mt-1 text-xs text-slate-500">{stat.description}</div>
                    </div>
                    <Icon className="h-4 w-4 text-slate-500" />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-slate-100">
            Provider Key Pool Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <HealthSummary />
        </CardContent>
      </Card>

      {/* Affected Services Section */}
      {affectedServices.length > 0 && (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-slate-100">
              Affected Services
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {affectedServices.map((service) => (
                <div
                  key={service.name}
                  className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-950/50 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'h-2.5 w-2.5 rounded-full',
                        STATUS_DOT_COLORS[service.status],
                      )}
                    />
                    <span className="text-sm font-medium text-slate-200">
                      {service.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {service.message && (
                      <span className="text-xs text-slate-400">
                        {service.message}
                      </span>
                    )}
                    <Badge
                      className={cn(
                        'text-xs',
                        STATUS_COLORS[service.status],
                      )}
                    >
                      {getStatusLabel(service.status)}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
