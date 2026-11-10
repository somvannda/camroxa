import { useState } from 'react';
import { CheckCircle2, Download, Loader2, Play, ShieldCheck, Wallet } from 'lucide-react';

import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from '@/hooks/use-toast';
import {
  useApprovePayout,
  useCreatePayoutRun,
  useCreatorPayouts,
  useExportPayoutsCsv,
  useMarkPayoutPaid,
  type CreatorPayoutRecord,
} from '@/hooks/use-creators';

function usd(micros: number): string {
  return `$${(Number(micros || 0) / 1_000_000).toFixed(2)}`;
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function statusBadge(status: CreatorPayoutRecord['status']) {
  if (status === 'paid') return <Badge className="bg-emerald-500/15 text-emerald-300">Paid</Badge>;
  if (status === 'failed') return <Badge className="bg-rose-500/15 text-rose-300">Failed</Badge>;
  if (status === 'processing') return <Badge className="bg-sky-500/15 text-sky-300">Processing</Badge>;
  if (status === 'approved') return <Badge className="bg-violet-500/15 text-violet-300">Approved</Badge>;
  if (status === 'cancelled') return <Badge className="bg-slate-500/15 text-slate-300">Cancelled</Badge>;
  return <Badge className="bg-amber-500/15 text-amber-300">Requested</Badge>;
}

export default function CreatorPayoutsPage() {
  const [status, setStatus] = useState('requested');
  const { data, isLoading, isError, refetch } = useCreatorPayouts(status);
  const markPaid = useMarkPayoutPaid();
  const approve = useApprovePayout();
  const createRun = useCreatePayoutRun();
  const exportCsv = useExportPayoutsCsv();
  const [paying, setPaying] = useState<CreatorPayoutRecord | null>(null);
  const [reference, setReference] = useState('');

  const items = data?.items ?? [];

  function runPayouts() {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const iso = (date: Date) => date.toISOString().slice(0, 10);
    createRun.mutate(
      { period_start: iso(start), period_end: iso(now) },
      {
        onSuccess: (result) => {
          const payload = result as { created?: number; skipped?: number; eligible_creators?: number };
          toast({
            title: 'Payout run created',
            description: `${payload.created ?? 0} payouts created · ${payload.skipped ?? 0} skipped · ${payload.eligible_creators ?? 0} eligible.`,
          });
        },
        onError: (error) =>
          toast({
            title: 'Could not create payout run',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'destructive',
          }),
      },
    );
  }

  async function downloadCsv() {
    try {
      const csv = await exportCsv.mutateAsync(status);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `creator-payouts-${status}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: 'Could not export payouts',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  }

  function approveRecord(record: CreatorPayoutRecord) {
    approve.mutate(record.id, {
      onSuccess: () =>
        toast({
          title: 'Payout approved',
          description: 'A different admin must mark it paid.',
        }),
      onError: (error) =>
        toast({
          title: 'Could not approve payout',
          description: error instanceof Error ? error.message : 'Unknown error',
          variant: 'destructive',
        }),
    });
  }

  function submitPaid() {
    if (!paying || !reference.trim()) return;
    markPaid.mutate(
      { payoutId: paying.id, reference: reference.trim() },
      {
        onSuccess: () => {
          toast({
            title: 'Payout marked paid',
            description: `${usd(paying.amount_micros)} sent to ${paying.user_display_name || paying.email || 'the creator'}.`,
          });
          setPaying(null);
          setReference('');
        },
        onError: (error) =>
          toast({
            title: 'Could not mark payout paid',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'destructive',
          }),
      },
    );
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Creators"
        title="Creator payouts"
        description="Review payout requests, record the bank reference, and mark each payout paid."
        actions={
          <>
            <Button variant="outline" onClick={downloadCsv} disabled={exportCsv.isPending}>
              <Download className="mr-1 h-4 w-4" /> Export CSV
            </Button>
            <Button variant="outline" onClick={runPayouts} disabled={createRun.isPending}>
              {createRun.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-1 h-4 w-4" />
              )}
              Run payouts
            </Button>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="requested">Requested</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="paid">Paid</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
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
            <div className="p-8 text-sm text-slate-400">
              Could not load payouts.{' '}
              <button className="text-sky-400 underline" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-400">
              No {status === 'all' ? '' : status} payouts.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Creator</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Requested</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((payout) => (
                  <TableRow key={payout.id}>
                    <TableCell>
                      <div className="font-medium text-slate-100">
                        {payout.user_display_name || payout.email || payout.creator_id}
                      </div>
                      <div className="text-xs text-slate-500">
                        {payout.handle ? `@${payout.handle}` : payout.email}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium text-slate-100">
                      {usd(payout.amount_micros)}
                    </TableCell>
                    <TableCell className="uppercase text-xs text-slate-400">{payout.method}</TableCell>
                    <TableCell>{formatDate(payout.requested_at)}</TableCell>
                    <TableCell>{statusBadge(payout.status)}</TableCell>
                    <TableCell className="max-w-[180px] truncate text-xs text-slate-400">
                      {payout.payment_ref || '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {payout.status === 'requested' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => approveRecord(payout)}
                          disabled={approve.isPending}
                        >
                          {approve.isPending ? (
                            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                          ) : (
                            <ShieldCheck className="mr-1 h-4 w-4" />
                          )}
                          Approve
                        </Button>
                      ) : payout.status === 'approved' || payout.status === 'processing' ? (
                        <Button size="sm" onClick={() => setPaying(payout)} disabled={markPaid.isPending}>
                          {markPaid.isPending ? (
                            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="mr-1 h-4 w-4" />
                          )}
                          Mark paid
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-500">{formatDate(payout.paid_at)}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(paying)} onOpenChange={(open) => !open && setPaying(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark payout paid</DialogTitle>
            <DialogDescription>
              Record the bank or Wing reference for {paying ? usd(paying.amount_micros) : 'this payout'}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-xs text-slate-400" htmlFor="payout-reference">
              Payment reference
            </label>
            <Input
              id="payout-reference"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="ABA transfer ID, Wing receipt, or batch reference"
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPaying(null)}>
              Cancel
            </Button>
            <Button onClick={submitPaid} disabled={!reference.trim() || markPaid.isPending}>
              <Wallet className="mr-1 h-4 w-4" />
              Confirm paid
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
