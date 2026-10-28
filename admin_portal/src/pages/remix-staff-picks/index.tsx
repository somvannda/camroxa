import { useState } from 'react';
import { Loader2, Pencil, Plus, RefreshCcw, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { useToast } from '@/hooks/use-toast';
import {
  useCreateRemixStaffPick,
  useDeleteRemixStaffPick,
  useRemixStaffPicks,
  useUpdateRemixStaffPick,
} from '@/hooks/use-remix-staff-picks';
import type { RemixStaffPick, RemixStaffPickInput } from '@/types/remix-staff-picks';

const emptyForm: RemixStaffPickInput = {
  provider_clip_id: '',
  title: '',
  image_url: '',
  styles: '',
  model: 'V6',
  account_id: '',
  sort_order: 0,
  is_active: true,
};

export default function RemixStaffPicksPage() {
  const { toast } = useToast();
  const query = useRemixStaffPicks();
  const create = useCreateRemixStaffPick();
  const update = useUpdateRemixStaffPick();
  const remove = useDeleteRemixStaffPick();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<RemixStaffPick | null>(null);
  const [form, setForm] = useState<RemixStaffPickInput>(emptyForm);

  const items = query.data?.items ?? [];

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  }

  function openEdit(item: RemixStaffPick) {
    setEditing(item);
    setForm({
      provider_clip_id: item.provider_clip_id,
      title: item.title,
      image_url: item.image_url ?? '',
      styles: item.styles ?? '',
      model: item.model ?? 'V6',
      account_id: item.account_id ?? '',
      sort_order: item.sort_order,
      is_active: item.is_active,
    });
    setDialogOpen(true);
  }

  async function save() {
    if (!form.provider_clip_id.trim() || !form.title.trim()) {
      toast({ title: 'Clip ID and title are required', variant: 'destructive' });
      return;
    }
    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, input: form });
        toast({ title: 'Staff pick updated' });
      } else {
        await create.mutateAsync(form);
        toast({ title: 'Staff pick added' });
      }
      setDialogOpen(false);
    } catch (error) {
      toast({
        title: 'Could not save staff pick',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  }

  async function toggleActive(item: RemixStaffPick) {
    try {
      await update.mutateAsync({
        id: item.id,
        input: { is_active: !item.is_active },
      });
    } catch (error) {
      toast({
        title: 'Could not update staff pick',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  }

  async function deleteItem(item: RemixStaffPick) {
    if (!window.confirm(`Remove "${item.title}" from Staff Picks?`)) return;
    try {
      await remove.mutateAsync(item.id);
      toast({ title: 'Staff pick removed' });
    } catch (error) {
      toast({
        title: 'Could not remove staff pick',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Remix Staff Picks</h1>
          <p className="text-sm text-muted-foreground">
            Curated provider clips shown in the Remix picker’s Staff Picks tab.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
            <RefreshCcw className={`h-4 w-4 ${query.isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Add staff pick
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Catalog ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 w-full" />
              ))}
            </div>
          ) : query.isError ? (
            <p className="text-sm text-destructive">
              {query.error instanceof Error ? query.error.message : 'Could not load Staff Picks.'}
            </p>
          ) : items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No Staff Picks yet. Add a provider clip to populate the tab.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Cover</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Provider clip</TableHead>
                  <TableHead>Styles</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Order</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      {item.image_url ? (
                        <img
                          src={item.image_url}
                          alt=""
                          className="h-10 w-10 rounded object-cover"
                        />
                      ) : (
                        <div className="h-10 w-10 rounded bg-muted" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium">{item.title}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">
                      {item.provider_clip_id}
                    </TableCell>
                    <TableCell className="max-w-[240px] truncate text-xs">
                      {item.styles || '—'}
                    </TableCell>
                    <TableCell>{item.model || '—'}</TableCell>
                    <TableCell>{item.sort_order}</TableCell>
                    <TableCell>
                      <button type="button" onClick={() => void toggleActive(item)}>
                        <Badge variant={item.is_active ? 'default' : 'secondary'}>
                          {item.is_active ? 'Active' : 'Hidden'}
                        </Badge>
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" onClick={() => openEdit(item)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => void deleteItem(item)}
                          disabled={remove.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit staff pick' : 'Add staff pick'}</DialogTitle>
            <DialogDescription>
              Use a provider clip ID from a pool-owned song. The public Staff Picks tab
              will show this entry.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="staff-pick-title">Title</Label>
              <Input
                id="staff-pick-title"
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="Song title"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="staff-pick-clip">Provider clip ID</Label>
              <Input
                id="staff-pick-clip"
                value={form.provider_clip_id}
                onChange={(event) =>
                  setForm({ ...form, provider_clip_id: event.target.value })
                }
                placeholder="Suno / musicapi clip UUID"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="staff-pick-image">Cover image URL</Label>
              <Input
                id="staff-pick-image"
                value={form.image_url ?? ''}
                onChange={(event) => setForm({ ...form, image_url: event.target.value })}
                placeholder="https://…"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="staff-pick-account">Pool account</Label>
              <Input
                id="staff-pick-account"
                value={form.account_id ?? ''}
                onChange={(event) => setForm({ ...form, account_id: event.target.value })}
                placeholder="iamduke1987@gmail.com"
              />
              <p className="text-xs text-muted-foreground">
                The musicapi pool account that owns this provider clip.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="staff-pick-styles">Styles / tags</Label>
              <Textarea
                id="staff-pick-styles"
                value={form.styles ?? ''}
                onChange={(event) => setForm({ ...form, styles: event.target.value })}
                placeholder="pop, warm synths, 100 BPM"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="staff-pick-model">Model</Label>
                <Input
                  id="staff-pick-model"
                  value={form.model ?? ''}
                  onChange={(event) => setForm({ ...form, model: event.target.value })}
                  placeholder="V6"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="staff-pick-order">Sort order</Label>
                <Input
                  id="staff-pick-order"
                  type="number"
                  value={form.sort_order ?? 0}
                  onChange={(event) =>
                    setForm({ ...form, sort_order: Number(event.target.value) || 0 })
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="staff-pick-active">Active</Label>
                <label className="flex h-10 items-center gap-2 text-sm">
                  <input
                    id="staff-pick-active"
                    type="checkbox"
                    checked={Boolean(form.is_active)}
                    onChange={(event) =>
                      setForm({ ...form, is_active: event.target.checked })
                    }
                  />
                  Visible in Staff Picks
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void save()} disabled={create.isPending || update.isPending}>
              {create.isPending || update.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              {editing ? 'Save changes' : 'Add staff pick'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
