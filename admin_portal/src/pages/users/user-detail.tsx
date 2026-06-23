import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
} from '@/hooks/use-users';
import { useToast } from '@/hooks/use-toast';
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
              {user.credit_balance.toLocaleString()}
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
        <CardHeader>
          <CardTitle className="text-slate-100">Recent Transactions</CardTitle>
          <CardDescription className="text-slate-400">
            Last 10 credit transactions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user.recent_transactions.length === 0 ? (
            <p className="text-slate-500 text-sm">No transactions yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800">
                  <TableHead className="text-slate-400">Amount</TableHead>
                  <TableHead className="text-slate-400">Direction</TableHead>
                  <TableHead className="text-slate-400">Reason</TableHead>
                  <TableHead className="text-slate-400">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.recent_transactions.map((tx) => (
                  <TableRow key={tx.id} className="border-slate-800">
                    <TableCell className={tx.amount < 0 ? 'text-red-400' : 'text-green-400'}>
                      {tx.amount > 0 ? '+' : ''}{tx.amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-slate-300 capitalize">{tx.direction}</TableCell>
                    <TableCell className="text-slate-300">{tx.reason || '—'}</TableCell>
                    <TableCell className="text-slate-400">
                      {tx.created_at ? new Date(tx.created_at).toLocaleString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
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
            User's channel profiles
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user.channel_profiles.length === 0 ? (
            <p className="text-slate-500 text-sm">No channel profiles.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800">
                  <TableHead className="text-slate-400">Name</TableHead>
                  <TableHead className="text-slate-400">Folder</TableHead>
                  <TableHead className="text-slate-400">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.channel_profiles.map((profile) => (
                  <TableRow key={profile.id} className="border-slate-800">
                    <TableCell className="text-slate-200">{profile.name}</TableCell>
                    <TableCell className="text-slate-300">{profile.folder_name || '—'}</TableCell>
                    <TableCell className="text-slate-400">
                      {profile.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
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
