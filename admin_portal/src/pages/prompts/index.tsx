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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

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
import {
  useChannelPrompts,
  useCreateChannelPrompt,
  useUpdateChannelPrompt,
  useDeleteChannelPrompt,
} from '@/hooks/use-channel-prompts';
import type { MusicDescription, MusicStructure, ChannelPrompt } from '@/types/models';

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

type TabKey = 'descriptions' | 'structures' | 'channel';

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
          variant={activeTab === 'channel' ? 'default' : 'outline'}
          onClick={() => setActiveTab('channel')}
        >
          Channel Prompts
        </Button>
      </div>

      {activeTab === 'descriptions' && <DescriptionsTab />}
      {activeTab === 'structures' && <StructuresTab />}
      {activeTab === 'channel' && <ChannelPromptsTab />}
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

// --- Channel Prompts Tab ---

const CHANNEL_CATEGORIES = ['title', 'logo', 'cover', 'description', 'keyword', 'tag'] as const;

const CATEGORY_DISPLAY_LABELS: Record<string, string> = {
  title: 'Channel Name',
  logo: 'Logo',
  cover: 'Cover',
  description: 'Description',
  keyword: 'Keyword',
  tag: 'Tag',
};

const channelPromptSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Max 100 characters'),
  content: z.string().min(1, 'Content is required').max(5000, 'Max 5000 characters'),
  category: z.string().min(1, 'Category is required'),
  genre: z.string().max(100).optional().or(z.literal('')),
  match_key: z.string().max(100).optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

type ChannelPromptFormValues = z.infer<typeof channelPromptSchema>;

const CATEGORY_BADGE_CLASSES: Record<string, string> = {
  title: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  logo: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  cover: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  description: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  keyword: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  tag: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
};

function ChannelPromptsTab() {
  const { data: prompts, isLoading, isError, refetch } = useChannelPrompts();
  const createMutation = useCreateChannelPrompt();
  const updateMutation = useUpdateChannelPrompt();
  const deleteMutation = useDeleteChannelPrompt();

  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ChannelPrompt | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ChannelPrompt | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');

  const filtered = filterCategory === 'all'
    ? (prompts ?? [])
    : (prompts ?? []).filter(p => p.category === filterCategory);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: ChannelPrompt) {
    setEditingItem(item);
    setFormOpen(true);
  }

  function handleFormSubmit(values: ChannelPromptFormValues) {
    const payload = {
      name: values.name,
      content: values.content,
      category: values.category,
      genre: values.genre || '',
      match_key: values.match_key || null,
      is_active: values.is_active ?? true,
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
        <p className="text-destructive">Failed to load channel prompts.</p>
        <Button variant="outline" onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Select value={filterCategory} onValueChange={setFilterCategory}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CHANNEL_CATEGORIES.map(c => (
              <SelectItem key={c} value={c}>{CATEGORY_DISPLAY_LABELS[c] ?? c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Create Prompt
        </Button>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Genre</TableHead>
              <TableHead>Match Key</TableHead>
              <TableHead>Content</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No channel prompts found.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map(prompt => (
                <TableRow key={prompt.id}>
                  <TableCell className="font-medium">{prompt.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={CATEGORY_BADGE_CLASSES[prompt.category] ?? ''}>
                      {CATEGORY_DISPLAY_LABELS[prompt.category] ?? prompt.category}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{prompt.genre || '—'}</TableCell>
                  <TableCell>
                    {prompt.match_key ? (
                      <Badge variant="outline" className={getMatchKeyColor(prompt.match_key)}>
                        {prompt.match_key}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">
                    {truncateContent(prompt.content, 60)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={prompt.is_active ? 'bg-green-500/20 text-green-300 border-green-500/40' : 'bg-gray-500/20 text-gray-400 border-gray-500/40'}>
                      {prompt.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(prompt)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(prompt)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Form Dialog */}
      <ChannelPromptFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
        defaultValues={editingItem}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title="Delete Channel Prompt"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This cannot be undone.`}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

function ChannelPromptFormDialog({
  open,
  onOpenChange,
  onSubmit,
  defaultValues,
  isLoading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: ChannelPromptFormValues) => void;
  defaultValues: ChannelPrompt | null;
  isLoading: boolean;
}) {
  const form = useForm<ChannelPromptFormValues>({
    resolver: zodResolver(channelPromptSchema),
    defaultValues: defaultValues
      ? {
          name: defaultValues.name,
          content: defaultValues.content,
          category: defaultValues.category,
          genre: defaultValues.genre,
          match_key: defaultValues.match_key ?? '',
          is_active: defaultValues.is_active,
        }
      : { name: '', content: '', category: 'title', genre: '', match_key: '', is_active: true },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{defaultValues ? 'Edit Channel Prompt' : 'Create Channel Prompt'}</DialogTitle>
          <DialogDescription>
            {defaultValues ? 'Update the prompt used by the onboarding wizard.' : 'Add a new prompt for channel setup generation.'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cp-name">Name</Label>
            <Input id="cp-name" placeholder="e.g., EDM Channel Title" {...form.register('name')} />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="cp-category">Category</Label>
            <select
              id="cp-category"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              {...form.register('category')}
            >
              {CHANNEL_CATEGORIES.map(c => (
                <option key={c} value={c}>{CATEGORY_DISPLAY_LABELS[c] ?? c}</option>
              ))}
            </select>
            {form.formState.errors.category && (
              <p className="text-sm text-destructive">{form.formState.errors.category.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="cp-genre">Genre (optional — leave empty for default)</Label>
            <Input id="cp-genre" placeholder="e.g., EDM, Hip-Hop, Pop" {...form.register('genre')} />
          </div>

          <div className="space-y-2">
            <Label>Music Description (optional — link to description)</Label>
            <DescriptionSelect
              value={form.watch('match_key') ?? ''}
              onChange={(val) => form.setValue('match_key', val || undefined)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cp-content">Prompt Content</Label>
            <Textarea
              id="cp-content"
              rows={6}
              placeholder="The system or user prompt used during generation..."
              {...form.register('content')}
            />
            {form.formState.errors.content && (
              <p className="text-sm text-destructive">{form.formState.errors.content.message}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="cp-active"
              className="rounded"
              {...form.register('is_active')}
            />
            <Label htmlFor="cp-active">Active</Label>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
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

function DescriptionSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (matchKey: string) => void;
}) {
  const { data: descriptions, isLoading } = useDescriptions();
  const items = descriptions ?? [];

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="None (use genre/default)" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="">None</SelectItem>
        {items.map((d) => (
          <SelectItem key={d.id} value={d.match_key ?? d.name}>
            {d.name}
            {d.match_key ? (
              <span className="ml-2 text-muted-foreground text-xs">({d.match_key})</span>
            ) : null}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
