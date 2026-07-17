import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowLeft, Loader2, CreditCard, Crown, Users, Music } from 'lucide-react';

import {
  useUpdateUser,
  useSuspendUser,
  useReactivateUser,
  useDeleteUser,
  useUserDetails,
  useChannelProfileLogoBlob,
  useChannelProfileCoverBlob,
} from '@/hooks/use-users';
import { useToast } from '@/hooks/use-toast';
import { formatCredits } from '@/lib/credit-format';
import type { User } from '@/types/models';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { Skeleton } from '@/components/ui/skeleton';

// --- Zod schema for user edit form ---
const userEditSchema = z.object({
  display_name: z.string().min(1, 'Display name is required'),
  role: z.enum(['user', 'admin']),
});

type UserEditFormValues = z.infer<typeof userEditSchema>;

// --- Status badge styling ---
const STATUS_BADGE_CLASSES: Record<User['status'], string> = {
  active: 'border-green-500/30 bg-green-500/10 text-green-400',
  suspended: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  deleted: 'border-red-500/30 bg-red-500/10 text-red-400',
};

function useObjectUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const objUrl = URL.createObjectURL(blob);
    setUrl(objUrl);
    return () => URL.revokeObjectURL(objUrl);
  }, [blob]);
  return url;
}

function ProfileLogoCell({ profileId, enabled }: { profileId: string; enabled: boolean }) {
  const { data: blob } = useChannelProfileLogoBlob(enabled ? profileId : '');
  const url = useObjectUrl(blob);
  if (!enabled) return <div className="h-8 w-8 rounded bg-slate-800" />;
  if (!url) return <div className="h-8 w-8 rounded bg-slate-800" />;
  return <img src={url} alt="Logo" className="h-8 w-8 rounded object-cover" />;
}

function ProfileCoversCell({ profileId, coverCount }: { profileId: string; coverCount: number }) {
  const want = Math.min(2, Math.max(0, coverCount));
  const enabled0 = want >= 1;
  const enabled1 = want >= 2;
  const { data: blob0 } = useChannelProfileCoverBlob(enabled0 ? profileId : '', 0);
  const { data: blob1 } = useChannelProfileCoverBlob(enabled1 ? profileId : '', 1);
  const url0 = useObjectUrl(blob0);
  const url1 = useObjectUrl(blob1);
  const items = useMemo(() => [url0, url1].filter(Boolean) as string[], [url0, url1]);
  if (want === 0) return <span className="text-slate-500 text-sm">—</span>;
  return (
    <div className="flex items-center gap-2">
      {items.map((u) => (
        <img key={u} src={u} alt="Cover" className="h-8 w-14 rounded object-cover" />
      ))}
    </div>
  );
}

function formatAdminDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function formatVideoTemplateSummary(
  templateId: string | null | undefined,
  templateName: string | null | undefined,
  updatedAt: string | null | undefined,
  available: boolean | undefined,
): string {
  if (!templateId) {
    return 'Not linked';
  }
  if (!available) {
    return `${templateId} (not synced to server)`;
  }
  const label = templateName?.trim() || templateId;
  const savedAt = formatAdminDateTime(updatedAt);
  return savedAt === '—' ? label : `${label} — saved ${savedAt}`;
}

function ProfileMetaRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[150px_1fr] sm:items-start">
      <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
        {label}
      </span>
      <div className="min-w-0 text-sm text-slate-200 break-words">{value}</div>
    </div>
  );
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const { data: user, isLoading, isError, error, refetch } = useUserDetails(id!);

  const updateUser = useUpdateUser();
  const suspendUser = useSuspendUser();
  const reactivateUser = useReactivateUser();
  const deleteUser = useDeleteUser();

  // Dialog states
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [reactivateDialogOpen, setReactivateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');

  // Edit form
  const form = useForm<UserEditFormValues>({
    resolver: zodResolver(userEditSchema),
    values: user
      ? { display_name: user.display_name, role: user.role }
      : { display_name: '', role: 'user' },
  });

  // --- Handlers ---
  const handleUpdate = (values: UserEditFormValues) => {
    if (!id) return;
    updateUser.mutate(
      { id, updates: values },
      {
        onSuccess: () => {
          toast({ title: 'User updated', description: 'User details saved successfully.' });
          refetch();
        },
        onError: (err) => {
          toast({
            variant: 'destructive',
            title: 'Update failed',
            description: err instanceof Error ? err.message : 'An error occurred',
          });
        },
      },
    );
  };

  const handleSuspend = () => {
    if (!id || !suspendReason.trim()) return;
    suspendUser.mutate(
      { id, reason: suspendReason.trim() },
      {
        onSuccess: () => {
          toast({ title: 'User suspended', description: 'The user has been suspended.' });
          setSuspendDialogOpen(false);
          setSuspendReason('');
          refetch();
        },
        onError: (err) => {
          toast({
            variant: 'destructive',
            title: 'Suspend failed',
            description: err instanceof Error ? err.message : 'An error occurred',
          });
        },
      },
    );
  };

  const handleReactivate = () => {
    if (!id) return;
    reactivateUser.mutate(id, {
      onSuccess: () => {
        toast({ title: 'User reactivated', description: 'The user has been reactivated.' });
        setReactivateDialogOpen(false);
        refetch();
      },
      onError: (err) => {
        toast({
          variant: 'destructive',
          title: 'Reactivate failed',
          description: err instanceof Error ? err.message : 'An error occurred',
        });
      },
    });
  };

  const handleDelete = () => {
    if (!id) return;
    deleteUser.mutate(id, {
      onSuccess: () => {
        toast({ title: 'User deleted', description: 'The user has been deleted.' });
        navigate('/users');
      },
      onError: (err) => {
        toast({
          variant: 'destructive',
          title: 'Delete failed',
          description: err instanceof Error ? err.message : 'An error occurred',
        });
      },
    });
  };

  // --- Loading state ---
  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // --- Error state ---
  if (isError || !user) {
    return (
      <div className="p-6">
        <Button
          variant="ghost"
          size="sm"
          className="mb-4 text-slate-400"
          onClick={() => navigate('/users')}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Users
        </Button>
        <ErrorState
          message={error?.message ?? 'Failed to load user'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="text-slate-400"
          onClick={() => navigate('/users')}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-100">{user.display_name}</h1>
          <Badge variant="outline" className={STATUS_BADGE_CLASSES[user.status]}>
            {user.status}
          </Badge>
          <Badge variant="outline" className="border-slate-600 text-slate-300 capitalize">
            {user.role}
          </Badge>
        </div>
      </div>
      <p className="text-slate-400 -mt-4 ml-[76px]">{user.email}</p>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Credit Balance Card */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Credit Balance</CardTitle>
            <CreditCard className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">
              {formatCredits(user.credit_balance)}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {user.total_credits_spent.toLocaleString()} spent total
            </p>
          </CardContent>
        </Card>

        {/* Plan Card */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Plan</CardTitle>
            <Crown className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">
              {user.plan_name ?? <span className="text-slate-500 text-lg">No plan</span>}
            </div>
            {user.license_status && (
              <p className="text-xs text-slate-500 mt-1">
                Status: {user.license_status}
                {user.license_expires_at && (
                  <> · Expires {new Date(user.license_expires_at).toLocaleDateString()}</>
                )}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Profiles Card */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Profiles</CardTitle>
            <Users className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">
              {user.channel_profiles.length}
            </div>
            <p className="text-xs text-slate-500 mt-1">Channel profiles</p>
          </CardContent>
        </Card>

        {/* Usage Card */}
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Usage</CardTitle>
            <Music className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-100">
              {user.total_songs_generated}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Songs · {user.total_images_generated} images
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Edit form card */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-slate-100">Edit User</CardTitle>
          <CardDescription className="text-slate-400">
            Update display name and role
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleUpdate)} className="space-y-4">
              <FormField
                control={form.control}
                name="display_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-slate-300">Display Name</FormLabel>
                    <FormControl>
                      <Input {...field} className="bg-slate-800 border-slate-700 text-slate-100" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-slate-300">Role</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                          <SelectValue placeholder="Select a role" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="user">User</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" disabled={updateUser.isPending}>
                {updateUser.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      {/* Credit Transactions */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-slate-100">Recent Transactions</CardTitle>
            <CardDescription className="text-slate-400">
              Last 10 credit charges and refunds with provider and breakdown details
            </CardDescription>
          </div>
          <Button variant="outline" className="border-slate-700" asChild>
            <Link to={`/usage?user_id=${user.id}`}>View all usage</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {user.recent_transactions.length === 0 ? (
            <p className="text-slate-500 text-sm">No transactions yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800">
                  <TableHead className="text-slate-400">Cost</TableHead>
                  <TableHead className="text-slate-400">Direction</TableHead>
                  <TableHead className="text-slate-400">Purpose</TableHead>
                  <TableHead className="text-slate-400">Provider / Model</TableHead>
                  <TableHead className="text-slate-400">Breakdown</TableHead>
                  <TableHead className="text-slate-400">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.recent_transactions.map((tx) => {
                  const isDebit = tx.direction === 'debit';
                  const isRefund = tx.direction === 'refund';
                  const amountColor = isDebit
                    ? 'text-red-400'
                    : isRefund
                      ? 'text-amber-300'
                      : 'text-green-400';
                  const amountPrefix = isDebit ? '−' : '+';
                  return (
                    <TableRow key={tx.id} className="border-slate-800">
                      <TableCell className={amountColor}>
                        {amountPrefix}
                        {Math.abs(tx.amount).toLocaleString(undefined, {
                          maximumFractionDigits: 6,
                        })}
                      </TableCell>
                      <TableCell className="text-slate-300 capitalize">{tx.direction}</TableCell>
                      <TableCell className="text-slate-200">
                        <div>{tx.purpose || tx.reason || '—'}</div>
                        {tx.reason && tx.purpose && tx.reason !== tx.purpose && (
                          <div className="mt-1 font-mono text-xs text-slate-500">{tx.reason}</div>
                        )}
                      </TableCell>
                      <TableCell className="text-slate-300">
                        <div>{tx.provider || '—'}</div>
                        {tx.model && (
                          <div className="font-mono text-xs text-slate-500">{tx.model}</div>
                        )}
                      </TableCell>
                      <TableCell className="max-w-xs text-xs text-slate-400">
                        {tx.line_items_summary || '—'}
                      </TableCell>
                      <TableCell className="text-slate-400">
                        {tx.created_at ? new Date(tx.created_at).toLocaleString() : '—'}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Channel Profiles */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-slate-100">Channel Profiles</CardTitle>
          <CardDescription className="text-slate-400">
            Synced profile data saved from Electron and onboarding flows
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user.channel_profiles.length === 0 ? (
            <p className="text-slate-500 text-sm">No channel profiles.</p>
          ) : (
            <div className="space-y-4">
              {user.channel_profiles.map((profile) => (
                <div
                  key={profile.id}
                  className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 space-y-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <ProfileLogoCell profileId={profile.id} enabled={profile.logo_available} />
                      <div className="min-w-0">
                        <p className="text-base font-semibold text-slate-100 truncate">
                          {profile.name}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Badge variant="outline" className="border-slate-700 text-slate-300">
                            {profile.role || 'No role'}
                          </Badge>
                          <Badge variant="outline" className="border-slate-700 text-slate-300">
                            {profile.genre || 'No genre'}
                          </Badge>
                          <Badge variant="outline" className="border-slate-700 text-slate-300">
                            {profile.output_resolution || 'No resolution'}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <div className="text-right text-xs text-slate-400">
                      <p>Created</p>
                      <p className="mt-1 text-slate-300">
                        {formatAdminDateTime(profile.created_at)}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                    <div className="space-y-3">
                      <ProfileMetaRow label="Folder" value={profile.folder_name || '—'} />
                      <ProfileMetaRow label="Run Prefix" value={profile.run_prefix || '—'} />
                      <ProfileMetaRow
                        label="Video Template"
                        value={formatVideoTemplateSummary(
                          profile.video_template_id,
                          profile.video_template_name,
                          profile.video_template_updated_at,
                          profile.video_template_available,
                        )}
                      />
                      <ProfileMetaRow
                        label="Reel Template"
                        value={formatVideoTemplateSummary(
                          profile.reel_template_id,
                          profile.reel_template_name,
                          profile.reel_template_updated_at,
                          profile.reel_template_available,
                        )}
                      />
                      <ProfileMetaRow
                        label="Description"
                        value={profile.description || '—'}
                      />
                      <ProfileMetaRow
                        label="Keywords"
                        value={profile.keywords.length ? profile.keywords.join(', ') : '—'}
                      />
                      <ProfileMetaRow
                        label="Tags"
                        value={profile.tags.length ? profile.tags.join(', ') : '—'}
                      />
                    </div>

                    <div className="space-y-3">
                      <ProfileMetaRow label="Visibility" value={profile.visibility || '—'} />
                      <ProfileMetaRow
                        label="Publish At"
                        value={formatAdminDateTime(profile.publish_at)}
                      />
                      <ProfileMetaRow
                        label="Made For Kids"
                        value={profile.made_for_kids ? 'Yes' : 'No'}
                      />
                      <ProfileMetaRow label="AI Use" value={profile.ai_use ? 'Yes' : 'No'} />
                      <ProfileMetaRow label="Category" value={profile.category || '—'} />
                      <ProfileMetaRow label="Playlist" value={profile.playlist || '—'} />
                      <ProfileMetaRow
                        label="Title Template"
                        value={profile.title_template || '—'}
                      />
                      <ProfileMetaRow
                        label="Description Template"
                        value={profile.description_template || '—'}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                      Media
                    </p>
                    <div className="flex flex-wrap items-center gap-4">
                      <div>
                        <p className="text-xs text-slate-500">Logo</p>
                        <div className="mt-2">
                          <ProfileLogoCell
                            profileId={profile.id}
                            enabled={profile.logo_available}
                          />
                        </div>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-slate-500">Covers</p>
                        <div className="mt-2">
                          <ProfileCoversCell
                            profileId={profile.id}
                            coverCount={profile.cover_count}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-slate-100">Custom Music Prompts</CardTitle>
          <CardDescription className="text-slate-400">
            Descriptions and structures created by this user in the desktop app
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 xl:grid-cols-2">
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
              Descriptions ({user.custom_descriptions?.length ?? 0})
            </p>
            {user.custom_descriptions?.length ? (
              <div className="space-y-3">
                {user.custom_descriptions.map((item) => (
                  <div key={item.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-medium text-slate-100">{item.name}</p>
                      <Badge variant="outline" className="border-slate-700 text-slate-300">
                        {item.usage_count} uses
                      </Badge>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-400">{item.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No custom descriptions yet.</p>
            )}
          </div>
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
              Structures ({user.custom_structures?.length ?? 0})
            </p>
            {user.custom_structures?.length ? (
              <div className="space-y-3">
                {user.custom_structures.map((item) => (
                  <div key={item.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-medium text-slate-100">{item.name}</p>
                      <Badge variant="outline" className="border-slate-700 text-slate-300">
                        {item.usage_count} uses
                      </Badge>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap font-mono text-sm text-slate-400">{item.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No custom structures yet.</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions card */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-slate-100">Actions</CardTitle>
          <CardDescription className="text-slate-400">
            Manage user account status
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          {user.status === 'active' && (
            <Button
              variant="outline"
              className="border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
              onClick={() => setSuspendDialogOpen(true)}
            >
              Suspend User
            </Button>
          )}

          {user.status === 'suspended' && (
            <Button
              variant="outline"
              className="border-green-500/30 text-green-400 hover:bg-green-500/10"
              onClick={() => setReactivateDialogOpen(true)}
            >
              Reactivate User
            </Button>
          )}

          <Button
            variant="destructive"
            onClick={() => setDeleteDialogOpen(true)}
          >
            Delete User
          </Button>
        </CardContent>
      </Card>

      {/* Suspend dialog with reason */}
      <Dialog open={suspendDialogOpen} onOpenChange={setSuspendDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suspend User</DialogTitle>
            <DialogDescription>
              Please provide a reason for suspending this user. This will be recorded
              and visible to other admins.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Textarea
              placeholder="Reason for suspension..."
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
              className="bg-slate-800 border-slate-700 text-slate-100"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSuspendDialogOpen(false)}
              disabled={suspendUser.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="default"
              onClick={handleSuspend}
              disabled={!suspendReason.trim() || suspendUser.isPending}
              className="bg-yellow-600 hover:bg-yellow-700"
            >
              {suspendUser.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Suspend
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reactivate confirmation dialog */}
      <ConfirmDialog
        open={reactivateDialogOpen}
        onOpenChange={setReactivateDialogOpen}
        title="Reactivate User"
        description={`Are you sure you want to reactivate "${user.display_name}"? They will regain full access to the platform.`}
        onConfirm={handleReactivate}
        variant="default"
        confirmText="Reactivate"
        isLoading={reactivateUser.isPending}
      />

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete User"
        description={`Are you sure you want to delete "${user.display_name}"? This action cannot be undone.`}
        onConfirm={handleDelete}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteUser.isPending}
      />
    </div>
  );
}
