import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDollars } from '@/lib/credit-format';
import { cn } from '@/lib/utils';
import type { UserSpendItem } from '@/types/models';

type SpendSort = 'cogs_desc' | 'wallet_desc';

type TopSpendersTableProps = {
  items: UserSpendItem[];
  sort: SpendSort;
  onSortChange: (sort: SpendSort) => void;
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  windowLabel?: string;
};

export function TopSpendersTable({
  items,
  sort,
  onSortChange,
  isLoading,
  isError,
  errorMessage,
  windowLabel = 'Last 30 days',
}: TopSpendersTableProps) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Top 10 spenders</h2>
          <p className="text-sm text-slate-400">
            {windowLabel} · estimated COGS and wallet credit spent
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-slate-800 p-0.5">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                'h-7 px-2.5 text-xs',
                sort === 'cogs_desc' && 'bg-slate-800 text-white',
              )}
              onClick={() => onSortChange('cogs_desc')}
            >
              By COGS
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                'h-7 px-2.5 text-xs',
                sort === 'wallet_desc' && 'bg-slate-800 text-white',
              )}
              onClick={() => onSortChange('wallet_desc')}
            >
              By wallet spent
            </Button>
          </div>
          <Link
            to="/user-spent"
            className="inline-flex items-center text-xs font-medium text-violet-300 hover:text-violet-200"
          >
            View all
            <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/50">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : isError ? (
          <div className="px-4 py-6 text-sm text-red-300">
            {errorMessage || 'Failed to load top spenders'}
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-6 text-sm text-slate-500">No spenders in this window</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-slate-800 hover:bg-transparent">
                <TableHead className="w-12 text-slate-500">#</TableHead>
                <TableHead className="text-slate-500">User</TableHead>
                <TableHead className="text-slate-500">Plan</TableHead>
                <TableHead className="text-right text-slate-500">Est. COGS</TableHead>
                <TableHead className="text-right text-slate-500">Wallet spent</TableHead>
                <TableHead className="text-right text-slate-500">Alerts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, index) => (
                <TableRow key={item.user_id} className="border-slate-800/80">
                  <TableCell className="tabular-nums text-slate-500">{index + 1}</TableCell>
                  <TableCell>
                    <Link
                      to={`/users/${item.user_id}`}
                      className="font-medium text-slate-100 hover:text-violet-200"
                    >
                      {item.email}
                    </Link>
                    {item.display_name ? (
                      <div className="text-xs text-slate-500">{item.display_name}</div>
                    ) : null}
                  </TableCell>
                  <TableCell className="text-slate-300">{item.plan_name || '—'}</TableCell>
                  <TableCell className="text-right tabular-nums text-slate-100">
                    {formatDollars(item.est_cogs_usd)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-slate-100">
                    {formatDollars(item.wallet_charged_usd)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {item.alerts.over_allowance ? (
                        <Badge className="border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-300">
                          Overage
                        </Badge>
                      ) : null}
                      {item.alerts.margin_risk ? (
                        <Badge className="border-red-500/30 bg-red-500/10 text-[10px] text-red-300">
                          Margin
                        </Badge>
                      ) : null}
                      {!item.alerts.over_allowance && !item.alerts.margin_risk ? (
                        <span className="text-xs text-slate-600">—</span>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}

/** Local sort state helper for the dashboard page. */
export function useTopSpendSort(initial: SpendSort = 'cogs_desc') {
  return useState<SpendSort>(initial);
}
