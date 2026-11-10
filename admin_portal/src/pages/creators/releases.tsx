import { useState } from 'react';
import { EyeOff, Loader2 } from 'lucide-react';

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
  useCreatorReleases,
  useTakedownRelease,
  type CreatorReleaseRecord,
} from '@/hooks/use-creators';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function statusBadge(status: string) {
  if (status === 'published') return <Badge className="bg-emerald-500/15 text-emerald-300">Live</Badge>;
  if (status === 'taken_down') return <Badge className="bg-rose-500/15 text-rose-300">Taken down</Badge>;
  if (status === 'rejected') return <Badge className="bg-rose-500/15 text-rose-300">Rejected</Badge>;
  if (status === 'submitted' || status === 'in_review') return <Badge className="bg-sky-500/15 text-sky-300">In review</Badge>;
  return <Badge className="bg-slate-500/15 text-slate-300">{status}</Badge>;
}

export default function CreatorReleasesPage() {
  const [status, setStatus] = useState('published');
  const { data, isLoading, isError, refetch } = useCreatorReleases(status);
  const takedown = useTakedownRelease();
  const [takingDown, setTakingDown] = useState<CreatorReleaseRecord | null>(null);
  const [reason, setReason] = useState('');

  const items = data?.items ?? [];

  function submitTakedown() {
    if (!takingDown || !reason.trim()) return;
    takedown.mutate(
      { releaseId: takingDown.id, reason: reason.trim() },
      {
        onSuccess: () => {
          toast({
            title: 'Release taken down',
            description: 'The creator has been notified with the reason.',
          });
          setTakingDown(null);
          setReason('');
        },
        onError: (error) =>
          toast({
            title: 'Could not take down release',
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
        title="Release moderation"
        description="Releases publish instantly. Review reports and take down anything that breaks the rules."
        actions={
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="published">Live</SelectItem>
              <SelectItem value="taken_down">Taken down</SelectItem>
              <SelectItem value="submitted">Legacy review</SelectItem>
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
              Could not load releases.{' '}
              <button className="text-sky-400 underline" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-400">
              No {status === 'all' ? '' : status.replace('_', ' ')} releases.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Release</TableHead>
                  <TableHead>Creator</TableHead>
                  <TableHead>Genre</TableHead>
                  <TableHead>Published</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((release) => (
                  <TableRow key={release.id}>
                    <TableCell>
                      <div className="font-medium text-slate-100">
                        {release.metadata?.title || 'Untitled'}
                      </div>
                      <div className="text-xs text-slate-500">
                        {release.metadata?.release_type || 'single'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-slate-300">
                        {release.user_display_name || release.email || release.creator_id}
                      </div>
                      <div className="text-xs text-slate-500">
                        {release.handle ? `@${release.handle}` : release.email}
                      </div>
                    </TableCell>
                    <TableCell>{release.metadata?.genre || '—'}</TableCell>
                    <TableCell>{formatDate(release.published_at)}</TableCell>
                    <TableCell>{statusBadge(release.status)}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs text-slate-400">
                      {release.takedown_reason || '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {release.status === 'published' ? (
                        <Button size="sm" variant="outline" onClick={() => setTakingDown(release)}>
                          <EyeOff className="mr-1 h-4 w-4" /> Take down
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

      <Dialog open={Boolean(takingDown)} onOpenChange={(open) => !open && setTakingDown(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Take down release</DialogTitle>
            <DialogDescription>
              The release is unpublished immediately. The creator is notified with this reason.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Copyright report, unlicensed sample, misleading metadata…"
            rows={4}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTakingDown(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={submitTakedown} disabled={!reason.trim() || takedown.isPending}>
              {takedown.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
              Take down
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
