import { useEffect, useState } from 'react';
import { Gift, Loader2 } from 'lucide-react';

import { useDeleteSetting, useSystemSettings, useUpsertSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

/** Matches platform_api.routers.users.WEB_MUSIC_FREE_DAILY_CREDITS_KEY. */
export const WEB_MUSIC_FREE_DAILY_CREDITS_KEY = 'web_music_free_daily_credits';
export const WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT = 50;
export const WEB_MUSIC_CREDITS_PER_SONG = 10;

const SONG_PRESETS = [1, 3, 5] as const;

function readCredits(
  settings: Array<{ key: string; value: string }>,
): { value: string; fromDb: boolean } {
  const match = settings.find((item) => item.key === WEB_MUSIC_FREE_DAILY_CREDITS_KEY);
  if (!match?.value?.trim()) {
    return { value: String(WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT), fromDb: false };
  }
  return { value: match.value.trim(), fromDb: true };
}

function songPreview(credits: number): string {
  if (credits <= 0) {
    return 'Listen-only until they subscribe (no free generations).';
  }
  const songs = Math.floor(credits / WEB_MUSIC_CREDITS_PER_SONG);
  const leftover = credits % WEB_MUSIC_CREDITS_PER_SONG;
  const songLabel = songs === 1 ? '1 song' : `${songs} songs`;
  if (leftover === 0) {
    return `≈ ${songLabel}/day (${WEB_MUSIC_CREDITS_PER_SONG} credits per song).`;
  }
  return `≈ ${songLabel}/day plus ${leftover} leftover credit${leftover === 1 ? '' : 's'} for style/lyrics assist.`;
}

export function MusicWebFreeCreditsSection() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const deleteSetting = useDeleteSetting();
  const settings = data?.settings ?? [];

  const [credits, setCredits] = useState(String(WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT));
  const [fromDb, setFromDb] = useState(false);

  useEffect(() => {
    const resolved = readCredits(settings);
    setCredits(resolved.value);
    setFromDb(resolved.fromDb);
  }, [settings]);

  const parsed = Number.parseInt(credits, 10);
  const isValid =
    Number.isFinite(parsed) && parsed >= 0 && parsed <= 5000 && String(parsed) === credits.trim();

  const handleSave = () => {
    if (!isValid) {
      toast({
        title: 'Invalid daily credits',
        description: 'Enter a whole number from 0 to 5000. 0 disables free generations.',
        variant: 'destructive',
      });
      return;
    }
    upsertSetting.mutate(
      { key: WEB_MUSIC_FREE_DAILY_CREDITS_KEY, value: String(parsed), value_type: 'integer' },
      {
        onSuccess: () => {
          toast({
            title: 'Free daily credits saved',
            description: songPreview(parsed),
          });
        },
      },
    );
  };

  const handleResetDefault = () => {
    deleteSetting.mutate(WEB_MUSIC_FREE_DAILY_CREDITS_KEY, {
      onSuccess: () => {
        toast({
          title: 'Using default',
          description: `${WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT} credits/day (≈ ${
            WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT / WEB_MUSIC_CREDITS_PER_SONG
          } songs).`,
        });
      },
    });
  };

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading Music Web free daily credits…
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
          <Gift className="h-5 w-5" />
          Camxora Music — Free daily pool
        </CardTitle>
        <CardDescription>
          Unpaid Music Web users share this credit pool each billing day (midnight Asia/Phnom_Penh).
          Songs cost {WEB_MUSIC_CREDITS_PER_SONG} credits. Style and lyrics assist also spend from
          the same pool. Paid Music subscribers use their monthly plan credits instead. This is not
          a desktop Studio plan limit.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="web-music-free-daily-credits">Daily credits</Label>
          <Input
            id="web-music-free-daily-credits"
            type="number"
            min={0}
            max={5000}
            step={1}
            value={credits}
            onChange={(e) => setCredits(e.target.value)}
            className="max-w-xs"
          />
          <p className="text-sm text-slate-400">
            {isValid ? songPreview(parsed) : 'Enter a whole number from 0 to 5000.'}{' '}
            {fromDb
              ? 'Saved in system settings.'
              : `Using default (${WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT}). Save to override.`}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {SONG_PRESETS.map((songs) => {
            const amount = songs * WEB_MUSIC_CREDITS_PER_SONG;
            return (
              <Button
                key={songs}
                type="button"
                size="sm"
                variant="outline"
                className="border-slate-700"
                onClick={() => setCredits(String(amount))}
              >
                {songs} song{songs === 1 ? '' : 's'} ({amount} cr)
              </Button>
            );
          })}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-slate-700"
            onClick={() => setCredits('0')}
          >
            0 (listen-only)
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={handleSave} disabled={!isValid || upsertSetting.isPending}>
            {upsertSetting.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save daily credits
          </Button>
          {fromDb && (
            <Button
              type="button"
              variant="outline"
              className="border-slate-700"
              onClick={handleResetDefault}
              disabled={deleteSetting.isPending}
            >
              {deleteSetting.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Reset to {WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
