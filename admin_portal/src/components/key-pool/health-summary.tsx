import { AlertTriangle } from 'lucide-react';

import { useAllProvidersHealth } from '@/hooks/use-key-pool';
import type { ProviderHealth, HealthIndicator } from '@/types/key-pool';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

const PROVIDERS = ['suno', 'fal', 'openai', 'slai', 'youtube', 'facebook'] as const;

const PROVIDER_LABELS: Record<string, string> = {
  suno: 'Suno',
  fal: 'FAL',
  openai: 'OpenAI',
  slai: 'Slai',
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

interface ProviderHealthCardProps {
  health: ProviderHealth;
}

function ProviderHealthCard({ health }: ProviderHealthCardProps) {
  return (
    <Card className={`bg-navy-900 ${getHealthBorderColor(health.health_indicator)}`}>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-200">
            {PROVIDER_LABELS[health.provider] ?? health.provider}
          </p>
          <Badge className={`text-[10px] ${getHealthBadgeStyles(health.health_indicator)}`}>
            {health.health_indicator}
          </Badge>
        </div>

        <p className="text-lg font-semibold text-white">
          {health.active_keys}/{health.total_keys}{' '}
          <span className="text-xs font-normal text-slate-400">active</span>
        </p>

        <div className="grid grid-cols-3 gap-1 text-[11px] text-slate-400">
          <div>
            <span className="text-yellow-400 font-medium">{health.rate_limited_keys}</span>{' '}
            limited
          </div>
          <div>
            <span className="text-red-400 font-medium">{health.exhausted_keys}</span>{' '}
            exhausted
          </div>
          <div>
            <span className="text-slate-500 font-medium">{health.disabled_keys}</span>{' '}
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
        <p className="text-xs text-red-400/80 mt-0.5">
          {providerNames} {criticalProviders.length === 1 ? 'has' : 'have'} no active API keys.
          Requests to {criticalProviders.length === 1 ? 'this provider' : 'these providers'} will fail.
        </p>
      </div>
    </div>
  );
}

export function HealthSummary() {
  const { data, isLoading, isError } = useAllProvidersHealth();

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {PROVIDERS.map((p) => (
            <Skeleton key={p} className="h-28 w-full" />
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

  // Only show cards for providers that have entries (total_keys > 0)
  const providersWithEntries = PROVIDERS.filter((providerId) => {
    const health = providers.find((h: ProviderHealth) => h.provider === providerId);
    return health && health.total_keys > 0;
  });

  // Identify critical providers (have entries but zero active keys)
  const criticalProviders = providers
    .filter((h: ProviderHealth) => h.health_indicator === 'critical' && h.total_keys > 0)
    .map((h: ProviderHealth) => h.provider);

  return (
    <div className="space-y-3">
      <CriticalAlertBanner criticalProviders={criticalProviders} />

      {providersWithEntries.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {providersWithEntries.map((providerId) => {
            const health = providers.find((h: ProviderHealth) => h.provider === providerId);
            if (!health) return null;
            return <ProviderHealthCard key={providerId} health={health} />;
          })}
        </div>
      ) : (
        <p className="text-sm text-slate-400 text-center py-4">
          No providers have API keys configured yet.
        </p>
      )}
    </div>
  );
}
