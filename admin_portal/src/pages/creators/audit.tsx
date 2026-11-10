import { useState } from 'react';
import { RefreshCw, ShieldCheck } from 'lucide-react';

import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useMoneyAudit } from '@/hooks/use-creators';

const ACTION_LABEL: Record<string, string> = {
  kyc_approve: 'KYC approved',
  kyc_reject: 'KYC rejected',
  payout_approved: 'Payout approved',
  payout_paid: 'Payout paid',
  payout_run_created: 'Payout run created',
};

function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action.replace(/_/g, ' ');
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
}

function usd(micros?: number | null): string {
  if (micros == null) return '—';
  return `$${(Number(micros) / 1_000_000).toFixed(2)}`;
}

function detailSummary(detail?: Record<string, unknown> | null): string {
  if (!detail) return '';
  const parts: string[] = [];
  const reference = detail.reference;
  const currency = detail.currency;
  const withheld = detail.withheld_micros;
  const fx = detail.fx_rate;
  if (typeof reference === 'string' && reference) parts.push(reference);
  if (typeof currency === 'string' && currency) parts.push(currency);
  if (typeof withheld === 'number' && withheld > 0) parts.push(`${usd(withheld)} withheld`);
  if (typeof fx === 'number' && fx !== 1) parts.push(`${fx} ៛/USD`);
  if (typeof detail.reason === 'string' && detail.reason) parts.push(detail.reason);
  return parts.join(' · ');
}

export default function CreatorMoneyAuditPage() {
  const [limit, setLimit] = useState('100');
  const { data, isLoading, isError, refetch, isFetching } = useMoneyAudit(Number(limit));

  const items = data?.items ?? [];

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Creators"
        title="Money audit trail"
        description="Every money action, in order, with who did it. Entries cannot be edited or deleted."
        actions={
          <>
            <Select value={limit} onValueChange={setLimit}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="50">50 rows</SelectItem>
                <SelectItem value="100">100 rows</SelectItem>
                <SelectItem value="200">200 rows</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className="mr-1 h-4 w-4" /> Refresh
            </Button>
          </>
        }
      />

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-3 p-6">
              {[0, 1, 2, 3].map((item) => (
                <Skeleton key={item} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-6 text-sm text-rose-300">
              Could not load the audit trail.
            </div>
          ) : items.length === 0 ? (
            <div className="p-6 text-sm text-slate-400">
              No money actions recorded yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Creator</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-xs text-slate-400">
                      {formatDate(entry.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge className="bg-slate-700/60 text-slate-200">
                        {actionLabel(entry.action)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-slate-300">
                      {entry.actor_email ?? 'system'}
                    </TableCell>
                    <TableCell className="text-xs text-slate-400">
                      {entry.creator_email ?? '—'}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-slate-100">
                      {usd(entry.amount_micros)}
                    </TableCell>
                    <TableCell className="max-w-[280px] truncate text-xs text-slate-500">
                      {detailSummary(entry.detail)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <p className="flex items-center gap-2 text-xs text-slate-500">
        <ShieldCheck className="h-3.5 w-3.5" />
        Append-only. Updates and deletes are rejected by the database.
      </p>
    </div>
  );
}
