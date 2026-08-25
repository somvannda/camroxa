import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, KeyRound, Trash2 } from 'lucide-react';
import { AxiosError } from 'axios';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { FilterBar } from '@/components/data-table/filter-bar';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSetUserPassword, useUsers } from '@/hooks/use-users';
import { toast } from '@/hooks/use-toast';
import { formatVerificationDurationShort } from '@/lib/format-datetime';
import httpClient from '@/lib/http-client';
import type { User } from '@/types/models';
import type { UserListParams } from '@/types/api';

const PAGE_SIZE = 25;

const STATUS_BADGE_CLASSES: Record<User['status'], string> = {
  active: 'border-green-500/30 bg-green-500/10 text-green-400',
  suspended: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  deleted: 'border-red-500/30 bg-red-500/10 text-red-400',
};

const createUserSchema = z.object({
  email: z.string().email('Valid email required'),
  password: z.string().min(8, 'At least 8 characters'),
  display_name: z.string().min(2, 'At least 2 characters').max(50),
});

type CreateUserFormValues = z.infer<typeof createUserSchema>;

const setPasswordSchema = z
  .object({
    password: z
      .string()
      .min(8, 'At least 8 characters')
      .max(128)
      .regex(/[A-Z]/, 'Need an uppercase letter')
      .regex(/[a-z]/, 'Need a lowercase letter')
      .regex(/\d/, 'Need a digit'),
    confirm_password: z.string().min(1, 'Confirm the password'),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type SetPasswordFormValues = z.infer<typeof setPasswordSchema>;

export default function UsersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [userForPassword, setUserForPassword] = useState<User | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const setUserPassword = useSetUserPassword();

  const params: UserListParams = {
    page,
    page_size: PAGE_SIZE,
    ...(statusFilter !== 'all' && { status: statusFilter as UserListParams['status'] }),
    ...(fromDate && { from_date: fromDate }),
    ...(toDate && { to_date: toDate }),
  };

  const { data, isLoading, isError, error, refetch } = useUsers(params);

  const handleRowClick = (user: User) => {
    navigate(`/users/${user.id}`);
  };

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const handlePasswordClick = (user: User) => {
    setUserForPassword(user);
    passwordForm.reset({ password: '', confirm_password: '' });
    setPasswordDialogOpen(true);
  };

  async function handleCopyCode(event: React.MouseEvent, code: string) {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(code);
      toast({ title: 'Code copied', description: code });
    } catch {
      toast({
        variant: 'destructive',
        title: 'Copy failed',
        description: 'Could not copy to clipboard.',
      });
    }
  }

  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    setIsDeleting(true);
    try {
      await httpClient.delete(`/api/v3/users/${userToDelete.id}/permanent`);
      toast({ title: 'User permanently deleted' });
      setDeleteDialogOpen(false);
      setUserToDelete(null);
      refetch();
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: { message?: string } }>;
      toast({
        title: 'Error',
        description: axiosError.response?.data?.error?.message ?? 'Failed to delete user',
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const columns: ColumnDef<User>[] = [
    {
      id: 'email',
      header: 'Email',
      accessorFn: (row) => <span className="text-slate-200">{row.email}</span>,
      sortable: true,
    },
    {
      id: 'email_confirmed',
      header: 'Email status',
      accessorFn: (row) => (
        row.email_confirmed ? (
          <Badge variant="outline" className="border-green-500/30 bg-green-500/10 text-green-400">
            Verified
          </Badge>
        ) : (
          <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-300">
            Pending
          </Badge>
        )
      ),
    },
    {
      id: 'pending_verification_code',
      header: 'Confirm code',
      accessorFn: (row) => {
        if (row.email_confirmed) {
          return <span className="text-slate-500">—</span>;
        }
        if (!row.pending_verification_code) {
          return <span className="text-slate-500 italic">Not sent</span>;
        }
        const duration = formatVerificationDurationShort(row.verification_code_expires_at);
        return (
          <button
            type="button"
            onClick={(event) => handleCopyCode(event, row.pending_verification_code!)}
            className={`rounded px-1.5 py-0.5 font-mono text-sm tracking-widest transition-colors hover:bg-fuchsia-500/10 ${
              duration.expired
                ? 'text-slate-500 line-through'
                : 'text-fuchsia-200 hover:text-fuchsia-100'
            }`}
            title="Click to copy code"
          >
            {row.pending_verification_code}
          </button>
        );
      },
    },
    {
      id: 'verification_code_expires_at',
      header: 'Expires',
      accessorFn: (row) => {
        if (row.email_confirmed || !row.pending_verification_code) {
          return <span className="text-slate-500">—</span>;
        }
        const duration = formatVerificationDurationShort(row.verification_code_expires_at);
        if (!row.verification_code_expires_at) {
          return <span className="text-slate-500">—</span>;
        }
        return (
          <span className={duration.expired ? 'text-red-400' : 'text-amber-300'}>
            {duration.label}
          </span>
        );
      },
    },
    {
      id: 'display_name',
      header: 'Display Name',
      accessorFn: (row) => <span className="text-slate-300">{row.display_name}</span>,
      sortable: true,
    },
    {
      id: 'role',
      header: 'Role',
      accessorFn: (row) => (
        <span className="capitalize text-slate-300">{row.role}</span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      accessorFn: (row) => (
        <Badge variant="outline" className={STATUS_BADGE_CLASSES[row.status]}>
          {row.status}
        </Badge>
      ),
    },
    {
      id: 'credit_balance',
      header: 'Credits',
      accessorFn: (row) => (
        <span className="text-slate-200 font-medium">
          {row.credit_balance.toLocaleString()} cr
        </span>
      ),
    },
    {
      id: 'credits_burned',
      header: 'Burned',
      accessorFn: (row) => {
        if (row.credits_burned == null) {
          return <span className="text-slate-500">—</span>;
        }
        return (
          <span className="text-slate-200">
            {row.credits_burned.toLocaleString()} cr
          </span>
        );
      },
    },
    {
      id: 'plan_name',
      header: 'Plan',
      accessorFn: (row) => (
        row.plan_name
          ? <span className="text-slate-200">{row.plan_name}</span>
          : <span className="text-slate-500 italic">No plan</span>
      ),
    },
    {
      id: 'channel_profile_count',
      header: 'Profiles',
      accessorFn: (row) => (
        <span className="text-slate-300">{row.channel_profile_count}</span>
      ),
    },
    {
      id: 'created_at',
      header: 'Registered',
      accessorFn: (row) => (
        <span className="text-slate-400">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'actions',
      header: '',
      accessorFn: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handlePasswordClick(row);
            }}
            className="rounded p-1.5 text-slate-400 hover:bg-fuchsia-500/10 hover:text-fuchsia-300 transition-colors"
            title="Change password"
          >
            <KeyRound className="h-4 w-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleDeleteClick(row);
            }}
            className="rounded p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-colors"
            title="Permanently delete user"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ];

  const createForm = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { email: '', password: '', display_name: '' },
  });

  const passwordForm = useForm<SetPasswordFormValues>({
    resolver: zodResolver(setPasswordSchema),
    defaultValues: { password: '', confirm_password: '' },
  });

  const handleSetPassword = (values: SetPasswordFormValues) => {
    if (!userForPassword) return;
    setUserPassword.mutate(
      { id: userForPassword.id, password: values.password },
      {
        onSuccess: () => {
          toast({
            title: 'Password updated',
            description: `${userForPassword.email} can sign in with the new password. Existing sessions were revoked.`,
          });
          setPasswordDialogOpen(false);
          setUserForPassword(null);
          passwordForm.reset();
        },
        onError: (err) => {
          const axiosError = err as AxiosError<{ error?: { message?: string } }>;
          toast({
            title: 'Failed to set password',
            description: axiosError.response?.data?.error?.message ?? 'Request failed',
            variant: 'destructive',
          });
        },
      },
    );
  };

  const handleCreateUser = async (values: CreateUserFormValues) => {
    setIsCreating(true);
    try {
      await httpClient.post('/api/v3/auth/register', values);
      toast({ title: 'User created successfully' });
      setCreateDialogOpen(false);
      createForm.reset();
      refetch();
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: { message?: string } }>;
      toast({
        title: 'Error',
        description: axiosError.response?.data?.error?.message ?? 'Failed to create user',
        variant: 'destructive',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleFromDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFromDate(e.target.value);
    setPage(1);
  };

  const handleToDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setToDate(e.target.value);
    setPage(1);
  };

  if (isError && !data) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Users</h1>
        <ErrorState
          message={error?.message ?? 'Failed to load users'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Users</h1>
        <Button onClick={() => setCreateDialogOpen(true)}>
          Create User
        </Button>
      </div>

      <DataTable<User>
        columns={columns}
        data={data?.items ?? []}
        totalCount={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
        onRowClick={handleRowClick}
        emptyMessage="No users found."
        filterBar={
          <FilterBar>
            <Select value={statusFilter} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
                <SelectItem value="deleted">Deleted</SelectItem>
              </SelectContent>
            </Select>

            <Input
              type="date"
              value={fromDate}
              onChange={handleFromDateChange}
              placeholder="From date"
              className="w-[160px]"
            />

            <Input
              type="date"
              value={toDate}
              onChange={handleToDateChange}
              placeholder="To date"
              className="w-[160px]"
            />
          </FilterBar>
        }
      />

      {/* Create User Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
            <DialogDescription>
              Create a new user account. They can log in immediately after creation.
            </DialogDescription>
          </DialogHeader>
          <Form {...createForm}>
            <form onSubmit={createForm.handleSubmit(handleCreateUser)} className="space-y-4">
              <FormField
                control={createForm.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder="user@example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="display_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Display Name</FormLabel>
                    <FormControl>
                      <Input placeholder="John Doe" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Min 8 characters" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)} disabled={isCreating}>Cancel</Button>
                <Button type="submit" disabled={isCreating}>
                  {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create User
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-400">Permanently Delete User</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The user <span className="font-semibold text-slate-200">{userToDelete?.email}</span> and all associated data will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete} disabled={isDeleting}>
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete Permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={passwordDialogOpen}
        onOpenChange={(open) => {
          setPasswordDialogOpen(open);
          if (!open) {
            setUserForPassword(null);
            passwordForm.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change password</DialogTitle>
            <DialogDescription>
              Set a new password for{' '}
              <span className="font-semibold text-slate-200">{userForPassword?.email}</span>.
              Their existing sessions will be signed out.
            </DialogDescription>
          </DialogHeader>
          <Form {...passwordForm}>
            <form onSubmit={passwordForm.handleSubmit(handleSetPassword)} className="space-y-4">
              <FormField
                control={passwordForm.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New password</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" placeholder="Min 8 chars, upper, lower, digit" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={passwordForm.control}
                name="confirm_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm password</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPasswordDialogOpen(false)}
                  disabled={setUserPassword.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={setUserPassword.isPending}>
                  {setUserPassword.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save password
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
