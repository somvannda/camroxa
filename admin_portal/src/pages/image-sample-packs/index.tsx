import { useMemo, useRef, useState } from 'react';
import { AxiosError } from 'axios';
import { Edit3, Loader2, Plus, RefreshCcw, Trash2, Upload } from 'lucide-react';

import {
  useCreateImageSamplePack,
  useDeleteImageSamplePack,
  useImageSamplePacks,
  useImportImageSamplePackUrl,
  useUpdateImageSamplePack,
  useUploadImageSamplePack,
} from '@/hooks/use-image-sample-packs';
import { useToast } from '@/hooks/use-toast';
import type {
  ImageSamplePackCategory,
  ImageSamplePackCreateRequest,
  ImageSamplePackRecord,
  ImageSamplePackUpdateRequest,
} from '@/types/image-sample-packs';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

function getImportErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{ detail?: string; error?: { message?: string } }>;
  return axiosError.response?.data?.error?.message ?? axiosError.response?.data?.detail ?? fallback;
}
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

type PackFormState = {
  category: ImageSamplePackCategory;
  name: string;
  is_active: boolean;
  sort_order: string;
  version_label: string;
  notes: string;
};

const CATEGORY_OPTIONS: Array<{ value: ImageSamplePackCategory; label: string }> = [
  { value: 'background', label: 'Background' },
  { value: 'thumbnail', label: 'Thumbnail' },
];

function createEmptyForm(): PackFormState {
  return {
    category: 'background',
    name: '',
    is_active: true,
    sort_order: '0',
    version_label: '',
    notes: '',
  };
}

function packToForm(pack: ImageSamplePackRecord): PackFormState {
  return {
    category: (pack.category.toLowerCase() === 'thumbnail' ? 'thumbnail' : 'background') as ImageSamplePackCategory,
    name: pack.name,
    is_active: pack.is_active,
    sort_order: String(pack.sort_order ?? 0),
    version_label: pack.version_label ?? '',
    notes: pack.notes ?? '',
  };
}

export default function ImageSamplePacksPage() {
  const { toast } = useToast();
  const packsQuery = useImageSamplePacks();
  const createMutation = useCreateImageSamplePack();
  const updateMutation = useUpdateImageSamplePack();
  const deleteMutation = useDeleteImageSamplePack();
  const uploadMutation = useUploadImageSamplePack();
  const importUrlMutation = useImportImageSamplePackUrl();
  const uploadFileRef = useRef<HTMLInputElement>(null);
  const reuploadFileRef = useRef<HTMLInputElement>(null);

  const [uploadTab, setUploadTab] = useState<'zip' | 'url'>('zip');
  const [importSourceType, setImportSourceType] = useState<'google_drive' | 'url'>('google_drive');
  const [importUrl, setImportUrl] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [reuploadPack, setReuploadPack] = useState<ImageSamplePackRecord | null>(null);
  const [editPack, setEditPack] = useState<ImageSamplePackRecord | null>(null);
  const [deletePack, setDeletePack] = useState<ImageSamplePackRecord | null>(null);
  const [form, setForm] = useState<PackFormState>(() => createEmptyForm());

  const packs = useMemo(() => {
    const items = packsQuery.data?.items ?? [];
    return [...items].sort((a, b) => {
      const byCategory = a.category.localeCompare(b.category);
      if (byCategory !== 0) return byCategory;
      const byOrder = (a.sort_order ?? 0) - (b.sort_order ?? 0);
      if (byOrder !== 0) return byOrder;
      return a.name.localeCompare(b.name);
    });
  }, [packsQuery.data?.items]);

  const openCreate = () => {
    setForm(createEmptyForm());
    setCreateOpen(true);
  };

  const openEdit = (pack: ImageSamplePackRecord) => {
    setForm(packToForm(pack));
    setEditPack(pack);
  };

  const closeDialogs = () => {
    setCreateOpen(false);
    setEditPack(null);
  };

  const buildCreatePayload = (): ImageSamplePackCreateRequest | null => {
    const name = form.name.trim();
    const sortOrder = Number(form.sort_order);

    if (!name) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return null;
    }

    return {
      category: form.category,
      name,
      is_active: Boolean(form.is_active),
      sort_order: Number.isFinite(sortOrder) ? sortOrder : 0,
      version_label: form.version_label.trim() || null,
      notes: form.notes.trim() || null,
    };
  };

  const buildUpdatePatch = (): ImageSamplePackUpdateRequest | null => {
    const name = form.name.trim();
    const sortOrder = Number(form.sort_order);

    if (!name) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return null;
    }

    return {
      category: form.category,
      name,
      is_active: Boolean(form.is_active),
      sort_order: Number.isFinite(sortOrder) ? sortOrder : 0,
      version_label: form.version_label.trim() || null,
      notes: form.notes.trim() || null,
    };
  };

  const handleSubmitCreate = async () => {
    const payload = buildCreatePayload();
    if (!payload) return;
    try {
      await createMutation.mutateAsync(payload);
      toast({ title: 'Sample pack created — upload a ZIP to populate assets' });
      closeDialogs();
    } catch {
      toast({ title: 'Unable to create pack', variant: 'destructive' });
    }
  };

  const handleSubmitEdit = async () => {
    if (!editPack) return;
    const patch = buildUpdatePatch();
    if (!patch) return;
    try {
      await updateMutation.mutateAsync({ packId: editPack.id, patch });
      toast({ title: 'Sample pack updated' });
      closeDialogs();
    } catch {
      toast({ title: 'Unable to update pack', variant: 'destructive' });
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletePack) return;
    try {
      await deleteMutation.mutateAsync(deletePack.id);
      toast({ title: 'Sample pack deleted' });
      setDeletePack(null);
    } catch {
      toast({ title: 'Unable to delete pack', variant: 'destructive' });
    }
  };

  const handleSubmitUpload = async () => {
    const name = form.name.trim();
    if (!name) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return;
    }

    if (uploadTab === 'url') {
      const sourceValue = importUrl.trim();
      if (!sourceValue) {
        toast({ title: 'URL is required', variant: 'destructive' });
        return;
      }
      try {
        await importUrlMutation.mutateAsync({
          category: form.category,
          name,
          source_type: importSourceType,
          source_value: sourceValue,
          is_active: form.is_active,
          sort_order: Number(form.sort_order) || 0,
          version_label: form.version_label.trim() || null,
          notes: form.notes.trim() || null,
        });
        toast({ title: 'Sample pack imported from URL' });
        setUploadOpen(false);
        setForm(createEmptyForm());
        setImportUrl('');
        setUploadTab('zip');
      } catch (error) {
        toast({
          title: 'URL import failed',
          description: getImportErrorMessage(error, 'Check the link, sharing settings, and 1 GB URL import limit.'),
          variant: 'destructive',
        });
      }
      return;
    }

    const file = uploadFileRef.current?.files?.[0] ?? null;
    if (!file) {
      toast({ title: 'Choose a ZIP file', variant: 'destructive' });
      return;
    }
    try {
      await uploadMutation.mutateAsync({
        file,
        category: form.category,
        name,
        is_active: form.is_active,
        sort_order: Number(form.sort_order) || 0,
        version_label: form.version_label.trim() || null,
        notes: form.notes.trim() || null,
      });
      toast({ title: 'Sample pack uploaded to VPS' });
      setUploadOpen(false);
      setForm(createEmptyForm());
      if (uploadFileRef.current) uploadFileRef.current.value = '';
    } catch {
      toast({ title: 'Upload failed', variant: 'destructive' });
    }
  };

  const sourceTypeLabel = (sourceType: string) => {
    if (sourceType === 'vps_upload') return 'VPS upload';
    if (sourceType === 'google_drive') return 'Google Drive';
    if (sourceType === 'url') return 'Direct URL';
    return sourceType;
  };

  const handleSubmitReupload = async () => {
    if (!reuploadPack) return;
    const file = reuploadFileRef.current?.files?.[0] ?? null;
    if (!file) {
      toast({ title: 'Choose a ZIP file', variant: 'destructive' });
      return;
    }
    try {
      await uploadMutation.mutateAsync({
        file,
        packId: reuploadPack.id,
        category: (reuploadPack.category.toLowerCase() === 'thumbnail' ? 'thumbnail' : 'background') as ImageSamplePackCategory,
        name: reuploadPack.name,
        is_active: reuploadPack.is_active,
        sort_order: reuploadPack.sort_order ?? 0,
        version_label: reuploadPack.version_label,
        notes: reuploadPack.notes,
      });
      toast({ title: 'Sample pack assets replaced on VPS' });
      setReuploadPack(null);
      if (reuploadFileRef.current) reuploadFileRef.current.value = '';
    } catch {
      toast({ title: 'Re-upload failed', variant: 'destructive' });
    }
  };

  const dialogOpen = createOpen || Boolean(editPack);
  const isEditing = Boolean(editPack);
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Image Sample Packs</h1>
          <p className="text-sm text-slate-400">
            Upload ZIP archives to VPS storage for server-side background and thumbnail image generation.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => packsQuery.refetch()}
            disabled={packsQuery.isFetching}
          >
            <RefreshCcw className="h-4 w-4" />
            Reload
          </Button>
          <Button onClick={() => { setForm(createEmptyForm()); setUploadOpen(true); }}>
            <Upload className="h-4 w-4" />
            Upload ZIP
          </Button>
          <Button variant="outline" onClick={openCreate}>
            <Plus className="h-4 w-4" />
            New Pack
          </Button>
        </div>
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-slate-100">Catalog</CardTitle>
          <Badge variant="secondary">{packs.length} packs</Badge>
        </CardHeader>
        <CardContent>
          {packsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading packs…
            </div>
          ) : packsQuery.isError ? (
            <div className="text-sm text-red-400">Unable to load sample packs.</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[130px]">Category</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-[120px]">Version</TableHead>
                    <TableHead className="w-[90px] text-right">Assets</TableHead>
                    <TableHead className="w-[120px]">Source</TableHead>
                    <TableHead>Storage path</TableHead>
                    <TableHead className="w-[90px] text-right">Sort</TableHead>
                    <TableHead className="w-[110px]">Status</TableHead>
                    <TableHead className="w-[150px] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {packs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-sm text-slate-400 py-8">
                        No sample packs yet. Upload a ZIP to get started.
                      </TableCell>
                    </TableRow>
                  ) : (
                    packs.map((pack) => (
                      <TableRow key={pack.id}>
                        <TableCell className="font-medium text-slate-200">
                          {pack.category}
                        </TableCell>
                        <TableCell className="text-slate-200">
                          <div className="font-medium">{pack.name}</div>
                        </TableCell>
                        <TableCell className="text-slate-300">
                          {pack.version_label || '—'}
                        </TableCell>
                        <TableCell className="text-right text-slate-300">
                          {pack.asset_count ?? 0}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{sourceTypeLabel(pack.source_type)}</Badge>
                        </TableCell>
                        <TableCell className="max-w-[280px] truncate text-xs text-slate-400">
                          {pack.storage_path || '—'}
                        </TableCell>
                        <TableCell className="text-right text-slate-300">{pack.sort_order}</TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={
                              pack.is_active
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                                : 'border-slate-600/40 bg-slate-800/40 text-slate-300'
                            }
                          >
                            {pack.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="default"
                              size="sm"
                              onClick={() => setReuploadPack(pack)}
                            >
                              <Upload className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openEdit(pack)}
                            >
                              <Edit3 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => setDeletePack(pack)}
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

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) closeDialogs(); }}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{isEditing ? 'Edit Sample Pack' : 'Create Sample Pack'}</DialogTitle>
            <DialogDescription>
              Create catalog metadata, then upload a ZIP to populate VPS assets.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>Category</Label>
              <Select
                value={form.category}
                onValueChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    category: (value === 'thumbnail' ? 'thumbnail' : 'background') as ImageSamplePackCategory,
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="e.g. Background Pack v1"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={form.is_active ? 'active' : 'inactive'}
                  onValueChange={(value) => setForm((current) => ({ ...current, is_active: value === 'active' }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
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
                  onChange={(event) => setForm((current) => ({ ...current, sort_order: event.target.value }))}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>Version label (optional)</Label>
              <Input
                value={form.version_label}
                onChange={(event) => setForm((current) => ({ ...current, version_label: event.target.value }))}
                placeholder="e.g. v1"
              />
            </div>

            <div className="grid gap-2">
              <Label>Notes (optional)</Label>
              <Textarea
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Shown to users under the pack selector."
                className="min-h-[90px]"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={closeDialogs}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={isEditing ? handleSubmitEdit : handleSubmitCreate}
              disabled={isSubmitting}
            >
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {isEditing ? 'Save Changes' : 'Create Pack'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Upload sample pack</DialogTitle>
            <DialogDescription>
              Upload a ZIP to VPS storage or import from Google Drive / direct URL (up to 1 GB for URL import).
            </DialogDescription>
          </DialogHeader>
          <Tabs value={uploadTab} onValueChange={(value) => setUploadTab(value as 'zip' | 'url')}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="zip">Upload ZIP</TabsTrigger>
              <TabsTrigger value="url">Import from URL</TabsTrigger>
            </TabsList>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label>Category</Label>
                <Select
                  value={form.category}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, category: value as ImageSamplePackCategory }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                />
              </div>
              <TabsContent value="zip" className="mt-0">
                <div className="grid gap-2">
                  <Label>ZIP file</Label>
                  <Input ref={uploadFileRef} type="file" accept=".zip,application/zip" />
                </div>
              </TabsContent>
              <TabsContent value="url" className="mt-0 space-y-4">
                <div className="grid gap-2">
                  <Label>Source type</Label>
                  <Select
                    value={importSourceType}
                    onValueChange={(value) => setImportSourceType(value as 'google_drive' | 'url')}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="google_drive">Google Drive</SelectItem>
                      <SelectItem value="url">Direct URL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>URL</Label>
                  <Input
                    value={importUrl}
                    onChange={(event) => setImportUrl(event.target.value)}
                    placeholder={
                      importSourceType === 'google_drive'
                        ? 'https://drive.google.com/file/d/...'
                        : 'https://example.com/pack.zip'
                    }
                  />
                </div>
              </TabsContent>
            </div>
          </Tabs>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setUploadOpen(false)}
              disabled={uploadMutation.isPending || importUrlMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitUpload}
              disabled={uploadMutation.isPending || importUrlMutation.isPending}
            >
              {uploadMutation.isPending || importUrlMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              {uploadTab === 'url' ? 'Import' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(reuploadPack)} onOpenChange={(open) => { if (!open) setReuploadPack(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Re-upload ZIP</DialogTitle>
            <DialogDescription>
              Replace assets for &quot;{reuploadPack?.name ?? ''}&quot; on VPS storage.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>ZIP file</Label>
              <Input ref={reuploadFileRef} type="file" accept=".zip,application/zip" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReuploadPack(null)} disabled={uploadMutation.isPending}>
              Cancel
            </Button>
            <Button onClick={handleSubmitReupload} disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Upload
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deletePack)}
        onOpenChange={(open) => { if (!open) setDeletePack(null); }}
        title="Delete sample pack?"
        description={`This removes "${deletePack?.name ?? ''}" from the catalog. Users will no longer see it.`}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
}
