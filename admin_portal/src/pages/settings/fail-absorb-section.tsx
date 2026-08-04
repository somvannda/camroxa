import { useEffect, useState } from 'react';
import { Loader2, RotateCcw } from 'lucide-react';

import { useDeleteSetting, useSystemSettings, useUpsertSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

/** Matches platform_api UsageEnforcementService / PLATFORM_DAILY_FAIL_ABSORB_BUDGET. */
export const DAILY_FAIL_ABSORB_BUDGET_KEY = 'daily_fail_absorb_budget';
const ENV_DEFAULT_BUDGET = 25;

function readBudget(
  settings: Array<{ key: string; value: string }>,
): { value: string; fromDb: boolean } {
  const match = settings.find((item) => item.key === DAILY_FAIL_ABSORB_BUDGET_KEY);
  if (!match?.value?.trim()) {
    return { value: String(ENV_DEFAULT_BUDGET), fromDb: false };
  }
  return { value: match.value.trim(), fromDb: true };
}

export function FailAbsorbSection() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const deleteSetting = useDeleteSetting();
  const settings = data?.settings ?? [];

  const [budget, setBudget] = useState(String(ENV_DEFAULT_BUDGET));
  const [fromDb, setFromDb] = useState(false);

  useEffect(() => {
    const resolved = readBudget(settings);
    setBudget(resolved.value);
    setFromDb(resolved.fromDb);
  }, [settings]);

  const parsed = Number.parseInt(budget, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 0 && String(parsed) === budget.trim();

  const handleSave = () => {
    if (!isValid) {
      toast({
        title: 'Invalid budget',
        description: 'Enter a whole number ≥ 0 (0 disables the fail/retry absorb cap).',
        variant: 'destructive',
      });
      return;
    }
    upsertSetting.mutate(
      { key: DAILY_FAIL_ABSORB_BUDGET_KEY, value: String(parsed), value_type: 'integer' },
      {
        onSuccess: () => {
          toast({ title: 'Fail/retry absorb budget saved' });
        },
      },
    );
  };

  const handleResetToEnv = () => {
    deleteSetting.mutate(DAILY_FAIL_ABSORB_BUDGET_KEY, {
      onSuccess: () => {
        toast({
          title: 'Using environment default',
          description: `Cleared admin override. Env default is ${ENV_DEFAULT_BUDGET} (PLATFORM_DAILY_FAIL_ABSORB_BUDGET).`,
        });
      },
    });
  };

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading fail/retry absorb settings…
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="py-8">
          <Button onClick={() => refetch()}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-800 bg-slate-900/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg text-slate-100">
          <RotateCcw className="h-5 w-5" />
          Fail / Retry Absorb
        </CardTitle>
        <CardDescription>
          Maximum platform-absorbed failed generations per user per billing day. When a plan-covered
          generation fails, the platform refunds quota and counts it against this budget. After the
          cap, the user is blocked until tomorrow (or an admin resets their counter on the user
          detail page).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="daily-fail-absorb-budget">Max absorb retries per user / day</Label>
          <Input
            id="daily-fail-absorb-budget"
            type="number"
            min={0}
            step={1}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="max-w-xs"
          />
          <p className="text-sm text-slate-400">
            {fromDb
              ? 'Saved in admin system settings (overrides env).'
              : `Using environment / default (${ENV_DEFAULT_BUDGET}). Save to override.`}{' '}
            Set to 0 to disable the daily absorb cap.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={handleSave} disabled={!isValid || upsertSetting.isPending}>
            {upsertSetting.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save budget
          </Button>
          {fromDb && (
            <Button
              type="button"
              variant="outline"
              className="border-slate-700"
              onClick={handleResetToEnv}
              disabled={deleteSetting.isPending}
            >
              {deleteSetting.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Clear override
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
