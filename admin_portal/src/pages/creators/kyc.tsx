import { useState } from 'react';
import { ExternalLink, Loader2, ShieldCheck, ShieldX } from 'lucide-react';

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
  useCreatorKyc,
  useDecideKyc,
  useKycDocumentLink,
  type CreatorKycRecord,
} from '@/hooks/use-creators';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function statusBadge(status: CreatorKycRecord['status']) {
  if (status === 'verified') return <Badge className="bg-emerald-500/15 text-emerald-300">Verified</Badge>;
  if (status === 'rejected') return <Badge className="bg-rose-500/15 text-rose-300">Rejected</Badge>;
  if (status === 'expired') return <Badge className="bg-slate-500/15 text-slate-300">Expired</Badge>;
  return <Badge className="bg-amber-500/15 text-amber-300">Pending</Badge>;
}

export default function CreatorKycPage() {
  const [status, setStatus] = useState('pending');
  const { data, isLoading, isError, refetch } = useCreatorKyc(status);
  const decide = useDecideKyc();
  const openDoc = useKycDocumentLink();
  const [rejecting, setRejecting] = useState<CreatorKycRecord | null>(null);
  const [reason, setReason] = useState('');

  const items = data?.items ?? [];

  function openDocument(record: CreatorKycRecord, kind: 'id' | 'selfie') {
    const tab = window.open('', '_blank', 'noopener,noreferrer');
    openDoc.mutate(
      { userId: record.user_id, kind },
      {
        onSuccess: (payload) => {
          if (tab) {
            tab.location.href = payload.url;
          } else {
            window.open(payload.url, '_blank', 'noopener,noreferrer');
          }
        },
        onError: (error) => {
          tab?.close();
          toast({
            title: 'Could not open the document',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'destructive',
          });
        },
      },
    );
  }

  function approve(record: CreatorKycRecord) {
    decide.mutate(
      { userId: record.user_id, decision: 'approve' },
      {
        onSuccess: () =>
          toast({
            title: 'Verification approved',
            description: `${record.user_display_name || record.email || record.user_id} can now request payouts.`,
          }),
        onError: (error) =>
          toast({
            title: 'Could not approve verification',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'destructive',
          }),
      },
    );
  }

  function reject() {
    if (!rejecting) return;
    if (!reason.trim()) return;
    decide.mutate(
      { userId: rejecting.user_id, decision: 'reject', reason: reason.trim() },
      {
        onSuccess: () => {
          toast({ title: 'Verification rejected', description: 'The creator can resubmit.' });
          setRejecting(null);
          setReason('');
        },
        onError: (error) =>
          toast({
            title: 'Could not reject verification',
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
        title="Payout verification"
        description="Review identity verification before a creator can request a payout."
        actions={
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="verified">Verified</SelectItem>
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
              Could not load verification records.{' '}
              <button className="text-sky-400 underline" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-400">
              No {status === 'all' ? '' : status} verification records.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Creator</TableHead>
                  <TableHead>Legal name</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((record) => (
                  <TableRow key={record.user_id}>
                    <TableCell>
                      <div className="font-medium text-slate-100">
                        {record.user_display_name || record.email || record.user_id}
                      </div>
                      <div className="text-xs text-slate-500">
                        {record.handle ? `@${record.handle}` : record.email}
                      </div>
                    </TableCell>
                    <TableCell>{record.legal_name}</TableCell>
                    <TableCell>{record.country_code}</TableCell>
                    <TableCell>
                      <div className="text-sm capitalize">{record.id_type.replace('_', ' ')}</div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        •••• {record.id_last4}
                        <button
                          type="button"
                          onClick={() => openDocument(record, 'id')}
                          className="text-sky-400 hover:text-sky-300 disabled:opacity-50"
                          title="Open ID document"
                          disabled={openDoc.isPending}
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </button>
                        {record.selfie_ref ? (
                          <button
                            type="button"
                            onClick={() => openDocument(record, 'selfie')}
                            className="text-sky-400 hover:text-sky-300 disabled:opacity-50"
                            title="Open selfie"
                            disabled={openDoc.isPending}
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </button>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>{formatDate(record.submitted_at)}</TableCell>
                    <TableCell>{statusBadge(record.status)}</TableCell>
                    <TableCell className="text-right">
                      {record.status === 'pending' ? (
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="outline" onClick={() => setRejecting(record)}>
                            <ShieldX className="mr-1 h-4 w-4" /> Reject
                          </Button>
                          <Button size="sm" onClick={() => approve(record)} disabled={decide.isPending}>
                            {decide.isPending ? (
                              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                            ) : (
                              <ShieldCheck className="mr-1 h-4 w-4" />
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

      <Dialog open={Boolean(rejecting)} onOpenChange={(open) => !open && setRejecting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject verification</DialogTitle>
            <DialogDescription>
              Give the creator a reason so they can fix and resubmit.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="The ID document is unreadable or does not match the legal name."
            rows={4}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejecting(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={reject} disabled={!reason.trim() || decide.isPending}>
              Reject verification
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
