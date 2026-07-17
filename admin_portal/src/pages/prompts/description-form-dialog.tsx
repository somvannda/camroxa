import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { MusicDescription, VocalProfile } from '@/types/models';

const descriptionFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  content: z.string().min(1, 'Content is required').max(5000),
  match_key: z.string().max(100).optional().or(z.literal('')),
  vocal_mode: z.enum(['monolingual', 'bilingual']).default('monolingual'),
  primary_language: z.string().min(2).max(20).default('en'),
  secondary_language: z.string().max(20).optional().or(z.literal('')),
  verse_role: z.enum(['primary', 'secondary']).default('secondary'),
  chorus_role: z.enum(['primary', 'secondary']).default('primary'),
  section_language_map_json: z.string().optional().or(z.literal('')),
});

export type DescriptionFormValues = z.infer<typeof descriptionFormSchema>;

const VERSE_SECTION_KEYS = [
  'intro',
  'verse',
  'build-up',
  'build up',
  'break',
  'bridge',
  'outro',
  'pre-chorus',
  'pre chorus',
] as const;

const CHORUS_SECTION_KEYS = [
  'chorus',
  'hook',
  'drop',
  'final drop',
  'final-drop',
] as const;

function buildSectionLanguageMapFromRoles(
  verseRole: 'primary' | 'secondary',
  chorusRole: 'primary' | 'secondary',
): Record<string, 'primary' | 'secondary'> {
  const sectionMap: Record<string, 'primary' | 'secondary'> = {};
  for (const key of VERSE_SECTION_KEYS) {
    sectionMap[key] = verseRole;
  }
  for (const key of CHORUS_SECTION_KEYS) {
    sectionMap[key] = chorusRole;
  }
  return sectionMap;
}

function vocalProfileToFormValues(profile: VocalProfile | null | undefined): Partial<DescriptionFormValues> {
  if (!profile || profile.mode !== 'bilingual') {
    return { vocal_mode: 'monolingual' };
  }
  return {
    vocal_mode: 'bilingual',
    primary_language: profile.primary_language ?? 'en',
    secondary_language: profile.secondary_language ?? '',
    verse_role: profile.verse_role ?? 'secondary',
    chorus_role: profile.chorus_role ?? 'primary',
    section_language_map_json: profile.section_language_map
      ? JSON.stringify(profile.section_language_map, null, 2)
      : '',
  };
}

export function formValuesToVocalProfile(values: DescriptionFormValues): VocalProfile | null {
  if (values.vocal_mode !== 'bilingual') {
    return null;
  }
  let section_language_map: Record<string, 'primary' | 'secondary'> | undefined;
  const rawMap = values.section_language_map_json?.trim();
  if (rawMap) {
    const parsed = JSON.parse(rawMap) as Record<string, string>;
    section_language_map = Object.fromEntries(
      Object.entries(parsed).map(([key, role]) => [key, role === 'primary' ? 'primary' : 'secondary']),
    );
  }
  return {
    mode: 'bilingual',
    primary_language: values.primary_language,
    secondary_language: values.secondary_language || undefined,
    verse_role: values.verse_role,
    chorus_role: values.chorus_role,
    section_language_map,
  };
}

interface DescriptionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  defaultItem?: MusicDescription | null;
  onSubmit: (values: DescriptionFormValues, vocalProfile: VocalProfile | null) => void;
  isLoading: boolean;
}

export function DescriptionFormDialog({
  open,
  onOpenChange,
  title,
  defaultItem,
  onSubmit,
  isLoading,
}: DescriptionFormDialogProps) {
  const form = useForm<DescriptionFormValues>({
    resolver: zodResolver(descriptionFormSchema),
    defaultValues: {
      name: '',
      content: '',
      match_key: '',
      vocal_mode: 'monolingual',
      primary_language: 'en',
      secondary_language: '',
      verse_role: 'secondary',
      chorus_role: 'primary',
      section_language_map_json: '',
    },
  });

  const vocalMode = form.watch('vocal_mode');
  const verseRole = form.watch('verse_role');
  const chorusRole = form.watch('chorus_role');

  function handleAutoGenerateSectionMap() {
    const sectionMap = buildSectionLanguageMapFromRoles(verseRole, chorusRole);
    form.setValue('section_language_map_json', JSON.stringify(sectionMap, null, 2), {
      shouldDirty: true,
    });
    form.clearErrors('section_language_map_json');
  }

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: defaultItem?.name ?? '',
      content: defaultItem?.content ?? '',
      match_key: defaultItem?.match_key ?? '',
      vocal_mode: 'monolingual',
      primary_language: 'en',
      secondary_language: '',
      verse_role: 'secondary',
      chorus_role: 'primary',
      section_language_map_json: '',
      ...vocalProfileToFormValues(defaultItem?.vocal_profile),
    });
  }, [defaultItem, form, open]);

  const handleSubmit = form.handleSubmit((values) => {
    try {
      const vocalProfile = formValuesToVocalProfile(values);
      onSubmit(values, vocalProfile);
    } catch {
      form.setError('section_language_map_json', {
        message: 'Section language map must be valid JSON object.',
      });
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Production notes go in Content. Vocal language policy is configured separately for bilingual
            templates such as Eurodance (German verses, English chorus).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="description-name">Name</Label>
            <Input id="description-name" {...form.register('name')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description-content">Production Content</Label>
            <Textarea id="description-content" rows={6} {...form.register('content')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description-match-key">Match Key (optional)</Label>
            <Input id="description-match-key" {...form.register('match_key')} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="description-vocal-mode">Vocal Mode</Label>
              <select
                id="description-vocal-mode"
                className="flex h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                {...form.register('vocal_mode')}
              >
                <option value="monolingual">Monolingual</option>
                <option value="bilingual">Bilingual</option>
              </select>
            </div>
            {vocalMode === 'bilingual' ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="description-primary-language">Primary Language Code</Label>
                  <Input id="description-primary-language" placeholder="en" {...form.register('primary_language')} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description-secondary-language">Secondary Language Code</Label>
                  <Input
                    id="description-secondary-language"
                    placeholder="de"
                    {...form.register('secondary_language')}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description-verse-role">Verse Sections Use</Label>
                  <select
                    id="description-verse-role"
                    className="flex h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    {...form.register('verse_role')}
                  >
                    <option value="secondary">Secondary language</option>
                    <option value="primary">Primary language</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description-chorus-role">Chorus/Drop Sections Use</Label>
                  <select
                    id="description-chorus-role"
                    className="flex h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    {...form.register('chorus_role')}
                  >
                    <option value="primary">Primary language</option>
                    <option value="secondary">Secondary language</option>
                  </select>
                </div>
              </>
            ) : null}
          </div>

          {vocalMode === 'bilingual' ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="description-section-map">Section Language Map (optional JSON)</Label>
                <Button type="button" variant="outline" size="sm" onClick={handleAutoGenerateSectionMap}>
                  Auto-generate from roles
                </Button>
              </div>
              <Textarea
                id="description-section-map"
                rows={8}
                placeholder={'{\n  "intro": "secondary",\n  "verse": "secondary",\n  "chorus": "primary",\n  "drop": "primary"\n}'}
                {...form.register('section_language_map_json')}
              />
              <p className="text-xs text-slate-400">
                Keys are normalized section names (verse, chorus, drop, bridge, etc.). At lyric time each
                structure header is matched by name; unknown sections fall back to the verse/chorus roles above.
              </p>
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {defaultItem ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
