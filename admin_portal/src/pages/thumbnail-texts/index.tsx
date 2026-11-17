import { useMemo, useRef, useState } from 'react';
import {
  Edit3,
  Loader2,
  Plus,
  RefreshCcw,
  Trash2,
  Upload,
} from 'lucide-react';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import {
  useCreateThumbnailText,
  useDeleteAllThumbnailTexts,
  useDeleteThumbnailText,
  useImportThumbnailTexts,
  useThumbnailTexts,
  useUpdateThumbnailText,
} from '@/hooks/use-thumbnail-texts';
import type {
  ThumbnailTextCreateRequest,
  ThumbnailTextRecord,
} from '@/types/thumbnail-texts';

type FormState = {
  title: string;
  subtitle: string;
  subline: string;
  placement: string;
  alignment: string;
  style_hint: string;
  is_active: boolean;
  sort_order: string;
  notes: string;
};

const PLACEMENTS = [
  { value: 'top_center', label: 'Top center' },
  { value: 'center', label: 'Center' },
  { value: 'bottom_center', label: 'Bottom center' },
];

const ALIGNMENTS = [
  { value: 'center', label: 'Center' },
  { value: 'left', label: 'Left' },
  { value: 'right', label: 'Right' },
];

function emptyForm(): FormState {
  return {
    title: '',
    subtitle: '',
    subline: '',
    placement: 'top_center',
    alignment: 'center',
    style_hint: '',
    is_active: true,
    sort_order: '0',
    notes: '',
  };
}

function toForm(record: ThumbnailTextRecord): FormState {
  return {
    title: record.title,
    subtitle: record.subtitle ?? '',
    subline: record.subline ?? '',
    placement: record.placement,
    alignment: record.alignment,
    style_hint: record.style_hint ?? '',
    is_active: record.is_active,
    sort_order: String(record.sort_order ?? 0),
    notes: record.notes ?? '',
  };
}

export default function ThumbnailTextsPage() {
  const { toast } = useToast();
  const query = useThumbnailTexts();
  const createMutation = useCreateThumbnailText();
  const updateMutation = useUpdateThumbnailText();
  const deleteMutation = useDeleteThumbnailText();
  const deleteAllMutation = useDeleteAllThumbnailTexts();
  const importMutation = useImportThumbnailTexts();
  const importFileRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<FormState>(() => emptyForm());
  const [createOpen, setCreateOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<ThumbnailTextRecord | null>(null);
  const [deleteRecord, setDeleteRecord] = useState<ThumbnailTextRecord | null>(null);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const items = useMemo(
    () =>
      [...(query.data?.items ?? [])].sort((a, b) => {
        const byOrder = (a.sort_order ?? 0) - (b.sort_order ?? 0);
        return byOrder !== 0 ? byOrder : a.title.localeCompare(b.title);
      }),
    [query.data],
  );

  const dialogOpen = createOpen || Boolean(editRecord);
  const isEditing = Boolean(editRecord);
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  const openCreate = () => {
    setForm(emptyForm());
    setEditRecord(null);
    setCreateOpen(true);
  };

  const openEdit = (record: ThumbnailTextRecord) => {
    setForm(toForm(record));
    setEditRecord(record);
    setCreateOpen(false);
  };

  const closeDialog = () => {
    setCreateOpen(false);
    setEditRecord(null);
  };

  const buildPayload = (): ThumbnailTextCreateRequest | null => {
    const title = form.title.trim();
    if (!title) {
      toast({ title: 'Title is required', variant: 'destructive' });
      return null;
    }
    return {
      title,
      subtitle: form.subtitle.trim() || null,
      subline: form.subline.trim() || null,
      placement: form.placement,
      alignment: form.alignment,
      style_hint: form.style_hint.trim() || null,
      is_active: form.is_active,
      sort_order: Number(form.sort_order || 0),
      notes: form.notes.trim() || null,
    };
  };

  const handleSave = async () => {
    const payload = buildPayload();
    if (!payload) return;
    try {
      if (editRecord) {
        await updateMutation.mutateAsync({ id: editRecord.id, patch: payload });
        toast({ title: 'Thumbnail text updated' });
      } else {
        await createMutation.mutateAsync(payload);
        toast({ title: 'Thumbnail text created' });
      }
      closeDialog();
    } catch {
      toast({ title: 'Unable to save thumbnail text', variant: 'destructive' });
    }
  };

  const handleDelete = async () => {
    if (!deleteRecord) return;
    try {
      await deleteMutation.mutateAsync(deleteRecord.id);
      toast({ title: 'Thumbnail text deleted' });
      setDeleteRecord(null);
    } catch {
      toast({ title: 'Unable to delete thumbnail text', variant: 'destructive' });
    }
  };

  const handleDeleteAll = async () => {
    try {
      const result = await deleteAllMutation.mutateAsync();
      toast({ title: `Deleted ${result.deleted} thumbnail texts` });
      setDeleteAllOpen(false);
    } catch {
      toast({ title: 'Unable to delete thumbnail texts', variant: 'destructive' });
    }
  };

  const handleImport = async () => {
    const file = importFileRef.current?.files?.[0] ?? null;
    if (!file) {
      toast({ title: 'Choose a CSV, XLS, XLSX, or JSON file', variant: 'destructive' });
      return;
    }
    try {
      const result = await importMutation.mutateAsync(file);
      toast({
        title: `Imported ${result.inserted} thumbnail texts`,
        description: [
          `Skipped duplicates ${result.skipped_existing}`,
          `Skipped empty ${result.skipped_empty}`,
          result.errors.length ? `${result.errors.length} row errors` : '',
        ]
          .filter(Boolean)
          .join(' · '),
      });
      if (result.errors.length) {
        toast({
          title: 'Some rows were not imported',
          description: result.errors.slice(0, 5).join(' | '),
          variant: 'destructive',
        });
      }
      setImportOpen(false);
      if (importFileRef.current) importFileRef.current.value = '';
      query.refetch();
    } catch {
      toast({ title: 'Import failed', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Thumbnail Texts</h1>
          <p className="text-sm text-slate-400">
            Maintain the exact Title / Subtitle / Subline used on AI thumbnails. One row is
            picked per user cycle, so texts rotate without repeating.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => query.refetch()} disabled={query.isFetching}>
            <RefreshCcw className="h-4 w-4" />
            Reload
          </Button>
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4" />
            Import CSV / XLS / JSON
          </Button>
          <Button variant="outline" onClick={() => setDeleteAllOpen(true)} disabled={!items.length}>
            <Trash2 className="h-4 w-4" />
            Delete all
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            New text
          </Button>
        </div>
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-slate-100">Text library</CardTitle>
          <Badge variant="secondary">{items.length} rows</Badge>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading thumbnail texts…
            </div>
          ) : query.isError ? (
            <div className="text-sm text-red-400">Unable to load thumbnail texts.</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Subtitle</TableHead>
                    <TableHead>Subline</TableHead>
                    <TableHead>Placement</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[120px] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-slate-400">
                        No thumbnail texts yet. Add or import a few.
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map((record) => (
                      <TableRow key={record.id}>
                        <TableCell className="font-medium text-slate-100">{record.title}</TableCell>
                        <TableCell className="text-slate-300">{record.subtitle || '-'}</TableCell>
                        <TableCell className="text-slate-300">{record.subline || '-'}</TableCell>
                        <TableCell className="text-slate-400">{record.placement}</TableCell>
                        <TableCell>
                          <Badge variant={record.is_active ? 'secondary' : 'outline'}>
                            {record.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon" onClick={() => openEdit(record)}>
                              <Edit3 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteRecord(record)}
                            >
                              <Trash2 className="h-4 w-4 text-red-400" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) closeDialog(); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{isEditing ? 'Edit thumbnail text' : 'New thumbnail text'}</DialogTitle>
            <DialogDescription>
              These exact words are used for the thumbnail lockup. No title or album tokens are
              required.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Title</Label>
              <Input
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="BASS"
                maxLength={200}
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Subtitle</Label>
                <Input
                  value={form.subtitle}
                  onChange={(event) => setForm((current) => ({ ...current, subtitle: event.target.value }))}
                  placeholder="CAR MUSIC"
                  maxLength={200}
                />
              </div>
              <div className="grid gap-2">
                <Label>Subline</Label>
                <Input
                  value={form.subline}
                  onChange={(event) => setForm((current) => ({ ...current, subline: event.target.value }))}
                  placeholder="2026"
                  maxLength={200}
                />
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Placement</Label>
                <Select
                  value={form.placement}
                  onValueChange={(value) => setForm((current) => ({ ...current, placement: value }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PLACEMENTS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Alignment</Label>
                <Select
                  value={form.alignment}
                  onValueChange={(value) => setForm((current) => ({ ...current, alignment: value }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ALIGNMENTS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>Style hint (optional)</Label>
              <Input
                value={form.style_hint}
                onChange={(event) => setForm((current) => ({ ...current, style_hint: event.target.value }))}
                placeholder="chrome with electric-blue rim light"
                maxLength={400}
              />
            </div>
            <div className="grid gap-2">
              <Label>Notes (optional)</Label>
              <Input
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                maxLength={1000}
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Sort order</Label>
                <Input
                  type="number"
                  value={form.sort_order}
                  onChange={(event) => setForm((current) => ({ ...current, sort_order: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={form.is_active ? 'active' : 'inactive'}
                  onValueChange={(value) => setForm((current) => ({ ...current, is_active: value === 'active' }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Import thumbnail texts</DialogTitle>
            <DialogDescription>
              Upload CSV, XLS, XLSX, or JSON with columns <code>title, subtitle, subline</code>.
              Duplicate rows are skipped; existing rows are never overwritten.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <Input
              ref={importFileRef}
              type="file"
              accept=".csv,.xls,.xlsx,.json,text/csv,application/json,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            />
            <p className="text-xs text-slate-400">
              CSV example: <code>title,subtitle,subline</code> then <code>BASS,CAR MUSIC,2026</code>.
              Optional column: <code>placement</code>.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)} disabled={importMutation.isPending}>
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={importMutation.isPending}>
              {importMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteRecord)}
        onOpenChange={(open) => { if (!open) setDeleteRecord(null); }}
        title="Delete thumbnail text?"
        description={`This removes "${deleteRecord?.title ?? ''}" from the text library.`}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />

      <ConfirmDialog
        open={deleteAllOpen}
        onOpenChange={setDeleteAllOpen}
        title="Delete all thumbnail texts?"
        description={`This permanently removes all ${items.length} thumbnail texts. Existing image jobs keep their stored prompt. This cannot be undone.`}
        variant="destructive"
        confirmText="Delete all"
        isLoading={deleteAllMutation.isPending}
        onConfirm={handleDeleteAll}
      />
    </div>
  );
}
