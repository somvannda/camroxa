import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useProviderConfig, useUpdateProviderConfig } from '@/hooks/use-key-pool';
import { UPSTREAM_HOST_PRESETS } from '@/types/key-pool';
import type { SelectionStrategy } from '@/types/key-pool';

interface ProviderSettingsProps {
  provider: string;
}

export function ProviderSettings({ provider }: ProviderSettingsProps) {
  const { data: config, isLoading } = useProviderConfig(provider);
  const updateConfig = useUpdateProviderConfig(provider);

  const [strategy, setStrategy] = useState<SelectionStrategy>('priority');
  const [cooldown, setCooldown] = useState<number>(60);
  const [baseUrl, setBaseUrl] = useState<string>('');

  // Sync local state when config loads or changes
  useEffect(() => {
    if (config) {
      setStrategy(config.selection_strategy);
      setCooldown(config.cooldown_seconds);
      setBaseUrl(config.base_url ?? '');
    }
  }, [config]);

  const trimmedBaseUrl = baseUrl.trim();

  const handleSave = () => {
    updateConfig.mutate({
      selection_strategy: strategy,
      cooldown_seconds: cooldown,
      base_url: trimmedBaseUrl || null,
      clear_base_url: !trimmedBaseUrl,
    });
  };

  const hasChanges =
    config &&
    (strategy !== config.selection_strategy ||
      cooldown !== config.cooldown_seconds ||
      trimmedBaseUrl !== (config.base_url ?? ''));

  if (isLoading) {
    return (
      <div className="rounded-md border border-navy-700 bg-navy-900/50 p-4">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading settings...
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-navy-700 bg-navy-900/50 p-4">
      <h4 className="mb-4 text-sm font-medium text-white">Provider Settings</h4>

      <div className="grid grid-cols-2 gap-4">
        {/* Selection Strategy */}
        <div className="space-y-2">
          <Label htmlFor={`strategy-${provider}`} className="text-xs text-slate-400">
            Selection Strategy
          </Label>
          <Select value={strategy} onValueChange={(v) => setStrategy(v as SelectionStrategy)}>
            <SelectTrigger
              id={`strategy-${provider}`}
              className="w-full bg-navy-900 border-navy-700 text-white"
            >
              <SelectValue placeholder="Select strategy" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="round_robin">Round Robin</SelectItem>
              <SelectItem value="priority">Priority</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Cooldown Period */}
        <div className="space-y-2">
          <Label htmlFor={`cooldown-${provider}`} className="text-xs text-slate-400">
            Cooldown Period (seconds)
          </Label>
          <Input
            id={`cooldown-${provider}`}
            type="number"
            min={10}
            max={3600}
            step={10}
            value={cooldown}
            onChange={(e) => setCooldown(Number(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      {/* Active upstream host (provider switching / rollback) */}
      <div className="mt-4 space-y-2">
        <Label htmlFor={`base-url-${provider}`} className="text-xs text-slate-400">
          Active Upstream Host
        </Label>
        <Input
          id={`base-url-${provider}`}
          list={`base-url-presets-${provider}`}
          placeholder="Default (PLATFORM_SUNO_API_BASE_URL)"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          className="w-full"
        />
        <datalist id={`base-url-presets-${provider}`}>
          {UPSTREAM_HOST_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </datalist>
        <div className="flex flex-wrap gap-2">
          {UPSTREAM_HOST_PRESETS.map((preset) => (
            <Button
              key={preset.value}
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setBaseUrl(preset.value)}
            >
              {preset.label}
            </Button>
          ))}
          <Button type="button" size="sm" variant="ghost" onClick={() => setBaseUrl('')}>
            Use default
          </Button>
        </div>
        <p className="text-xs text-slate-500">
          Only keys tagged with this host are used. Leave blank to use the environment
          default and every key.
        </p>
      </div>

      {/* Save button */}
      <div className="mt-4 flex justify-end">
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!hasChanges || updateConfig.isPending}
        >
          {updateConfig.isPending && (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          )}
          Save Settings
        </Button>
      </div>
    </div>
  );
}
