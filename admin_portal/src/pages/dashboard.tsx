import { Users, KeyRound, Coins, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingSkeleton } from '@/components/shared/loading-skeleton';
import { ErrorState } from '@/components/shared/error-state';
import { useHealthStatus, useSunoBalance } from '@/hooks/use-dashboard';
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

function getStatusLabel(status: StatusLevel): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function getAffectedServices(
  services: Record<string, ServiceHealth>,
): Array<{ name: string; status: StatusLevel; message?: string }> {
  return Object.entries(services)
    .filter(([, svc]) => svc.status !== 'healthy')
    .map(([name, svc]) => ({
      name,
      status: svc.status,
      message: svc.message,
    }));
}

export default function DashboardPage() {
  const healthQuery = useHealthStatus();
  const balanceQuery = useSunoBalance();

  const isLoading = healthQuery.isLoading || balanceQuery.isLoading;
  const isError = healthQuery.isError || balanceQuery.isError;
  const errorMessage =
    healthQuery.error?.message || balanceQuery.error?.message || 'Failed to load dashboard data';

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
        }}
      />
    );
  }

  const health = healthQuery.data;
  const balance = balanceQuery.data?.balance ?? 0;
  const affectedServices = health ? getAffectedServices(health.services) : [];

  return (
    <div className="space-y-6 p-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-400">
          Platform overview and system health
        </p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Users */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Total Users
            </CardTitle>
            <Users className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">—</div>
            <p className="text-xs text-slate-500">All registered accounts</p>
          </CardContent>
        </Card>

        {/* Active Licenses */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Active Licenses
            </CardTitle>
            <KeyRound className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">—</div>
            <p className="text-xs text-slate-500">Currently active</p>
          </CardContent>
        </Card>

        {/* Suno Balance */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Suno Balance
            </CardTitle>
            <Coins className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">
              {balance.toLocaleString()}
            </div>
            <p className="text-xs text-slate-500">External API credits</p>
          </CardContent>
        </Card>

        {/* System Health */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              System Health
            </CardTitle>
            <Activity className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            {health && (
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'h-3 w-3 rounded-full',
                    STATUS_DOT_COLORS[health.status],
                  )}
                />
                <Badge
                  className={cn(
                    'text-sm font-semibold',
                    STATUS_COLORS[health.status],
                  )}
                >
                  {getStatusLabel(health.status)}
                </Badge>
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">Platform API status</p>
          </CardContent>
        </Card>
      </div>

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
