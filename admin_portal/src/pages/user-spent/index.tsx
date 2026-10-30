import React from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  DollarSign,
  Info,
  RefreshCw,
  Search,
  Wallet,
} from 'lucide-react';

import { Pagination } from '@/components/data-table/pagination';
import { DateRangePicker, type DateRangeValue } from '@/components/shared/date-range-picker';
import { ErrorState } from '@/components/shared/error-state';
import { StatCard } from '@/components/shared/stat-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useUsageFilters } from '@/hooks/use-usage';
import { useUserSpend } from '@/hooks/use-user-spend';
import { formatDollars } from '@/lib/credit-format';
import { formatOperationLabel, truncateId } from '@/lib/usage-labels';
import type { UserSpendListParams } from '@/types/api';
import type { UserSpendItem } from '@/types/models';

const PAGE_SIZE = 50;

interface FiltersState {
  q: string;
  planId: string;
  provider: string;
  operation: string;
  alert: 'all' | 'margin_risk' | 'healthy';
  sort: 'cogs_desc' | 'wallet_desc';
  dateRange: DateRangeValue;
}

function defaultDateRange(): DateRangeValue {
  const now = new Date();
  const from = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const to = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { from: iso(from), to: iso(to) };
}

const EMPTY_FILTERS: FiltersState = {
  q: '',
  planId: 'all',
  provider: 'all',
  operation: 'all',
  alert: 'all',
  sort: 'cogs_desc',
  dateRange: defaultDateRange(),
};

function filtersToParams(filters: FiltersState, page: number): UserSpendListParams {
  return {
    page,
    page_size: PAGE_SIZE,
    sort: filters.sort,
    alert: filters.alert,
    ...(filters.q.trim() && { q: filters.q.trim() }),
    ...(filters.planId !== 'all' && { plan_id: filters.planId }),
    ...(filters.provider !== 'all' && { provider: filters.provider }),
    ...(filters.operation !== 'all' && { operation: filters.operation }),
    ...(filters.dateRange.from && { from_date: filters.dateRange.from }),
    ...(filters.dateRange.to && { to_date: `${filters.dateRange.to}T23:59:59` }),
  };
}

function alertBadges(item: UserSpendItem) {
  const badges: React.ReactNode[] = [];
  if (item.alerts.margin_risk) {
    badges.push(
      <Badge
        key="margin"
        className="border-transparent bg-rose-500/15 text-rose-300 hover:bg-rose-500/15"
      >
        Margin risk
      </Badge>,
    );
  }
  if (badges.length === 0) {
    return <span className="text-xs text-slate-600">—</span>;
  }
  return <div className="flex flex-wrap gap-1">{badges}</div>;
}

function usageLedgerHref(item: UserSpendItem, filters: FiltersState): string {
  const params = new URLSearchParams();
  params.set('user_id', item.user_id);
  if (filters.dateRange.from) params.set('from_date', filters.dateRange.from);
  if (filters.dateRange.to) params.set('to_date', filters.dateRange.to);
  return `/usage?${params.toString()}`;
}

function ExpandedBreakdown({
  item,
  filters,
}: {
  item: UserSpendItem;
  filters: FiltersState;
}) {
  const total = item.est_cogs_usd || 0;
  return (
    <div className="space-y-3 border-t border-slate-800/80 bg-slate-950/60 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Est. COGS by provider × operation
        </div>
        <div className="flex gap-3 text-xs">
          <Link
            to={`/users/${item.user_id}`}
            className="text-violet-300 hover:underline"
          >
            User detail
          </Link>
          <Link
            to={usageLedgerHref(item, filters)}
            className="text-blue-300 hover:underline"
          >
            Open Usage ledger
          </Link>
        </div>
      </div>
      {item.by_cog.length === 0 ? (
        <p className="text-sm text-slate-500">No billable events in this range.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 font-medium">Provider / Op</th>
                <th className="px-3 py-2 font-medium">Events</th>
                <th className="px-3 py-2 font-medium">Plan cash $</th>
                <th className="px-3 py-2 font-medium">Wallet $</th>
                <th className="px-3 py-2 font-medium">Est. COGS $</th>
                <th className="px-3 py-2 font-medium">% of user</th>
              </tr>
            </thead>
            <tbody>
              {item.by_cog.map((cog) => {
                const cogs = cog.est_cogs_usd ?? 0;
                const pct = total > 0 ? (cogs / total) * 100 : 0;
                return (
                  <tr
                    key={`${cog.provider}-${cog.operation}-${cog.model}`}
                    className="border-b border-slate-800/60 last:border-0"
                  >
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-200">
                        {formatOperationLabel(cog.operation)}
                      </div>
                      <div className="mt-0.5 space-y-0.5 text-[11px] text-slate-500">
                        <div>
                          <span className="text-slate-600">Provider </span>
                          <span className="font-medium text-slate-300">
                            {cog.provider || '—'}
                          </span>
                        </div>
                        <div className="font-mono">
                          <span className="font-sans text-slate-600">Model </span>
                          {cog.model || '—'}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-slate-300">{cog.events}</td>
                    <td className="px-3 py-2 tabular-nums text-sky-300">
                      {formatDollars(cog.plan_included_usd)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-violet-300">
                      {formatDollars(cog.wallet_usd)}
                    </td>
                    <td className="px-3 py-2 tabular-nums font-medium text-white">
                      {formatDollars(cog.est_cogs_usd)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-slate-400">
                      {pct.toFixed(1)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="text-[11px] text-slate-500">
        Period revenue (prorated): {formatDollars(item.plan_revenue_usd)} · Soft overage
        events: {item.soft_overage_events}
      </div>
    </div>
  );
}

export default function UserSpentPage() {
  const [draftFilters, setDraftFilters] = React.useState<FiltersState>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = React.useState<FiltersState>(EMPTY_FILTERS);
  const [page, setPage] = React.useState(1);
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const params = React.useMemo(
    () => filtersToParams(appliedFilters, page),
    [appliedFilters, page],
  );
  const { data, isLoading, isError, error, refetch, isFetching } = useUserSpend(params);
  const filtersQuery = useUsageFilters();

  const applyFilters = () => {
    setPage(1);
    setAppliedFilters(draftFilters);
  };

  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const toggleExpand = (userId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load user spend'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const summary = data?.summary;
  const items = data?.items ?? [];

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top,rgba(244,63,94,0.06),transparent_35%),linear-gradient(180deg,#020617_0%,#030712_100%)] p-8">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-rose-400/80">
              User Spent
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
              Per-user estimated COGS
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
              Highest spenders first. Plan filter uses the unified catalog (desktop
              license or CutLuy web). Compare estimated COGS to prorated plan cash.
              Meter chips are retired.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              asChild
            >
              <Link to="/finance">Finance</Link>
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

        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-slate-300">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div>
              <div className="font-medium text-slate-100">Estimates only</div>
              <p className="mt-1 text-slate-400">
                Est. COGS uses admin model costs / pricing external cost — not provider invoices.
                Plan revenue is prorated by the selected date range and plan billing cycle.
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Margin risk"
            value={summary?.users_margin_risk ?? 0}
            hint="Est. COGS > period revenue"
            icon={AlertTriangle}
            tone="danger"
          />
          <StatCard
            label="Total est. COGS"
            value={formatDollars(summary?.total_est_cogs_usd)}
            hint="Filtered users"
            icon={DollarSign}
            tone="success"
          />
          <StatCard
            label="Total wallet $"
            value={formatDollars(summary?.total_wallet_usd)}
            hint={`GCV $${(summary?.gcv ?? 0.01).toFixed(4)}`}
            icon={Wallet}
          />
        </div>

        <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/50 p-4">
          <div className="min-w-[180px] flex-1 space-y-1">
            <label className="text-xs text-slate-500">Search</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
              <Input
                value={draftFilters.q}
                onChange={(e) => setDraftFilters((f) => ({ ...f, q: e.target.value }))}
                placeholder="Email or user id"
                className="border-slate-700 bg-slate-900 pl-9 text-slate-100"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Date range</label>
            <DateRangePicker
              value={draftFilters.dateRange}
              onChange={(dateRange) => setDraftFilters((f) => ({ ...f, dateRange }))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Alert</label>
            <Select
              value={draftFilters.alert}
              onValueChange={(alert) =>
                setDraftFilters((f) => ({
                  ...f,
                  alert: alert as FiltersState['alert'],
                }))
              }
            >
              <SelectTrigger className="w-[150px] border-slate-700 bg-slate-900 text-slate-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="margin_risk">Margin risk</SelectItem>
                <SelectItem value="healthy">Healthy</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Sort</label>
            <Select
              value={draftFilters.sort}
              onValueChange={(sort) =>
                setDraftFilters((f) => ({
                  ...f,
                  sort: sort as FiltersState['sort'],
                }))
              }
            >
              <SelectTrigger className="w-[150px] border-slate-700 bg-slate-900 text-slate-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cogs_desc">Est. COGS</SelectItem>
                <SelectItem value="wallet_desc">Wallet $</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Provider</label>
            <Select
              value={draftFilters.provider}
              onValueChange={(provider) => setDraftFilters((f) => ({ ...f, provider }))}
            >
              <SelectTrigger className="w-[140px] border-slate-700 bg-slate-900 text-slate-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {(filtersQuery.data?.providers ?? []).map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Operation</label>
            <Select
              value={draftFilters.operation}
              onValueChange={(operation) => setDraftFilters((f) => ({ ...f, operation }))}
            >
              <SelectTrigger className="w-[140px] border-slate-700 bg-slate-900 text-slate-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {(filtersQuery.data?.operations ?? []).map((op) => (
                  <SelectItem key={op} value={op}>
                    {formatOperationLabel(op)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={applyFilters} className="bg-violet-600 hover:bg-violet-500">
            Apply
          </Button>
          <Button
            variant="outline"
            className="border-slate-700 bg-slate-900 text-slate-200"
            onClick={clearFilters}
          >
            Clear
          </Button>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 shadow-xl shadow-black/20">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 bg-slate-900/80 hover:bg-slate-900/80">
                  <TableHead className="w-10 text-slate-400" />
                  <TableHead className="sticky left-0 z-10 bg-slate-900/95 text-slate-300">
                    User
                  </TableHead>
                  <TableHead className="text-slate-300">Plan</TableHead>
                  <TableHead className="text-right text-slate-300">Est. COGS $</TableHead>
                  <TableHead className="text-right text-slate-300">Wallet $</TableHead>
                  <TableHead className="text-right text-slate-300">Plan cash $</TableHead>
                  <TableHead className="text-slate-300">Alert</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={i} className="border-slate-800">
                      <TableCell colSpan={7} className="h-12 animate-pulse bg-slate-900/40" />
                    </TableRow>
                  ))
                ) : items.length === 0 ? (
                  <TableRow className="border-slate-800">
                    <TableCell colSpan={7} className="py-12 text-center text-slate-500">
                      No users with spend in this range.
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((item) => {
                    const isOpen = expanded.has(item.user_id);
                    return (
                      <React.Fragment key={item.user_id}>
                        <TableRow
                          className="cursor-pointer border-slate-800 hover:bg-slate-900/50"
                          onClick={() => toggleExpand(item.user_id)}
                        >
                          <TableCell className="text-slate-500">
                            {isOpen ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </TableCell>
                          <TableCell
                            className="sticky left-0 z-10 bg-slate-950/95"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Link
                              to={`/users/${item.user_id}`}
                              className="block font-medium text-slate-100 hover:text-violet-300"
                            >
                              {item.email || '—'}
                            </Link>
                            <div className="font-mono text-[11px] text-slate-500">
                              {truncateId(item.user_id)}
                            </div>
                          </TableCell>
                          <TableCell className="text-slate-300">{item.plan_name}</TableCell>
                          <TableCell className="text-right font-semibold tabular-nums text-white">
                            {formatDollars(item.est_cogs_usd)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-violet-300">
                            {formatDollars(item.wallet_charged_usd)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sky-300">
                            {formatDollars(item.plan_revenue_usd)}
                          </TableCell>
                          <TableCell>{alertBadges(item)}</TableCell>
                        </TableRow>
                        {isOpen ? (
                          <TableRow className="border-slate-800 hover:bg-transparent">
                            <TableCell colSpan={7} className="p-0">
                              <ExpandedBreakdown item={item} filters={appliedFilters} />
                            </TableCell>
                          </TableRow>
                        ) : null}
                      </React.Fragment>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            totalCount={data?.total ?? 0}
            onPageChange={setPage}
          />
        </div>
      </div>
    </div>
  );
}
