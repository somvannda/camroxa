import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Loader2, Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';

import {
  useCreateSunoBlocklistTerm,
  useDeleteSunoBlocklistTerm,
  usePromoteSunoBlocklistTerm,
  useSunoBlocklist,
  useSunoFailureMetrics,
  useUpdateSunoBlocklistTerm,
} from '@/hooks/use-suno-blocklist';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import type { SunoBlocklistSeverity, SunoBlocklistTerm } from '@/types/suno-blocklist';

export function SunoBlocklistSection() {
  const [searchParams] = useSearchParams();
  const { data, isLoading, isError, refetch } = useSunoBlocklist();
  const { data: metricsData } = useSunoFailureMetrics(30);
  const createTerm = useCreateSunoBlocklistTerm();
  const updateTerm = useUpdateSunoBlocklistTerm();
  const deleteTerm = useDeleteSunoBlocklistTerm();
  const promoteTerm = usePromoteSunoBlocklistTerm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<SunoBlocklistTerm | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [term, setTerm] = useState('');
  const [replacement, setReplacement] = useState('');
  const [severity, setSeverity] = useState<SunoBlocklistSeverity>('block');
  const [enabled, setEnabled] = useState(true);
  const [notes, setNotes] = useState('');
  const [promoteTermValue, setPromoteTermValue] = useState(() => searchParams.get('term') ?? '');
  const [promoteReplacement, setPromoteReplacement] = useState('');
  const [promoteNotes, setPromoteNotes] = useState('');

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const enabledCount = useMemo(() => items.filter((item) => item.enabled).length, [items]);

  const resetForm = () => {
    setTerm('');
    setReplacement('');
    setSeverity('block');
    setEnabled(true);
    setNotes('');
    setEditTarget(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setDialogOpen(true);
  };

  const openEditDialog = (item: SunoBlocklistTerm) => {
    setEditTarget(item);
    setTerm(item.term);
    setReplacement(item.replacement ?? '');
    setSeverity(item.severity);
    setEnabled(item.enabled);
    setNotes(item.notes ?? '');
    setDialogOpen(true);
  };

  const handleSave = () => {
    const normalizedTerm = term.trim().toLowerCase();
    const normalizedReplacement = replacement.trim() || null;

    if (editTarget) {
      updateTerm.mutate(
        {
          id: editTarget.id,
          patch: {
            term: normalizedTerm,
            replacement: normalizedReplacement,
            severity,
            enabled,
            notes: notes.trim() || null,
            clear_replacement: !normalizedReplacement,
          },
        },
        {
          onSuccess: () => {
            toast({ title: 'Blocklist term updated' });
            setDialogOpen(false);
            resetForm();
          },
          onError: (error: Error) => {
            toast({ title: 'Update failed', description: error.message, variant: 'destructive' });
          },
        },
      );
      return;
    }

    createTerm.mutate(
      {
        term: normalizedTerm,
        replacement: normalizedReplacement,
        severity,
        enabled,
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          toast({ title: 'Blocklist term added' });
          setDialogOpen(false);
          resetForm();
        },
        onError: (error: Error) => {
          toast({ title: 'Failed to add term', description: error.message, variant: 'destructive' });
        },
      },
    );
  };

  const handleToggle = (item: SunoBlocklistTerm, nextEnabled: boolean) => {
    updateTerm.mutate(
      {
        id: item.id,
        patch: { enabled: nextEnabled },
      },
      {
        onSuccess: () => toast({ title: nextEnabled ? 'Term enabled' : 'Term disabled' }),
        onError: (error: Error) => {
          toast({ title: 'Update failed', description: error.message, variant: 'destructive' });
        },
      },
    );
  };

  const handleDelete = () => {
    if (!deleteId) return;
    deleteTerm.mutate(deleteId, {
      onSuccess: () => {
        toast({ title: 'Blocklist term deleted' });
        setDeleteId(null);
      },
      onError: (error: Error) => {
        toast({ title: 'Delete failed', description: error.message, variant: 'destructive' });
      },
    });
  };

  const handlePromote = () => {
    const normalizedTerm = promoteTermValue.trim().toLowerCase();
    if (!normalizedTerm) return;
    promoteTerm.mutate(
      {
        term: normalizedTerm,
        replacement: promoteReplacement.trim() || null,
        severity: 'block',
        notes: promoteNotes.trim() || 'Promoted from admin quick form',
      },
      {
        onSuccess: () => {
          toast({ title: 'Learned term promoted to blocklist' });
          setPromoteTermValue('');
          setPromoteReplacement('');
          setPromoteNotes('');
        },
        onError: (error: Error) => {
          toast({ title: 'Promote failed', description: error.message, variant: 'destructive' });
        },
      },
    );
  };

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (isError) {
    return <Button onClick={() => refetch()}>Retry loading Suno blocklist</Button>;
  }

  return (
    <div className="space-y-4">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Suno Failure Metrics (30d)</CardTitle>
          <CardDescription>
            Failed Suno tasks grouped by failure type and first submit vs retry.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {metricsData?.buckets?.length ? (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {metricsData.buckets.map((bucket) => (
                <div
                  key={`${bucket.failure_type}-${bucket.submit_kind}`}
                  className="rounded-md border border-slate-700 p-3 text-sm"
                >
                  <p className="font-medium text-slate-100">{bucket.failure_type}</p>
                  <p className="text-xs uppercase tracking-wide text-slate-400">{bucket.submit_kind}</p>
                  <p className="mt-1 text-2xl font-semibold text-amber-300">{bucket.count}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No failed Suno tasks in the selected window.</p>
          )}
          <p className="mt-3 text-xs text-slate-500">
            Total failed tasks: {metricsData?.total ?? 0}
          </p>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Promote Learned Term</CardTitle>
          <CardDescription>
            Upsert a Suno-learned block term into the runtime registry (source=learned).
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <Input
            value={promoteTermValue}
            onChange={(e) => setPromoteTermValue(e.target.value)}
            placeholder="blocked term"
          />
          <Input
            value={promoteReplacement}
            onChange={(e) => setPromoteReplacement(e.target.value)}
            placeholder="replacement (optional)"
          />
          <Input
            value={promoteNotes}
            onChange={(e) => setPromoteNotes(e.target.value)}
            placeholder="notes (optional)"
          />
          <Button onClick={handlePromote} disabled={!promoteTermValue.trim() || promoteTerm.isPending}>
            {promoteTerm.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Promote
          </Button>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldAlert className="h-5 w-5 text-amber-400" />
              Suno Blocklist
            </CardTitle>
            <CardDescription>
              Manage Suno lyrics block and warn terms. Enabled terms apply to server-side sanitize/scan and the desktop Music workspace.
            </CardDescription>
          </div>
          <Button onClick={openCreateDialog}>
            <Plus className="mr-2 h-4 w-4" />
            Add Term
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-slate-200">
            <p className="font-medium text-amber-200">Runtime behavior</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-300">
              <li><strong>Block</strong> terms are auto-replaced before Suno submit (replacement or echo fallback).</li>
              <li><strong>Warn</strong> terms flag lyrics in desktop/API scan without mandatory replacement.</li>
              <li>Static code defaults (e.g. lowlight) remain as fallback when DB is unavailable.</li>
            </ul>
            <p className="mt-2 text-xs text-slate-400">
              {enabledCount} of {items.length} terms enabled.
            </p>
          </div>

          {items.length === 0 ? (
            <p className="text-sm text-slate-400">No blocklist terms configured yet.</p>
          ) : null}

          {items.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center gap-4 rounded-md border border-slate-700 p-3"
            >
              <div className="min-w-[140px] flex-1">
                <p className="text-sm font-medium text-slate-100">{item.term}</p>
                <p className="text-xs text-slate-400">
                  {item.replacement ? `→ ${item.replacement}` : 'No replacement'}
                </p>
              </div>
              <div className="text-xs uppercase tracking-wide text-slate-400">{item.severity}</div>
              <div className="text-xs text-slate-400">{item.source}</div>
              <div className="flex items-center gap-2">
                <Label htmlFor={`enabled-${item.id}`} className="text-xs text-slate-300">
                  Enabled
                </Label>
                <input
                  id={`enabled-${item.id}`}
                  type="checkbox"
                  checked={item.enabled}
                  onChange={(event) => handleToggle(item, event.target.checked)}
                  disabled={updateTerm.isPending}
                  className="h-4 w-4 rounded border-slate-600"
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => openEditDialog(item)}
                disabled={updateTerm.isPending}
              >
                <Pencil className="h-4 w-4 text-slate-300" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setDeleteId(item.id)}
                disabled={deleteTerm.isPending}
              >
                <Trash2 className="h-4 w-4 text-red-400" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editTarget ? 'Edit Blocklist Term' : 'Add Blocklist Term'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Term</Label>
              <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="lowlight" />
            </div>
            <div className="space-y-2">
              <Label>Replacement</Label>
              <Input
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
                placeholder="afterglow (optional for warn-only)"
              />
            </div>
            <div className="space-y-2">
              <Label>Severity</Label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as SunoBlocklistSeverity)}
                className="h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100"
              >
                <option value="block">Block</option>
                <option value="warn">Warn</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional admin note" />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                id="blocklist-enabled"
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-slate-600"
              />
              Enabled for runtime sanitize/scan
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!term.trim() || createTerm.isPending || updateTerm.isPending}
            >
              {(createTerm.isPending || updateTerm.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
        title="Delete Blocklist Term"
        description="Delete this Suno blocklist term? Runtime sanitize will stop applying it immediately."
        onConfirm={handleDelete}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteTerm.isPending}
      />
    </div>
  );
}
