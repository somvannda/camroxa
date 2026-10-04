import { AlertTriangle } from 'lucide-react';

import { useAllProvidersHealth } from '@/hooks/use-key-pool';
import type { ProviderHealth, HealthIndicator } from '@/types/key-pool';
import type { ServiceHealth } from '@/types/models';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const PROVIDERS = ['suno', 'fal', 'openai', 'deepseek', 'slai', 'cala', 'kie', 'youtube', 'facebook'] as const;

/** Core generation providers shown on the dashboard key-pool row. */
const DASHBOARD_ROW_PROVIDERS = ['suno', 'fal', 'openai', 'deepseek', 'slai', 'cala', 'kie'] as const;

const PROVIDER_LABELS: Record<string, string> = {
  suno: 'Camxora Pool Key',
  fal: 'FAL',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  slai: 'Slai',
  cala: 'CALA',
  kie: 'kie.ai',
  youtube: 'YouTube',
  facebook: 'Facebook',
};

function getHealthBadgeStyles(indicator: HealthIndicator): string {
  switch (indicator) {
    case 'healthy':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'degraded':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'critical':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    default:
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  }
}

function getHealthBorderColor(indicator: HealthIndicator): string {
  switch (indicator) {
    case 'healthy':
      return 'border-green-500/30';
    case 'degraded':
      return 'border-yellow-500/30';
    case 'critical':
      return 'border-red-500/30';
    default:
      return 'border-navy-700';
  }
}

function serviceAvailable(
  services: Record<string, ServiceHealth | boolean> | null | undefined,
  provider: string,
): boolean | null {
  if (!services || !(provider in services)) return null;
  const svc = services[provider];
  if (typeof svc === 'boolean') return svc;
  return svc?.status === 'healthy';
}

function fallbackFromApiHealth(
  provider: string,
  services: Record<string, ServiceHealth | boolean> | null | undefined,
): ProviderHealth {
  const available = serviceAvailable(services, provider);
  return {
    provider,
    total_keys: 0,
    active_keys: 0,
    rate_limited_keys: 0,
    exhausted_keys: 0,
    disabled_keys: 0,
    health_indicator: available === true ? 'healthy' : 'critical',
  };
}

interface ProviderHealthCardProps {
  health: ProviderHealth;
  className?: string;
}

function ProviderHealthCard({ health, className }: ProviderHealthCardProps) {
  return (
    <Card
      className={cn(
        'h-full bg-navy-900',
        getHealthBorderColor(health.health_indicator),
        className,
      )}
    >
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium text-slate-200">
            {PROVIDER_LABELS[health.provider] ?? health.provider}
          </p>
          <Badge className={`shrink-0 text-[10px] ${getHealthBadgeStyles(health.health_indicator)}`}>
            {health.health_indicator}
          </Badge>
        </div>

        <p className="text-lg font-semibold text-white">
          {health.active_keys}/{health.total_keys}{' '}
          <span className="text-xs font-normal text-slate-400">active</span>
        </p>

        <div className="grid grid-cols-3 gap-1 text-[11px] text-slate-400">
          <div>
            <span className="font-medium text-yellow-400">{health.rate_limited_keys}</span>{' '}
            limited
          </div>
          <div>
            <span className="font-medium text-red-400">{health.exhausted_keys}</span>{' '}
            exhausted
          </div>
          <div>
            <span className="font-medium text-slate-500">{health.disabled_keys}</span>{' '}
            disabled
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CriticalAlertBanner({ criticalProviders }: { criticalProviders: string[] }) {
  if (criticalProviders.length === 0) return null;

  const providerNames = criticalProviders
    .map((p) => PROVIDER_LABELS[p] ?? p)
    .join(', ');

  return (
    <div className="flex items-center gap-3 rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3">
      <AlertTriangle className="h-5 w-5 shrink-0 text-red-400" />
      <div>
        <p className="text-sm font-medium text-red-300">
          Critical: No active keys available
        </p>
        <p className="mt-0.5 text-xs text-red-400/80">
          {providerNames} {criticalProviders.length === 1 ? 'has' : 'have'} no active API keys.
          Requests to {criticalProviders.length === 1 ? 'this provider' : 'these providers'} will fail.
        </p>
      </div>
    </div>
  );
}

export function HealthSummary({
  showAllWithKeys = true,
  alwaysIncludeCritical = true,
  /** Merge /health services so providers like CALA still appear when key-pool omits them. */
  apiServices = null,
  /** Stretch cards evenly across the full container width. */
  fillRow = false,
  /** Prefer the compact dashboard provider set (includes CALA). */
  dashboardRow = false,
}: {
  showAllWithKeys?: boolean;
  alwaysIncludeCritical?: boolean;
  apiServices?: Record<string, ServiceHealth | boolean> | null;
  fillRow?: boolean;
  dashboardRow?: boolean;
} = {}) {
  const { data, isLoading, isError } = useAllProvidersHealth();

  const skeletonCount = dashboardRow ? DASHBOARD_ROW_PROVIDERS.length : PROVIDERS.length;

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div
          className={cn(
            'grid gap-3',
            fillRow
              ? 'w-full'
              : 'grid-cols-2 md:grid-cols-4 xl:grid-cols-8',
          )}
          style={
            fillRow
              ? { gridTemplateColumns: `repeat(${skeletonCount}, minmax(0, 1fr))` }
              : undefined
          }
        >
          {Array.from({ length: skeletonCount }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="text-sm text-destructive">Failed to load health overview.</p>
    );
  }

  const providers = data.providers ?? [];

  const baseIds = dashboardRow
    ? [...DASHBOARD_ROW_PROVIDERS]
    : [
        ...PROVIDERS,
        ...providers
          .map((h) => h.provider)
          .filter((id) => !PROVIDERS.includes(id as (typeof PROVIDERS)[number])),
      ];

  // Always include any provider present in API health services (e.g. unhealthy CALA).
  if (apiServices) {
    for (const id of Object.keys(apiServices)) {
      if (!baseIds.includes(id as (typeof baseIds)[number])) {
        baseIds.push(id as (typeof DASHBOARD_ROW_PROVIDERS)[number]);
      }
    }
  }

  const resolved: ProviderHealth[] = [];
  for (const providerId of baseIds) {
    const fromPool = providers.find((h: ProviderHealth) => h.provider === providerId);
    if (fromPool) {
      if (
        fromPool.total_keys > 0 ||
        (alwaysIncludeCritical && fromPool.health_indicator === 'critical') ||
        serviceAvailable(apiServices, providerId) === false
      ) {
        resolved.push(fromPool);
      } else if (showAllWithKeys && fromPool.total_keys > 0) {
        resolved.push(fromPool);
      }
      continue;
    }

    // Not in key-pool response — still show if API health knows about it.
    const available = serviceAvailable(apiServices, providerId);
    if (available === false || (dashboardRow && DASHBOARD_ROW_PROVIDERS.includes(providerId as (typeof DASHBOARD_ROW_PROVIDERS)[number]))) {
      // For dashboard row, always show the six core providers (synthesize if missing).
      if (
        dashboardRow &&
        DASHBOARD_ROW_PROVIDERS.includes(providerId as (typeof DASHBOARD_ROW_PROVIDERS)[number])
      ) {
        resolved.push(fallbackFromApiHealth(providerId, apiServices));
      } else if (available === false) {
        resolved.push(fallbackFromApiHealth(providerId, apiServices));
      }
    }
  }

  // Dashboard: force all six core slots so CALA is never missing.
  const visible = dashboardRow
    ? DASHBOARD_ROW_PROVIDERS.map((id) => {
        const found = resolved.find((h) => h.provider === id);
        return found ?? fallbackFromApiHealth(id, apiServices);
      })
    : resolved.filter((h) => {
        if (alwaysIncludeCritical && h.health_indicator === 'critical') return true;
        if (showAllWithKeys) return h.total_keys > 0 || serviceAvailable(apiServices, h.provider) === false;
        return h.total_keys > 0;
      });

  const criticalProviders = visible
    .filter((h) => h.health_indicator === 'critical')
    .map((h) => h.provider);

  return (
    <div className="space-y-3">
      <CriticalAlertBanner criticalProviders={criticalProviders} />

      {visible.length > 0 ? (
        <div
          className={cn('grid w-full gap-3', !fillRow && 'grid-cols-2 md:grid-cols-4 xl:grid-cols-8')}
          style={
            fillRow
              ? { gridTemplateColumns: `repeat(${visible.length}, minmax(0, 1fr))` }
              : undefined
          }
        >
          {visible.map((health) => (
            <ProviderHealthCard key={health.provider} health={health} />
          ))}
        </div>
      ) : (
        <p className="py-4 text-center text-sm text-slate-400">
          No providers have API keys configured yet.
        </p>
      )}
    </div>
  );
}
