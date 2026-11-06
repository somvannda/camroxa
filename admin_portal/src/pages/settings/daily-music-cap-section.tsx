import { useEffect, useState } from 'react';
import { Gauge, Loader2, RotateCcw } from 'lucide-react';

import { useDeleteSetting, useSystemSettings, useUpsertSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

/**
 * Per-user daily music cap. Mirrors platform_api
 * CreditsOnlyBillingService._assert_daily_music_cap: this row wins over
 * MUSIC_DAILY_CREDIT_CAP, and 0 disables the cap entirely.
 */
export const MUSIC_DAILY_CAP_KEY = 'music_daily_credit_cap';
const ENV_DEFAULT_CAP = 500;

function readCap(settings: Array<{ key: string; value: string }>): {
  value: string;
  fromDb: boolean;
} {
  const match = settings.find((item) => item.key === MUSIC_DAILY_CAP_KEY);
  if (!match?.value?.trim()) {
    return { value: String(ENV_DEFAULT_CAP), fromDb: false };
  }
  return { value: match.value.trim(), fromDb: true };
}

export function DailyMusicCapSection() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const deleteSetting = useDeleteSetting();
  const settings = data?.settings ?? [];

  const [cap, setCap] = useState(String(ENV_DEFAULT_CAP));
  const [fromDb, setFromDb] = useState(false);

  useEffect(() => {
    const resolved = readCap(settings);
    setCap(resolved.value);
    setFromDb(resolved.fromDb);
  }, [settings]);

  const parsed = Number.parseInt(cap, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 0 && String(parsed) === cap.trim();
  const songs = isValid ? Math.floor(parsed / 10) : 0;

  const handleSave = () => {
    if (!isValid) {
      toast({
        title: 'Invalid daily cap',
        description: 'Enter a whole number of credits ≥ 0 (0 disables the cap).',
        variant: 'destructive',
      });
      return;
    }
    upsertSetting.mutate(
      { key: MUSIC_DAILY_CAP_KEY, value: String(parsed), value_type: 'integer' },
      {
        onSuccess: () => toast({ title: 'Daily music cap saved' }),
      },
    );
  };

  const handleResetToEnv = () => {
    deleteSetting.mutate(MUSIC_DAILY_CAP_KEY, {
      onSuccess: () =>
        toast({
          title: 'Using environment default',
          description: `Cleared the admin override. Env default is ${ENV_DEFAULT_CAP} (MUSIC_DAILY_CREDIT_CAP).`,
        }),
    });
  };

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading daily music cap…
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
          <Gauge className="h-5 w-5" />
          Daily Music Cap
        </CardTitle>
        <CardDescription>
          Maximum music credits one user can spend per calendar day, across web and desktop. The
          paid Suno accounts are a shared pool, so this stops a single account draining it. A song
          costs 10 credits on our musicapi (15 on the sunoapi.org reseller), so the
          current value allows about {songs} songs per user per day.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="music-daily-credit-cap">Max music credits per user / day</Label>
          <Input
            id="music-daily-credit-cap"
            type="number"
            min={0}
            step={10}
            value={cap}
            onChange={(e) => setCap(e.target.value)}
            className="max-w-xs"
          />
          <p className="text-sm text-slate-400">
            {fromDb
              ? 'Saved in admin system settings (overrides env).'
              : `Using environment / default (${ENV_DEFAULT_CAP}). Save to override.`}{' '}
            Set to 0 to disable the cap. Takes effect on the next generation — no deploy needed.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={handleSave} disabled={!isValid || upsertSetting.isPending}>
            {upsertSetting.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              'Save'
            )}
          </Button>
          <Button
            variant="outline"
            onClick={handleResetToEnv}
            disabled={!fromDb || deleteSetting.isPending}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Use env default
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
