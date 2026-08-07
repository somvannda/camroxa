import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import {
  useForceRefreshProviderKeyBalances,
  useProviderKeyBalances,
} from '@/hooks/use-dashboard';
import type { ProviderKeyBalanceItem } from '@/types/provider-balances';
import { cn } from '@/lib/utils';

const PROVIDER_LABELS: Record<string, string> = {
  slai: 'SLAI',
  suno: 'Suno',
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
  fal: 'Fal',
  cala: 'CALA',
};

const PROVIDER_ORDER = ['suno', 'slai', 'fal', 'openai', 'deepseek', 'cala'] as const;

function balanceText(item: ProviderKeyBalanceItem): string {
  if (item.fetch_status === 'ok' || item.fetch_status === 'cached') {
    return item.display ?? '—';
  }
  if (item.fetch_status === 'unsupported') return 'N/A';
  return '—';
}

function balanceClass(item: ProviderKeyBalanceItem): string {
  if (
    (item.fetch_status === 'ok' || item.fetch_status === 'cached') &&
    typeof item.balance === 'number' &&
    item.balance <= 0
  ) {
    return 'text-red-400';
  }
  if (item.fetch_status === 'ok' || item.fetch_status === 'cached') {
    return 'text-emerald-300';
  }
  return 'text-slate-500';
}

/** True when at least one key has a numeric balance we can show. */
function hasReadableBalance(keys: ProviderKeyBalanceItem[]): boolean {
  return keys.some(
    (k) =>
      (k.fetch_status === 'ok' || k.fetch_status === 'cached') &&
      typeof k.balance === 'number',
  );
}

function formatTotal(
  keys: ProviderKeyBalanceItem[],
): { text: string; tone: 'ok' | 'low' | 'muted'; remainingLabel: string } {
  const numeric = keys.filter(
    (k) =>
      (k.fetch_status === 'ok' || k.fetch_status === 'cached') &&
      typeof k.balance === 'number',
  );
  if (numeric.length === 0) {
    return { text: '—', tone: 'muted', remainingLabel: 'Remaining' };
  }

  const units = new Set(
    numeric.map((k) => {
      if (k.unit === 'usd' || k.currency === 'USD') return 'usd';
      return 'credits';
    }),
  );

  if (units.size > 1) {
    return {
      text: `${numeric.length}`,
      tone: 'muted',
      remainingLabel: 'Keys (mixed units)',
    };
  }

  const unit = [...units][0];
  const total = numeric.reduce((sum, k) => sum + (k.balance as number), 0);
  const low = total <= 0;
  if (unit === 'usd') {
    return {
      text: `$${total.toLocaleString(undefined, { maximumFractionDigits: 4 })}`,
      tone: low ? 'low' : 'ok',
      remainingLabel: 'Remaining',
    };
  }
  return {
    text: total.toLocaleString(undefined, { maximumFractionDigits: 2 }),
    tone: low ? 'low' : 'ok',
    remainingLabel: 'Remaining',
  };
}

type CompactProviderCardProps = {
  title: string;
  keyCountLabel: string;
  totalText: string;
  totalTone: 'ok' | 'low' | 'muted';
  remainingLabel: string;
  error?: string | null;
  rows: Array<{ id: string; label: string; value: string; valueClass: string }>;
};

function CompactProviderCard({
  title,
  keyCountLabel,
  totalText,
  totalTone,
  remainingLabel,
  error,
  rows,
}: CompactProviderCardProps) {
  const manyKeys = rows.length > 4;

  return (
    <div
      className={cn(
        'rounded-xl border bg-slate-900/55 px-3 py-2.5',
        totalTone === 'low' ? 'border-red-500/35' : 'border-slate-800',
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 truncate text-sm font-semibold text-slate-100">
          {title}{' '}
          <span className="font-normal text-slate-500">({keyCountLabel})</span>
        </div>
        <div
          className={cn(
            'shrink-0 text-lg font-semibold tabular-nums leading-none',
            totalTone === 'ok' && 'text-emerald-300',
            totalTone === 'low' && 'text-red-400',
            totalTone === 'muted' && 'text-slate-400',
          )}
        >
          {totalText}
        </div>
      </div>

      <div className="mt-0.5 flex items-center justify-between gap-2">
        <div className="min-w-0">
          {error ? (
            <span className="truncate text-[10px] text-amber-400">{error}</span>
          ) : null}
        </div>
        <div className="shrink-0 text-[10px] uppercase tracking-wide text-slate-500">
          {remainingLabel}
        </div>
      </div>

      {rows.length > 0 ? (
        <div
          className={cn(
            'mt-2 border-t border-white/5 pt-1.5',
            manyKeys ? 'grid grid-cols-2 gap-x-4 gap-y-0.5' : 'space-y-0.5',
          )}
        >
          {rows.map((row) => (
            <div key={row.id} className="flex items-baseline justify-between gap-2 py-0.5">
              <span className="min-w-0 truncate text-xs text-slate-400" title={row.label}>
                {row.label}
              </span>
              <span className={cn('shrink-0 text-xs font-medium tabular-nums', row.valueClass)}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

type ProviderKeyBalancesPanelProps = {
  className?: string;
};

export function ProviderKeyBalancesPanel({ className }: ProviderKeyBalancesPanelProps) {
  const query = useProviderKeyBalances();
  const forceRefresh = useForceRefreshProviderKeyBalances();
  const refreshing = query.isFetching || forceRefresh.isPending;

  // Hide providers with no readable remaining balance (e.g. OpenAI N/A).
  const groups = [...(query.data?.providers ?? [])]
    .filter((group) => hasReadableBalance(group.keys))
    .sort((a, b) => {
      const ai = PROVIDER_ORDER.indexOf(a.provider as (typeof PROVIDER_ORDER)[number]);
      const bi = PROVIDER_ORDER.indexOf(b.provider as (typeof PROVIDER_ORDER)[number]);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });

  return (
    <section className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Credits remaining</h2>
          <p className="text-sm text-slate-400">Provider totals and each key balance</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-slate-400 hover:text-slate-200"
          disabled={refreshing}
          onClick={() => forceRefresh.mutate()}
          title="Force refresh provider balances"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          <span className="ml-1.5 text-xs">Refresh</span>
        </Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-slate-500">Loading balances…</p>
      ) : query.isError ? (
        <p className="text-sm text-red-300">Failed to load balances</p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-slate-500">No readable provider balances</p>
      ) : (
        <div
          className="grid w-full gap-2"
          style={{ gridTemplateColumns: `repeat(${groups.length}, minmax(0, 1fr))` }}
        >
          {groups.map((group) => {
            const label = PROVIDER_LABELS[group.provider] ?? group.provider;
            const total = formatTotal(group.keys);
            const keyCount = group.keys.length;
            return (
              <CompactProviderCard
                key={group.provider}
                title={label}
                keyCountLabel={`${keyCount} key${keyCount === 1 ? '' : 's'}`}
                totalText={total.text}
                totalTone={total.tone}
                remainingLabel={total.remainingLabel}
                error={group.error}
                rows={group.keys.map((item) => ({
                  id: item.key_id,
                  label: item.label,
                  value: balanceText(item),
                  valueClass: balanceClass(item),
                }))}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
