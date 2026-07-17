import { useState } from 'react';

import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useRetryUploadJob, useStreamingUploadJobs } from '@/hooks/use-streaming';
import { toast } from '@/hooks/use-toast';

export default function StreamingUploadJobsPage() {
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'success' | 'failed'>('all');
  const { data, isLoading, isError, refetch } = useStreamingUploadJobs(
    statusFilter === 'all' ? undefined : statusFilter,
  );
  const retry = useRetryUploadJob();

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Streaming Upload Jobs"
        description="Background uploads triggered from Suno callbacks and image generation."
        actions={
          <div className="flex items-center gap-3">
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as typeof statusFilter)}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refetch()}>
              Refresh
            </Button>
          </div>
        }
      />

      {isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-red-300">Unable to load upload jobs.</p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="space-y-3">
        {(data ?? []).map((job) => (
          <Card key={job.id} className="border-slate-800 bg-slate-900/50">
            <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-slate-100">{job.kind}</p>
                  <Badge
                    variant={
                      job.status === 'failed'
                        ? 'destructive'
                        : job.status === 'success'
                          ? 'default'
                          : 'secondary'
                    }
                  >
                    {job.status}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500">{job.id}</p>
                {job.storage_key ? (
                  <p className="text-xs text-slate-400">{job.storage_key}</p>
                ) : null}
                {job.error ? <p className="text-sm text-red-300">{job.error}</p> : null}
              </div>
              {job.status === 'failed' && String(job.kind).startsWith('mp3_') ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={retry.isPending}
                  onClick={() =>
                    retry.mutate(job.id, {
                      onSuccess: () => toast({ title: 'Upload job retried' }),
                      onError: (err: unknown) => {
                        const axiosError = err as {
                          response?: { data?: { error?: { message?: string } } };
                        };
                        toast({
                          title:
                            axiosError.response?.data?.error?.message ??
                            'Retry failed',
                          variant: 'destructive',
                        });
                      },
                    })
                  }
                >
                  Retry upload
                </Button>
              ) : null}
            </CardContent>
          </Card>
        ))}
        {!isLoading && !isError && (data ?? []).length === 0 ? (
          <Card className="border-slate-800 bg-slate-900/50">
            <CardContent className="p-6 text-sm text-slate-400">No upload jobs found.</CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
