import { useState } from 'react';

import { useAllProvidersHealth } from '@/hooks/use-key-pool';
import { ProviderTab } from '@/components/key-pool/provider-tab';
import type { ProviderHealth } from '@/types/key-pool';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

const PROVIDERS = ['suno', 'fal', 'openai', 'deepseek', 'slai', 'youtube', 'facebook'] as const;
type Provider = (typeof PROVIDERS)[number];

const PROVIDER_LABELS: Record<Provider, string> = {
  suno: 'Suno',
  fal: 'FAL',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  slai: 'Slai',
  youtube: 'YouTube',
  facebook: 'Facebook',
};

// --- Health Helpers ---

function getHealthColor(indicator: string): string {
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

// --- Health Summary ---

function HealthSummary() {
  const { data, isLoading, isError } = useAllProvidersHealth();

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {PROVIDERS.map((p) => (
          <Skeleton key={p} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-md border border-yellow-500/30 bg-yellow-500/5 px-4 py-3">
        <p className="text-sm text-yellow-400">
          Key pool service unavailable. Ensure PLATFORM_ENCRYPTION_MASTER_KEY is set and the database migration has been run.
        </p>
      </div>
    );
  }

  const providers = data.providers ?? [];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {PROVIDERS.map((providerId) => {
        const health = providers.find((h: ProviderHealth) => h.provider === providerId);
        if (!health) {
          return (
            <Card key={providerId} className="bg-navy-900 border-navy-700">
              <CardContent className="p-3 text-center">
                <p className="text-xs text-slate-400 font-medium">{PROVIDER_LABELS[providerId]}</p>
                <p className="text-xs text-slate-500 mt-1">No data</p>
              </CardContent>
            </Card>
          );
        }
        return (
          <Card key={providerId} className="bg-navy-900 border-navy-700">
            <CardContent className="p-3 text-center">
              <p className="text-xs text-slate-400 font-medium">{PROVIDER_LABELS[providerId]}</p>
              <Badge className={`mt-1 text-[10px] ${getHealthColor(health.health_indicator)}`}>
                {health.health_indicator}
              </Badge>
              <p className="text-xs text-slate-300 mt-1">
                {health.active_keys}/{health.total_keys} active
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// --- Page ---

export default function KeyPoolPage() {
  const [activeTab, setActiveTab] = useState<string>(PROVIDERS[0]);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">API Key Pool</h1>
        <p className="text-sm text-slate-400 mt-1">
          Manage API keys across providers with automatic failover and load balancing.
        </p>
      </div>

      <HealthSummary />

      <Card className="bg-navy-900 border-navy-700">
        <CardHeader>
          <CardTitle className="text-lg text-white">Keys by Provider</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-navy-800 border border-navy-700">
              {PROVIDERS.map((provider) => (
                <TabsTrigger
                  key={provider}
                  value={provider}
                  className="data-[state=active]:bg-navy-600 data-[state=active]:text-white text-slate-400"
                >
                  {PROVIDER_LABELS[provider]}
                </TabsTrigger>
              ))}
            </TabsList>
            {PROVIDERS.map((provider) => (
              <TabsContent key={provider} value={provider}>
                <ProviderTab provider={provider} />
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
