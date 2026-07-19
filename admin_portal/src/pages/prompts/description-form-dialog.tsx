import { useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, X } from 'lucide-react';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useGenreCatalogSearch, type GenreCatalogItem } from '@/hooks/use-genre-catalog';
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
  genres: z.array(z.string().min(1).max(60)).max(10).default([]),
  match_key: z.string().max(100).optional().or(z.literal('')),
  vocal_mode: z.enum(['monolingual', 'bilingual']).default('monolingual'),
  primary_language: z.string().min(2).max(20).default('en'),
  secondary_language: z.string().max(20).optional().or(z.literal('')),
  verse_role: z.enum(['primary', 'secondary']).default('secondary'),
  chorus_role: z.enum(['primary', 'secondary']).default('primary'),
  section_language_map_json: z.string().optional().or(z.literal('')),
});

export type DescriptionFormValues = z.infer<typeof descriptionFormSchema>;

function normalizeGenres(values: string[]): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const raw of values) {
    const genre = raw.trim();
    if (!genre) continue;
    const key = genre.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push(genre);
  }
  return normalized.slice(0, 10);
}

function GenreChipInput({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState('');
  const [category, setCategory] = useState('');
  const [open, setOpen] = useState(false);
  const { data, isFetching } = useGenreCatalogSearch(draft, category || undefined);

  const suggestions = useMemo(() => {
    const selected = new Set(value.map((item) => item.toLowerCase()));
    return (data?.items ?? []).filter((item: GenreCatalogItem) => !selected.has(item.name.toLowerCase()));
  }, [data?.items, value]);

  function addGenre(raw: string) {
    const genre = raw.trim();
    if (!genre) return;
    onChange(normalizeGenres([...value, genre]));
    setDraft('');
    setOpen(false);
  }

  function addGenres(raw: string) {
    const parts = raw
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length === 0) return;
    onChange(normalizeGenres([...value, ...parts]));
    setDraft('');
    setOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      if (suggestions.length === 1 && suggestions[0]) {
        addGenre(suggestions[0].name);
      } else {
        addGenres(draft);
      }
    } else if (event.key === 'Backspace' && !draft && value.length > 0) {
      onChange(value.slice(0, -1));
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          disabled={disabled}
          className="h-9 rounded-md border border-slate-700 bg-slate-950 px-2 text-sm text-slate-200"
        >
          <option value="">All categories</option>
          {(data?.categories ?? []).map((item: string) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="relative">
        <div className="flex min-h-10 flex-wrap items-center gap-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-2">
          {value.map((genre) => (
            <Badge key={genre} variant="outline" className="gap-1 pr-1">
              {genre}
              <button
                type="button"
                className="rounded-sm p-0.5 hover:bg-slate-800"
                onClick={() => onChange(value.filter((item) => item !== genre))}
                disabled={disabled}
                aria-label={`Remove ${genre}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          <Input
            id="description-genres"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            onBlur={() => {
              window.setTimeout(() => setOpen(false), 150);
              if (draft.trim()) addGenres(draft);
            }}
            placeholder={value.length === 0 ? 'Search genres…' : 'Add genre'}
            disabled={disabled || value.length >= 10}
            className="h-8 min-w-[160px] flex-1 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
          />
        </div>
        {open && !disabled && value.length < 10 ? (
          <div className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-slate-700 bg-slate-950 py-1 shadow-lg">
            {isFetching ? (
              <p className="px-3 py-2 text-xs text-slate-400">Searching catalog…</p>
            ) : suggestions.length ? (
              suggestions.map((item: GenreCatalogItem) => (
                <button
                  key={item.slug}
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-900"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => addGenre(item.name)}
                >
                  <span>{item.name}</span>
                  <span className="text-xs text-slate-500">{item.category}</span>
                </button>
              ))
            ) : (
              <p className="px-3 py-2 text-xs text-slate-400">
                {draft.trim()
                  ? 'No matching catalog genres. Pick a suggestion or use a standard label.'
                  : 'Type to search the genre catalog (Electronic, Pop, Hip Hop, …).'}
              </p>
            )}
          </div>
        ) : null}
      </div>
      <p className="text-xs text-slate-400">
        Pick from the curated industry genre catalog. Custom free-text genres are rejected on save. Max 10.
      </p>
    </div>
  );
}

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
      genres: [],
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
      genres: defaultItem?.genres ?? [],
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
            <Label htmlFor="description-genres">Browse Genres</Label>
            <GenreChipInput
              value={form.watch('genres')}
              onChange={(next) => form.setValue('genres', next, { shouldDirty: true })}
              disabled={isLoading}
            />
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
