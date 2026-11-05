import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  ClipboardCopy,
  Download,
  Info,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';

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
import { apiClient } from '@/lib/http-client';
import { formatAdminDateTime } from '@/lib/format-datetime';

type FailedCharge = {
  debit_id: string;
  user_id: string;
  email: string;
  created_at: string;
  credits: number;
  task_id: string | null;
  song_id: string | null;
  task_status: string | null;
  reason: 'no_task' | 'failed_task';
};

type UserSummary = {
  user_id: string;
  email: string;
  charges: number;
  credits: number;
  first_seen: string;
  last_seen: string;
};

type FailedRefundsPayload = {
  generated_at: string;
  window_days: number;
  min_age_minutes: number;
  summary: {
    charges: number;
    credits: number;
    users: number;
    no_task: number;
    failed_task: number;
  };
  users: UserSummary[];
  rows: FailedCharge[];
  truncated: boolean;
  refund_command: string;
};

function downloadCsv(rows: FailedCharge[]) {
  const header = [
    'email',
    'created_at',
    'credits',
    'reason',
    'task_status',
    'debit_id',
    'song_id',
  ];
  const body = rows.map((row) =>
    [
      row.email,
      row.created_at,
      row.credits,
      row.reason,
      row.task_status ?? '',
      row.debit_id,
      row.song_id ?? '',
    ]
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(','),
  );
  const blob = new Blob([[header.join(','), ...body].join('\n')], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'failed-music-refunds.csv';
  link.click();
  URL.revokeObjectURL(url);
}

export default function FailedRefundsPage() {
  const [days, setDays] = useState('30');
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [copied, setCopied] = useState(false);
  const [refundTarget, setRefundTarget] = useState<{
    user: UserSummary;
    rows: FailedCharge[];
  } | null>(null);
  const [refundNotice, setRefundNotice] = useState<{
    tone: 'success' | 'error';
    message: string;
  } | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, isFetching, refetch } =
    useQuery<FailedRefundsPayload>({
      queryKey: ['failed-refunds', days],
      queryFn: async () => {
        const response = await apiClient.get<FailedRefundsPayload>(
          '/api/v3/admin/failed-refunds',
          { params: { days } },
        );
        return response.data;
      },
    });

  const detailRows = useMemo(() => {
    if (!data || !selectedUser) return [];
    return data.rows.filter((row) => row.user_id === selectedUser.user_id);
  }, [data, selectedUser]);

  const refundMutation = useMutation({
    mutationFn: async (target: { user: UserSummary; rows: FailedCharge[] }) => {
      const response = await apiClient.post<{
        refunded: number;
        skipped: number;
        failed: number;
        credits: number;
      }>('/api/v3/admin/failed-refunds/refund', {
        user_id: target.user.user_id,
        debit_ids: target.rows.map((row) => row.debit_id),
        confirm: 'REFUND',
      });
      return response.data;
    },
    onSuccess: (result, target) => {
      setRefundTarget(null);
      setRefundNotice({
        tone: result.refunded > 0 ? 'success' : 'error',
        message:
          result.refunded > 0
            ? `Refunded ${result.credits.toLocaleString()} credits for ${target.user.email}. ${result.skipped} already settled.`
            : `Nothing refunded — ${result.skipped} row(s) were already settled or no longer matched.`,
      });
      void queryClient.invalidateQueries({ queryKey: ['failed-refunds'] });
    },
    onError: () => {
      setRefundNotice({
        tone: 'error',
        message: 'Refund failed. Check the API logs and try again.',
      });
    },
  });

  const copyCommand = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(data.refund_command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Failed Refunds
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Music generations that were charged but produced no successful Suno
            task and were never refunded. Review the rows before refunding —
            amounts are in credits.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger className="w-[130px] border-slate-800 bg-slate-950/60">
              <SelectValue placeholder="Window" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="180">Last 180 days</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            className="border-slate-800 bg-slate-950/60"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
            <span className="ml-2">Refresh</span>
          </Button>
          <Button
            variant="outline"
            className="border-slate-800 bg-slate-950/60"
            onClick={() => downloadCsv(data?.rows ?? [])}
            disabled={!data?.rows.length}
          >
            <Download className="h-4 w-4" />
            <span className="ml-2">Export CSV</span>
          </Button>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-200/90">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          A row is a <strong>real failure</strong> when the charge has no
          successful Suno task (no task or a failed one) and no refund settled
          it. The check is time-based because older desktop debits carry no
          song reference. Refunding is a manual, reviewed action.
        </div>
      </div>

      {refundNotice ? (
        <div
          className={
            refundNotice.tone === 'success'
              ? 'rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-200'
              : 'rounded-2xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-200'
          }
        >
          {refundNotice.message}
        </div>
      ) : null}

      {isError ? (
        <ErrorState
          message="Could not load failed refunds. Check the API connection and try again."
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-8 text-sm text-slate-400">
          Loading failed charges…
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Credits to refund"
              value={data.summary.credits.toLocaleString()}
              hint={`${data.summary.charges} charge(s) in the last ${data.window_days} days`}
              icon={RotateCcw}
              tone="warning"
            />
            <StatCard
              label="Affected users"
              value={data.summary.users.toLocaleString()}
              hint="One or more failed charges each"
              icon={AlertTriangle}
            />
            <StatCard
              label="No task created"
              value={data.summary.no_task.toLocaleString()}
              hint="Charge landed, submit never produced a task"
            />
            <StatCard
              label="Suno task failed"
              value={data.summary.failed_task.toLocaleString()}
              hint="Nearest task ended failed/error"
              tone="danger"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="text-sm text-slate-400">
              Refund command after review:
              <code className="ml-2 rounded bg-slate-900 px-2 py-1 text-xs text-slate-200">
                {data.refund_command}
              </code>
            </div>
            <Button
              variant="outline"
              className="border-slate-800 bg-slate-950/60"
              onClick={() => void copyCommand()}
            >
              {copied ? (
                <Check className="h-4 w-4" />
              ) : (
                <ClipboardCopy className="h-4 w-4" />
              )}
              <span className="ml-2">{copied ? 'Copied' : 'Copy command'}</span>
            </Button>
          </div>

          {data.truncated ? (
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-xs text-slate-400">
              Showing the first {data.rows.length} charges. Export CSV for the
              full list.
            </div>
          ) : null}

          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60">
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead>User</TableHead>
                  <TableHead className="text-right">Charges</TableHead>
                  <TableHead className="text-right">Credits</TableHead>
                  <TableHead>First seen</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead className="text-right">Refund</TableHead>
                  <TableHead className="text-right">Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-sm text-slate-400">
                      No unrefunded failures in this window. 🎉
                    </TableCell>
                  </TableRow>
                ) : (
                  data.users.map((user) => (
                    <TableRow key={user.user_id} className="border-slate-800/70">
                      <TableCell className="font-medium text-slate-200">
                        {user.email || user.user_id}
                      </TableCell>
                      <TableCell className="text-right text-slate-300">
                        {user.charges}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge className="border-transparent bg-amber-500/15 text-amber-300 hover:bg-amber-500/15">
                          {user.credits.toLocaleString()} cr
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {formatAdminDateTime(user.first_seen)}
                      </TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {formatAdminDateTime(user.last_seen)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                          onClick={() =>
                            setRefundTarget({
                              user,
                              rows: data.rows.filter(
                                (row) => row.user_id === user.user_id,
                              ),
                            })
                          }
                          disabled={refundMutation.isPending}
                        >
                          <RotateCcw className="mr-1 h-3.5 w-3.5" />
                          Refund
                        </Button>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-slate-300 hover:bg-slate-800/70"
                          onClick={() => setSelectedUser(user)}
                        >
                          View rows
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <Dialog
            open={selectedUser !== null}
            onOpenChange={(open) => !open && setSelectedUser(null)}
          >
            <DialogContent className="max-w-4xl border-slate-800 bg-slate-950">
              <DialogHeader>
                <DialogTitle className="text-slate-100">
                  {selectedUser?.email || 'Failed charges'}
                </DialogTitle>
                <DialogDescription>
                  {selectedUser?.charges} charge(s),{' '}
                  {selectedUser?.credits.toLocaleString()} credits
                </DialogDescription>
              </DialogHeader>
              <div className="max-h-[60vh] overflow-auto rounded-xl border border-slate-800">
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-800 hover:bg-transparent">
                      <TableHead>When</TableHead>
                      <TableHead className="text-right">Credits</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Task</TableHead>
                      <TableHead>Debit ID</TableHead>
                      <TableHead className="text-right">Refund</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detailRows.map((row) => (
                      <TableRow key={row.debit_id} className="border-slate-800/70">
                        <TableCell className="text-xs text-slate-400">
                          {formatAdminDateTime(row.created_at)}
                        </TableCell>
                        <TableCell className="text-right text-slate-200">
                          {row.credits}
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={
                              row.reason === 'no_task'
                                ? 'border-transparent bg-slate-700/40 text-slate-300 hover:bg-slate-700/40'
                                : 'border-transparent bg-red-500/15 text-red-300 hover:bg-red-500/15'
                            }
                          >
                            {row.reason === 'no_task' ? 'no task' : 'task failed'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-slate-400">
                          {row.task_status || '—'}
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-500">
                          {row.debit_id}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-red-300 hover:bg-red-500/10"
                            onClick={() => {
                              if (!selectedUser) return;
                              setRefundTarget({ user: selectedUser, rows: [row] });
                              setSelectedUser(null);
                            }}
                            disabled={refundMutation.isPending}
                          >
                            Refund
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </DialogContent>
          </Dialog>

          <Dialog
            open={refundTarget !== null}
            onOpenChange={(open) => !open && setRefundTarget(null)}
          >
            <DialogContent className="max-w-lg border-slate-800 bg-slate-950">
              <DialogHeader>
                <DialogTitle className="text-slate-100">
                  Refund{' '}
                  {(
                    refundTarget?.rows.reduce((sum, row) => sum + row.credits, 0) ??
                    0
                  ).toLocaleString()}{' '}
                  credits?
                </DialogTitle>
                <DialogDescription>
                  {refundTarget?.user.email} — {refundTarget?.rows.length} failed
                  charge(s). This writes a credit refund to the wallet and is
                  idempotent per charge.
                </DialogDescription>
              </DialogHeader>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
                Only charges that still have no successful task are refunded.
                Already-settled rows are skipped.
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  className="border-slate-800 bg-slate-950/60"
                  onClick={() => setRefundTarget(null)}
                  disabled={refundMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  className="bg-red-600 text-white hover:bg-red-500"
                  onClick={() => refundTarget && refundMutation.mutate(refundTarget)}
                  disabled={refundMutation.isPending}
                >
                  {refundMutation.isPending
                    ? 'Refunding…'
                    : `Refund ${(
                        refundTarget?.rows.reduce(
                          (sum, row) => sum + row.credits,
                          0,
                        ) ?? 0
                      ).toLocaleString()} credits`}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </>
      ) : null}
    </div>
  );
}
