import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useStreamingConfig, useUpdateStreamingConfig } from '@/hooks/use-streaming';
import { toast } from '@/hooks/use-toast';

export function StreamingStorageSection() {
  const { data, isLoading, isError, refetch } = useStreamingConfig();
  const updateConfig = useUpdateStreamingConfig();
  const [form, setForm] = useState({
    key_id: '',
    application_key: '',
    bucket: 'camxora-media',
    region: 'us-west-004',
    endpoint: '',
    cdn_base_url: 'https://media.camxora.com',
    stream_url_ttl_seconds: 3600,
  });

  useEffect(() => {
    if (!data) return;
    setForm((current) => ({
      ...current,
      bucket: data.bucket,
      region: data.region,
      endpoint: data.endpoint,
      cdn_base_url: data.cdn_base_url,
      stream_url_ttl_seconds: data.stream_url_ttl_seconds,
    }));
  }, [data]);

  const save = () => {
    if (!form.key_id.trim() && !data?.configured) {
      toast({ title: 'Application Key ID is required', variant: 'destructive' });
      return;
    }
    if (!form.application_key.trim() && !data?.configured) {
      toast({ title: 'Application Key is required for the first save', variant: 'destructive' });
      return;
    }

    updateConfig.mutate(form, {
      onSuccess: () => {
        toast({ title: 'Backblaze streaming settings saved' });
        setForm((current) => ({ ...current, key_id: '', application_key: '' }));
      },
      onError: (err: unknown) => {
        const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
        toast({
          title: axiosError.response?.data?.error?.message ?? 'Unable to save streaming settings',
          variant: 'destructive',
        });
      },
    });
  };

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center gap-2 p-6 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading streaming storage settings…
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="space-y-3 p-6">
          <p className="text-sm text-red-300">Unable to load streaming settings.</p>
          <Button variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Backblaze / CDN Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-300">
          <p>Status: {data?.configured ? 'Configured' : 'Not configured'}</p>
          <p className="text-slate-400">
            Key ID: {data?.key_id_masked || '—'} · App key: {data?.application_key_masked || '—'} · Source:{' '}
            {data?.secret_source || 'none'}
          </p>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Streaming Storage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-400">
            Keys are stored server-side only. Used to upload completed Suno tracks and covers for music.camxora.com.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>
                Application Key ID
                {data?.configured ? ' (leave blank to keep current)' : ''}
              </Label>
              <Input
                value={form.key_id}
                onChange={(e) => setForm({ ...form, key_id: e.target.value })}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label>
                Application Key
                {data?.configured ? ' (leave blank to keep current)' : ''}
              </Label>
              <Input
                type="password"
                value={form.application_key}
                onChange={(e) => setForm({ ...form, application_key: e.target.value })}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label>Bucket</Label>
              <Input value={form.bucket} onChange={(e) => setForm({ ...form, bucket: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Region</Label>
              <Input value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>S3 Endpoint</Label>
              <Input
                value={form.endpoint}
                onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                placeholder="https://s3.us-west-004.backblazeb2.com"
              />
            </div>
            <div className="space-y-2">
              <Label>CDN Base URL</Label>
              <Input
                value={form.cdn_base_url}
                onChange={(e) => setForm({ ...form, cdn_base_url: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Stream URL TTL (seconds)</Label>
              <Input
                type="number"
                value={form.stream_url_ttl_seconds}
                onChange={(e) =>
                  setForm({ ...form, stream_url_ttl_seconds: Number(e.target.value || 3600) })
                }
              />
            </div>
          </div>
          <Button onClick={save} disabled={updateConfig.isPending}>
            {updateConfig.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              'Save streaming settings'
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
