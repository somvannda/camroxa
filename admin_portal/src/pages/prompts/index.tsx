import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, Pencil, Trash2, BarChart3, Eye, EyeOff } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

import {
  useAdminUserMoods,
  useCreateDescription,
  useCreateMood,
  useCreateStructure,
  useDeleteDescription,
  useDeleteMood,
  useDeleteStructure,
  useDescriptionUsage,
  useDescriptions,
  useMoodUsage,
  useMoods,
  useStructureUsage,
  useStructures,
  useUpdateDescription,
  useUpdateMood,
  useUpdateStructure,
  useUserOwnedDescriptions,
  useUserOwnedStructures,
} from '@/hooks/use-prompts';
import ChannelSetupTab from './channel-setup-tab';
import { DescriptionFormDialog, type DescriptionFormValues } from './description-form-dialog';
import type {
  AdminUserOwnedPrompt,
  MusicDescription,
  MusicMood,
  MusicStructure,
  PromptUsageResponse,
} from '@/types/models';

const promptSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
  content: z.string().min(1, 'Content is required').max(5000, 'Content must be at most 5000 characters'),
  match_key: z.string().max(100, 'Match key must be at most 100 characters').optional().or(z.literal('')),
});

type PromptFormValues = z.infer<typeof promptSchema>;
type TabKey = 'descriptions' | 'structures' | 'moods' | 'setup';
type PromptScopeTabKey = 'camxora' | 'user';
type UsageViewKey = 'users' | 'profiles' | 'timeline';

function truncateContent(content: string, maxLen = 50): string {
  if (content.length <= maxLen) return content;
  return content.slice(0, maxLen) + '...';
}

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

function getVisibilityBadge(isActive: boolean) {
  return isActive
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : 'bg-slate-500/15 text-slate-300 border-slate-500/30';
}

function formatAdminDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function PromptUsageDialog({
  open,
  onOpenChange,
  title,
  usage,
  isLoading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  usage: PromptUsageResponse | undefined;
  isLoading: boolean;
}) {
  const [usageView, setUsageView] = useState<UsageViewKey>('users');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Counts are based on songs that stored this prompt ID. Channel counts include OK and ALT profiles from each batch.
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center gap-2 py-6 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading usage...
          </div>
        ) : usage ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3 text-sm">
              <Badge variant="outline">Owner: {usage.owner_label}</Badge>
              <Badge variant="outline">Total song uses: {usage.usage_count}</Badge>
              <Badge variant="outline">Users: {usage.users.length}</Badge>
              <Badge variant="outline">Channels: {usage.profiles.length}</Badge>
            </div>

            <div className="flex gap-2">
              <Button
                size="sm"
                variant={usageView === 'users' ? 'default' : 'outline'}
                onClick={() => setUsageView('users')}
              >
                By user
              </Button>
              <Button
                size="sm"
                variant={usageView === 'profiles' ? 'default' : 'outline'}
                onClick={() => setUsageView('profiles')}
              >
                By channel
              </Button>
              <Button
                size="sm"
                variant={usageView === 'timeline' ? 'default' : 'outline'}
                onClick={() => setUsageView('timeline')}
              >
                Timeline
              </Button>
            </div>

            {usageView === 'users' ? (
              usage.users.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Uses</TableHead>
                      <TableHead>Last used</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usage.users.map((row) => (
                      <TableRow key={row.user_id}>
                        <TableCell>{row.user_display_name || '-'}</TableCell>
                        <TableCell>{row.user_email || '-'}</TableCell>
                        <TableCell>{row.usage_count}</TableCell>
                        <TableCell>{formatAdminDateTime(row.last_used_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">No users have used this prompt yet.</p>
              )
            ) : null}

            {usageView === 'profiles' ? (
              usage.profiles.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Channel profile</TableHead>
                      <TableHead>Account</TableHead>
                      <TableHead>Uses</TableHead>
                      <TableHead>Last used</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usage.profiles.map((row) => (
                      <TableRow key={row.profile_id}>
                        <TableCell>{row.profile_name || '-'}</TableCell>
                        <TableCell>
                          <div>{row.user_display_name || '-'}</div>
                          <div className="text-xs text-muted-foreground">{row.user_email || '-'}</div>
                        </TableCell>
                        <TableCell>{row.usage_count}</TableCell>
                        <TableCell>{formatAdminDateTime(row.last_used_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">No channel profiles have used this prompt yet.</p>
              )
            ) : null}

            {usageView === 'timeline' ? (
              usage.by_day.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date (UTC)</TableHead>
                      <TableHead>Song uses</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usage.by_day.map((row) => (
                      <TableRow key={row.usage_date}>
                        <TableCell>{row.usage_date}</TableCell>
                        <TableCell>{row.usage_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">No usage history yet.</p>
              )
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function UserPromptTable({
  items,
  kindLabel,
  onViewUsage,
}: {
  items: AdminUserOwnedPrompt[];
  kindLabel: string;
  onViewUsage: (item: AdminUserOwnedPrompt) => void;
}) {
  const getStatusBadge = (isActive: boolean) =>
    isActive
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : 'bg-slate-500/15 text-slate-300 border-slate-500/30';

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Owner</TableHead>
          <TableHead>Content</TableHead>
          <TableHead className="w-[110px]">Status</TableHead>
          <TableHead className="w-[90px]">Uses</TableHead>
          <TableHead className="w-[160px]">Updated</TableHead>
          <TableHead className="w-[90px]">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.length ? (
          items.map((item) => (
            <TableRow key={item.id} className={item.is_active ? '' : 'opacity-60'}>
              <TableCell className="font-medium">{item.name}</TableCell>
              <TableCell>
                <div>{item.user_display_name || 'Unnamed user'}</div>
                <div className="text-xs text-muted-foreground">{item.user_email || '-'}</div>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {truncateContent(item.content, 72)}
              </TableCell>
              <TableCell>
                <Badge className={getStatusBadge(item.is_active)} variant="outline">
                  {item.is_active ? 'Active' : 'Archived'}
                </Badge>
              </TableCell>
              <TableCell>{item.usage_count}</TableCell>
              <TableCell className="text-muted-foreground">
                {formatAdminDateTime(item.updated_at)}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  title={`View ${kindLabel} usage`}
                  onClick={() => onViewUsage(item)}
                >
                  <BarChart3 className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))
        ) : (
          <TableRow>
            <TableCell colSpan={7} className="text-center text-muted-foreground">
              No user-owned {kindLabel.toLowerCase()} yet.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

export default function PromptsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('descriptions');

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Prompts</h1>

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
          variant={activeTab === 'moods' ? 'default' : 'outline'}
          onClick={() => setActiveTab('moods')}
        >
          Music Moods
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
      {activeTab === 'moods' && <MoodsTab />}
      {activeTab === 'setup' && <ChannelSetupTab />}
    </div>
  );
}

function DescriptionsTab() {
  const { data: descriptions, isLoading, isError, refetch } = useDescriptions();
  const {
    data: userDescriptions,
    isLoading: isUserLoading,
    isError: isUserError,
    refetch: refetchUserDescriptions,
  } = useUserOwnedDescriptions();
  const createMutation = useCreateDescription();
  const updateMutation = useUpdateDescription();
  const deleteMutation = useDeleteDescription();

  const [scopeTab, setScopeTab] = useState<PromptScopeTabKey>('camxora');
  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MusicDescription | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MusicDescription | null>(null);
  const [usageTarget, setUsageTarget] = useState<{ id: string; name: string } | null>(null);
  const usageQuery = useDescriptionUsage(usageTarget?.id ?? null);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: MusicDescription) {
    setEditingItem(item);
    setFormOpen(true);
  }

  function handleFormSubmit(values: DescriptionFormValues, vocalProfile: MusicDescription['vocal_profile']) {
    const payload = {
      name: values.name,
      content: values.content,
      genres: values.genres,
      match_key: values.match_key || undefined,
      vocal_profile: vocalProfile,
    };

    if (editingItem) {
      updateMutation.mutate(
        { id: editingItem.id, updates: payload },
        { onSuccess: () => setFormOpen(false) },
      );
      return;
    }

    createMutation.mutate(payload, {
      onSuccess: () => setFormOpen(false),
    });
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
      <Tabs value={scopeTab} onValueChange={(value) => setScopeTab(value as PromptScopeTabKey)}>
        <TabsList className="border border-slate-800 bg-slate-900/60">
          <TabsTrigger value="camxora">Camxora Prompts</TabsTrigger>
          <TabsTrigger value="user">User Prompts</TabsTrigger>
        </TabsList>

        <TabsContent value="camxora" className="space-y-4">
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
                <TableHead>Genres</TableHead>
                <TableHead>Content</TableHead>
                <TableHead>Match Key</TableHead>
                <TableHead className="w-[120px]">Visibility</TableHead>
                <TableHead className="w-[90px]">Uses</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {descriptions && descriptions.length > 0 ? (
                descriptions.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell>
                      {item.genres && item.genres.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {item.genres.map((genre) => (
                            <Badge key={genre} variant="outline">
                              {genre}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {truncateContent(item.content)}
                    </TableCell>
                    <TableCell>
                      {item.match_key ? (
                        <Badge className={getMatchKeyColor(item.match_key)} variant="outline">
                          {item.match_key}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={getVisibilityBadge(item.is_active)} variant="outline">
                        {item.is_active ? 'Visible' : 'Hidden'}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.usage_count ?? 0}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title={item.is_active ? 'Currently visible in onboarding. Click to hide.' : 'Currently hidden from onboarding. Click to show.'}
                          onClick={() =>
                            updateMutation.mutate({
                              id: item.id,
                              updates: { is_active: !item.is_active },
                            })
                          }
                        >
                          {item.is_active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="View usage by user"
                          onClick={() => setUsageTarget({ id: item.id, name: item.name })}
                        >
                          <BarChart3 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(item)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(item)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No descriptions yet. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="user" className="space-y-4">
          {isUserLoading ? (
            <TableSkeleton />
          ) : isUserError ? (
            <div className="text-center py-8 space-y-4">
              <p className="text-destructive">Failed to load user descriptions.</p>
              <Button variant="outline" onClick={() => refetchUserDescriptions()}>
                Retry
              </Button>
            </div>
          ) : (
            <UserPromptTable
              items={userDescriptions ?? []}
              kindLabel="Description"
              onViewUsage={(item) => setUsageTarget({ id: item.id, name: item.name })}
            />
          )}
        </TabsContent>
      </Tabs>

      <PromptUsageDialog
        open={!!usageTarget}
        onOpenChange={(open) => {
          if (!open) setUsageTarget(null);
        }}
        title={usageTarget ? `Usage: ${usageTarget.name}` : 'Usage'}
        usage={usageQuery.data}
        isLoading={usageQuery.isLoading}
      />

      <DescriptionFormDialog
        key={editingItem ? `description-${editingItem.id}` : 'description-create'}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingItem(null);
          }
        }}
        title={editingItem ? 'Edit Description' : 'Create Description'}
        defaultItem={editingItem}
        onSubmit={handleFormSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
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

function StructuresTab() {
  const { data: structures, isLoading, isError, refetch } = useStructures();
  const {
    data: userStructures,
    isLoading: isUserLoading,
    isError: isUserError,
    refetch: refetchUserStructures,
  } = useUserOwnedStructures();
  const createMutation = useCreateStructure();
  const updateMutation = useUpdateStructure();
  const deleteMutation = useDeleteStructure();

  const [scopeTab, setScopeTab] = useState<PromptScopeTabKey>('camxora');
  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MusicStructure | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MusicStructure | null>(null);
  const [usageTarget, setUsageTarget] = useState<{ id: string; name: string } | null>(null);
  const usageQuery = useStructureUsage(usageTarget?.id ?? null);

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
      return;
    }

    createMutation.mutate(payload, {
      onSuccess: () => setFormOpen(false),
    });
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
      <Tabs value={scopeTab} onValueChange={(value) => setScopeTab(value as PromptScopeTabKey)}>
        <TabsList className="border border-slate-800 bg-slate-900/60">
          <TabsTrigger value="camxora">Camxora Prompts</TabsTrigger>
          <TabsTrigger value="user">User Prompts</TabsTrigger>
        </TabsList>

        <TabsContent value="camxora" className="space-y-4">
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
                <TableHead className="w-[120px]">Visibility</TableHead>
                <TableHead className="w-[90px]">Uses</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
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
                        <Badge className={getMatchKeyColor(item.match_key)} variant="outline">
                          {item.match_key}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={getVisibilityBadge(item.is_active)} variant="outline">
                        {item.is_active ? 'Visible' : 'Hidden'}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.usage_count ?? 0}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title={item.is_active ? 'Currently visible in onboarding. Click to hide.' : 'Currently hidden from onboarding. Click to show.'}
                          onClick={() =>
                            updateMutation.mutate({
                              id: item.id,
                              updates: { is_active: !item.is_active },
                            })
                          }
                        >
                          {item.is_active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="View usage by user"
                          onClick={() => setUsageTarget({ id: item.id, name: item.name })}
                        >
                          <BarChart3 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(item)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(item)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No structures yet. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="user" className="space-y-4">
          {isUserLoading ? (
            <TableSkeleton />
          ) : isUserError ? (
            <div className="text-center py-8 space-y-4">
              <p className="text-destructive">Failed to load user structures.</p>
              <Button variant="outline" onClick={() => refetchUserStructures()}>
                Retry
              </Button>
            </div>
          ) : (
            <UserPromptTable
              items={userStructures ?? []}
              kindLabel="Structure"
              onViewUsage={(item) => setUsageTarget({ id: item.id, name: item.name })}
            />
          )}
        </TabsContent>
      </Tabs>

      <PromptUsageDialog
        open={!!usageTarget}
        onOpenChange={(open) => {
          if (!open) setUsageTarget(null);
        }}
        title={usageTarget ? `Usage: ${usageTarget.name}` : 'Usage'}
        usage={usageQuery.data}
        isLoading={usageQuery.isLoading}
      />

      <PromptFormDialog
        key={editingItem ? `structure-${editingItem.id}` : 'structure-create'}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingItem(null);
          }
        }}
        title={editingItem ? 'Edit Structure' : 'Create Structure'}
        defaultValues={
          editingItem
            ? { name: editingItem.name, content: editingItem.content, match_key: editingItem.match_key ?? '' }
            : undefined
        }
        onSubmit={handleFormSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
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

function MoodsTab() {
  const { data: moods, isLoading, isError, refetch } = useMoods();
  const {
    data: userMoods,
    isLoading: isUserLoading,
    isError: isUserError,
    refetch: refetchUserMoods,
  } = useAdminUserMoods();
  const createMutation = useCreateMood();
  const updateMutation = useUpdateMood();
  const deleteMutation = useDeleteMood();

  const [scopeTab, setScopeTab] = useState<PromptScopeTabKey>('camxora');
  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MusicMood | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MusicMood | null>(null);
  const [usageTarget, setUsageTarget] = useState<{ id: string; name: string } | null>(null);
  const usageQuery = useMoodUsage(usageTarget?.id ?? null);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: MusicMood) {
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
      return;
    }

    createMutation.mutate(payload, {
      onSuccess: () => setFormOpen(false),
    });
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
        <p className="text-destructive">Failed to load moods.</p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Tabs value={scopeTab} onValueChange={(value) => setScopeTab(value as PromptScopeTabKey)}>
        <TabsList className="border border-slate-800 bg-slate-900/60">
          <TabsTrigger value="camxora">Camxora Prompts</TabsTrigger>
          <TabsTrigger value="user">User Prompts</TabsTrigger>
        </TabsList>

        <TabsContent value="camxora" className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create Mood
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Content</TableHead>
                <TableHead>Match Key</TableHead>
                <TableHead className="w-[120px]">Visibility</TableHead>
                <TableHead className="w-[90px]">Uses</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {moods && moods.length > 0 ? (
                moods.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {truncateContent(item.content)}
                    </TableCell>
                    <TableCell>
                      {item.match_key ? (
                        <Badge className={getMatchKeyColor(item.match_key)} variant="outline">
                          {item.match_key}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={getVisibilityBadge(item.is_active)} variant="outline">
                        {item.is_active ? 'Visible' : 'Hidden'}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.usage_count ?? 0}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title={item.is_active ? 'Currently visible in onboarding. Click to hide.' : 'Currently hidden from onboarding. Click to show.'}
                          onClick={() =>
                            updateMutation.mutate({
                              id: item.id,
                              updates: { is_active: !item.is_active },
                            })
                          }
                        >
                          {item.is_active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="View usage by user"
                          onClick={() => setUsageTarget({ id: item.id, name: item.name })}
                        >
                          <BarChart3 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(item)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(item)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No moods yet. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="user" className="space-y-4">
          {isUserLoading ? (
            <TableSkeleton />
          ) : isUserError ? (
            <div className="text-center py-8 space-y-4">
              <p className="text-destructive">Failed to load user moods.</p>
              <Button variant="outline" onClick={() => refetchUserMoods()}>
                Retry
              </Button>
            </div>
          ) : (
            <UserPromptTable
              items={userMoods ?? []}
              kindLabel="Mood"
              onViewUsage={(item) => setUsageTarget({ id: item.id, name: item.name })}
            />
          )}
        </TabsContent>
      </Tabs>

      <PromptUsageDialog
        open={!!usageTarget}
        onOpenChange={(open) => {
          if (!open) setUsageTarget(null);
        }}
        title={usageTarget ? `Usage: ${usageTarget.name}` : 'Usage'}
        usage={usageQuery.data}
        isLoading={usageQuery.isLoading}
      />

      <PromptFormDialog
        key={editingItem ? `mood-${editingItem.id}` : 'mood-create'}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingItem(null);
          }
        }}
        title={editingItem ? 'Edit Mood' : 'Create Mood'}
        defaultValues={
          editingItem
            ? { name: editingItem.name, content: editingItem.content, match_key: editingItem.match_key ?? '' }
            : undefined
        }
        onSubmit={handleFormSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete Mood"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        onConfirm={handleDeleteConfirm}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

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

  useEffect(() => {
    if (open) {
      form.reset(defaultValues ?? { name: '', content: '', match_key: '' });
    }
  }, [defaultValues, form, open]);

  const handleSubmit = form.handleSubmit((values) => {
    onSubmit(values);
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
            {form.formState.errors.name ? (
              <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-content">Content</Label>
            <Textarea
              id="prompt-content"
              placeholder="Enter the prompt content..."
              rows={6}
              {...form.register('content')}
            />
            {form.formState.errors.content ? (
              <p className="text-sm text-destructive">{form.formState.errors.content.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-match-key">Match Key (optional)</Label>
            <Input
              id="prompt-match-key"
              placeholder="e.g., pop-ballad"
              {...form.register('match_key')}
            />
            {form.formState.errors.match_key ? (
              <p className="text-sm text-destructive">{form.formState.errors.match_key.message}</p>
            ) : null}
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
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {defaultValues ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

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
