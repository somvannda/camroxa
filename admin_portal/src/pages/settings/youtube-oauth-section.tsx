import { useMemo, useState } from 'react';
import { KeyRound, Loader2, Pencil, Plus, ShieldCheck, Trash2 } from 'lucide-react';

import {
  useCreateYouTubeOAuthApp,
  useDeleteYouTubeOAuthApp,
  useUpdateYouTubeOAuthApp,
  useYouTubeOAuthApps,
  type YouTubeOAuthApp,
} from '@/hooks/use-youtube-oauth-apps';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

type AppFormState = {
  name: string;
  clientId: string;
  clientSecret: string;
  isDefault: boolean;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return '—';
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
}

function buildFormState(app?: YouTubeOAuthApp | null): AppFormState {
  return {
    name: app?.name ?? '',
    clientId: app?.client_id ?? '',
    clientSecret: '',
    isDefault: app?.is_default ?? false,
  };
}

export function YouTubeOAuthSection() {
  const { data, isLoading, isError, refetch } = useYouTubeOAuthApps();
  const createMutation = useCreateYouTubeOAuthApp();
  const updateMutation = useUpdateYouTubeOAuthApp();
  const deleteMutation = useDeleteYouTubeOAuthApp();

  const apps = data?.apps ?? [];
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<YouTubeOAuthApp | null>(null);
  const [editingApp, setEditingApp] = useState<YouTubeOAuthApp | null>(null);
  const [form, setForm] = useState<AppFormState>(buildFormState());

  const sortedApps = useMemo(
    () => [...apps].sort((a, b) => Number(b.is_default) - Number(a.is_default) || a.name.localeCompare(b.name)),
    [apps],
  );

  const resetEditor = (app?: YouTubeOAuthApp | null) => {
    setEditingApp(app ?? null);
    setForm(buildFormState(app));
    setEditorOpen(true);
  };

  const handleSave = () => {
    if (!form.name.trim() || !form.clientId.trim() || (!editingApp && !form.clientSecret.trim())) {
      return;
    }

    if (editingApp) {
      updateMutation.mutate(
        {
          id: editingApp.id,
          name: form.name.trim(),
          client_id: form.clientId.trim(),
          client_secret: form.clientSecret.trim() || undefined,
          is_default: form.isDefault,
        },
        {
          onSuccess: () => {
            toast({ title: `Updated "${form.name.trim()}"` });
            setEditorOpen(false);
            setEditingApp(null);
          },
        },
      );
      return;
    }

    createMutation.mutate(
      {
        name: form.name.trim(),
        client_id: form.clientId.trim(),
        client_secret: form.clientSecret.trim(),
        is_default: form.isDefault,
      },
      {
        onSuccess: () => {
          toast({ title: `Created "${form.name.trim()}"` });
          setEditorOpen(false);
          setEditingApp(null);
        },
      },
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast({ title: `Deleted "${deleteTarget.name}"` });
        setDeleteTarget(null);
      },
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center justify-between gap-4 p-6">
          <div>
            <p className="text-sm font-medium text-slate-100">Unable to load YouTube OAuth apps</p>
            <p className="text-xs text-slate-400">Check backend connectivity and admin auth, then retry.</p>
          </div>
          <Button onClick={() => refetch()}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle className="text-lg text-slate-100">YouTube OAuth Apps</CardTitle>
            <p className="mt-1 text-sm text-slate-400">
              Manage Google OAuth apps for backend-mediated channel connection. Secrets stay admin-only and never appear in the user app.
            </p>
          </div>
          <Button onClick={() => resetEditor()}>
            <Plus className="mr-2 h-4 w-4" />
            New OAuth App
          </Button>
        </CardHeader>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-base text-slate-100">Configured Apps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {sortedApps.length ? (
              sortedApps.map((app) => (
                <div key={app.id} className="flex items-start gap-4 rounded-lg border border-slate-700 p-4">
                  <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10 text-red-300">
                    <KeyRound className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-100">{app.name}</p>
                      {app.is_default ? (
                        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                          Default
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 break-all text-xs text-slate-400">{app.client_id}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        {app.has_client_secret ? 'Secret configured' : 'Secret missing'}
                      </span>
                      <span>Updated {formatTimestamp(app.updated_at)}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="icon" variant="ghost" onClick={() => resetEditor(app)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setDeleteTarget(app)}>
                      <Trash2 className="h-4 w-4 text-red-400" />
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed border-slate-700 p-6 text-sm text-slate-400">
                No YouTube OAuth apps configured yet.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-base text-slate-100">Usage Notes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-300">
            <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
              <p className="font-medium text-slate-100">Admin-only visibility</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                Client credentials live here only. The Electron user app should expose connect/disconnect status and validated channel identity only.
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
              <p className="font-medium text-slate-100">Google redirect URI</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                In Google Cloud Console → OAuth client → Authorized redirect URIs, add your public API callback exactly:
              </p>
              <code className="mt-2 block break-all rounded bg-slate-900 px-2 py-1 text-[11px] text-emerald-300">
                https://api.sandbox.camxora.com/api/v3/youtube/oauth/callback
              </code>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Production uses <span className="text-slate-300">https://api.camxora.com/api/v3/youtube/oauth/callback</span>.
                Do not register the user portal host (<span className="text-slate-300">app.*</span>) — OAuth must hit the API domain.
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
              <p className="font-medium text-slate-100">Backend-mediated connect flow</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                The backend should select the active OAuth app, run Google auth, then validate channels using the returned account before marking a profile connected.
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
              <p className="font-medium text-slate-100">Default app</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                Mark one app as default so the user-facing connect flow can run without exposing credential choices in the desktop app.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingApp ? 'Edit YouTube OAuth App' : 'New YouTube OAuth App'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>App Name</Label>
              <Input value={form.name} onChange={(e) => setForm((current) => ({ ...current, name: e.target.value }))} placeholder="Studio Google OAuth" />
            </div>
            <div className="space-y-2">
              <Label>Client ID</Label>
              <Input
                value={form.clientId}
                onChange={(e) => setForm((current) => ({ ...current, clientId: e.target.value }))}
                placeholder="Google client id"
              />
            </div>
            <div className="space-y-2">
              <Label>{editingApp ? 'Replace Client Secret' : 'Client Secret'}</Label>
              <Input
                type="password"
                value={form.clientSecret}
                onChange={(e) => setForm((current) => ({ ...current, clientSecret: e.target.value }))}
                placeholder={editingApp ? 'Leave blank to keep current secret' : 'Google client secret'}
              />
            </div>
            <label className="flex items-center gap-3 rounded-md border border-slate-700 p-3 text-sm text-slate-200">
              <input
                checked={form.isDefault}
                className="h-4 w-4"
                type="checkbox"
                onChange={(e) => setForm((current) => ({ ...current, isDefault: e.target.checked }))}
              />
              Mark as default OAuth app
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={
                !form.name.trim() ||
                !form.clientId.trim() ||
                (!editingApp && !form.clientSecret.trim()) ||
                createMutation.isPending ||
                updateMutation.isPending
              }
              onClick={handleSave}
            >
              {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete YouTube OAuth App"
        description={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmText="Delete"
        variant="destructive"
        isLoading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
