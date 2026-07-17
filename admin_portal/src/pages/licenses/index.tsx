import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AxiosError } from 'axios';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { FilterBar } from '@/components/data-table/filter-bar';
import { ErrorState } from '@/components/shared/error-state';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useLicenses,
  useCreateLicense,
  useAssignLicense,
  useRevokeLicense,
  useUpdateProfileAddonSlots,
  type LicenseListParams,
} from '@/hooks/use-licenses';
import { usePlans } from '@/hooks/use-plans';
import { useUsers } from '@/hooks/use-users';
import { toast } from '@/hooks/use-toast';
import type { License, Plan } from '@/types/models';

const PAGE_SIZE = 25;
const MAX_ACCOUNT_CHANNELS = 10;
const PROFILE_ADDON_STEP = 2;

const STATUS_BADGE_CLASSES: Record<License['status'], string> = {
  unassigned: 'border-slate-500/30 bg-slate-500/10 text-slate-400',
  active: 'border-green-500/30 bg-green-500/10 text-green-400',
  expired: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  revoked: 'border-red-500/30 bg-red-500/10 text-red-400',
};

interface AddonSlotRowProps {
  label: string;
  description: string;
  value: number;
  tone: 'pending' | 'active';
  canAdd: boolean;
  canRemove: boolean;
  isPending: boolean;
  onAdjust: (delta: number) => void;
}

function AddonSlotRow({
  label,
  description,
  value,
  tone,
  canAdd,
  canRemove,
  isPending,
  onAdjust,
}: AddonSlotRowProps) {
  const valueClass = tone === 'pending' ? 'text-amber-300' : 'text-green-400';

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-slate-700/60 p-4">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-200">{label}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="min-w-[3rem]"
          disabled={!canRemove || isPending}
          onClick={() => onAdjust(-PROFILE_ADDON_STEP)}
        >
          −2
        </Button>
        <span className={`w-8 text-center text-lg font-semibold tabular-nums ${valueClass}`}>
          {value}
        </span>
        <Button
          variant="outline"
          size="sm"
          className="min-w-[3rem]"
          disabled={!canAdd || isPending}
          onClick={() => onAdjust(PROFILE_ADDON_STEP)}
        >
          +2
        </Button>
      </div>
    </div>
  );
}

export default function SubscriptionsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Dialogs
  const [subscribeDialogOpen, setSubscribeDialogOpen] = useState(false);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [addonDialogOpen, setAddonDialogOpen] = useState(false);
  const [selectedSubscription, setSelectedSubscription] = useState<License | null>(null);

  // Subscribe form
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedPlanId, setSelectedPlanId] = useState('');

  const params: LicenseListParams = {
    page,
    page_size: PAGE_SIZE,
    ...(statusFilter !== 'all' && { status: statusFilter as License['status'] }),
  };

  const { data, isLoading, isError, error, refetch } = useLicenses(params);
  const { data: plans } = usePlans();
  const { data: usersData } = useUsers({ page: 1, page_size: 100 });
  const createLicense = useCreateLicense();
  const assignLicense = useAssignLicense();
  const revokeLicense = useRevokeLicense();
  const updateProfileAddonSlots = useUpdateProfileAddonSlots();

  // Map plan IDs to names for display
  const planMap = new Map(plans?.map(p => [p.id, p.name]) ?? []);
  const planDetailsMap = new Map(plans?.map(p => [p.id, p]) ?? []);
  // Map user IDs to emails for display
  const userMap = new Map(usersData?.items?.map(u => [u.id, u.email]) ?? []);
  const userProfileCountMap = new Map(
    usersData?.items?.map(u => [u.id, u.channel_profile_count]) ?? [],
  );

  const columns: ColumnDef<License>[] = [
    {
      id: 'user',
      header: 'User',
      accessorFn: (row) => (
        <span className="text-slate-200">
          {row.user_id ? (userMap.get(row.user_id) ?? row.user_id) : '—'}
        </span>
      ),
    },
    {
      id: 'plan',
      header: 'Plan',
      accessorFn: (row) => (
        <span className="text-slate-300">
          {planMap.get(row.plan_id) ?? row.plan_id}
        </span>
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
      id: 'profile_addon_pending',
      header: 'Pending add-on',
      accessorFn: (row) => (
        <span className="text-amber-300">{row.profile_addon_pending ?? 0}</span>
      ),
    },
    {
      id: 'profile_addon_slots',
      header: 'Active add-on',
      accessorFn: (row) => (
        <span className="text-green-400">{row.profile_addon_slots ?? 0}</span>
      ),
    },
    {
      id: 'activated_at',
      header: 'Start Date',
      accessorFn: (row) => (
        <span className="text-slate-400">
          {row.activated_at ? new Date(row.activated_at).toLocaleDateString() : '—'}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'expires_at',
      header: 'Expiry Date',
      accessorFn: (row) => (
        <span className="text-slate-400">
          {row.expires_at ? new Date(row.expires_at).toLocaleDateString() : '∞ (Lifetime)'}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'actions',
      header: 'Actions',
      accessorFn: (row) => (
        <div className="flex gap-2">
          {row.status === 'active' && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscription(row);
                  setAddonDialogOpen(true);
                }}
              >
                Add-ons
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSubscription(row);
                  setRevokeDialogOpen(true);
                }}
              >
                Cancel
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];

  const handleSubscribe = async () => {
    if (!selectedUserId || !selectedPlanId) return;

    try {
      // Step 1: Create a license for the plan
      const licenseResp = await createLicense.mutateAsync({ plan_id: selectedPlanId }) as { id: string };
      // Step 2: Assign it to the user (this sets activated_at and calculates expires_at)
      await assignLicense.mutateAsync({ id: licenseResp.id, user_id: selectedUserId });

      toast({ title: 'Subscription created', description: 'User has been subscribed to the plan.' });
      setSubscribeDialogOpen(false);
      setSelectedUserId('');
      setSelectedPlanId('');
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: { message?: string } }>;
      const msg = axiosError.response?.data?.error?.message ?? 'Failed to create subscription';
      toast({ title: 'Error', description: msg, variant: 'destructive' });
    }
  };

  const handleRevoke = () => {
    if (!selectedSubscription) return;
    revokeLicense.mutate(selectedSubscription.id, {
      onSuccess: () => {
        toast({ title: 'Subscription cancelled' });
        setRevokeDialogOpen(false);
        setSelectedSubscription(null);
      },
    });
  };

  const addonLicense = selectedSubscription
    ? (data?.items?.find((item) => item.id === selectedSubscription.id) ?? selectedSubscription)
    : null;
  const addonPlan: Plan | undefined = addonLicense
    ? planDetailsMap.get(addonLicense.plan_id)
    : undefined;
  const addonBaseChannels = addonPlan?.profile_allowance ?? 0;
  const addonPending = addonLicense?.profile_addon_pending ?? 0;
  const addonActive = addonLicense?.profile_addon_slots ?? 0;
  const addonTotalChannels = addonBaseChannels + addonPending + addonActive;
  const addonRemaining = MAX_ACCOUNT_CHANNELS - addonTotalChannels;
  const addonProfileCount = addonLicense?.user_id
    ? userProfileCountMap.get(addonLicense.user_id)
    : undefined;

  const canRemovePending =
    addonPending >= PROFILE_ADDON_STEP &&
    (addonProfileCount === undefined ||
      addonProfileCount <=
        addonBaseChannels + addonActive + (addonPending - PROFILE_ADDON_STEP));

  const canRemoveActive =
    addonActive >= PROFILE_ADDON_STEP &&
    (addonProfileCount === undefined ||
      (addonProfileCount <=
        addonBaseChannels + (addonActive - PROFILE_ADDON_STEP) + addonPending &&
        addonProfileCount <= addonBaseChannels + (addonActive - PROFILE_ADDON_STEP)));

  const adjustAddonSlots = async (
    field: 'pending' | 'active',
    delta: number,
  ) => {
    if (!addonLicense) return;

    const current = field === 'pending' ? addonPending : addonActive;
    const next = current + delta;

    if (next < 0 || next % PROFILE_ADDON_STEP !== 0) {
      return;
    }

    const other = field === 'pending' ? addonActive : addonPending;
    if (addonBaseChannels + next + other > MAX_ACCOUNT_CHANNELS) {
      toast({
        title: 'Channel limit reached',
        description: `Total channels cannot exceed ${MAX_ACCOUNT_CHANNELS}.`,
        variant: 'destructive',
      });
      return;
    }

    try {
      await updateProfileAddonSlots.mutateAsync({
        id: addonLicense.id,
        ...(field === 'pending'
          ? { profile_addon_pending: next }
          : { profile_addon_slots: next }),
      });
      toast({
        title: delta > 0 ? 'Add-on channels added' : 'Add-on channels removed',
        description:
          field === 'pending'
            ? `Pending add-on is now ${next} (+${next} channels awaiting onboarding).`
            : `Active add-on is now ${next} (quotas scale immediately).`,
      });
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: { message?: string } }>;
      const msg = axiosError.response?.data?.error?.message ?? 'Failed to update add-on channels';
      toast({ title: 'Error', description: msg, variant: 'destructive' });
    }
  };

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  if (isError && !data) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Subscriptions</h1>
        <ErrorState
          message={error?.message ?? 'Failed to load subscriptions'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Subscriptions</h1>
        <Button onClick={() => setSubscribeDialogOpen(true)}>
          Subscribe User
        </Button>
      </div>

      <DataTable<License>
        columns={columns}
        data={data?.items ?? []}
        totalCount={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
        emptyMessage="No subscriptions found."
        filterBar={
          <FilterBar>
            <Select value={statusFilter} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
                <SelectItem value="revoked">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </FilterBar>
        }
      />

      {/* Subscribe User Dialog */}
      <Dialog open={subscribeDialogOpen} onOpenChange={setSubscribeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Subscribe User to Plan</DialogTitle>
            <DialogDescription>
              Select a user and a plan. The subscription will start immediately
              and expire based on the plan&apos;s billing cycle.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-300">User</label>
              <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>
                  {usersData?.items?.map(user => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.email} ({user.display_name})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-300">Plan</label>
              <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a plan" />
                </SelectTrigger>
                <SelectContent>
                  {plans?.filter(p => p.is_active).map(plan => (
                    <SelectItem key={plan.id} value={plan.id}>
                      {plan.name} — ${(plan.price_cents / 100).toFixed(2)}
                      {plan.billing_cycle_days ? ` / ${plan.billing_cycle_days} days` : ' (Lifetime)'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSubscribeDialogOpen(false)}
              disabled={createLicense.isPending || assignLicense.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubscribe}
              disabled={!selectedUserId || !selectedPlanId || createLicense.isPending || assignLicense.isPending}
            >
              {(createLicense.isPending || assignLicense.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Subscribe
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Profile add-on slots dialog */}
      <Dialog
        open={addonDialogOpen}
        onOpenChange={(open) => {
          setAddonDialogOpen(open);
          if (!open) setSelectedSubscription(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Manage profile add-ons</DialogTitle>
            <DialogDescription>
              Add or remove +2 channel bundles. Pending slots let the user create profiles but
              quotas activate only after onboarding. Active slots scale monthly quotas immediately.
            </DialogDescription>
          </DialogHeader>
          {addonLicense && (
            <div className="space-y-4 py-2">
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/50 p-4 text-sm">
                <div className="flex justify-between text-slate-400">
                  <span>User</span>
                  <span className="text-slate-200">
                    {addonLicense.user_id
                      ? (userMap.get(addonLicense.user_id) ?? addonLicense.user_id)
                      : '—'}
                  </span>
                </div>
                <div className="mt-2 flex justify-between text-slate-400">
                  <span>Plan</span>
                  <span className="text-slate-200">
                    {planMap.get(addonLicense.plan_id) ?? addonLicense.plan_id}
                    {' · '}
                    {addonBaseChannels} base channels
                  </span>
                </div>
                <div className="mt-2 flex justify-between text-slate-400">
                  <span>Channel profiles</span>
                  <span className="text-slate-200">
                    {addonProfileCount ?? '—'}
                    {addonProfileCount !== undefined ? ' created' : ''}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 border-t border-slate-700/60 pt-3">
                  <div>
                    <p className="text-xs text-slate-500">Total channels</p>
                    <p className="text-lg font-semibold text-slate-100">
                      {addonTotalChannels}
                      <span className="text-sm font-normal text-slate-500">
                        {' '}
                        / {MAX_ACCOUNT_CHANNELS}
                      </span>
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Pending</p>
                    <p className="text-lg font-semibold text-amber-300">{addonPending}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Active</p>
                    <p className="text-lg font-semibold text-green-400">{addonActive}</p>
                  </div>
                </div>
                {addonRemaining > 0 ? (
                  <p className="mt-2 text-xs text-slate-500">
                    Up to {addonRemaining} more channel{addonRemaining === 1 ? '' : 's'} can be
                    added.
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-amber-400/90">Account is at the 10-channel cap.</p>
                )}
                <p className="mt-2 text-xs text-slate-500">
                  Removing add-ons never deletes channel profiles or usage history. Reduction is
                  blocked when the user already has more profiles than the new allowance or quota
                  would support.
                </p>
              </div>

              <AddonSlotRow
                label="Pending add-on"
                description="Paid or admin-granted — awaiting profile onboarding"
                value={addonPending}
                tone="pending"
                canAdd={addonRemaining >= PROFILE_ADDON_STEP}
                canRemove={canRemovePending}
                isPending={updateProfileAddonSlots.isPending}
                onAdjust={(delta) => adjustAddonSlots('pending', delta)}
              />

              <AddonSlotRow
                label="Active add-on"
                description="Onboarded — monthly quotas scale with these channels"
                value={addonActive}
                tone="active"
                canAdd={addonRemaining >= PROFILE_ADDON_STEP}
                canRemove={canRemoveActive}
                isPending={updateProfileAddonSlots.isPending}
                onAdjust={(delta) => adjustAddonSlots('active', delta)}
              />
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAddonDialogOpen(false)}
              disabled={updateProfileAddonSlots.isPending}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Subscription Dialog */}
      <ConfirmDialog
        open={revokeDialogOpen}
        onOpenChange={setRevokeDialogOpen}
        title="Cancel Subscription"
        description="Are you sure you want to cancel this subscription? The user will lose access to the plan features."
        onConfirm={handleRevoke}
        variant="destructive"
        confirmText="Cancel Subscription"
        isLoading={revokeLicense.isPending}
      />
    </div>
  );
}
