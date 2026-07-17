import { useMemo, useState } from 'react';
import { Copy, Plus, RefreshCcw, Search, Shield, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { LoadingSkeleton } from '@/components/shared/loading-skeleton';
import { PageHeader } from '@/components/shared/page-header';
import { toast } from '@/hooks/use-toast';
import {
  useCreateInvitationCode,
  useDeleteInvitationCode,
  useInvitationCodes,
  useSignupMode,
  useUpdateInvitationCode,
  useUpdateSignupMode,
} from '@/hooks/use-invitations';
import type { InvitationCodeAdminItem, InvitationCodeCreateResponse } from '@/types/models';

type InviteFormState = {
  label: string;
  maxUses: string;
  expiresAt: string;
  isActive: boolean;
};

type InvitationFilter = 'all' | 'active' | 'inactive' | 'expired' | 'used_up' | 'legacy';

function createDefaultForm(): InviteFormState {
  return {
    label: '',
    maxUses: '1',
    expiresAt: '',
    isActive: true,
  };
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function usageLabel(item: InvitationCodeAdminItem): string {
  return `${item.current_uses.toLocaleString()} / ${item.max_uses.toLocaleString()}`;
}

function invitationDisplayCode(item: InvitationCodeAdminItem): string {
  return item.code ?? `...${item.code_hint}`;
}

function getInvitationState(item: InvitationCodeAdminItem): InvitationFilter {
  if (!item.code) return 'legacy';
  if (!item.is_active) return 'inactive';
  const expiresAt = item.expires_at ? new Date(item.expires_at) : null;
  if (expiresAt && !Number.isNaN(expiresAt.getTime()) && expiresAt.getTime() < Date.now()) {
    return 'expired';
  }
  if ((item.remaining_uses ?? 0) <= 0) {
    return 'used_up';
  }
  return 'active';
}

function getInvitationStateLabel(state: InvitationFilter): string {
  switch (state) {
    case 'active':
      return 'Active';
    case 'inactive':
      return 'Inactive';
    case 'expired':
      return 'Expired';
    case 'used_up':
      return 'Used up';
    case 'legacy':
      return 'Legacy';
    default:
      return 'All';
  }
}

function getInvitationStateBadgeClass(state: InvitationFilter): string {
  switch (state) {
    case 'active':
      return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300';
    case 'inactive':
      return 'border-slate-700 bg-slate-800 text-slate-300';
    case 'expired':
      return 'border-amber-400/25 bg-amber-500/10 text-amber-300';
    case 'used_up':
      return 'border-rose-400/25 bg-rose-500/10 text-rose-300';
    case 'legacy':
      return 'border-violet-400/25 bg-violet-500/10 text-violet-200';
    default:
      return 'border-slate-700 bg-slate-800 text-slate-300';
  }
}

export default function InvitationsPage() {
  const modeQuery = useSignupMode();
  const updateMode = useUpdateSignupMode();
  const codesQuery = useInvitationCodes();
  const createCode = useCreateInvitationCode();
  const updateCode = useUpdateInvitationCode();
  const deleteCode = useDeleteInvitationCode();

  const [createOpen, setCreateOpen] = useState(false);
  const [created, setCreated] = useState<InvitationCodeCreateResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<InvitationCodeAdminItem | null>(null);
  const [editing, setEditing] = useState<InvitationCodeAdminItem | null>(null);
  const [form, setForm] = useState<InviteFormState>(createDefaultForm);
  const [searchValue, setSearchValue] = useState('');
  const [filterValue, setFilterValue] = useState<InvitationFilter>('all');
  const items = codesQuery.data ?? [];

  const signupModeValue = modeQuery.data?.mode ?? 'invite_only';
  const canSaveMode = !updateMode.isPending && !modeQuery.isLoading;

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [items]);

  const filteredItems = useMemo(() => {
    const normalizedSearch = searchValue.trim().toLowerCase();

    return sortedItems.filter((item) => {
      const state = getInvitationState(item);
      if (filterValue !== 'all' && state !== filterValue) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      return [
        item.label ?? '',
        item.id,
        item.code ?? '',
        item.code_hint,
        invitationDisplayCode(item),
        getInvitationStateLabel(state),
      ]
        .join(' ')
        .toLowerCase()
        .includes(normalizedSearch);
    });
  }, [filterValue, searchValue, sortedItems]);

  function openCreate() {
    setEditing(null);
    setForm(createDefaultForm());
    setCreateOpen(true);
  }

  function openEdit(item: InvitationCodeAdminItem) {
    setEditing(item);
    setForm({
      label: item.label ?? '',
      maxUses: String(item.max_uses),
      expiresAt: item.expires_at ? item.expires_at.slice(0, 16) : '',
      isActive: item.is_active,
    });
    setCreateOpen(true);
  }

  function closeDialog() {
    if (createCode.isPending || updateCode.isPending) return;
    setCreateOpen(false);
    setEditing(null);
    setForm(createDefaultForm());
  }

  function copyToClipboard(value: string) {
    navigator.clipboard.writeText(value).then(
      () => toast({ title: 'Copied' }),
      () => toast({ title: 'Copy failed', variant: 'destructive' }),
    );
  }

  function submitForm() {
    const payload = {
      label: form.label.trim() ? form.label.trim() : null,
      max_uses: Number.parseInt(form.maxUses || '1', 10),
      expires_at: form.expiresAt ? new Date(form.expiresAt).toISOString() : null,
      is_active: form.isActive,
    };

    if (editing) {
      updateCode.mutate(
        { id: editing.id, payload },
        {
          onSuccess: () => {
            toast({ title: 'Invitation updated' });
            closeDialog();
          },
          onError: (err) => {
            toast({
              title: 'Update failed',
              description: err instanceof Error ? err.message : 'Unable to update invitation',
              variant: 'destructive',
            });
          },
        },
      );
      return;
    }

    createCode.mutate(payload, {
      onSuccess: (result) => {
        toast({ title: 'Invitation created' });
        setCreated(result);
        closeDialog();
      },
      onError: (err) => {
        toast({
          title: 'Create failed',
          description: err instanceof Error ? err.message : 'Unable to create invitation',
          variant: 'destructive',
        });
      },
    });
  }

  function confirmDelete() {
    if (!deleteTarget) return;
    deleteCode.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast({ title: 'Invitation deleted' });
        setDeleteTarget(null);
      },
      onError: (err) => {
        toast({
          title: 'Delete failed',
          description: err instanceof Error ? err.message : 'Unable to delete invitation',
          variant: 'destructive',
        });
      },
    });
  }

  function saveMode(mode: 'open' | 'invite_only') {
    updateMode.mutate(
      { mode },
      {
        onSuccess: () => toast({ title: 'Signup mode updated' }),
        onError: (err) =>
          toast({
            title: 'Unable to update mode',
            description: err instanceof Error ? err.message : 'Failed to update signup mode',
            variant: 'destructive',
          }),
      },
    );
  }

  if (codesQuery.isLoading || modeQuery.isLoading) {
    return <LoadingSkeleton />;
  }

  if (codesQuery.isError) {
    return <ErrorState message={codesQuery.error.message} onRetry={() => codesQuery.refetch()} />;
  }

  if (modeQuery.isError) {
    return <ErrorState message={modeQuery.error.message} onRetry={() => modeQuery.refetch()} />;
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Access control"
        title="Invitations"
        description="Control private registration, manage invitation inventory, and keep onboarding limited to approved testers."
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Create invitation
          </Button>
        }
      />

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-slate-100">
              <Shield className="h-4 w-4 text-slate-300" />
              Signup access
            </CardTitle>
            <div className="text-sm text-slate-400">
              Switch between open signup and invitation-only mode.
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select
              value={signupModeValue}
              onValueChange={(value) => saveMode(value as 'open' | 'invite_only')}
              disabled={!canSaveMode}
            >
              <SelectTrigger className="w-56 border-slate-800 bg-slate-950/60 text-slate-100">
                <SelectValue placeholder="Select signup mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="invite_only">Invitation only</SelectItem>
                <SelectItem value="open">Open signup</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              onClick={() => {
                modeQuery.refetch();
                codesQuery.refetch();
              }}
              className="border-slate-800 bg-slate-950/60"
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-slate-300">
            Current mode:{' '}
            <span className="font-medium text-white">
              {signupModeValue === 'invite_only' ? 'Invitation only' : 'Open signup'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-slate-100">Invitation codes</CardTitle>
          <div className="text-sm text-slate-400">
            {filteredItems.length.toLocaleString()} shown
            {filteredItems.length !== sortedItems.length
              ? ` of ${sortedItems.length.toLocaleString()}`
              : ''}
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="grid flex-1 gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <Input
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  placeholder="Search by code, label, ID, or state"
                  className="pl-10"
                />
              </div>
              <Select
                value={filterValue}
                onValueChange={(value) => setFilterValue(value as InvitationFilter)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                  <SelectItem value="used_up">Used up</SelectItem>
                  <SelectItem value="legacy">Legacy</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {(searchValue || filterValue !== 'all') && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSearchValue('');
                    setFilterValue('all');
                  }}
                >
                  Clear filters
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => {
                  modeQuery.refetch();
                  codesQuery.refetch();
                }}
              >
                <RefreshCcw className="h-4 w-4" />
                Refresh list
              </Button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-3 font-medium">Code</th>
                  <th className="pb-3 font-medium">Label</th>
                  <th className="pb-3 font-medium">Usage</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Expiry</th>
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const state = getInvitationState(item);
                  return (
                    <tr key={item.id} className="border-b border-slate-900/80 text-slate-200">
                      <td className="py-4">
                        <div className="flex items-center gap-2">
                          <div className="font-mono text-xs text-white">{invitationDisplayCode(item)}</div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => item.code && copyToClipboard(item.code)}
                            disabled={!item.code}
                            className="h-7 px-2"
                          >
                            <Copy className="h-3.5 w-3.5" />
                            Copy
                          </Button>
                        </div>
                        <div className="text-xs text-slate-500">{item.id}</div>
                        {!item.code ? (
                          <div className="text-xs text-amber-300/80">
                            Legacy code only shows its hint. Create a new code to enable copy.
                          </div>
                        ) : null}
                      </td>
                      <td className="py-4 text-slate-300">{item.label ?? '—'}</td>
                      <td className="py-4 text-slate-300">
                        {usageLabel(item)}
                        <div className="text-xs text-slate-500">
                          Remaining: {item.remaining_uses?.toLocaleString() ?? '—'}
                        </div>
                      </td>
                      <td className="py-4">
                        <Badge className={getInvitationStateBadgeClass(state)}>
                          {getInvitationStateLabel(state)}
                        </Badge>
                      </td>
                      <td className="py-4 text-slate-300">{formatDateTime(item.expires_at)}</td>
                      <td className="py-4 text-slate-300">{formatDateTime(item.created_at)}</td>
                      <td className="py-4">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                            Edit
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => setDeleteTarget(item)}>
                            <Trash2 className="h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-sm text-slate-500">
                      {sortedItems.length === 0
                        ? 'No invitation codes created yet. Create the first code to begin private onboarding.'
                        : 'No invitation codes match the current filters.'}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={(open) => (open ? setCreateOpen(true) : closeDialog())}>
        <DialogContent className="border-slate-800 bg-slate-950 text-slate-100">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit invitation' : 'Create invitation'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="label">Label</Label>
              <Input
                id="label"
                value={form.label}
                onChange={(e) => setForm((prev) => ({ ...prev, label: e.target.value }))}
                className="border-slate-800 bg-slate-950/60"
                placeholder="e.g. Private beta - creator cohort"
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="maxUses">Max uses</Label>
                <Input
                  id="maxUses"
                  type="number"
                  min={1}
                  value={form.maxUses}
                  onChange={(e) => setForm((prev) => ({ ...prev, maxUses: e.target.value }))}
                  className="border-slate-800 bg-slate-950/60"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="expiresAt">Expires at (optional)</Label>
                <Input
                  id="expiresAt"
                  type="datetime-local"
                  value={form.expiresAt}
                  onChange={(e) => setForm((prev) => ({ ...prev, expiresAt: e.target.value }))}
                  className="border-slate-800 bg-slate-950/60"
                />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <div>
                <div className="text-sm font-medium text-white">Active</div>
                <div className="text-xs text-slate-400">
                  Inactive codes cannot be used for signup.
                </div>
              </div>
              <Button
                variant={form.isActive ? 'default' : 'outline'}
                onClick={() => setForm((prev) => ({ ...prev, isActive: !prev.isActive }))}
              >
                {form.isActive ? 'Enabled' : 'Disabled'}
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              onClick={submitForm}
              disabled={createCode.isPending || updateCode.isPending}
            >
              {createCode.isPending || updateCode.isPending
                ? 'Saving...'
                : editing
                  ? 'Save changes'
                  : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!created} onOpenChange={(open) => (!open ? setCreated(null) : null)}>
        <DialogContent className="border-slate-800 bg-slate-950 text-slate-100">
          <DialogHeader>
            <DialogTitle>Invitation code created</DialogTitle>
          </DialogHeader>
          {created ? (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-500">Code</div>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                  <div className="font-mono text-lg text-white">{created.code}</div>
                  <Button variant="outline" size="sm" onClick={() => copyToClipboard(created.code)}>
                    <Copy className="h-4 w-4" />
                    Copy
                  </Button>
                </div>
                <div className="mt-2 text-xs text-slate-400">This code is also visible in the invitation list for admins.</div>
              </div>
              <div className="text-sm text-slate-300">
                Hint: …{created.code_hint} • Max uses: {created.max_uses.toLocaleString()}
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setCreated(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => (!open ? setDeleteTarget(null) : null)}
        title="Delete invitation?"
        description={`This permanently removes invitation ${deleteTarget ? invitationDisplayCode(deleteTarget) : '—'} and cannot be undone.`}
        onConfirm={confirmDelete}
        variant="destructive"
        confirmText={deleteCode.isPending ? 'Deleting...' : 'Delete invitation'}
        isLoading={deleteCode.isPending}
      />
    </div>
  );
}
