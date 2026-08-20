import { useState } from 'react';

import { Pagination } from '@/components/data-table/pagination';
import { PageHeader } from '@/components/shared/page-header';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useBackfillAudioPackages,
  useExportEvents,
  usePlaybackEvents,
} from '@/hooks/use-playback-audit';
import { toast } from '@/hooks/use-toast';
import { formatAdminDateTime } from '@/lib/format-datetime';

const PAGE_SIZE = 50;

export default function PlaybackAuditPage() {
  const [tab, setTab] = useState('playback');
  const [userId, setUserId] = useState('');
  const [appliedUserId, setAppliedUserId] = useState('');
  const [page, setPage] = useState(1);
  const offset = (page - 1) * PAGE_SIZE;
  const playback = usePlaybackEvents({
    userId: appliedUserId || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const exports = useExportEvents({
    userId: appliedUserId || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const backfill = useBackfillAudioPackages();

  const applyFilter = () => {
    setAppliedUserId(userId.trim());
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Playback audit"
        description="Per-user play and download events for Camxora Music. Storage keys are never playable URLs."
      />
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs text-slate-400">User ID</label>
          <Input
            className="w-80"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="Filter by user UUID"
          />
        </div>
        <Button variant="outline" onClick={applyFilter}>
          Apply
        </Button>
        <Button
          variant="outline"
          disabled={backfill.isPending}
          onClick={() =>
            backfill.mutate(10, {
              onSuccess: (data) =>
                toast({ title: `Packaged ${data.packaged} leftover track(s)` }),
              onError: () =>
                toast({ title: 'Backfill failed', variant: 'destructive' }),
            })
          }
        >
          Backfill 10 packages
        </Button>
      </div>
      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value);
          setPage(1);
        }}
      >
        <TabsList>
          <TabsTrigger value="playback">Playback</TabsTrigger>
          <TabsTrigger value="exports">Exports</TabsTrigger>
        </TabsList>
        <TabsContent value="playback">
          <Card className="border-slate-800 bg-slate-900/50">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Event</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Variant</TableHead>
                    <TableHead>Package</TableHead>
                    <TableHead className="text-right">Bytes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(playback.data?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-slate-400">
                        No playback events.
                      </TableCell>
                    </TableRow>
                  ) : (
                    (playback.data?.items ?? []).map((row) => (
                      <TableRow key={String(row.id)}>
                        <TableCell>{formatAdminDateTime(row.created_at)}</TableCell>
                        <TableCell className="font-mono text-xs">{row.user_id ?? '—'}</TableCell>
                        <TableCell>{row.event}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {row.subject_type}:{row.subject_id ?? ''}
                        </TableCell>
                        <TableCell>{row.variant ?? '—'}</TableCell>
                        <TableCell>{row.package_status ?? '—'}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {(row.bytes_served ?? 0).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            totalCount={playback.data?.total ?? 0}
            onPageChange={setPage}
          />
        </TabsContent>
        <TabsContent value="exports">
          <Card className="border-slate-800 bg-slate-900/50">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>Task</TableHead>
                    <TableHead>Variant</TableHead>
                    <TableHead>Watermark</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(exports.data?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-slate-400">
                        No export events.
                      </TableCell>
                    </TableRow>
                  ) : (
                    (exports.data?.items ?? []).map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{formatAdminDateTime(row.created_at)}</TableCell>
                        <TableCell className="font-mono text-xs">{row.user_id}</TableCell>
                        <TableCell>{row.actor}</TableCell>
                        <TableCell className="uppercase">{row.format}</TableCell>
                        <TableCell className="font-mono text-xs">{row.suno_task_id ?? '—'}</TableCell>
                        <TableCell>{row.variant ?? '—'}</TableCell>
                        <TableCell className="font-mono text-xs">{row.watermark_id ?? '—'}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            totalCount={exports.data?.total ?? 0}
            onPageChange={setPage}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
