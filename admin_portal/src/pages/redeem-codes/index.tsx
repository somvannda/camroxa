import { useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { Pencil, Plus, TicketPercent, Trash2 } from 'lucide-react';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { usePlans } from '@/hooks/use-plans';
import {
  useCreateRedeemCode,
  useDeleteRedeemCode,
  useRedeemCodeRedemptions,
  useRedeemCodes,
  useUpdateRedeemCode,
} from '@/hooks/use-redeem-codes';
import { toast } from '@/hooks/use-toast';
import type {
  CreateRedeemCodeRequest,
  RedeemRedemptionListParams,
  UpdateRedeemCodeRequest,
} from '@/types/api';
import type { RedeemCode, RedeemCodeRedemption } from '@/types/models';

type RedeemFormState = {
  code: string;
  description: string;
  reward_type: 'discount_amount' | 'discount_percentage' | 'credit_grant';
  discount_amount_cents: string;
  discount_percent: string;
  credit_amount: string;
  applicable_plan_id: string;
  max_redemptions: string;
  per_user_limit: string;
  starts_at: string;
  expires_at: string;
  is_active: boolean;
};

function createDefaultForm(): RedeemFormState {
  return {
    code: '',
    description: '',
    reward_type: 'discount_amount',
    discount_amount_cents: '',
    discount_percent: '',
    credit_amount: '',
    applicable_plan_id: '',
    max_redemptions: '',
    per_user_limit: '1',
    starts_at: '',
    expires_at: '',
    is_active: true,
  };
}

function toDatetimeLocal(value: string | null): string {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  const offset = parsed.getTimezoneOffset();
  const local = new Date(parsed.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

function toFormState(item: RedeemCode): RedeemFormState {
  return {
    code: item.code,
    description: item.description ?? '',
    reward_type: item.reward_type,
    discount_amount_cents: item.discount_amount_cents?.toString() ?? '',
    discount_percent: item.discount_percent?.toString() ?? '',
    credit_amount: item.credit_amount?.toString() ?? '',
    applicable_plan_id: item.applicable_plan_id ?? '',
    max_redemptions: item.max_redemptions?.toString() ?? '',
    per_user_limit: item.per_user_limit.toString(),
    starts_at: toDatetimeLocal(item.starts_at),
    expires_at: toDatetimeLocal(item.expires_at),
    is_active: item.is_active,
  };
}

function toPayload(form: RedeemFormState): CreateRedeemCodeRequest | UpdateRedeemCodeRequest {
  return {
    code: form.code.trim().toUpperCase(),
    description: form.description.trim() || null,
    reward_type: form.reward_type,
    discount_amount_cents:
      form.reward_type === 'discount_amount' && form.discount_amount_cents.trim()
        ? Number(form.discount_amount_cents)
        : null,
    discount_percent:
      form.reward_type === 'discount_percentage' && form.discount_percent.trim()
        ? Number(form.discount_percent)
        : null,
    credit_amount:
      form.reward_type === 'credit_grant' && form.credit_amount.trim()
        ? Number(form.credit_amount)
        : null,
    applicable_plan_id:
      form.reward_type === 'credit_grant' || !form.applicable_plan_id ? null : form.applicable_plan_id,
    max_redemptions: form.max_redemptions.trim() ? Number(form.max_redemptions) : null,
    per_user_limit: Number(form.per_user_limit || '1'),
    starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
    expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
    is_active: form.is_active,
  };
}

function getRewardSummary(item: RedeemCode): string {
  if (item.reward_type === 'discount_amount') {
    return `$${((item.discount_amount_cents ?? 0) / 100).toFixed(2)} off`;
  }
  if (item.reward_type === 'discount_percentage') {
    return `${item.discount_percent ?? 0}% off`;
  }
  return `${item.credit_amount ?? 0} credits`;
}

function formatMoney(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return '—';
  return `$${(cents / 100).toFixed(2)}`;
}

function getRedemptionValueLabel(item: RedeemCodeRedemption): string {
  if (item.reward_type === 'credit_grant') {
    return `+${item.credit_amount ?? 0} credits`;
  }
  return formatMoney(item.amount_cents);
}

function formatRewardTypeLabel(value: RedeemCode['reward_type']): string {
  return value.replace(/_/g, ' ');
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'redeemed':
    case 'paid':
      return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300';
    case 'failed':
    case 'rejected':
      return 'border-rose-400/25 bg-rose-500/10 text-rose-300';
    default:
      return 'border-slate-700 bg-slate-800 text-slate-300';
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{ detail?: string; error?: { message?: string } }>;
  return axiosError.response?.data?.error?.message ?? axiosError.response?.data?.detail ?? fallback;
}

export default function RedeemCodesPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<RedeemCode | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RedeemCode | null>(null);
  const [form, setForm] = useState<RedeemFormState>(createDefaultForm);
  const [redemptionPage, setRedemptionPage] = useState(1);
  const [redemptionCodeFilter, setRedemptionCodeFilter] = useState('');
  const [redemptionRewardType, setRedemptionRewardType] = useState('');
  const [redemptionStatus, setRedemptionStatus] = useState('');

  const codesQuery = useRedeemCodes();
  const plansQuery = usePlans();
  const createRedeemCode = useCreateRedeemCode();
  const updateRedeemCode = useUpdateRedeemCode();
  const deleteRedeemCode = useDeleteRedeemCode();
  const redemptionParams: RedeemRedemptionListParams = useMemo(
    () => ({
      page: redemptionPage,
      page_size: 12,
      ...(redemptionCodeFilter.trim() ? { code: redemptionCodeFilter.trim() } : {}),
      ...(redemptionRewardType ? { reward_type: redemptionRewardType as RedeemRedemptionListParams['reward_type'] } : {}),
      ...(redemptionStatus ? { status: redemptionStatus } : {}),
    }),
    [redemptionCodeFilter, redemptionPage, redemptionRewardType, redemptionStatus],
  );
  const redemptionsQuery = useRedeemCodeRedemptions(redemptionParams);

  const planOptions = useMemo(() => plansQuery.data ?? [], [plansQuery.data]);
  const redemptionItems = redemptionsQuery.data?.items ?? [];
  const visibleCreditGrantCount = redemptionItems.filter((item) => item.reward_type === 'credit_grant').length;
  const visibleDiscountCount = redemptionItems.filter((item) => item.reward_type !== 'credit_grant').length;

  function openCreate() {
    setEditing(null);
    setForm(createDefaultForm());
    setDialogOpen(true);
  }

  function openEdit(item: RedeemCode) {
    setEditing(item);
    setForm(toFormState(item));
    setDialogOpen(true);
  }

  function handleSave() {
    const payload = toPayload(form);
    if (editing) {
      updateRedeemCode.mutate(
        { id: editing.id, payload },
        {
          onSuccess: () => {
            toast({ title: 'Redeem code updated' });
            setDialogOpen(false);
          },
          onError: (error) => {
            toast({
              title: 'Update failed',
              description: getErrorMessage(error, 'Unable to update redeem code.'),
              variant: 'destructive',
            });
          },
        },
      );
      return;
    }

    createRedeemCode.mutate(payload, {
      onSuccess: () => {
        toast({ title: 'Redeem code created' });
        setDialogOpen(false);
      },
      onError: (error) => {
        toast({
          title: 'Create failed',
          description: getErrorMessage(error, 'Unable to create redeem code.'),
          variant: 'destructive',
        });
      },
    });
  }

  function handleDelete() {
    if (!deleteTarget) return;
    deleteRedeemCode.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast({ title: 'Redeem code deleted' });
        setDeleteTarget(null);
      },
      onError: (error) => {
        toast({
          title: 'Delete failed',
          description: getErrorMessage(error, 'Unable to delete redeem code.'),
          variant: 'destructive',
        });
      },
    });
  }

  if (codesQuery.isLoading) {
    return <div className="p-6 text-sm text-slate-400">Loading redeem codes...</div>;
  }

  if (codesQuery.isError) {
    return (
      <ErrorState
        message={codesQuery.error.message || 'Failed to load redeem codes'}
        onRetry={() => codesQuery.refetch()}
      />
    );
  }

  const items = codesQuery.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Redeem Codes</h1>
          <p className="text-sm text-slate-400">
            Manage discount and credit-grant codes for signup, onboarding checkout, and signed-in wallet redemption.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Create redeem code
        </Button>
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-slate-100">Code inventory</CardTitle>
          <div className="text-sm text-slate-400">{items.length.toLocaleString()} total codes</div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-3 font-medium">Code</th>
                  <th className="pb-3 font-medium">Reward</th>
                  <th className="pb-3 font-medium">Plan scope</th>
                  <th className="pb-3 font-medium">Usage</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Window</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-900/80 text-slate-200">
                    <td className="py-4">
                      <div className="font-medium text-white">{item.code}</div>
                      <div className="text-xs text-slate-500">{item.description ?? 'No description'}</div>
                    </td>
                    <td className="py-4">
                      <div>{getRewardSummary(item)}</div>
                      <div className="text-xs capitalize text-slate-500">{formatRewardTypeLabel(item.reward_type)}</div>
                    </td>
                    <td className="py-4 text-slate-300">
                      {item.applicable_plan_name ?? (item.reward_type === 'credit_grant' ? 'Wallet only' : 'All plans')}
                    </td>
                    <td className="py-4 text-slate-300">
                      {item.current_redemptions.toLocaleString()}
                      {item.max_redemptions === null ? ' / unlimited' : ` / ${item.max_redemptions.toLocaleString()}`}
                      <div className="text-xs text-slate-500">Per user: {item.per_user_limit}</div>
                    </td>
                    <td className="py-4">
                      <Badge
                        className={
                          item.is_active
                            ? 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300'
                            : 'border-slate-700 bg-slate-800 text-slate-300'
                        }
                      >
                        {item.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="py-4 text-xs text-slate-400">
                      <div>{item.starts_at ? new Date(item.starts_at).toLocaleString() : 'Immediate'}</div>
                      <div>{item.expires_at ? `Until ${new Date(item.expires_at).toLocaleString()}` : 'No expiry'}</div>
                    </td>
                    <td className="py-4">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                          <Pencil className="h-4 w-4" />
                          Edit
                        </Button>
                        <Button variant="destructive" size="sm" onClick={() => setDeleteTarget(item)}>
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-sm text-slate-500">
                      No redeem codes created yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <CardTitle className="text-slate-100">Redemption reporting</CardTitle>
              <p className="mt-1 text-sm text-slate-400">
                Monitor which codes were redeemed, what value they delivered, and whether they landed as checkout discounts or wallet credits.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Recorded</div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {(redemptionsQuery.data?.total ?? 0).toLocaleString()}
                </div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Visible discounts</div>
                <div className="mt-2 text-lg font-semibold text-white">{visibleDiscountCount.toLocaleString()}</div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Visible credits</div>
                <div className="mt-2 text-lg font-semibold text-white">{visibleCreditGrantCount.toLocaleString()}</div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_220px_180px]">
            <Input
              placeholder="Filter by redeem code"
              value={redemptionCodeFilter}
              onChange={(event) => {
                setRedemptionCodeFilter(event.target.value.toUpperCase());
                setRedemptionPage(1);
              }}
            />
            <select
              value={redemptionRewardType}
              onChange={(event) => {
                setRedemptionRewardType(event.target.value);
                setRedemptionPage(1);
              }}
              className="flex h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
            >
              <option value="">All reward types</option>
              <option value="discount_amount">Discount amount</option>
              <option value="discount_percentage">Discount percentage</option>
              <option value="credit_grant">Credit grant</option>
            </select>
            <select
              value={redemptionStatus}
              onChange={(event) => {
                setRedemptionStatus(event.target.value);
                setRedemptionPage(1);
              }}
              className="flex h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
            >
              <option value="">All statuses</option>
              <option value="redeemed">Redeemed</option>
              <option value="paid">Paid</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {redemptionsQuery.isError ? (
            <ErrorState
              message={redemptionsQuery.error.message || 'Failed to load redeem-code redemptions'}
              onRetry={() => redemptionsQuery.refetch()}
            />
          ) : redemptionsQuery.isLoading ? (
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-10 text-center text-sm text-slate-400">
              Loading redemption history...
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800">
                    <TableHead>Code</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Reward</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Redeemed at</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {redemptionItems.map((item) => (
                    <TableRow key={item.id} className="border-slate-900/80">
                      <TableCell>
                        <div className="font-medium text-white">{item.code}</div>
                        <div className="text-xs text-slate-500">{item.description ?? 'No description'}</div>
                      </TableCell>
                      <TableCell>
                        <div className="text-slate-100">{item.user_display_name ?? 'User'}</div>
                        <div className="text-xs text-slate-500">{item.user_email ?? item.user_id}</div>
                      </TableCell>
                      <TableCell className="capitalize text-slate-300">
                        {formatRewardTypeLabel(item.reward_type)}
                      </TableCell>
                      <TableCell className="text-slate-100">{getRedemptionValueLabel(item)}</TableCell>
                      <TableCell className="text-slate-300">{item.plan_name ?? 'Wallet credit'}</TableCell>
                      <TableCell>
                        <Badge className={getStatusBadgeClass(item.status)}>{item.status}</Badge>
                      </TableCell>
                      <TableCell className="text-slate-400">
                        {new Date(item.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                  {redemptionItems.length === 0 ? (
                    <TableRow className="border-slate-900/80">
                      <TableCell colSpan={7} className="py-10 text-center text-sm text-slate-500">
                        No redemption records match the current filters.
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-slate-400">
                  Page {redemptionsQuery.data?.page ?? 1} of {redemptionsQuery.data?.total_pages ?? 1}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setRedemptionPage((current) => Math.max(1, current - 1))}
                    disabled={(redemptionsQuery.data?.page ?? 1) <= 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setRedemptionPage((current) =>
                        Math.min(redemptionsQuery.data?.total_pages ?? current, current + 1),
                      )
                    }
                    disabled={(redemptionsQuery.data?.page ?? 1) >= (redemptionsQuery.data?.total_pages ?? 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit redeem code' : 'Create redeem code'}</DialogTitle>
            <DialogDescription>
              Configure discount amount, discount percentage, or wallet credit grant behavior.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="code">Code</Label>
              <Input
                id="code"
                value={form.code}
                onChange={(event) => setForm((current) => ({ ...current, code: event.target.value.toUpperCase() }))}
                placeholder="CAMXORA100"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="reward_type">Reward type</Label>
              <select
                id="reward_type"
                value={form.reward_type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    reward_type: event.target.value as RedeemFormState['reward_type'],
                    applicable_plan_id: event.target.value === 'credit_grant' ? '' : current.applicable_plan_id,
                  }))
                }
                className="flex h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
              >
                <option value="discount_amount">Discount amount</option>
                <option value="discount_percentage">Discount percentage</option>
                <option value="credit_grant">Credit grant</option>
              </select>
            </div>

            <div className="grid gap-2 md:col-span-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Summer launch campaign"
              />
            </div>

            {form.reward_type === 'discount_amount' ? (
              <div className="grid gap-2">
                <Label htmlFor="discount_amount_cents">Discount amount (cents)</Label>
                <Input
                  id="discount_amount_cents"
                  type="number"
                  min="1"
                  value={form.discount_amount_cents}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, discount_amount_cents: event.target.value }))
                  }
                />
              </div>
            ) : null}

            {form.reward_type === 'discount_percentage' ? (
              <div className="grid gap-2">
                <Label htmlFor="discount_percent">Discount percentage</Label>
                <Input
                  id="discount_percent"
                  type="number"
                  min="1"
                  max="100"
                  value={form.discount_percent}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, discount_percent: event.target.value }))
                  }
                />
              </div>
            ) : null}

            {form.reward_type === 'credit_grant' ? (
              <div className="grid gap-2">
                <Label htmlFor="credit_amount">Credit amount</Label>
                <Input
                  id="credit_amount"
                  type="number"
                  min="1"
                  value={form.credit_amount}
                  onChange={(event) => setForm((current) => ({ ...current, credit_amount: event.target.value }))}
                />
              </div>
            ) : null}

            {form.reward_type !== 'credit_grant' ? (
              <div className="grid gap-2">
                <Label htmlFor="applicable_plan_id">Plan scope</Label>
                <select
                  id="applicable_plan_id"
                  value={form.applicable_plan_id}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, applicable_plan_id: event.target.value }))
                  }
                  className="flex h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
                >
                  <option value="">All paid plans</option>
                  {planOptions.map((plan) => (
                    <option key={plan.id} value={plan.id}>
                      {plan.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="grid gap-2">
                <Label>Wallet delivery</Label>
                <div className="flex h-10 items-center rounded-md border border-slate-800 bg-slate-950 px-3 text-sm text-slate-400">
                  Redeemable in signed-in user panel
                </div>
              </div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="max_redemptions">Maximum redemptions</Label>
              <Input
                id="max_redemptions"
                type="number"
                min="1"
                value={form.max_redemptions}
                onChange={(event) => setForm((current) => ({ ...current, max_redemptions: event.target.value }))}
                placeholder="Leave blank for unlimited"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="per_user_limit">Per-user limit</Label>
              <Input
                id="per_user_limit"
                type="number"
                min="1"
                value={form.per_user_limit}
                onChange={(event) => setForm((current) => ({ ...current, per_user_limit: event.target.value }))}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="starts_at">Starts at</Label>
              <Input
                id="starts_at"
                type="datetime-local"
                value={form.starts_at}
                onChange={(event) => setForm((current) => ({ ...current, starts_at: event.target.value }))}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="expires_at">Expires at</Label>
              <Input
                id="expires_at"
                type="datetime-local"
                value={form.expires_at}
                onChange={(event) => setForm((current) => ({ ...current, expires_at: event.target.value }))}
              />
            </div>

            <label className="md:col-span-2 flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
              />
              Code is active and available for redemption
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={createRedeemCode.isPending || updateRedeemCode.isPending}
            >
              <TicketPercent className="h-4 w-4" />
              {editing ? 'Save changes' : 'Create code'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete redeem code?"
        description={`This permanently removes ${deleteTarget?.code ?? 'this redeem code'} from the system.`}
        onConfirm={handleDelete}
        confirmText="Delete"
        variant="destructive"
        isLoading={deleteRedeemCode.isPending}
      />
    </div>
  );
}
