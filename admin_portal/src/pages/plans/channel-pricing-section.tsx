import { useMemo, useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useCreatePlan, useDeletePlan, usePlans, useUpdatePlan } from '@/hooks/use-plans';
import { formatUsd, roundWholeDollars } from '@/lib/plan-tier-pricing';
import { toast } from '@/hooks/use-toast';
import type { Plan } from '@/types/models';

type DraftRow = {
  id: string;
  planId?: string;
  channels: number;
  monthlyDollars: string;
  isNew?: boolean;
};

function addonPlans(plans: Plan[] | undefined): Plan[] {
  return (plans ?? [])
    .filter((plan) => plan.plan_kind === 'profile_addon')
    .sort((a, b) => a.profile_allowance - b.profile_allowance);
}

function twoChannelBasePlan(plans: Plan[] | undefined): Plan | undefined {
  return (plans ?? [])
    .filter(
      (plan) =>
        plan.plan_kind !== 'profile_addon' &&
        plan.is_active &&
        plan.profile_allowance === 2 &&
        plan.billing_cycle_days === 30,
    )
    .sort((a, b) => a.price_cents - b.price_cents)[0];
}

function nextAvailableChannels(existing: DraftRow[]): number {
  const used = new Set(existing.map((row) => row.channels));
  for (let channels = 2; channels <= 8; channels += 2) {
    if (!used.has(channels)) return channels;
  }
  return 0;
}

export function ChannelPricingSection() {
  const { data: plans, isLoading, isError, refetch } = usePlans();
  const createPlan = useCreatePlan();
  const updatePlan = useUpdatePlan();
  const deletePlan = useDeletePlan();
  const [drafts, setDrafts] = useState<DraftRow[] | null>(null);

  const addonRows = addonPlans(plans);
  const basePlan = twoChannelBasePlan(plans);

  const rows = useMemo(() => {
    if (drafts !== null) return drafts;
    return addonRows.map((plan) => ({
      id: plan.id,
      planId: plan.id,
      channels: plan.profile_allowance,
      monthlyDollars: String(plan.price_cents / 100),
    }));
  }, [addonRows, drafts]);

  const handleAddRow = () => {
    const channels = nextAvailableChannels(rows);
    if (channels === 0) {
      toast({
        title: 'Cannot add more bundles',
        description: 'Add-on plans are limited to even channel counts from +2 through +8.',
        variant: 'destructive',
      });
      return;
    }
    const defaultDollars = basePlan
      ? String((basePlan.price_cents * (channels / 2)) / 100)
      : '79';
    setDrafts([
      ...rows,
      {
        id: `new-${Date.now()}`,
        channels,
        monthlyDollars: defaultDollars,
        isNew: true,
      },
    ]);
  };

  const handleSave = async () => {
    const seen = new Set<number>();
    for (const row of rows) {
      if (row.channels < 2 || row.channels > 8 || row.channels % 2 !== 0) {
        toast({
          title: 'Invalid add-on row',
          description: 'Each row must use an even channel count between 2 and 8.',
          variant: 'destructive',
        });
        return;
      }
      if (seen.has(row.channels)) {
        toast({
          title: 'Duplicate add-on size',
          description: `You already have a +${row.channels} channel plan row.`,
          variant: 'destructive',
        });
        return;
      }
      seen.add(row.channels);
    }

    try {
      for (const row of rows) {
        const priceCents = roundWholeDollars(Math.round(Number(row.monthlyDollars || '0') * 100));
        const name = `Add-on · +${row.channels} channels`;
        if (row.planId) {
          await updatePlan.mutateAsync({
            id: row.planId,
            updates: {
              name,
              price_cents: priceCents,
              profile_allowance: row.channels,
              billing_cycle_days: 30,
            },
          });
        } else {
          await createPlan.mutateAsync({
            name,
            price_cents: priceCents,
            profile_allowance: row.channels,
            billing_cycle_days: 30,
            plan_kind: 'profile_addon',
            monthly_song_limit: 0,
            monthly_image_limit: 0,
            monthly_draft_limit: 0,
            monthly_video_limit: 0,
            monthly_merge_limit: 0,
            daily_song_limit_per_channel: 1,
            daily_image_limit_per_channel: 1,
            daily_draft_limit_per_channel: 1,
            daily_video_limit: 1,
            daily_merge_limit: 1,
          });
        }
      }

      const keptIds = new Set(rows.map((row) => row.planId).filter(Boolean));
      for (const plan of addonRows) {
        if (!keptIds.has(plan.id) && plan.can_delete) {
          await deletePlan.mutateAsync(plan.id);
        }
      }

      setDrafts(null);
      toast({ title: 'Profile add-on plan rows saved' });
    } catch {
      toast({
        title: 'Failed to save add-on plan rows',
        variant: 'destructive',
      });
    }
  };

  const isSaving = createPlan.isPending || updatePlan.isPending || deletePlan.isPending;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading profile add-on plans…
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-sm text-red-300">Failed to load plans.</p>
          <Button className="mt-3" size="sm" variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-lg">Profile add-on plans</CardTitle>
          <p className="mt-1 text-sm text-slate-400">
            Each row is a real plan record — checkout and quotes read <code className="text-slate-300">price_cents</code>{' '}
            directly from these plans. Subscription pricing lives in the plan table below.
          </p>
          {basePlan ? (
            <p className="mt-2 text-xs text-slate-500">
              2-channel monthly base plan: <span className="text-slate-300">{basePlan.name}</span> at{' '}
              {formatUsd(basePlan.price_cents)}/mo
            </p>
          ) : (
            <p className="mt-2 text-xs text-amber-300/90">
              Create an active Monthly · 2-channel subscription plan — it becomes the pricing anchor.
            </p>
          )}
        </div>
        <Button type="button" size="sm" variant="outline" onClick={handleAddRow}>
          <Plus className="mr-2 h-4 w-4" />
          Add bundle
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-x-auto rounded-xl border border-slate-700/80">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-[0.14em] text-slate-400">
              <tr>
                <th className="px-4 py-3">Add-on channels</th>
                <th className="px-4 py-3">Monthly price (USD)</th>
                <th className="px-4 py-3">Plan row</th>
                <th className="px-4 py-3 w-[80px]" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                    No add-on plan rows yet. Click &quot;Add bundle&quot; to create one.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="border-t border-slate-800">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400">+</span>
                        <Input
                          type="number"
                          min={2}
                          max={8}
                          step={2}
                          className="max-w-[100px]"
                          value={row.channels}
                          onChange={(e) => {
                            const channels = Number(e.target.value);
                            setDrafts(
                              rows.map((item) =>
                                item.id === row.id ? { ...item, channels } : item,
                              ),
                            );
                          }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Input
                        value={row.monthlyDollars}
                        onChange={(e) =>
                          setDrafts(
                            rows.map((item) =>
                              item.id === row.id ? { ...item, monthlyDollars: e.target.value } : item,
                            ),
                          )
                        }
                      />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {row.planId ? row.planId.slice(0, 8) : 'New plan row'}
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="text-slate-400 hover:text-red-300"
                        onClick={() => setDrafts(rows.filter((item) => item.id !== row.id))}
                        aria-label="Remove add-on bundle"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save add-on plans
        </Button>
      </CardContent>
    </Card>
  );
}
