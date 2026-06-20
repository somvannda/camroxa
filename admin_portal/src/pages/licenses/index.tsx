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
  type LicenseListParams,
} from '@/hooks/use-licenses';
import { usePlans } from '@/hooks/use-plans';
import { useUsers } from '@/hooks/use-users';
import { toast } from '@/hooks/use-toast';
import type { License } from '@/types/models';

const PAGE_SIZE = 25;

const STATUS_BADGE_CLASSES: Record<License['status'], string> = {
  unassigned: 'border-slate-500/30 bg-slate-500/10 text-slate-400',
  active: 'border-green-500/30 bg-green-500/10 text-green-400',
  expired: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  revoked: 'border-red-500/30 bg-red-500/10 text-red-400',
};

export default function SubscriptionsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Dialogs
  const [subscribeDialogOpen, setSubscribeDialogOpen] = useState(false);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
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

  // Map plan IDs to names for display
  const planMap = new Map(plans?.map(p => [p.id, p.name]) ?? []);
  // Map user IDs to emails for display
  const userMap = new Map(usersData?.items?.map(u => [u.id, u.email]) ?? []);

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
