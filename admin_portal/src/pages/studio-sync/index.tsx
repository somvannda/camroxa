import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, RefreshCw } from 'lucide-react';

import { ErrorState } from '@/components/shared/error-state';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import httpClient from '@/lib/http-client';

/**
 * Operations view of the Suno Studio project mirror.
 *
 * The mirror lives in musicapi; the platform forwards its health payload so
 * operators can see link states, outbox pressure, pinned accounts and the
 * field-coverage registry without touching the provider directly.
 */
type StudioSyncHealth = {
  configured: boolean;
  ok: boolean;
  projects?: Record<string, number>;
  outbox?: { due: number; total: number };
  pinned_accounts?: Array<{ account_label: string; users: number }>;
  coverage?: { mapped: number; pending: number; remove: number; pending_keys: string[] };
  state_sync?: boolean;
};

export default function StudioSyncPage() {
  const [backfilling, setBackfilling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['studio-sync-health'],
    queryFn: () => httpClient.get<StudioSyncHealth>('/api/v3/admin/studio-sync'),
    refetchInterval: 30_000,
  });

  async function backfill() {
    setBackfilling(true);
    setNotice(null);
    try {
      const result = await httpClient.post<{ scanned: number; queued: number }>(
        '/api/v3/admin/studio-sync/backfill?limit=20',
      );
      setNotice(`Queued ${result.queued} of ${result.scanned} project(s) for linking.`);
      await refetch();
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Backfill failed.');
    } finally {
      setBackfilling(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Could not load mirror health.'}
        onRetry={() => void refetch()}
      />
    );
  }

  const projects = data?.projects ?? {};
  const coverage = data?.coverage;
  const outbox = data?.outbox;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Studio Sync</h1>
          <p className="mt-1 text-sm text-slate-400">
            Suno Studio project mirror: links, retries and field coverage.
          </p>
        </div>
        <Button variant="outline" onClick={() => void refetch()} disabled={isFetching}>
          <RefreshCw className={`mr-2 h-4 w-4${isFetching ? ' animate-spin' : ''}`} />
          Refresh
        </Button>
        <Button variant="outline" onClick={() => void backfill()} disabled={backfilling}>
          {backfilling ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Backfill 20
        </Button>
      </div>

      {notice ? (
        <p className="rounded-md border border-slate-800 bg-slate-900/60 px-4 py-2 text-sm text-slate-300">
          {notice}
        </p>
      ) : null}

      {!data?.configured ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-6 text-sm text-slate-300">
            The mirror is not configured: set <code>PLATFORM_SUNO_API_BASE_URL</code> and{' '}
            <code>PLATFORM_STUDIO_INTERNAL_TOKEN</code>.
          </CardContent>
        </Card>
      ) : !data?.ok ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-6 text-sm text-slate-300">
            musicapi did not answer the mirror health check. Projects keep saving locally and the
            outbox retries once it returns.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader>
                <CardTitle className="text-sm text-slate-400">Projects</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-slate-200">
                {Object.keys(projects).length === 0 ? (
                  <span className="text-slate-400">No links yet</span>
                ) : (
                  Object.entries(projects).map(([status, count]) => (
                    <div key={status} className="flex justify-between">
                      <span className="capitalize">{status}</span>
                      <span className="tabular-nums">{count}</span>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader>
                <CardTitle className="text-sm text-slate-400">Outbox</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-slate-200">
                <div className="flex justify-between">
                  <span>Due now</span>
                  <span className="tabular-nums">{outbox?.due ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Queued</span>
                  <span className="tabular-nums">{outbox?.total ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Arrangement writes</span>
                  <span>{data.state_sync ? 'enabled' : 'paused'}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader>
                <CardTitle className="text-sm text-slate-400">Field coverage</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-slate-200">
                <div className="flex justify-between">
                  <span>Mapped</span>
                  <span className="tabular-nums">{coverage?.mapped ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pending</span>
                  <span className="tabular-nums">{coverage?.pending ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Removed</span>
                  <span className="tabular-nums">{coverage?.remove ?? 0}</span>
                </div>
                {coverage?.pending_keys?.length ? (
                  <p className="pt-1 text-xs text-slate-400">
                    Pending: {coverage.pending_keys.join(', ')}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card className="border-slate-800 bg-slate-900/50">
            <CardHeader>
              <CardTitle className="text-sm text-slate-400">Pinned accounts</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-200">
              {(data.pinned_accounts ?? []).length === 0 ? (
                <span className="text-slate-400">No account has been pinned yet.</span>
              ) : (
                <ul className="space-y-1">
                  {(data.pinned_accounts ?? []).map((account) => (
                    <li key={account.account_label} className="flex justify-between">
                      <span>{account.account_label}</span>
                      <span className="tabular-nums text-slate-400">
                        {account.users} user{account.users === 1 ? '' : 's'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
