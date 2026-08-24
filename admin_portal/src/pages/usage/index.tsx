import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  Coins,
  Info,
  RefreshCw,
  RotateCcw,
  Search,
} from 'lucide-react';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { DateRangePicker, type DateRangeValue } from '@/components/shared/date-range-picker';
import { ErrorState } from '@/components/shared/error-state';
import { StatCard } from '@/components/shared/stat-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUsage, useUsageFilters, useExportTelemetry } from '@/hooks/use-usage';
import type { UsageListParams } from '@/types/api';
import type { UsageEntry } from '@/types/models';
import { formatAdminDateTime } from '@/lib/format-datetime';
import {
  formatCredits,
  formatOperationLabel,
  formatProviderLabel,
  formatUsageCostLabel,
  truncateId,
} from '@/lib/usage-labels';

const PAGE_SIZE = 50;

interface UsageFiltersState {
  userId: string;
  provider: string;
  operation: string;
  direction: string;
  reason: string;
  dateRange: DateRangeValue;
}

const EMPTY_FILTERS: UsageFiltersState = {
  userId: '',
  provider: 'all',
  operation: 'all',
  direction: 'all',
  reason: '',
  dateRange: {},
};

function directionBadge(direction: string) {
  if (direction === 'debit') {
    return (
      <Badge className="border-transparent bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/15">
        billed
      </Badge>
    );
  }
  if (direction === 'refund') {
    return (
      <Badge className="border-transparent bg-amber-500/15 text-amber-300 hover:bg-amber-500/15">
        refunded
      </Badge>
    );
  }
  return (
    <Badge className="border-transparent bg-blue-500/15 text-blue-300 hover:bg-blue-500/15">
      credit
    </Badge>
  );
}

function amountCell(row: UsageEntry) {
  const billing = row.billing ?? (row.metadata && typeof row.metadata.billing === 'string'
    ? row.metadata.billing
    : null);
  const isPlan = billing === 'plan_allowance' || billing === 'plan_included';
  const isDebit = row.direction === 'debit' && !isPlan;
  const isRefund = row.direction === 'refund';
  const color = isPlan
    ? 'text-sky-300'
    : isDebit
      ? 'text-red-300'
      : isRefund
        ? 'text-amber-300'
        : 'text-emerald-300';
  return (
    <span className={`font-mono text-sm ${color}`} title={formatUsageCostLabel(row)}>
      {formatUsageCostLabel(row)}
    </span>
  );
}

function providerModelCell(row: UsageEntry) {
  const meta = row.metadata ?? {};
  const routed =
    typeof meta.routed_provider === 'string' ? meta.routed_provider : null;
  const executed =
    typeof meta.executed_provider === 'string' ? meta.executed_provider : null;
  const showRouteSplit =
    Boolean(routed && executed && routed !== executed) ||
    Boolean(routed && !executed);

  return (
    <div className="space-y-1">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-slate-600">Provider</div>
        <div className="font-medium text-slate-200">
          {formatProviderLabel(row.provider) === 'All providers'
            ? '—'
            : formatProviderLabel(row.provider)}
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-wide text-slate-600">Model</div>
        <div className="font-mono text-xs text-slate-500">{row.model || '—'}</div>
      </div>
      {showRouteSplit ? (
        <div className="text-[10px] text-slate-600">
          routed {routed || '—'}
          {executed ? ` · ran ${executed}` : ' · not executed'}
        </div>
      ) : null}
      {row.legacy ? (
        <div className="text-[10px] uppercase tracking-wide text-slate-600">legacy estimate</div>
      ) : null}
    </div>
  );
}

function traceCell(row: UsageEntry) {
  if (!row.batch_id && !row.song_id && !row.ref_id) {
    return <span className="text-slate-500">—</span>;
  }

  return (
    <div className="min-w-[120px] space-y-1 text-xs">
      {row.batch_id ? (
        <div>
          <Link to={`/batches/${row.batch_id}`} className="font-mono text-blue-400 hover:underline">
            batch {truncateId(row.batch_id, 8)}
          </Link>
        </div>
      ) : null}
      {(row.song_id || row.ref_id) ? (
        <div>
          <Link
            to={`/songs/${row.song_id || row.ref_id}`}
            className="font-mono text-blue-400 hover:underline"
          >
            song {truncateId(row.song_id || row.ref_id || '', 8)}
          </Link>
          {row.batch_index != null ? (
            <span className="ml-2 text-slate-500">#{row.batch_index + 1}</span>
          ) : null}
        </div>
      ) : null}
      {row.attempts_used != null && row.attempts_used > 1 ? (
        <div className="text-amber-400/90">{row.attempts_used} lyric attempts</div>
      ) : null}
      {(row.llm_calls_title ?? 0) + (row.llm_calls_album ?? 0) + (row.llm_calls_lyric ?? 0) >
      0 ? (
        <div className="text-slate-500">
          LLM{' '}
          {(row.llm_calls_title ?? 0) +
            (row.llm_calls_album ?? 0) +
            (row.llm_calls_lyric ?? 0)}{' '}
          <span className="text-slate-600">
            (T{row.llm_calls_title ?? 0}/A{row.llm_calls_album ?? 0}/L{row.llm_calls_lyric ?? 0})
          </span>
        </div>
      ) : null}
    </div>
  );
}

function UsageDetailDialog({
  entry,
  open,
  onOpenChange,
}: {
  entry: UsageEntry | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!entry) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl border-slate-800 bg-slate-950 text-slate-100">
        <DialogHeader>
          <DialogTitle>Usage event</DialogTitle>
          <DialogDescription className="text-slate-400">{entry.purpose}</DialogDescription>
        </DialogHeader>

        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-slate-500">User</dt>
            <dd className="mt-1">
              <Link to={`/users/${entry.user_id}`} className="text-blue-400 hover:underline">
                {entry.user_display_name || entry.user_email}
              </Link>
              <div className="text-xs text-slate-500">{entry.user_email}</div>
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Time</dt>
            <dd className="mt-1">{formatAdminDateTime(entry.created_at)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Provider</dt>
            <dd className="mt-1">{entry.provider || '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Model</dt>
            <dd className="mt-1 font-mono text-xs">{entry.model || '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Operation</dt>
            <dd className="mt-1">{formatOperationLabel(entry.operation)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Cost</dt>
            <dd className="mt-1">{amountCell(entry)}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-slate-500">Event ID</dt>
            <dd className="mt-1 break-all font-mono text-xs text-slate-400">{entry.id}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-slate-500">Reference</dt>
            <dd className="mt-1 break-all font-mono text-xs text-slate-400">{entry.ref_id || '—'}</dd>
          </div>
          {entry.batch_id ? (
            <div>
              <dt className="text-slate-500">Batch</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                <Link to={`/batches/${entry.batch_id}`} className="text-blue-400 hover:underline">
                  {entry.batch_id}
                </Link>
              </dd>
            </div>
          ) : null}
          {entry.song_id ? (
            <div>
              <dt className="text-slate-500">Song</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                <Link to={`/songs/${entry.song_id}`} className="text-blue-400 hover:underline">
                  {entry.song_id}
                </Link>
              </dd>
            </div>
          ) : entry.ref_id ? (
            <div>
              <dt className="text-slate-500">Song / ref</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                <Link to={`/songs/${entry.ref_id}`} className="text-blue-400 hover:underline">
                  {entry.ref_id}
                </Link>
              </dd>
            </div>
          ) : null}
          {entry.batch_index != null ? (
            <div>
              <dt className="text-slate-500">Batch index</dt>
              <dd className="mt-1">{entry.batch_index + 1}</dd>
            </div>
          ) : null}
          {entry.attempts_used != null ? (
            <div>
              <dt className="text-slate-500">Draft attempts</dt>
              <dd className="mt-1">
                {entry.attempts_used}
                {entry.attempts_used > 1 ? (
                  <span className="ml-2 text-xs text-amber-400/90">retries without extra charge</span>
                ) : null}
              </dd>
            </div>
          ) : null}
          {entry.llm_calls_title != null ||
          entry.llm_calls_album != null ||
          entry.llm_calls_lyric != null ? (
            <div className="col-span-2">
              <dt className="text-slate-500">Internal LLM calls</dt>
              <dd className="mt-2">
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Title</div>
                    <div className="mt-1 font-mono text-sm text-slate-200">
                      {entry.llm_calls_title ?? 0}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Album</div>
                    <div className="mt-1 font-mono text-sm text-slate-200">
                      {entry.llm_calls_album ?? 0}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Lyrics</div>
                    <div className="mt-1 font-mono text-sm text-slate-200">
                      {entry.llm_calls_lyric ?? 0}
                    </div>
                  </div>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Actual provider calls during draft generation. User is billed once per song;
                  extra calls are internal retry cost.
                </p>
              </dd>
            </div>
          ) : null}
        </dl>

        {entry.line_items.length > 0 ? (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-slate-200">Cost breakdown</h3>
            <div className="overflow-hidden rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/80 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Slot</th>
                    <th className="px-4 py-3 text-left font-medium">Provider</th>
                    <th className="px-4 py-3 text-left font-medium">Model</th>
                    <th className="px-4 py-3 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {entry.line_items.map((item, index) => (
                    <tr key={`${item.operation}-${index}`} className="border-t border-slate-800/80">
                      <td className="px-4 py-3 text-slate-200">{formatOperationLabel(item.operation)}</td>
                      <td className="px-4 py-3 text-slate-300">{item.provider || '—'}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{item.model || '—'}</td>
                      <td className="px-4 py-3 text-right font-mono text-red-300">
                        {item.amount != null ? `−${formatCredits(item.amount)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function filtersToParams(filters: UsageFiltersState, page: number): UsageListParams {
  return {
    page,
    page_size: PAGE_SIZE,
    ...(filters.userId && { user_id: filters.userId }),
    ...(filters.provider !== 'all' && { provider: filters.provider }),
    ...(filters.operation !== 'all' && { operation: filters.operation }),
    ...(filters.direction !== 'all' && { direction: filters.direction }),
    ...(filters.reason && { reason: filters.reason }),
    ...(filters.dateRange.from && { from_date: filters.dateRange.from }),
    ...(filters.dateRange.to && { to_date: `${filters.dateRange.to}T23:59:59` }),
  };
}

export default function UsagePage() {
  const [searchParams] = useSearchParams();
  const initialUserId = searchParams.get('user_id') || '';

  const [page, setPage] = React.useState(1);
  const [draftFilters, setDraftFilters] = React.useState<UsageFiltersState>({
    ...EMPTY_FILTERS,
    userId: initialUserId,
  });
  const [appliedFilters, setAppliedFilters] = React.useState<UsageFiltersState>({
    ...EMPTY_FILTERS,
    userId: initialUserId,
  });
  const [selectedEntry, setSelectedEntry] = React.useState<UsageEntry | null>(null);

  const params = React.useMemo(
    () => filtersToParams(appliedFilters, page),
    [appliedFilters, page],
  );

  const { data, isLoading, isError, error, refetch, isFetching } = useUsage(params);
  const filtersQuery = useUsageFilters();
  const exportTelemetry = useExportTelemetry(
    appliedFilters.userId ? { user_id: appliedFilters.userId } : undefined,
  );

  const providerOptions = filtersQuery.data?.providers ?? [];
  const operationOptions = filtersQuery.data?.operations ?? [];

  const applyFilters = () => {
    setPage(1);
    setAppliedFilters(draftFilters);
  };

  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const columns: ColumnDef<UsageEntry>[] = [
    {
      id: 'created_at',
      header: 'Time',
      accessorFn: (row) => (
        <div className="whitespace-nowrap text-sm text-slate-300">
          {formatAdminDateTime(row.created_at)}
        </div>
      ),
    },
    {
      id: 'user',
      header: 'User',
      accessorFn: (row) => (
        <div className="min-w-[160px]">
          <Link to={`/users/${row.user_id}`} className="font-medium text-blue-400 hover:underline">
            {row.user_display_name || row.user_email}
          </Link>
          <div className="text-xs text-slate-500">{row.user_email}</div>
        </div>
      ),
    },
    {
      id: 'purpose',
      header: 'Purpose',
      accessorFn: (row) => (
        <div className="max-w-xs">
          <div className="font-medium text-slate-100">{row.purpose}</div>
          {row.line_items_summary ? (
            <div className="mt-1 text-xs leading-relaxed text-slate-500">{row.line_items_summary}</div>
          ) : null}
        </div>
      ),
    },
    {
      id: 'provider_model',
      header: 'Provider / Model',
      accessorFn: (row) => providerModelCell(row),
    },
    {
      id: 'trace',
      header: 'Trace',
      accessorFn: (row) => traceCell(row),
    },
    {
      id: 'amount',
      header: 'Cost',
      accessorFn: (row) => amountCell(row),
    },
    {
      id: 'direction',
      header: 'Status',
      accessorFn: (row) => directionBadge(row.direction),
    },
    {
      id: 'event_id',
      header: 'Event ID',
      accessorFn: (row) => (
        <span className="font-mono text-xs text-slate-500" title={row.id}>
          {truncateId(row.id, 12)}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      accessorFn: (row) => (
        <Button
          variant="ghost"
          size="sm"
          className="text-blue-400 hover:bg-slate-800 hover:text-blue-300"
          onClick={() => setSelectedEntry(row)}
        >
          View details
        </Button>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load usage'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const summary = data?.summary;

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.08),transparent_35%),linear-gradient(180deg,#020617_0%,#030712_100%)] p-8">
      <div className="mx-auto max-w-[1400px] space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-blue-400/80">
              Usage
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
              Credit usage & transactions
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
              Ledger of wallet events: charges, refunds, period/daily grants, packs,
              web leftover, admin adjust, and absorb. Historical plan_allowance stays
              labeled. Grant issued on Finance is period/daily only.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              asChild
            >
              <Link to="/finance">Open finance</Link>
            </Button>
            <Button
              variant="outline"
              className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-4 text-sm text-slate-300">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" />
            <div>
              <div className="font-medium text-slate-100">Billing notes</div>
              <p className="mt-1 text-slate-400">
                Credits-only v3 generate rows are wallet charges (
                <span className="font-mono text-slate-300">v3_music</span> / lyric / style).
                Historical <span className="font-mono text-slate-300">plan_allowance</span> rows
                stay labeled and are not rewritten as wallet debits. Period and daily grants are
                on{' '}
                <Link to="/finance" className="text-blue-300 hover:underline">
                  Finance
                </Link>
                .
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-5 shadow-xl shadow-black/20">
          <div className="mb-1 text-sm font-medium text-slate-200">Desktop export timing</div>
          <p className="mb-4 text-xs text-slate-500">
            Studio = Progress/pipeline exports · Manual = Video-page Manual Export. Duration and
            encoder hints help compare hardware.
            {appliedFilters.userId ? ' Filtered to the selected user.' : ''}
          </p>
          {exportTelemetry.isError ? (
            <div className="text-sm text-rose-300">
              {(exportTelemetry.error as Error)?.message ?? 'Failed to load export telemetry'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                    <th className="pb-2 font-medium">When</th>
                    <th className="pb-2 font-medium">User</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium">Tracks</th>
                    <th className="pb-2 font-medium">Duration</th>
                    <th className="pb-2 font-medium">Codec / HW</th>
                    <th className="pb-2 font-medium">Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {(exportTelemetry.data?.items ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-6 text-slate-500">
                        {exportTelemetry.isLoading
                          ? 'Loading…'
                          : 'No export telemetry yet. Runs after desktop posts duration.'}
                      </td>
                    </tr>
                  ) : (
                    (exportTelemetry.data?.items ?? []).map((row) => (
                      <tr key={row.id} className="border-b border-slate-900/80 text-slate-300">
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {row.created_at ? formatAdminDateTime(row.created_at) : '—'}
                        </td>
                        <td className="py-2 pr-3">
                          <Link
                            to={`/users/${row.user_id}`}
                            className="text-blue-400 hover:underline"
                          >
                            {row.user_email || truncateId(row.user_id, 10)}
                          </Link>
                        </td>
                        <td className="py-2 pr-3">
                          {formatOperationLabel(row.operation_type)}
                        </td>
                        <td className="py-2 pr-3">
                          {row.completed_count}/{row.track_count}
                        </td>
                        <td className="py-2 pr-3">
                          {row.duration_ms != null
                            ? `${(row.duration_ms / 1000).toFixed(1)}s`
                            : '—'}
                        </td>
                        <td className="py-2 pr-3">
                          <div>{row.codec || '—'}</div>
                          <div className="text-xs text-slate-500">
                            {[row.hw_encoder, row.hw_gpu, row.resolution].filter(Boolean).join(' · ') ||
                              '—'}
                          </div>
                        </td>
                        <td className="py-2">
                          {[row.export_tier, row.speed_mode].filter(Boolean).join(' / ') || '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <StatCard
            label="Billable events"
            value={summary?.billable_events ?? '—'}
            icon={Activity}
          />
          <StatCard
            label="Wallet charged"
            value={summary ? formatCredits(summary.wallet_charged ?? 0) : '—'}
            tone="danger"
            icon={Coins}
            hint="Actual wallet debits"
          />
          <StatCard
            label="Grant issued"
            value={summary ? formatCredits(summary.grant_issued ?? 0) : '—'}
            icon={Coins}
            hint={`${summary?.grant_issued_events ?? 0} period/daily grants`}
          />
          <StatCard
            label="Historical plan allowance (list)"
            value={summary ? formatCredits(summary.plan_included_list ?? 0) : '—'}
            icon={Activity}
            hint={`${summary?.plan_allowance_events ?? 0} plan_allowance rows (not wallet)`}
          />
          <StatCard
            label="Refunds"
            value={summary ? formatCredits(summary.refund_total) : '—'}
            hint={`${summary?.refund_events ?? 0} events`}
            tone="warning"
            icon={RotateCcw}
          />
          <StatCard
            label="Net wallet cost"
            value={summary ? formatCredits(summary.net_credit_cost) : '—'}
            icon={AlertCircle}
          />
        </div>

        {(summary?.by_operation?.length ?? 0) > 0 ? (
          <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-5 shadow-xl shadow-black/20">
            <div className="mb-3 text-sm font-medium text-slate-200">By operation type</div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                    <th className="pb-2 font-medium">Operation</th>
                    <th className="pb-2 font-medium">Provider / Model</th>
                    <th className="pb-2 font-medium">Events</th>
                    <th className="pb-2 font-medium">Wallet charged</th>
                    <th className="pb-2 font-medium">Historical allowance (list)</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.by_operation?.map((row) => (
                    <tr
                      key={`${row.operation}|${row.provider ?? ''}|${row.model ?? ''}`}
                      className="border-b border-slate-900/80 text-slate-300"
                    >
                      <td className="py-2.5 pr-4 font-medium text-slate-200">
                        {formatOperationLabel(row.operation)}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-sm text-slate-400">
                        {row.provider || row.model
                          ? `${row.provider || '—'}${row.model ? ` / ${row.model}` : ''}`
                          : '—'}
                      </td>
                      <td className="py-2.5 pr-4 font-mono">{row.events}</td>
                      <td className="py-2.5 pr-4 font-mono text-red-300/90">
                        {formatCredits(row.wallet_charged)}
                      </td>
                      <td className="py-2.5 font-mono text-sky-300/90">
                        {formatCredits(row.plan_included_list)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-5 shadow-xl shadow-black/20">
          <div className="mb-4 text-sm font-medium text-slate-200">Filters</div>
          <div className="grid gap-3 xl:grid-cols-6">
            <Input
              placeholder="User ID"
              value={draftFilters.userId}
              onChange={(e) => setDraftFilters((prev) => ({ ...prev, userId: e.target.value }))}
              className="border-slate-700/80 bg-slate-900/70 text-slate-100 xl:col-span-2"
            />
            <Select
              value={draftFilters.provider}
              onValueChange={(value) => setDraftFilters((prev) => ({ ...prev, provider: value }))}
            >
              <SelectTrigger className="border-slate-700/80 bg-slate-900/70 text-slate-100">
                <SelectValue placeholder="Provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All providers</SelectItem>
                {providerOptions.map((provider) => (
                  <SelectItem key={provider} value={provider}>
                    {formatProviderLabel(provider)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={draftFilters.operation}
              onValueChange={(value) => setDraftFilters((prev) => ({ ...prev, operation: value }))}
            >
              <SelectTrigger className="border-slate-700/80 bg-slate-900/70 text-slate-100">
                <SelectValue placeholder="Operation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All operations</SelectItem>
                {operationOptions.map((operation) => (
                  <SelectItem key={operation} value={operation}>
                    {formatOperationLabel(operation)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={draftFilters.direction}
              onValueChange={(value) => setDraftFilters((prev) => ({ ...prev, direction: value }))}
            >
              <SelectTrigger className="border-slate-700/80 bg-slate-900/70 text-slate-100">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="debit">Billed</SelectItem>
                <SelectItem value="refund">Refunded</SelectItem>
                <SelectItem value="credit">Credit</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Reason contains"
              value={draftFilters.reason}
              onChange={(e) => setDraftFilters((prev) => ({ ...prev, reason: e.target.value }))}
              className="border-slate-700/80 bg-slate-900/70 text-slate-100"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <DateRangePicker
              value={draftFilters.dateRange}
              onChange={(dateRange) => setDraftFilters((prev) => ({ ...prev, dateRange }))}
            />
            <Button onClick={applyFilters} className="bg-blue-600 hover:bg-blue-500">
              <Search className="mr-2 h-4 w-4" />
              Apply
            </Button>
            <Button
              variant="outline"
              className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-900"
              onClick={clearFilters}
            >
              Clear
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-2">
          <DataTable<UsageEntry>
            columns={columns}
            data={data?.items ?? []}
            totalCount={data?.total ?? 0}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            isLoading={isLoading}
            emptyMessage="No usage events match the current filters."
          />
        </div>
      </div>

      <UsageDetailDialog
        entry={selectedEntry}
        open={selectedEntry != null}
        onOpenChange={(open) => {
          if (!open) setSelectedEntry(null);
        }}
      />
    </div>
  );
}
