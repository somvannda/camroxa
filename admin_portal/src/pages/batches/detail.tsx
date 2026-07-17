import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAdminBatch } from '@/hooks/use-pipeline-trace';
import { truncateId } from '@/lib/usage-labels';

export default function BatchDetailPage() {
  const { batchId = '' } = useParams();
  const { data, isLoading, isError, error, refetch } = useAdminBatch(batchId || null);

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load batch'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="sm" className="text-slate-400 hover:text-slate-200">
          <Link to="/usage">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to usage
          </Link>
        </Button>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-slate-100">Batch trace</h1>
        <p className="mt-1 font-mono text-xs text-slate-500">{batchId}</p>
      </div>

      {isLoading || !data ? (
        <div className="text-sm text-slate-400">Loading batch…</div>
      ) : (
        <>
          <Card className="border-slate-800 bg-slate-950/60">
            <CardHeader>
              <CardTitle className="text-slate-100">Overview</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm md:grid-cols-2">
              <div>
                <div className="text-slate-500">User</div>
                <Link to={`/users/${data.user_id}`} className="text-blue-400 hover:underline">
                  {data.user_display_name || data.user_email}
                </Link>
                <div className="text-xs text-slate-500">{data.user_email}</div>
              </div>
              <div>
                <div className="text-slate-500">Status</div>
                <Badge className="mt-1 border-transparent bg-slate-800 text-slate-200">{data.status}</Badge>
              </div>
              <div>
                <div className="text-slate-500">Songs</div>
                <div className="text-slate-200">{data.songs.length} / {data.song_count}</div>
              </div>
              <div>
                <div className="text-slate-500">Language</div>
                <div className="text-slate-200">{data.language}</div>
              </div>
              <div>
                <div className="text-slate-500">Created</div>
                <div className="text-slate-200">
                  {data.created_at ? new Date(data.created_at).toLocaleString() : '—'}
                </div>
              </div>
              <div>
                <div className="text-slate-500">Updated</div>
                <div className="text-slate-200">
                  {data.updated_at ? new Date(data.updated_at).toLocaleString() : '—'}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-slate-950/60">
            <CardHeader>
              <CardTitle className="text-slate-100">Songs</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800">
                    <TableHead className="text-slate-400">#</TableHead>
                    <TableHead className="text-slate-400">Song</TableHead>
                    <TableHead className="text-slate-400">Title</TableHead>
                    <TableHead className="text-slate-400">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.songs.map((song) => (
                    <TableRow key={song.id} className="border-slate-800">
                      <TableCell className="text-slate-300">{song.batch_index + 1}</TableCell>
                      <TableCell>
                        <Link
                          to={`/songs/${song.id}`}
                          className="font-mono text-xs text-blue-400 hover:underline"
                          title={song.id}
                        >
                          {truncateId(song.id, 12)}
                        </Link>
                      </TableCell>
                      <TableCell className="text-slate-200">{song.title || '—'}</TableCell>
                      <TableCell className="text-slate-400">{song.status}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
