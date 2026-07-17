import { useEffect, useState } from 'react';
import { ImageIcon, Loader2 } from 'lucide-react';

import { useSystemSettings, useUpsertSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const SETTING_KEY = 'thumbnailReferenceMode';

const MODE_OPTIONS = [
  {
    value: 'composite',
    label: 'Composite (python_app style)',
    description:
      'Style sample in corner box → AI typography on black → composite onto generated background.',
  },
  {
    value: 'dual_reference',
    label: 'Dual reference (phase 2)',
    description:
      'Send background + style sample to the provider in one call. Not active yet; falls back to composite.',
  },
] as const;

function readSettingValue(
  settings: Array<{ key: string; value: string }>,
  key: string,
  fallback: string,
): string {
  const match = settings.find((item) => item.key === key);
  return match?.value?.trim() || fallback;
}

export function ImageGenerationSection() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const settings = data?.settings ?? [];

  const [mode, setMode] = useState('composite');

  useEffect(() => {
    setMode(readSettingValue(settings, SETTING_KEY, 'composite'));
  }, [settings]);

  const handleSave = () => {
    upsertSetting.mutate(
      { key: SETTING_KEY, value: mode, value_type: 'string' },
      {
        onSuccess: () => {
          toast({ title: 'Image generation settings saved' });
        },
      },
    );
  };

  const selected = MODE_OPTIONS.find((option) => option.value === mode) ?? MODE_OPTIONS[0];

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading image generation settings…
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
          <ImageIcon className="h-5 w-5" />
          Image Generation
        </CardTitle>
        <CardDescription>
          Control thumbnail reference strategy and sample rotation defaults for all users.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="thumbnail-reference-mode">Thumbnail reference mode</Label>
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger id="thumbnail-reference-mode">
              <SelectValue placeholder="Select mode" />
            </SelectTrigger>
            <SelectContent>
              {MODE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-sm text-slate-400">{selected.description}</p>
        </div>

        <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-300">
          Background and thumbnail style samples use database-backed least-used rotation.
          Selected samples rotate fairly; random mode scans the configured folder and still rotates
          by least-used usage.
        </div>

        <Button onClick={handleSave} disabled={upsertSetting.isPending}>
          {upsertSetting.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving…
            </>
          ) : (
            'Save image settings'
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
