import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, Pencil, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

import {
  useDescriptions,
  useCreateDescription,
  useUpdateDescription,
  useDeleteDescription,
  useStructures,
  useCreateStructure,
  useUpdateStructure,
  useDeleteStructure,
} from '@/hooks/use-prompts';
import ChannelSetupTab from './channel-setup-tab';
import type { MusicDescription, MusicStructure } from '@/types/models';

// --- Validation schema ---

const promptSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
  content: z.string().min(1, 'Content is required').max(5000, 'Content must be at most 5000 characters'),
  match_key: z.string().max(100, 'Match key must be at most 100 characters').optional().or(z.literal('')),
});

type PromptFormValues = z.infer<typeof promptSchema>;

// --- Helper ---

function truncateContent(content: string, maxLen = 50): string {
  if (content.length <= maxLen) return content;
  return content.slice(0, maxLen) + '...';
}

/** Generate a consistent color class for a given match_key. */
function getMatchKeyColor(matchKey: string): string {
  const colors = [
    'bg-blue-500/20 text-blue-300 border-blue-500/40',
    'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    'bg-purple-500/20 text-purple-300 border-purple-500/40',
    'bg-amber-500/20 text-amber-300 border-amber-500/40',
    'bg-rose-500/20 text-rose-300 border-rose-500/40',
    'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
    'bg-orange-500/20 text-orange-300 border-orange-500/40',
    'bg-pink-500/20 text-pink-300 border-pink-500/40',
  ] as const;
  let hash = 0;
  for (let i = 0; i < matchKey.length; i++) {
    hash = matchKey.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length] as string;
}

// --- Tab type ---

type TabKey = 'descriptions' | 'structures' | 'setup';

// --- Main Page ---

export default function PromptsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('descriptions');

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Prompts</h1>

      {/* Tab buttons */}
      <div className="flex gap-2">
        <Button
          variant={activeTab === 'descriptions' ? 'default' : 'outline'}
          onClick={() => setActiveTab('descriptions')}
        >
          Music Descriptions
        </Button>
        <Button
          variant={activeTab === 'structures' ? 'default' : 'outline'}
          onClick={() => setActiveTab('structures')}
        >
          Music Structures
        </Button>
        <Button
          variant={activeTab === 'setup' ? 'default' : 'outline'}
          onClick={() => setActiveTab('setup')}
        >
          Channel Setup
        </Button>
      </div>

      {activeTab === 'descriptions' && <DescriptionsTab />}
      {activeTab === 'structures' && <StructuresTab />}
      {activeTab === 'setup' && <ChannelSetupTab />}
    </div>
  );
}

// --- Descriptions Tab ---

function DescriptionsTab() {
  const { data: descriptions, isLoading, isError, refetch } = useDescriptions();
  const createMutation = useCreateDescription();
  const updateMutation = useUpdateDescription();
  const deleteMutation = useDeleteDescription();

  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MusicDescription | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MusicDescription | null>(null);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: MusicDescription) {
    setEditingItem(item);
    setFormOpen(true);
  }

  function handleFormSubmit(values: PromptFormValues) {
    const payload = {
      name: values.name,
      content: values.content,
      match_key: values.match_key || undefined,
    };

    if (editingItem) {
      updateMutation.mutate(
        { id: editingItem.id, updates: payload },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => setFormOpen(false),
      });
    }
  }

  function handleDeleteConfirm() {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  }

  if (isLoading) return <TableSkeleton />;
  if (isError) {
    return (
      <div className="text-center py-8 space-y-4">
        <p className="text-destructive">Failed to load descriptions.</p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Create Description
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Content</TableHead>
            <TableHead>Match Key</TableHead>
            <TableHead className="w-[100px]">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {descriptions && descriptions.length > 0 ? (
            descriptions.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {truncateContent(item.content)}
                </TableCell>
                <TableCell>
                  {item.match_key ? (
                    <Badge
                      className={getMatchKeyColor(item.match_key)}
                      variant="outline"
                    >
                      {item.match_key}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEdit(item)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(item)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                No descriptions yet. Create one to get started.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Create/Edit Form Dialog */}
      <PromptFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editingItem ? 'Edit Description' : 'Create Description'}
        defaultValues={
          editingItem
            ? { name: editingItem.name, content: editingItem.content, match_key: editingItem.match_key ?? '' }
            : undefined
        }
        onSubmit={handleFormSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title="Delete Description"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        onConfirm={handleDeleteConfirm}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

// --- Structures Tab ---

function StructuresTab() {
  const { data: structures, isLoading, isError, refetch } = useStructures();
  const createMutation = useCreateStructure();
  const updateMutation = useUpdateStructure();
  const deleteMutation = useDeleteStructure();

  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MusicStructure | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MusicStructure | null>(null);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: MusicStructure) {
    setEditingItem(item);
    setFormOpen(true);
  }

  function handleFormSubmit(values: PromptFormValues) {
    const payload = {
      name: values.name,
      content: values.content,
      match_key: values.match_key || undefined,
    };

    if (editingItem) {
      updateMutation.mutate(
        { id: editingItem.id, updates: payload },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => setFormOpen(false),
      });
    }
  }

  function handleDeleteConfirm() {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  }

  if (isLoading) return <TableSkeleton />;
  if (isError) {
    return (
      <div className="text-center py-8 space-y-4">
        <p className="text-destructive">Failed to load structures.</p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Create Structure
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Content</TableHead>
            <TableHead>Match Key</TableHead>
            <TableHead className="w-[100px]">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {structures && structures.length > 0 ? (
            structures.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {truncateContent(item.content)}
                </TableCell>
                <TableCell>
                  {item.match_key ? (
                    <Badge
                      className={getMatchKeyColor(item.match_key)}
                      variant="outline"
                    >
                      {item.match_key}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEdit(item)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(item)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                No structures yet. Create one to get started.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Create/Edit Form Dialog */}
      <PromptFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editingItem ? 'Edit Structure' : 'Create Structure'}
        defaultValues={
          editingItem
            ? { name: editingItem.name, content: editingItem.content, match_key: editingItem.match_key ?? '' }
            : undefined
        }
        onSubmit={handleFormSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title="Delete Structure"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        onConfirm={handleDeleteConfirm}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

// --- Shared Form Dialog ---

interface PromptFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  defaultValues?: PromptFormValues;
  onSubmit: (values: PromptFormValues) => void;
  isLoading: boolean;
}

function PromptFormDialog({
  open,
  onOpenChange,
  title,
  defaultValues,
  onSubmit,
  isLoading,
}: PromptFormDialogProps) {
  const form = useForm<PromptFormValues>({
    resolver: zodResolver(promptSchema),
    defaultValues: defaultValues ?? { name: '', content: '', match_key: '' },
  });

  // Reset form when dialog opens with new values
  const handleOpenChange = (isOpen: boolean) => {
    if (isOpen) {
      form.reset(defaultValues ?? { name: '', content: '', match_key: '' });
    }
    onOpenChange(isOpen);
  };

  const handleSubmit = form.handleSubmit((values) => {
    onSubmit(values);
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Fill in the fields below. Match key is optional and used to pair descriptions with structures.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="prompt-name">Name</Label>
            <Input
              id="prompt-name"
              placeholder="e.g., Upbeat Pop"
              {...form.register('name')}
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-content">Content</Label>
            <Textarea
              id="prompt-content"
              placeholder="Enter the prompt content..."
              rows={6}
              {...form.register('content')}
            />
            {form.formState.errors.content && (
              <p className="text-sm text-destructive">
                {form.formState.errors.content.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-match-key">Match Key (optional)</Label>
            <Input
              id="prompt-match-key"
              placeholder="e.g., pop-ballad"
              {...form.register('match_key')}
            />
            {form.formState.errors.match_key && (
              <p className="text-sm text-destructive">
                {form.formState.errors.match_key.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {defaultValues ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// --- Loading Skeleton ---

function TableSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Skeleton className="h-10 w-40" />
      </div>
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}
