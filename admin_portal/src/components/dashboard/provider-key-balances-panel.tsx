import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { useProviderKeyBalances } from '@/hooks/use-dashboard';
import type { ProviderKeyBalanceItem } from '@/types/provider-balances';
import { cn } from '@/lib/utils';

const PROVIDER_LABELS: Record<string, string> = {
  slai: 'SLAI',
  suno: 'Suno',
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
  fal: 'Fal',
};

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
    return 'text-emerald-400';
  }
  return 'text-slate-500';
}

export function ProviderKeyBalancesPanel() {
  const query = useProviderKeyBalances();
  const rows = (query.data?.providers ?? []).flatMap((group) =>
    group.keys.map((item) => ({
      provider: PROVIDER_LABELS[group.provider] ?? group.provider,
      item,
    })),
  );

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50">
      <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-3 py-2">
        <div className="text-sm font-medium text-slate-200">Key balances</div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-slate-400 hover:text-slate-200"
          disabled={query.isFetching}
          onClick={() => query.refetch()}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', query.isFetching && 'animate-spin')} />
        </Button>
      </div>

      {query.isLoading ? (
        <p className="px-3 py-2 text-xs text-slate-500">Loading…</p>
      ) : query.isError ? (
        <p className="px-3 py-2 text-xs text-red-300">Failed to load</p>
      ) : rows.length === 0 ? (
        <p className="px-3 py-2 text-xs text-slate-500">No keys</p>
      ) : (
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800/80 text-[10px] uppercase tracking-wide text-slate-500">
              <th className="px-3 py-1.5 font-medium">Provider</th>
              <th className="px-3 py-1.5 font-medium">Key</th>
              <th className="px-3 py-1.5 text-right font-medium">Remaining</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ provider, item }) => (
              <tr key={item.key_id} className="border-b border-slate-800/40 last:border-0">
                <td className="whitespace-nowrap px-3 py-1.5 text-slate-400">{provider}</td>
                <td className="max-w-[14rem] truncate px-3 py-1.5 text-slate-200" title={item.label}>
                  {item.label}
                </td>
                <td className={cn('whitespace-nowrap px-3 py-1.5 text-right font-medium tabular-nums', balanceClass(item))}>
                  {balanceText(item)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
