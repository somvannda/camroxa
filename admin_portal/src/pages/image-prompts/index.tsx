import { useMemo, useState } from 'react';
import { Edit3, Loader2, Plus, RefreshCcw, Trash2 } from 'lucide-react';

import {
  useCreateImagePrompt,
  useDeleteImagePrompt,
  useImagePrompts,
  useUpdateImagePrompt,
} from '@/hooks/use-image-prompts';
import { useToast } from '@/hooks/use-toast';
import type {
  ImagePromptKind,
  ImagePromptStyleCreateRequest,
  ImagePromptStyleRecord,
  ImagePromptStyleUpdateRequest,
} from '@/types/image-prompts';
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
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

const PROMPT_MAX_CHARS = 3000;

type FormState = {
  kind: ImagePromptKind;
  name: string;
  prompt_text: string;
  text_template: string;
  is_active: boolean;
  sort_order: string;
  notes: string;
};

function emptyForm(kind: ImagePromptKind = 'background'): FormState {
  return {
    kind,
    name: '',
    prompt_text: '',
    text_template: '',
    is_active: true,
    sort_order: '0',
    notes: '',
  };
}

function recordToForm(record: ImagePromptStyleRecord): FormState {
  return {
    kind: record.kind,
    name: record.name,
    prompt_text: record.prompt_text,
    text_template: record.text_template ?? '',
    is_active: record.is_active,
    sort_order: String(record.sort_order ?? 0),
    notes: record.notes ?? '',
  };
}

export default function ImagePromptsPage() {
  const { toast } = useToast();
  const promptsQuery = useImagePrompts();
  const createMutation = useCreateImagePrompt();
  const updateMutation = useUpdateImagePrompt();
  const deleteMutation = useDeleteImagePrompt();

  const [kindTab, setKindTab] = useState<ImagePromptKind>('background');
  const [form, setForm] = useState<FormState>(() => emptyForm());
  const [createOpen, setCreateOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<ImagePromptStyleRecord | null>(null);
  const [deleteRecord, setDeleteRecord] = useState<ImagePromptStyleRecord | null>(null);

  const allItems = promptsQuery.data?.items ?? [];
  const items = useMemo(
    () =>
      allItems
        .filter((item) => item.kind === kindTab)
        .sort((a, b) => {
          const byOrder = (a.sort_order ?? 0) - (b.sort_order ?? 0);
          if (byOrder !== 0) return byOrder;
          return a.name.localeCompare(b.name);
        }),
    [allItems, kindTab],
  );

  const counts = useMemo(
    () => ({
      background: allItems.filter((item) => item.kind === 'background' && item.is_active).length,
      thumbnail: allItems.filter((item) => item.kind === 'thumbnail' && item.is_active).length,
    }),
    [allItems],
  );

  const dialogOpen = createOpen || Boolean(editRecord);
  const isEditing = Boolean(editRecord);
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  const openCreate = () => {
    setForm(emptyForm(kindTab));
    setEditRecord(null);
    setCreateOpen(true);
  };

  const openEdit = (record: ImagePromptStyleRecord) => {
    setForm(recordToForm(record));
    setEditRecord(record);
    setCreateOpen(false);
  };

  const closeDialog = () => {
    setCreateOpen(false);
    setEditRecord(null);
  };

  const buildPayload = (): ImagePromptStyleCreateRequest | null => {
    const name = form.name.trim();
    const promptText = form.prompt_text.trim();
    if (!name) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return null;
    }
    if (!promptText) {
      toast({ title: 'Prompt text is required', variant: 'destructive' });
      return null;
    }
    if (promptText.length > PROMPT_MAX_CHARS) {
      toast({
        title: `Prompt is too long (${promptText.length}/${PROMPT_MAX_CHARS})`,
        variant: 'destructive',
      });
      return null;
    }
    return {
      kind: form.kind,
      name,
      prompt_text: promptText,
      text_template: form.kind === 'thumbnail' ? form.text_template.trim() || null : null,
      is_active: form.is_active,
      sort_order: Number(form.sort_order) || 0,
      notes: form.notes.trim() || null,
    };
  };

  const handleSubmit = async () => {
    const payload = buildPayload();
    if (!payload) return;
    try {
      if (editRecord) {
        const patch: ImagePromptStyleUpdateRequest = { ...payload };
        await updateMutation.mutateAsync({ styleId: editRecord.id, patch });
        toast({ title: 'Prompt style updated' });
      } else {
        await createMutation.mutateAsync(payload);
        toast({ title: 'Prompt style created' });
      }
      closeDialog();
    } catch {
      toast({ title: 'Unable to save prompt style', variant: 'destructive' });
    }
  };

  const handleDelete = async () => {
    if (!deleteRecord) return;
    try {
      await deleteMutation.mutateAsync(deleteRecord.id);
      toast({ title: 'Prompt style deleted' });
      setDeleteRecord(null);
    } catch {
      toast({ title: 'Unable to delete prompt style', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Image Prompts</h1>
          <p className="text-sm text-slate-400">
            Curate prompt styles for desktop image generation. Each channel picks a different
            active style from the library when the desktop user selects Admin prompt library.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => promptsQuery.refetch()}
            disabled={promptsQuery.isFetching}
          >
            <RefreshCcw className="h-4 w-4" />
            Reload
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            New Prompt
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="flex items-center justify-between py-4">
            <span className="text-sm text-slate-300">Active background styles</span>
            <Badge variant="secondary">{counts.background}</Badge>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="flex items-center justify-between py-4">
            <span className="text-sm text-slate-300">Active thumbnail styles</span>
            <Badge variant="secondary">{counts.thumbnail}</Badge>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-slate-100">Prompt library</CardTitle>
          <Tabs
            value={kindTab}
            onValueChange={(value) => setKindTab(value as ImagePromptKind)}
          >
            <TabsList>
              <TabsTrigger value="background">Background</TabsTrigger>
              <TabsTrigger value="thumbnail">Thumbnail</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          {promptsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading prompt styles…
            </div>
          ) : promptsQuery.isError ? (
            <div className="text-sm text-red-400">Unable to load prompt styles.</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Prompt preview</TableHead>
                    <TableHead>Text template</TableHead>
                    <TableHead className="w-[90px] text-right">Sort</TableHead>
                    <TableHead className="w-[110px]">Status</TableHead>
                    <TableHead className="w-[150px] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-slate-400">
                        No {kindTab} prompt styles yet. Add at least two for two-channel batches.
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map((record) => (
                      <TableRow key={record.id}>
                        <TableCell className="font-medium text-slate-200">{record.name}</TableCell>
                        <TableCell className="max-w-[360px]">
                          <div className="line-clamp-2 text-sm text-slate-300">
                            {record.prompt_text}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-slate-300">
                          {record.text_template || '—'}
                        </TableCell>
                        <TableCell className="text-right text-slate-300">
                          {record.sort_order}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={
                              record.is_active
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                                : 'border-slate-600/40 bg-slate-800/40 text-slate-300'
                            }
                          >
                            {record.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEdit(record)}>
                              <Edit3 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => setDeleteRecord(record)}
                            >
                              <Trash2 className="h-4 w-4" />
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
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{isEditing ? 'Edit Prompt Style' : 'Create Prompt Style'}</DialogTitle>
            <DialogDescription>
              Background prompts must not ask for text. Thumbnail styles may include a text
              template with {'{title}'}, {'{album}'}, or {'{channel}'}.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Kind</Label>
                <Select
                  value={form.kind}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, kind: value as ImagePromptKind }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="background">Background</SelectItem>
                    <SelectItem value="thumbnail">Thumbnail</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder="e.g. Neon Night Drive"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>Prompt text</Label>
                <span className="text-xs text-slate-400">
                  {form.prompt_text.length}/{PROMPT_MAX_CHARS}
                </span>
              </div>
              <Textarea
                value={form.prompt_text}
                onChange={(event) =>
                  setForm((current) => ({ ...current, prompt_text: event.target.value }))
                }
                placeholder="Describe the art direction or typography style…"
                className="min-h-[150px]"
              />
            </div>

            {form.kind === 'thumbnail' ? (
              <div className="grid gap-2">
                <Label>Text template (optional)</Label>
                <Input
                  value={form.text_template}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, text_template: event.target.value }))
                  }
                  placeholder="{album} or NEW DROP"
                />
                <p className="text-xs text-slate-400">
                  Tokens: {'{title}'}, {'{album}'}, {'{channel}'}. Empty uses the song title.
                </p>
              </div>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={form.is_active ? 'active' : 'inactive'}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, is_active: value === 'active' }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Sort order</Label>
                <Input
                  inputMode="numeric"
                  type="number"
                  value={form.sort_order}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, sort_order: event.target.value }))
                  }
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>Notes (optional)</Label>
              <Textarea
                value={form.notes}
                onChange={(event) =>
                  setForm((current) => ({ ...current, notes: event.target.value }))
                }
                className="min-h-[70px]"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {isEditing ? 'Save Changes' : 'Create Prompt'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteRecord)}
        onOpenChange={(open) => { if (!open) setDeleteRecord(null); }}
        title="Delete prompt style?"
        description={`This removes "${deleteRecord?.name ?? ''}" from the library. Existing image jobs keep their stored prompt.`}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
