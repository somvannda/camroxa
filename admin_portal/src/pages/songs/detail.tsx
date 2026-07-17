import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAdminSong } from '@/hooks/use-pipeline-trace';

export default function SongDetailPage() {
  const { songId = '' } = useParams();
  const { data, isLoading, isError, error, refetch } = useAdminSong(songId || null);

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load song'}
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
        <h1 className="text-2xl font-bold text-slate-100">Song trace</h1>
        <p className="mt-1 font-mono text-xs text-slate-500">{songId}</p>
      </div>

      {isLoading || !data ? (
        <div className="text-sm text-slate-400">Loading song…</div>
      ) : (
        <Card className="border-slate-800 bg-slate-950/60">
          <CardHeader>
            <CardTitle className="text-slate-100">{data.title || 'Untitled song'}</CardTitle>
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
              <div className="text-slate-500">Batch</div>
              <Link to={`/batches/${data.batch_id}`} className="font-mono text-xs text-blue-400 hover:underline">
                {data.batch_id}
              </Link>
            </div>
            <div>
              <div className="text-slate-500">Batch index</div>
              <div className="text-slate-200">{data.batch_index + 1}</div>
            </div>
            <div>
              <div className="text-slate-500">Status</div>
              <Badge className="mt-1 border-transparent bg-slate-800 text-slate-200">{data.status}</Badge>
            </div>
            <div>
              <div className="text-slate-500">Album</div>
              <div className="text-slate-200">{data.album || '—'}</div>
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
            <div className="md:col-span-2">
              <div className="text-slate-500">Usage for this song</div>
              <Link
                to={`/usage?user_id=${data.user_id}`}
                className="text-sm text-blue-400 hover:underline"
              >
                Filter usage by user
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
