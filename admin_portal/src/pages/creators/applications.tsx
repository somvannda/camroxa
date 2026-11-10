import { useState } from 'react';
import { BadgeCheck, Loader2, MessageSquareWarning, XCircle } from 'lucide-react';

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
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/hooks/use-toast';
import {
  useCreatorApplications,
  useDecideApplication,
  type CreatorApplicationRecord,
} from '@/hooks/use-creators';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function statusBadge(status: CreatorApplicationRecord['status']) {
  if (status === 'approved') return <Badge className="bg-emerald-500/15 text-emerald-300">Approved</Badge>;
  if (status === 'rejected') return <Badge className="bg-rose-500/15 text-rose-300">Rejected</Badge>;
  if (status === 'changes_requested') return <Badge className="bg-amber-500/15 text-amber-300">Changes requested</Badge>;
  if (status === 'withdrawn') return <Badge className="bg-slate-500/15 text-slate-300">Withdrawn</Badge>;
  return <Badge className="bg-sky-500/15 text-sky-300">In review</Badge>;
}

type DecisionMode = 'request_changes' | 'reject';

export default function CreatorApplicationsPage() {
  const [status, setStatus] = useState('submitted');
  const { data, isLoading, isError, refetch } = useCreatorApplications(status);
  const decide = useDecideApplication();
  const [pendingDecision, setPendingDecision] = useState<{
    record: CreatorApplicationRecord;
    mode: DecisionMode;
  } | null>(null);
  const [reason, setReason] = useState('');

  const items = data?.items ?? [];

  function approve(record: CreatorApplicationRecord) {
    decide.mutate(
      { applicationId: record.id, decision: 'approve' },
      {
        onSuccess: () =>
          toast({
            title: 'Badge approved',
            description: `${record.user_display_name || record.email || 'The creator'} now has the Verified badge.`,
          }),
        onError: (error) =>
          toast({
            title: 'Could not approve',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'destructive',
          }),
      },
    );
  }

  function submitDecision() {
    if (!pendingDecision || !reason.trim()) return;
    decide.mutate(
      {
        applicationId: pendingDecision.record.id,
        decision: pendingDecision.mode,
        reason: reason.trim(),
      },
      {
        onSuccess: () => {
          toast({
            title: pendingDecision.mode === 'reject' ? 'Request rejected' : 'Changes requested',
            description: 'The creator will see the note on their verification page.',
          });
          setPendingDecision(null);
          setReason('');
        },
        onError: (error) =>
          toast({
            title: 'Could not update request',
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
        title="Badge requests"
        description="Review optional Verified Creator badge requests. This does not gate publishing or payouts."
        actions={
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="submitted">In review</SelectItem>
              <SelectItem value="changes_requested">Changes requested</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="all">All</SelectItem>
            </SelectContent>
          </Select>
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
              Could not load badge requests.{' '}
              <button className="text-sky-400 underline" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-400">
              No {status === 'all' ? '' : status.replace('_', ' ')} badge requests.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Creator</TableHead>
                  <TableHead>Pitch</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Review by</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell>
                      <div className="font-medium text-slate-100">
                        {record.user_display_name || record.email || record.user_id}
                      </div>
                      <div className="text-xs text-slate-500">
                        {record.handle ? `@${record.handle}` : record.email}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[320px] text-sm text-slate-300">
                      <p className="line-clamp-3">{record.payload?.pitch || '—'}</p>
                    </TableCell>
                    <TableCell>{formatDate(record.submitted_at)}</TableCell>
                    <TableCell>{formatDate(record.sla_due_at)}</TableCell>
                    <TableCell>{statusBadge(record.status)}</TableCell>
                    <TableCell className="text-right">
                      {['submitted', 'in_review'].includes(record.status) ? (
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPendingDecision({ record, mode: 'request_changes' })}
                          >
                            <MessageSquareWarning className="mr-1 h-4 w-4" /> Changes
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPendingDecision({ record, mode: 'reject' })}
                          >
                            <XCircle className="mr-1 h-4 w-4" /> Reject
                          </Button>
                          <Button size="sm" onClick={() => approve(record)} disabled={decide.isPending}>
                            {decide.isPending ? (
                              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                            ) : (
                              <BadgeCheck className="mr-1 h-4 w-4" />
                            )}
                            Approve
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">{formatDate(record.reviewed_at)}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(pendingDecision)} onOpenChange={(open) => !open && setPendingDecision(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingDecision?.mode === 'reject' ? 'Reject badge request' : 'Request changes'}
            </DialogTitle>
            <DialogDescription>
              The note is shown to the creator. Be specific about what to fix.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Add a short note for the creator."
            rows={4}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPendingDecision(null)}>
              Cancel
            </Button>
            <Button
              variant={pendingDecision?.mode === 'reject' ? 'destructive' : 'default'}
              onClick={submitDecision}
              disabled={!reason.trim() || decide.isPending}
            >
              {pendingDecision?.mode === 'reject' ? 'Reject request' : 'Request changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
