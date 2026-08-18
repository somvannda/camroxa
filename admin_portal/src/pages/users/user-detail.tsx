import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowLeft, Loader2, CreditCard, Crown, Users, Music, KeyRound, RotateCcw } from 'lucide-react';

import {
  useUpdateUser,
  useSuspendUser,
  useReactivateUser,
  useDeleteUser,
  useSetUserPassword,
  useUserDetails,
  useQuotaTopup,
  useFreezeGeneration,
  useUnfreezeGeneration,
  useChannelProfileLogoBlob,
  useChannelProfileCoverBlob,
} from '@/hooks/use-users';
import { useFailAbsorb, useResetFailAbsorb } from '@/hooks/use-fail-absorb';
import { useAdjustBalance } from '@/hooks/use-credits';
import { useToast } from '@/hooks/use-toast';
import { formatCredits } from '@/lib/credit-format';
import type { User, QuotaPeriodSnapshot } from '@/types/models';

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

const setPasswordSchema = z
  .object({
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Must include an uppercase letter')
      .regex(/[a-z]/, 'Must include a lowercase letter')
      .regex(/[0-9]/, 'Must include a digit'),
    confirm_password: z.string().min(1, 'Confirm the password'),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type SetPasswordFormValues = z.infer<typeof setPasswordSchema>;

const quotaTopupSchema = z.object({
  quota_kind: z.enum(['draft', 'music', 'image', 'video', 'merge']),
  amount: z.number().int().positive('Amount must be a positive integer'),
  reason: z.string().min(1, 'Reason is required').max(500),
});

type QuotaTopupFormValues = z.infer<typeof quotaTopupSchema>;

const creditTopupSchema = z.object({
  amount: z
    .number({ invalid_type_error: 'Amount is required' })
    .refine((v) => v !== 0, 'Amount cannot be zero'),
  reason: z.string().min(1, 'Reason is required').max(500),
});

type CreditTopupFormValues = z.infer<typeof creditTopupSchema>;

const QUOTA_KIND_LABELS: Record<QuotaTopupFormValues['quota_kind'], string> = {
  draft: 'Draft (album / title / lyrics)',
  music: 'Suno packages',
  image: 'Images',
  video: 'Export (video)',
  merge: 'Merge',
};

const QUOTA_KIND_ORDER: QuotaTopupFormValues['quota_kind'][] = [
  'draft',
  'music',
  'image',
  'video',
  'merge',
];

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

function formatQuotaPeriodLabel(snapshot: QuotaPeriodSnapshot | null | undefined): string {
  if (!snapshot?.period_start || !snapshot?.period_end) {
    return 'No active billing period';
  }
  return `Period ${snapshot.period_start} → ${snapshot.period_end} (top-ups reset at period end)`;
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
  const freezeGeneration = useFreezeGeneration();
  const unfreezeGeneration = useUnfreezeGeneration();
  const deleteUser = useDeleteUser();
  const setUserPassword = useSetUserPassword();
  const quotaTopup = useQuotaTopup(id!);
  const adjustBalance = useAdjustBalance();
  const { data: failAbsorb, isLoading: failAbsorbLoading, isError: failAbsorbError, refetch: refetchFailAbsorb } =
    useFailAbsorb(id!);
  const resetFailAbsorb = useResetFailAbsorb(id!);

  // Dialog states
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [reactivateDialogOpen, setReactivateDialogOpen] = useState(false);
  const [freezeDialogOpen, setFreezeDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [quotaTopupOpen, setQuotaTopupOpen] = useState(false);
  const [creditTopupOpen, setCreditTopupOpen] = useState(false);
  const [failAbsorbResetOpen, setFailAbsorbResetOpen] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');
  const [freezeReason, setFreezeReason] = useState('');
  const [freezeHours, setFreezeHours] = useState('6');

  // Edit form
  const form = useForm<UserEditFormValues>({
    resolver: zodResolver(userEditSchema),
    values: user
      ? { display_name: user.display_name, role: user.role }
      : { display_name: '', role: 'user' },
  });

  const passwordForm = useForm<SetPasswordFormValues>({
    resolver: zodResolver(setPasswordSchema),
    defaultValues: { password: '', confirm_password: '' },
  });

  const quotaForm = useForm<QuotaTopupFormValues>({
    resolver: zodResolver(quotaTopupSchema),
    defaultValues: { quota_kind: 'draft', amount: 10, reason: '' },
  });

  const creditForm = useForm<CreditTopupFormValues>({
    resolver: zodResolver(creditTopupSchema),
    defaultValues: { amount: 0, reason: '' },
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

  const handleSetPassword = (values: SetPasswordFormValues) => {
    if (!id) return;
    setUserPassword.mutate(
      { id, password: values.password },
      {
        onSuccess: () => {
          toast({
            title: 'Password updated',
            description: 'The user can sign in with the new password. Existing sessions were revoked.',
          });
          setPasswordDialogOpen(false);
          passwordForm.reset();
        },
        onError: (err) => {
          toast({
            variant: 'destructive',
            title: 'Password change failed',
            description: err instanceof Error ? err.message : 'An error occurred',
          });
        },
      },
    );
  };

  const handleQuotaTopup = (values: QuotaTopupFormValues) => {
    if (!id) return;
    quotaTopup.mutate(values, {
      onSuccess: () => {
        toast({
          title: 'Quota topped up',
          description: `Added ${values.amount} ${QUOTA_KIND_LABELS[values.quota_kind]} for this billing period.`,
        });
        setQuotaTopupOpen(false);
        quotaForm.reset({ quota_kind: values.quota_kind, amount: 10, reason: '' });
        refetch();
      },
      onError: (err) => {
        toast({
          variant: 'destructive',
          title: 'Quota top-up failed',
          description: err instanceof Error ? err.message : 'An error occurred',
        });
      },
    });
  };

  const handleCreditTopup = async (values: CreditTopupFormValues) => {
    if (!id) return;
    try {
      const result = await adjustBalance.mutateAsync({
        user_id: id,
        amount: values.amount,
        reason: values.reason,
      });
      const pending =
        result &&
        typeof result === 'object' &&
        'requires_approval' in result &&
        Boolean((result as { requires_approval?: boolean }).requires_approval);
      toast({
        title: pending ? 'Queued for dual-control approval' : 'Credits adjusted',
        description: pending
          ? 'A second admin must approve this large adjustment before it applies.'
          : `Wallet adjusted by ${values.amount} credits.`,
      });
      setCreditTopupOpen(false);
      creditForm.reset({ amount: 0, reason: '' });
      refetch();
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Credit adjustment failed',
        description: err instanceof Error ? err.message : 'An error occurred',
      });
    }
  };

  const handleFailAbsorbReset = () => {
    if (!id) return;
    resetFailAbsorb.mutate(undefined, {
      onSuccess: (result) => {
        const previous = result.fail_absorb_used_before ?? failAbsorb?.fail_absorb_used ?? 0;
        toast({
          title: 'Fail/retry absorb reset',
          description: `Cleared today's counter (was ${previous}). User can generate again.`,
        });
        setFailAbsorbResetOpen(false);
      },
      onError: (err) => {
        toast({
          variant: 'destructive',
          title: 'Reset failed',
          description: err instanceof Error ? err.message : 'An error occurred',
        });
      },
    });
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

  const handleFreezeGeneration = () => {
    if (!id || !freezeReason.trim()) return;
    freezeGeneration.mutate(
      { id, hours: Number(freezeHours), reason: freezeReason.trim() },
      {
        onSuccess: () => {
          toast({
            title: 'Generation frozen',
            description: `Music generation paused for ${freezeHours} hours.`,
          });
          setFreezeDialogOpen(false);
          setFreezeReason('');
          refetch();
        },
        onError: (err) => {
          toast({
            variant: 'destructive',
            title: 'Freeze failed',
            description: err instanceof Error ? err.message : 'An error occurred',
          });
        },
      },
    );
  };

  const handleUnfreezeGeneration = () => {
    if (!id) return;
    unfreezeGeneration.mutate(id, {
      onSuccess: () => {
        toast({ title: 'Generation unfrozen', description: 'The user can generate music again.' });
        refetch();
      },
      onError: (err) => {
        toast({
          variant: 'destructive',
          title: 'Unfreeze failed',
          description: err instanceof Error ? err.message : 'An error occurred',
        });
      },
    });
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

      {/* Period quota + top-ups */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="text-slate-100">Plan Quota (this period)</CardTitle>
            <CardDescription className="text-slate-400">
              {formatQuotaPeriodLabel(user.quota_period)}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              className="border-slate-700"
              onClick={() => setCreditTopupOpen(true)}
            >
              Top up credits
            </Button>
            <Button type="button" onClick={() => setQuotaTopupOpen(true)}>
              Top up quota
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {!user.quota_period?.period_start ? (
            <p className="text-sm text-slate-500">
              No active subscription period. Assign a plan before topping up quota.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800">
                  <TableHead className="text-slate-400">Quota</TableHead>
                  <TableHead className="text-slate-400">Used</TableHead>
                  <TableHead className="text-slate-400">Base</TableHead>
                  <TableHead className="text-slate-400">Top-up</TableHead>
                  <TableHead className="text-slate-400">Effective</TableHead>
                  <TableHead className="text-slate-400">Remaining</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {QUOTA_KIND_ORDER.map((kind) => {
                  const row = user.quota_period?.kinds?.[kind];
                  return (
                    <TableRow key={kind} className="border-slate-800">
                      <TableCell className="text-slate-200">
                        {QUOTA_KIND_LABELS[kind]}
                      </TableCell>
                      <TableCell className="text-slate-300">{row?.used ?? 0}</TableCell>
                      <TableCell className="text-slate-300">
                        {row?.base_limit == null ? 'Unlimited' : row.base_limit}
                      </TableCell>
                      <TableCell className="text-slate-300">
                        {row?.topup_extra ? `+${row.topup_extra}` : '—'}
                      </TableCell>
                      <TableCell className="text-slate-100 font-medium">
                        {row?.effective_limit == null ? 'Unlimited' : row.effective_limit}
                      </TableCell>
                      <TableCell className="text-slate-100">
                        {row?.remaining == null ? '—' : row.remaining}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Fail / retry absorb (today) */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-slate-100">
              <RotateCcw className="h-4 w-4 text-slate-500" />
              Fail / Retry Absorb (today)
            </CardTitle>
            <CardDescription className="text-slate-400">
              Platform-absorbed failed plan generations for {failAbsorb?.usage_date ?? 'today'}.
              Budget is set under Settings → Fail / Retry Absorb.
            </CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            className="border-slate-700"
            disabled={
              failAbsorbLoading ||
              !failAbsorb ||
              (failAbsorb.fail_absorb_used ?? 0) <= 0 ||
              resetFailAbsorb.isPending
            }
            onClick={() => setFailAbsorbResetOpen(true)}
          >
            Reset today
          </Button>
        </CardHeader>
        <CardContent>
          {failAbsorbLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading absorb counter…
            </div>
          ) : failAbsorbError ? (
            <div className="space-y-2">
              <p className="text-sm text-slate-400">Could not load fail/retry absorb status.</p>
              <Button type="button" variant="outline" size="sm" onClick={() => refetchFailAbsorb()}>
                Retry
              </Button>
            </div>
          ) : failAbsorb ? (
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs text-slate-500">Used / budget</p>
                <p className="text-2xl font-bold text-slate-100">
                  {failAbsorb.fail_absorb_used}
                  <span className="text-slate-500 text-lg font-normal">
                    {' '}
                    / {failAbsorb.fail_absorb_budget}
                  </span>
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Remaining</p>
                <p className="text-lg font-medium text-slate-200">
                  {failAbsorb.remaining == null ? '—' : failAbsorb.remaining}
                </p>
              </div>
              <Badge
                variant="outline"
                className={
                  failAbsorb.blocked
                    ? 'border-red-500/40 text-red-300'
                    : 'border-emerald-500/40 text-emerald-300'
                }
              >
                {failAbsorb.blocked ? 'Blocked' : 'OK'}
              </Badge>
            </div>
          ) : null}
        </CardContent>
      </Card>

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
            {user.generation_frozen
              ? ` — music generation frozen${
                  user.generation_frozen_retry_after
                    ? ` (~${Math.max(1, Math.ceil(user.generation_frozen_retry_after / 3600))}h left`
                    : ''
                }${user.generation_frozen_reason ? `, ${user.generation_frozen_reason}` : ''}${
                  user.generation_frozen_retry_after ? ')' : ''
                }`
              : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            className="border-slate-600 text-slate-200"
            onClick={() => {
              passwordForm.reset();
              setPasswordDialogOpen(true);
            }}
          >
            <KeyRound className="mr-2 h-4 w-4" />
            Change Password
          </Button>

          {user.status === 'active' && (
            <Button
              variant="outline"
              className="border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
              onClick={() => setSuspendDialogOpen(true)}
            >
              Suspend User
            </Button>
          )}

          {user.generation_frozen ? (
            <Button
              variant="outline"
              className="border-green-500/30 text-green-400 hover:bg-green-500/10"
              onClick={handleUnfreezeGeneration}
              disabled={unfreezeGeneration.isPending}
            >
              {unfreezeGeneration.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Unfreeze Generation
            </Button>
          ) : (
            <Button
              variant="outline"
              className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
              onClick={() => setFreezeDialogOpen(true)}
            >
              Freeze Generation
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

      <Dialog open={freezeDialogOpen} onOpenChange={setFreezeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Freeze music generation</DialogTitle>
            <DialogDescription>
              Pause this user&apos;s music-web generate for a set time. They can still browse
              and listen. Full suspend remains available for a complete lockout.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <p className="text-sm text-slate-300">Duration</p>
              <Select value={freezeHours} onValueChange={setFreezeHours}>
                <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 hour</SelectItem>
                  <SelectItem value="6">6 hours</SelectItem>
                  <SelectItem value="24">24 hours</SelectItem>
                  <SelectItem value="72">72 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Textarea
              placeholder="Reason for freeze..."
              value={freezeReason}
              onChange={(e) => setFreezeReason(e.target.value)}
              className="bg-slate-800 border-slate-700 text-slate-100"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setFreezeDialogOpen(false)}
              disabled={freezeGeneration.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleFreezeGeneration}
              disabled={!freezeReason.trim() || freezeGeneration.isPending}
              className="bg-orange-600 hover:bg-orange-700"
            >
              {freezeGeneration.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Freeze
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

      <ConfirmDialog
        open={failAbsorbResetOpen}
        onOpenChange={setFailAbsorbResetOpen}
        title="Reset fail/retry absorb"
        description={`Clear today's platform absorb counter for "${user.display_name}" (currently ${failAbsorb?.fail_absorb_used ?? 0} / ${failAbsorb?.fail_absorb_budget ?? '—'})? They will be able to generate again immediately.`}
        onConfirm={handleFailAbsorbReset}
        variant="default"
        confirmText="Reset counter"
        isLoading={resetFailAbsorb.isPending}
      />

      <Dialog
        open={passwordDialogOpen}
        onOpenChange={(open) => {
          setPasswordDialogOpen(open);
          if (!open) passwordForm.reset();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change password</DialogTitle>
            <DialogDescription>
              Set a new password for{' '}
              <span className="font-semibold text-slate-200">{user.email}</span>.
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

      <Dialog
        open={quotaTopupOpen}
        onOpenChange={(open) => {
          setQuotaTopupOpen(open);
          if (!open) quotaForm.reset({ quota_kind: 'draft', amount: 10, reason: '' });
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Top up plan quota</DialogTitle>
            <DialogDescription>
              Adds units to this user&apos;s effective period limit. Top-ups expire when the
              billing period ends ({user.quota_period?.period_end ?? 'unknown'}).
            </DialogDescription>
          </DialogHeader>
          <Form {...quotaForm}>
            <form onSubmit={quotaForm.handleSubmit(handleQuotaTopup)} className="space-y-4">
              <FormField
                control={quotaForm.control}
                name="quota_kind"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quota type</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select quota" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {QUOTA_KIND_ORDER.map((kind) => (
                          <SelectItem key={kind} value={kind}>
                            {QUOTA_KIND_LABELS[kind]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={quotaForm.control}
                name="amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Amount</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={1}
                        step={1}
                        value={field.value}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={quotaForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Why are you topping up this quota?" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setQuotaTopupOpen(false)}
                  disabled={quotaTopup.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={quotaTopup.isPending}>
                  {quotaTopup.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Apply top-up
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={creditTopupOpen}
        onOpenChange={(open) => {
          setCreditTopupOpen(open);
          if (!open) creditForm.reset({ amount: 0, reason: '' });
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Top up credits</DialogTitle>
            <DialogDescription>
              Adjust wallet balance for {user.email}. Positive adds credits; negative deducts.
              Applies immediately (admin-only, audit-logged).
            </DialogDescription>
          </DialogHeader>
          <Form {...creditForm}>
            <form onSubmit={creditForm.handleSubmit(handleCreditTopup)} className="space-y-4">
              <FormField
                control={creditForm.control}
                name="amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Amount</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
                        value={Number.isFinite(field.value) ? field.value : ''}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                        placeholder="Positive to add, negative to deduct"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={creditForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Reason for adjustment" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCreditTopupOpen(false)}
                  disabled={adjustBalance.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={adjustBalance.isPending}>
                  {adjustBalance.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Adjust balance
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
