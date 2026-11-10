import { useState } from 'react';
import { Calculator, FileText, Loader2, Lock, Undo2 } from 'lucide-react';

import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  useCalculateRoyalty,
  useGenerateTaxStatements,
  useLockRoyaltyPeriod,
  useReleaseReserve,
  useRoyaltyPeriods,
  type RoyaltyPeriodRecord,
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

function statusBadge(status: RoyaltyPeriodRecord['status']) {
  if (status === 'paid') return <Badge className="bg-emerald-500/15 text-emerald-300">Paid</Badge>;
  if (status === 'locked') return <Badge className="bg-violet-500/15 text-violet-300">Locked</Badge>;
  if (status === 'calculated') return <Badge className="bg-sky-500/15 text-sky-300">Calculated</Badge>;
  return <Badge className="bg-slate-500/15 text-slate-300">Open</Badge>;
}

export default function CreatorRoyaltiesPage() {
  const { data, isLoading, isError, refetch } = useRoyaltyPeriods();
  const calculate = useCalculateRoyalty();
  const lock = useLockRoyaltyPeriod();
  const generateStatements = useGenerateTaxStatements();
  const releaseReserve = useReleaseReserve();
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [poolUsd, setPoolUsd] = useState('3000');
  const [taxYear, setTaxYear] = useState(String(new Date().getFullYear()));

  const items = data?.items ?? [];

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const parsedPool = poolUsd.trim() ? Number(poolUsd) : undefined;
    calculate.mutate(
      {
        period_start: periodStart,
        period_end: periodEnd,
        pool_usd: Number.isFinite(parsedPool) ? parsedPool : undefined,
      },
      {
        onSuccess: (result) => {
          const payload = result as {
            creators?: number;
            tracks?: number;
            allocated_micros?: number;
          };
          toast({
            title: 'Royalty period calculated',
            description: `${payload.creators ?? 0} creators · ${payload.tracks ?? 0} tracks · ${usd(payload.allocated_micros ?? 0)} allocated.`,
          });
        },
        onError: (error) =>
          toast({
            title: 'Could not calculate royalties',
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
        title="Royalty periods"
        description="Calculate the monthly pool, write accruals to the ledger, and create creator earnings."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Annual tax statements</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="tax-year">Tax year</Label>
              <Input
                id="tax-year"
                type="number"
                min={2000}
                max={2100}
                value={taxYear}
                onChange={(event) => setTaxYear(event.target.value)}
                className="w-32"
              />
            </div>
            <Button
              variant="outline"
              disabled={generateStatements.isPending}
              onClick={() =>
                generateStatements.mutate(Number(taxYear), {
                  onSuccess: (result) =>
                    toast({
                      title: 'Statements generated',
                      description: `${result.generated} of ${result.creators} creators for ${result.year}.`,
                    }),
                  onError: (error) =>
                    toast({
                      title: 'Could not generate statements',
                      description: error instanceof Error ? error.message : 'Unknown error',
                      variant: 'destructive',
                    }),
                })
              }
            >
              {generateStatements.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <FileText className="mr-1 h-4 w-4" />
              )}
              Generate statements
            </Button>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Rolls up paid payouts into one statement per creator. Re-running replaces the year.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Calculate a period</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-4" onSubmit={submit}>
            <div className="space-y-2">
              <Label htmlFor="period-start">Period start</Label>
              <Input
                id="period-start"
                type="date"
                value={periodStart}
                onChange={(event) => setPeriodStart(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="period-end">Period end (exclusive)</Label>
              <Input
                id="period-end"
                type="date"
                value={periodEnd}
                onChange={(event) => setPeriodEnd(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pool-usd">Pool USD</Label>
              <Input
                id="pool-usd"
                type="number"
                min="0"
                step="1"
                value={poolUsd}
                onChange={(event) => setPoolUsd(event.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={calculate.isPending || !periodStart || !periodEnd}>
                {calculate.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Calculator className="mr-2 h-4 w-4" />
                )}
                Calculate
              </Button>
            </div>
          </form>
          <p className="mt-4 text-xs text-slate-500">
            Recalculating an open period replaces its accruals. Locked periods must be adjusted with a new entry.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-3 p-6">
              {[0, 1, 2].map((item) => (
                <Skeleton key={item} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-8 text-sm text-slate-400">
              Could not load royalty periods.{' '}
              <button className="text-sky-400 underline" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-400">
              No royalty periods calculated yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Pool</TableHead>
                  <TableHead>Weighted streams</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Calculated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((period) => (
                  <TableRow key={period.id}>
                    <TableCell>
                      {formatDate(period.period_start)} – {formatDate(period.period_end)}
                    </TableCell>
                    <TableCell>{usd(period.pool_micros)}</TableCell>
                    <TableCell>{period.total_weighted_streams.toLocaleString()}</TableCell>
                    <TableCell>
                      ${(Number(period.rate_micros || 0) / 1_000_000).toFixed(6)} / weighted stream
                    </TableCell>
                    <TableCell>{statusBadge(period.status)}</TableCell>
                    <TableCell>{formatDate(period.calculated_at)}</TableCell>
                    <TableCell className="text-right">
                      {period.status === 'calculated' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            lock.mutate(period.id, {
                              onSuccess: () =>
                                toast({
                                  title: 'Period locked',
                                  description: 'Further corrections must be adjustment entries.',
                                }),
                              onError: (error) =>
                                toast({
                                  title: 'Could not lock period',
                                  description: error instanceof Error ? error.message : 'Unknown error',
                                  variant: 'destructive',
                                }),
                            })
                          }
                          disabled={lock.isPending}
                        >
                          {lock.isPending ? (
                            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                          ) : (
                            <Lock className="mr-1 h-4 w-4" />
                          )}
                          Lock
                        </Button>
                      ) : null}
                      {period.status !== 'open' ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="ml-1"
                          onClick={() =>
                            releaseReserve.mutate(period.id, {
                              onSuccess: (result) =>
                                toast({
                                  title: 'Reserve released',
                                  description: `$${(result.released_micros / 1_000_000).toFixed(2)} to ${result.creators} creators.`,
                                }),
                              onError: (error) =>
                                toast({
                                  title: 'Could not release reserve',
                                  description:
                                    error instanceof Error ? error.message : 'Unknown error',
                                  variant: 'destructive',
                                }),
                            })
                          }
                          disabled={releaseReserve.isPending}
                        >
                          {releaseReserve.isPending ? (
                            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                          ) : (
                            <Undo2 className="mr-1 h-4 w-4" />
                          )}
                          Release reserve
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
