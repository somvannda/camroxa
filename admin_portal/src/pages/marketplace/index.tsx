import { useRef, useState } from 'react';
import { Edit, ImagePlus, Power, PowerOff, Trash2, Upload } from 'lucide-react';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  useDeleteItem,
  useMarketplaceItems,
  useToggleStatus,
  useUpdateItem,
  useUploadPreview,
} from '@/hooks/use-marketplace';
import { toast } from '@/hooks/use-toast';
import type { MarketplaceItem } from '@/types/marketplace';
import { resolveApiBaseUrl } from '@/lib/api-base';
import { UploadDialog } from '@/components/marketplace/upload-dialog';

const PAGE_SIZE = 25;

/** Resolve preview_url to a full URL that the browser can load as an img src. */
function resolvePreviewUrl(previewUrl: string): string {
  if (previewUrl.startsWith('http')) return previewUrl;
  const apiBase = resolveApiBaseUrl();
  return `${apiBase}${previewUrl}`;
}

const STATUS_CLASSES: Record<MarketplaceItem['status'], string> = {
  enabled: 'border-green-500/30 bg-green-500/10 text-green-400',
  disabled: 'border-red-500/30 bg-red-500/10 text-red-400',
};

const KIND_CLASSES: Record<MarketplaceItem['kind'], string> = {
  video: 'border-sky-400/25 bg-sky-500/10 text-sky-200',
  reel: 'border-purple-400/25 bg-purple-500/10 text-purple-200',
};

// --- Edit Dialog ---

interface EditDialogProps {
  item: MarketplaceItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function EditDialog({ item, open, onOpenChange }: EditDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [price, setPrice] = useState('');
  const updateMutation = useUpdateItem(item?.id ?? '');

  // Sync form when item changes
  if (item && open && name === '' && description === '') {
    setName(item.name);
    setDescription(item.description);
    setTags(item.tags.join(', '));
    setPrice(String(item.price ?? 0));
  }

  const handleSave = () => {
    if (!item) return;
    const tagList = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    const priceNum = parseFloat(price) || 0;
    updateMutation.mutate(
      { name: name.trim() || undefined, description: description.trim() || undefined, tags: tagList, price: priceNum },
      {
        onSuccess: () => {
          toast({ title: 'Updated', description: `"${name}" updated successfully.` });
          handleClose();
        },
        onError: () => {
          toast({ variant: 'destructive', title: 'Update failed', description: 'Could not update item.' });
        },
      },
    );
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setTags('');
    setPrice('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Template</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={4} />
          </div>
          <div className="space-y-2">
            <Label>Price (USD) — enter 0 for Free</Label>
            <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />
          </div>
          <div className="space-y-2">
            <Label>Tags (comma-separated)</Label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="tag1, tag2, tag3" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// --- Preview Upload ---

interface PreviewUploadProps {
  item: MarketplaceItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function PreviewUploadDialog({ item, open, onOpenChange }: PreviewUploadProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const uploadMutation = useUploadPreview(item?.id ?? '');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/png')) {
      toast({ variant: 'destructive', title: 'Invalid file', description: 'Only PNG images are allowed.' });
      return;
    }
    setSelectedFile(file);
    setPreviewSrc(URL.createObjectURL(file));
  };

  const handleUpload = () => {
    if (!selectedFile || !item) return;
    uploadMutation.mutate(selectedFile, {
      onSuccess: () => {
        toast({ title: 'Preview updated', description: `Preview for "${item.name}" uploaded.` });
        handleClose();
      },
      onError: () => {
        toast({ variant: 'destructive', title: 'Upload failed', description: 'Could not upload preview image.' });
      },
    });
  };

  const handleClose = () => {
    setSelectedFile(null);
    setPreviewSrc(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Preview Image</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <p className="text-sm text-slate-400">
            Upload a PNG image to use as the preview for "{item?.name}".
          </p>
          {previewSrc && (
            <img src={previewSrc} alt="Preview" className="mx-auto h-40 w-auto rounded border border-slate-700" />
          )}
          <Input
            ref={fileRef}
            type="file"
            accept="image/png"
            onChange={handleFileChange}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleUpload} disabled={!selectedFile || uploadMutation.isPending}>
            {uploadMutation.isPending ? 'Uploading...' : 'Upload Preview'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// --- Row Actions ---

interface RowActionsProps {
  item: MarketplaceItem;
  onEdit: (item: MarketplaceItem) => void;
  onPreview: (item: MarketplaceItem) => void;
}

function RowActions({ item, onEdit, onPreview }: RowActionsProps) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const toggleMutation = useToggleStatus(item.id);
  const deleteMutation = useDeleteItem(item.id);

  const isEnabled = item.status === 'enabled';

  const handleToggle = () => {
    const newStatus = isEnabled ? 'disabled' : 'enabled';
    toggleMutation.mutate(newStatus, {
      onError: () => {
        toast({ variant: 'destructive', title: 'Toggle failed', description: `Could not ${newStatus === 'enabled' ? 'enable' : 'disable'} "${item.name}".` });
      },
    });
  };

  const handleDelete = () => {
    deleteMutation.mutate(undefined, {
      onSuccess: () => {
        setDeleteOpen(false);
        toast({ title: 'Deleted', description: `"${item.name}" has been deleted.` });
      },
      onError: () => {
        setDeleteOpen(false);
        toast({ variant: 'destructive', title: 'Delete failed', description: `Could not delete "${item.name}".` });
      },
    });
  };

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        title={isEnabled ? 'Disable' : 'Enable'}
        onClick={handleToggle}
        disabled={toggleMutation.isPending}
        className={isEnabled ? 'text-green-400 hover:text-red-400' : 'text-red-400 hover:text-green-400'}
      >
        {isEnabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
      </Button>
      <Button variant="ghost" size="icon" title="Edit" onClick={() => onEdit(item)} className="text-slate-400 hover:text-sky-400">
        <Edit className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" title="Upload Preview" onClick={() => onPreview(item)} className="text-slate-400 hover:text-purple-400">
        <ImagePlus className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" title="Delete" onClick={() => setDeleteOpen(true)} className="text-slate-400 hover:text-red-400">
        <Trash2 className="h-4 w-4" />
      </Button>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Template"
        description={`Are you sure you want to delete "${item.name}"? This action cannot be undone.`}
        onConfirm={handleDelete}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

// --- Main Page ---

export default function MarketplacePage() {
  const [page, setPage] = useState(1);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<MarketplaceItem | null>(null);
  const [previewItem, setPreviewItem] = useState<MarketplaceItem | null>(null);

  const { data, isLoading, isError, error, refetch } = useMarketplaceItems(page);

  if (isError && !data) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Template Marketplace</h1>
        <ErrorState message={error?.message ?? 'Failed to load marketplace items'} onRetry={() => refetch()} />
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Template Marketplace</h1>
          <p className="text-sm text-slate-400 mt-1">Manage video template bundles available to desktop app users</p>
        </div>
        <Button onClick={() => setUploadDialogOpen(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Template
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded bg-slate-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex h-48 items-center justify-center rounded-md border border-slate-800">
          <p className="text-slate-400">No marketplace templates found. Upload your first template to get started.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-md border border-slate-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900">
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Preview</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Kind</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Version</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Price</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Tags</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Created</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-300">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-800 bg-slate-950 hover:bg-slate-900/50">
                    <td className="px-4 py-3">
                      <img
                        src={resolvePreviewUrl(item.preview_url)}
                        alt={item.name}
                        className="h-10 w-16 rounded object-cover bg-slate-800"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <span className="font-medium text-slate-100">{item.name}</span>
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{item.description}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className={KIND_CLASSES[item.kind]}>{item.kind}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{item.version}</td>
                    <td className="px-4 py-3">
                      {item.price === 0 ? (
                        <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">Free</Badge>
                      ) : (
                        <span className="font-medium text-slate-200">${item.price.toFixed(2)}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className={STATUS_CLASSES[item.status]}>{item.status}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {item.tags.length > 0 ? item.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                        )) : <span className="text-slate-500">—</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{new Date(item.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <RowActions item={item} onEdit={setEditItem} onPreview={setPreviewItem} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data && data.total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-slate-400">
                Page {page} of {Math.ceil(data.total / PAGE_SIZE)} ({data.total} items)
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" onClick={() => setPage((p) => p + 1)} disabled={page >= Math.ceil(data.total / PAGE_SIZE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <UploadDialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen} />
      <EditDialog item={editItem} open={!!editItem} onOpenChange={(open) => { if (!open) setEditItem(null); }} />
      <PreviewUploadDialog item={previewItem} open={!!previewItem} onOpenChange={(open) => { if (!open) setPreviewItem(null); }} />
    </div>
  );
}
