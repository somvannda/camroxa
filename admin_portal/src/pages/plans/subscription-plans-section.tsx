import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  usePlanTermDiscounts,
  usePlanPriceDrift,
  useSyncTermPlanPrices,
  useUpdatePlanTermDiscounts,
} from '@/hooks/use-plans';
import { billingTermQuotes, formatChannelPlanName, formatUsd } from '@/lib/plan-tier-pricing';
import { toast } from '@/hooks/use-toast';
import type { Plan } from '@/types/models';

const CHANNEL_TIERS = [2, 6, 10] as const;

type TierGroup = {
  channels: number;
  monthly: Plan | undefined;
  semi: Plan | undefined;
  annual: Plan | undefined;
};

type SubscriptionPlansSectionProps = {
  plans: Plan[];
  isLoading: boolean;
  onCreatePlan: () => void;
  onEditPlan: (plan: Plan) => void;
  onToggleActive: (plan: Plan) => void;
  onDeletePlan: (plan: Plan) => void;
};

function groupSubscriptionPlans(plans: Plan[]): TierGroup[] {
  return CHANNEL_TIERS.map((channels) => ({
    channels,
    monthly: plans.find((plan) => plan.profile_allowance === channels && plan.billing_cycle_days === 30),
    semi: plans.find((plan) => plan.profile_allowance === channels && plan.billing_cycle_days === 180),
    annual: plans.find((plan) => plan.profile_allowance === channels && plan.billing_cycle_days === 365),
  }));
}

function termLabel(cycleDays: number | null | undefined): string {
  if (cycleDays === 180) return '6 Months';
  if (cycleDays === 365) return 'Annual';
  return 'Monthly';
}

function PlanTermRow({
  plan,
  expectedCents,
  discountLabel,
  onEdit,
  onToggleActive,
  onDelete,
}: {
  plan: Plan | undefined;
  expectedCents?: number;
  discountLabel?: string;
  onEdit: (plan: Plan) => void;
  onToggleActive: (plan: Plan) => void;
  onDelete: (plan: Plan) => void;
}) {
  if (!plan) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-dashed border-slate-700 px-4 py-3 text-sm text-slate-500">
        <span>No plan row yet</span>
      </div>
    );
  }

  const outOfSync = expectedCents != null && plan.price_cents !== expectedCents;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
      <div className="min-w-[120px]">
        <div className="text-sm font-medium text-white">{termLabel(plan.billing_cycle_days)}</div>
        {discountLabel ? <div className="text-xs text-slate-500">{discountLabel}</div> : null}
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className={`text-sm font-semibold ${outOfSync ? 'text-amber-200' : 'text-emerald-100'}`}>
            {formatUsd(plan.price_cents)}
          </div>
          {outOfSync && expectedCents != null ? (
            <div className="text-xs text-amber-300/80">Expected {formatUsd(expectedCents)}</div>
          ) : null}
        </div>
        <Badge variant="outline" className="border-slate-600 text-slate-400">
          {plan.subscriber_count} sub
        </Badge>
        <Badge
          variant="outline"
          className={
            plan.is_active
              ? 'border-green-500/30 bg-green-500/10 text-green-400'
              : 'border-red-500/30 bg-red-500/10 text-red-400'
          }
        >
          {plan.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => onEdit(plan)}>
          Edit
        </Button>
        <Button size="sm" variant="outline" onClick={() => onToggleActive(plan)}>
          {plan.is_active ? 'Deactivate' : 'Activate'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!plan.can_delete}
          onClick={() => onDelete(plan)}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

export function SubscriptionPlansSection({
  plans,
  isLoading,
  onCreatePlan,
  onEditPlan,
  onToggleActive,
  onDeletePlan,
}: SubscriptionPlansSectionProps) {
  const { data: termDiscounts, isLoading: discountsLoading } = usePlanTermDiscounts();
  const updateDiscounts = useUpdatePlanTermDiscounts();
  const syncTermPrices = useSyncTermPlanPrices();
  const { data: priceDrift } = usePlanPriceDrift();

  const [semiDiscount, setSemiDiscount] = useState('15');
  const [annualDiscount, setAnnualDiscount] = useState('25');
  const [expandedTier, setExpandedTier] = useState<number | null>(null);

  useEffect(() => {
    if (!termDiscounts) return;
    setSemiDiscount(String(termDiscounts.semi_annual_discount_percent));
    setAnnualDiscount(String(termDiscounts.annual_discount_percent));
  }, [termDiscounts]);

  const groups = useMemo(() => groupSubscriptionPlans(plans), [plans]);

  const saveDiscounts = () => {
    updateDiscounts.mutate(
      {
        semi_annual_discount_percent: Number(semiDiscount || '0'),
        annual_discount_percent: Number(annualDiscount || '0'),
      },
      {
        onSuccess: () => {
          toast({ title: 'Term discounts saved' });
        },
        onError: () =>
          toast({ title: 'Failed to save term discounts', variant: 'destructive' }),
      },
    );
  };

  const handleSyncPrices = () => {
    syncTermPrices.mutate(undefined, {
      onSuccess: (result) => {
        toast({
          title: 'Term plan prices synced',
          description:
            result.updated_plan_ids.length > 0
              ? `Updated ${result.updated_plan_ids.length} plan row(s).`
              : 'All 6-month and annual rows already matched the saved discounts.',
        });
      },
      onError: () =>
        toast({ title: 'Failed to sync term plan prices', variant: 'destructive' }),
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading subscription plans…
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      {priceDrift && priceDrift.drift_count > 0 ? (
        <div className="mx-6 mt-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {priceDrift.drift_count} plan row{priceDrift.drift_count === 1 ? '' : 's'} differ from
          computed term prices. Run <strong>Sync 6-month &amp; annual prices</strong> before sandbox
          checkout testing.
        </div>
      ) : null}
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-lg">Subscription Plans</CardTitle>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Checkout prices live on plan rows. Monthly rows are the base price; 6-month and annual rows
            should be synced from the discount settings below.
          </p>
        </div>
        <Button size="sm" onClick={onCreatePlan}>
          Create Plan
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/5 p-4">
          <div className="text-xs uppercase tracking-[0.16em] text-cyan-200/80">Billing term discounts</div>
          <p className="mt-2 text-sm text-slate-400">
            These percentages are saved in admin settings and used by the plan calculator + sync tool.
            They do not change checkout until you update or sync the 6-month / annual plan rows.
          </p>
          <div className="mt-4 flex flex-wrap items-end gap-4">
            <label className="space-y-1 text-sm">
              <span className="text-slate-400">6-month discount (%)</span>
              <Input
                className="max-w-[120px]"
                type="number"
                min={0}
                max={50}
                value={semiDiscount}
                onChange={(e) => setSemiDiscount(e.target.value)}
                disabled={discountsLoading}
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-slate-400">Annual discount (%)</span>
              <Input
                className="max-w-[120px]"
                type="number"
                min={0}
                max={50}
                value={annualDiscount}
                onChange={(e) => setAnnualDiscount(e.target.value)}
                disabled={discountsLoading}
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              onClick={saveDiscounts}
              disabled={updateDiscounts.isPending || discountsLoading}
            >
              {updateDiscounts.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save discounts
            </Button>
            <Button
              type="button"
              onClick={handleSyncPrices}
              disabled={syncTermPrices.isPending || discountsLoading}
            >
              {syncTermPrices.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sync 6-month &amp; annual prices
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          {groups.map((group) => {
            const monthly = group.monthly;
            const terms = monthly
              ? billingTermQuotes(monthly.price_cents, {
                  semiAnnualDiscountPercent: Number(semiDiscount || '0'),
                  annualDiscountPercent: Number(annualDiscount || '0'),
                })
              : [];
            const semiExpected = terms[1]?.totalCents;
            const annualExpected = terms[2]?.totalCents;
            const expanded = expandedTier === group.channels;
            const quotaPlan = monthly ?? group.semi ?? group.annual;

            return (
              <div key={group.channels} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold text-white">{group.channels} channels</div>
                    <div className="text-xs text-slate-500">
                      {monthly
                        ? `Monthly base ${formatUsd(monthly.price_cents)}`
                        : 'Missing monthly base plan row'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-slate-400"
                    onClick={() => setExpandedTier(expanded ? null : group.channels)}
                  >
                    {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    Quotas
                  </Button>
                </div>

                <div className="space-y-2">
                  <PlanTermRow
                    plan={group.monthly}
                    onEdit={onEditPlan}
                    onToggleActive={onToggleActive}
                    onDelete={onDeletePlan}
                  />
                  <PlanTermRow
                    plan={group.semi}
                    expectedCents={semiExpected}
                    discountLabel={`${semiDiscount}% off combined monthly`}
                    onEdit={onEditPlan}
                    onToggleActive={onToggleActive}
                    onDelete={onDeletePlan}
                  />
                  <PlanTermRow
                    plan={group.annual}
                    expectedCents={annualExpected}
                    discountLabel={`${annualDiscount}% off combined monthly`}
                    onEdit={onEditPlan}
                    onToggleActive={onToggleActive}
                    onDelete={onDeletePlan}
                  />
                </div>

                {expanded && quotaPlan ? (
                  <div className="mt-4 grid gap-2 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-400 md:grid-cols-3">
                    <div>Suno packages / period: {quotaPlan.monthly_song_limit ?? '∞'}</div>
                    <div>Images / period: {quotaPlan.monthly_image_limit ?? '∞'}</div>
                    <div>Drafts / period: {quotaPlan.monthly_draft_limit ?? '∞'}</div>
                    <div>Videos / period: {quotaPlan.monthly_video_limit ?? '∞'}</div>
                    <div>Merges / period: {quotaPlan.monthly_merge_limit ?? '∞'}</div>
                    <div>Daily song / channel: {quotaPlan.daily_song_limit_per_channel}</div>
                    <div>Daily image / channel: {quotaPlan.daily_image_limit_per_channel}</div>
                    <div>Daily draft / channel: {quotaPlan.daily_draft_limit_per_channel ?? 300}</div>
                    <div>Daily video (account): {quotaPlan.daily_video_limit ?? 10}</div>
                    <div>Daily merge (account): {quotaPlan.daily_merge_limit ?? 1}</div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export { formatChannelPlanName };
