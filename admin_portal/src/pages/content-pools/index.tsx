import { useEffect, useMemo, useState } from 'react';
import { Edit3, Loader2, Plus, RefreshCcw, Sparkles, Trash2, Upload } from 'lucide-react';

import {
  useClearContentPool,
  useContentPoolItems,
  useContentPoolPresetPacks,
  useContentPoolStats,
  useCreateContentPoolPresetPack,
  useDeleteContentPoolItem,
  useDeleteContentPoolPresetPack,
  useGenerateContentPool,
  useGenerateContentPoolPresetBanks,
  useImportContentPool,
  useUpdateContentPoolItem,
  useUpdateContentPoolPresetPack,
} from '@/hooks/use-content-pools';
import { useToast } from '@/hooks/use-toast';
import type {
  ContentPoolKind,
  GenerateContentPoolResponse,
  ContentPoolPresetConfig,
  ContentPoolPresetPack,
  ContentPoolRow,
} from '@/types/content-pools';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

const POOL_KINDS: ContentPoolKind[] = ['titles', 'albums', 'openings'];
const KIND_LABELS: Record<ContentPoolKind, string> = {
  titles: 'Titles',
  albums: 'Albums',
  openings: 'Openings',
};
const PAGE_SIZE = 100;
const DEFAULT_PRESET_PACK_VALUE = '__default__';
const MASSIVE_PRESET_TARGET_COUNT = 10000;

type PresetListField =
  | 'adjectives'
  | 'nouns'
  | 'verbs'
  | 'places'
  | 'feelings'
  | 'whos'
  | 'moods'
  | 'times';

type PresetPackFormState = {
  name: string;
  description: string;
  includeDefaults: boolean;
  isActive: boolean;
  adjectives: string;
  nouns: string;
  verbs: string;
  places: string;
  feelings: string;
  whos: string;
  moods: string;
  times: string;
};

const PRESET_FIELDS: Record<
  ContentPoolKind,
  Array<{ key: PresetListField; label: string; helper: string }>
> = {
  titles: [
    { key: 'adjectives', label: 'Adjectives', helper: 'Theme words like neon, midnight, velvet.' },
    { key: 'nouns', label: 'Nouns', helper: 'Objects or concepts like skyline, static, heartbeat.' },
    { key: 'verbs', label: 'Verbs', helper: 'Action words like run, fade, remember.' },
    { key: 'places', label: 'Places', helper: 'Line-based phrases like under streetlights.' },
    { key: 'feelings', label: 'Feelings', helper: 'Mood phrases like like home or in the afterglow.' },
  ],
  albums: [
    { key: 'adjectives', label: 'Adjectives', helper: 'Descriptive theme words for album naming.' },
    { key: 'nouns', label: 'Nouns', helper: 'Core nouns mixed into album titles.' },
  ],
  openings: [
    { key: 'adjectives', label: 'Adjectives', helper: 'Descriptive words for opening lines.' },
    { key: 'nouns', label: 'Nouns', helper: 'Core nouns used across opening pairs.' },
    { key: 'verbs', label: 'Verbs', helper: 'Action words for the first line.' },
    { key: 'places', label: 'Places', helper: 'Line-based phrases like in the backseat.' },
    { key: 'whos', label: 'Who / Subject', helper: 'Speakers or subjects like I, We, Tonight.' },
    { key: 'moods', label: 'Moods', helper: 'Emotion words like longing, euphoria, regret.' },
    { key: 'times', label: 'Time Phrases', helper: 'Timing cues like after midnight or before dawn.' },
  ],
};

function formatDate(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatCount(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString('en-US');
}

function getReservationBadgeClass(state: ContentPoolRow['reservation_state']): string {
  if (state === 'reserved') {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  }
  if (state === 'stale') {
    return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
  }
  return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
}

function createEmptyPresetPackForm(): PresetPackFormState {
  return {
    name: '',
    description: '',
    includeDefaults: true,
    isActive: true,
    adjectives: '',
    nouns: '',
    verbs: '',
    places: '',
    feelings: '',
    whos: '',
    moods: '',
    times: '',
  };
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function formatLines(values: string[]): string {
  return values.join('\n');
}

function presetPackToForm(pack: ContentPoolPresetPack): PresetPackFormState {
  return {
    name: pack.name,
    description: pack.description,
    includeDefaults: pack.config.include_defaults,
    isActive: pack.is_active,
    adjectives: formatLines(pack.config.adjectives),
    nouns: formatLines(pack.config.nouns),
    verbs: formatLines(pack.config.verbs),
    places: formatLines(pack.config.places),
    feelings: formatLines(pack.config.feelings),
    whos: formatLines(pack.config.whos),
    moods: formatLines(pack.config.moods),
    times: formatLines(pack.config.times),
  };
}

function buildPresetConfig(form: PresetPackFormState): ContentPoolPresetConfig {
  return {
    include_defaults: form.includeDefaults,
    adjectives: parseLines(form.adjectives),
    nouns: parseLines(form.nouns),
    verbs: parseLines(form.verbs),
    places: parseLines(form.places),
    feelings: parseLines(form.feelings),
    whos: parseLines(form.whos),
    moods: parseLines(form.moods),
    times: parseLines(form.times),
  };
}

function summarizePresetPack(kind: ContentPoolKind, config: ContentPoolPresetConfig): string {
  const counts = PRESET_FIELDS[kind]
    .map((field) => `${field.label}: ${config[field.key].length}`)
    .join(' • ');
  return `${config.include_defaults ? 'Merge defaults' : 'Custom only'} • ${counts}`;
}

function buildMassivePresetPackName(kind: ContentPoolKind): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 13);
  return `${KIND_LABELS[kind]} Massive Pack ${stamp}`;
}

function buildMassivePresetPackDescription(kind: ContentPoolKind): string {
  return `Auto-generated ${MASSIVE_PRESET_TARGET_COUNT.toLocaleString()}-entry starter banks for ${KIND_LABELS[kind].toLowerCase()}.`;
}

export default function ContentPoolsPage() {
  const { toast } = useToast();
  const [activeKind, setActiveKind] = useState<ContentPoolKind>('titles');
  const [offsetByKind, setOffsetByKind] = useState<Record<ContentPoolKind, number>>({
    titles: 0,
    albums: 0,
    openings: 0,
  });
  const [generateOpen, setGenerateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editItem, setEditItem] = useState<ContentPoolRow | null>(null);
  const [deleteItem, setDeleteItem] = useState<ContentPoolRow | null>(null);
  const [clearOpen, setClearOpen] = useState(false);
  const [generateCount, setGenerateCount] = useState('10000');
  const [generatePresetPackId, setGeneratePresetPackId] = useState(DEFAULT_PRESET_PACK_VALUE);
  const [lastGenerateResult, setLastGenerateResult] = useState<GenerateContentPoolResponse | null>(null);
  const [lastGenerateSource, setLastGenerateSource] = useState('Default Mixer');
  const [importText, setImportText] = useState('');
  const [editText, setEditText] = useState('');
  const [editSecondaryText, setEditSecondaryText] = useState('');
  const [presetPackOpen, setPresetPackOpen] = useState(false);
  const [presetPackEditId, setPresetPackEditId] = useState<string | null>(null);
  const [presetPackDeleteItem, setPresetPackDeleteItem] = useState<ContentPoolPresetPack | null>(null);
  const [presetPackForm, setPresetPackForm] = useState<PresetPackFormState>(() => createEmptyPresetPackForm());

  const currentOffset = offsetByKind[activeKind];
  const statsQuery = useContentPoolStats();
  const itemsQuery = useContentPoolItems(activeKind, PAGE_SIZE, currentOffset);
  const presetPacksQuery = useContentPoolPresetPacks(activeKind);
  const generateMutation = useGenerateContentPool(activeKind);
  const importMutation = useImportContentPool(activeKind);
  const updateMutation = useUpdateContentPoolItem(activeKind);
  const deleteMutation = useDeleteContentPoolItem(activeKind);
  const clearMutation = useClearContentPool(activeKind);
  const createPresetMutation = useCreateContentPoolPresetPack(activeKind);
  const updatePresetMutation = useUpdateContentPoolPresetPack(activeKind);
  const deletePresetMutation = useDeleteContentPoolPresetPack(activeKind);
  const generatePresetBanksMutation = useGenerateContentPoolPresetBanks(activeKind);

  const currentStats = statsQuery.data?.[activeKind];
  const totalPages = Math.max(1, Math.ceil((itemsQuery.data?.total ?? 0) / PAGE_SIZE));
  const currentPage = Math.floor(currentOffset / PAGE_SIZE) + 1;
  const presetPacks = presetPacksQuery.data?.items ?? [];
  const activePresetPacks = presetPacks.filter((item) => item.is_active);
  const presetPackSavePending = createPresetMutation.isPending || updatePresetMutation.isPending;
  const presetPackGenerateSavePending = presetPackSavePending || generatePresetBanksMutation.isPending;

  const importHelper = useMemo(() => {
    if (activeKind === 'openings') {
      return 'Paste one opening pair per line separated by a tab, or use alternating line1/line2 lines.';
    }
    return 'Paste one entry per line. Duplicate normalized values are skipped automatically.';
  }, [activeKind]);

  useEffect(() => {
    setGeneratePresetPackId(DEFAULT_PRESET_PACK_VALUE);
    setLastGenerateResult(null);
    setLastGenerateSource('Default Mixer');
  }, [activeKind]);

  useEffect(() => {
    setLastGenerateResult(null);
    const selectedPack =
      generatePresetPackId === DEFAULT_PRESET_PACK_VALUE
        ? null
        : activePresetPacks.find((item) => item.id === generatePresetPackId) ?? null;
    setLastGenerateSource(selectedPack?.name ?? 'Default Mixer');
  }, [generatePresetPackId, activePresetPacks]);

  function openEditDialog(item: ContentPoolRow) {
    setEditItem(item);
    setEditText(item.text);
    setEditSecondaryText(item.secondary_text ?? '');
  }

  function openCreatePresetPackDialog() {
    setPresetPackEditId(null);
    setPresetPackForm(createEmptyPresetPackForm());
    setPresetPackOpen(true);
  }

  function openEditPresetPackDialog(pack: ContentPoolPresetPack) {
    setPresetPackEditId(pack.id);
    setPresetPackForm(presetPackToForm(pack));
    setPresetPackOpen(true);
  }

  function setPresetField(field: keyof PresetPackFormState, value: string | boolean) {
    setPresetPackForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function savePresetPackFromForm(
    form: PresetPackFormState,
  options?: { allowGeneratedName?: boolean; successTitle?: string; openGenerateDialog?: boolean },
): Promise<ContentPoolPresetPack | null> {
    const generatedName = options?.allowGeneratedName ? buildMassivePresetPackName(activeKind) : '';
    const payload = {
      name: form.name.trim() || generatedName,
      description: form.description.trim() || (options?.allowGeneratedName ? buildMassivePresetPackDescription(activeKind) : ''),
      isActive: form.isActive,
      config: buildPresetConfig(form),
    };

    if (!payload.name) {
      toast({
        variant: 'destructive',
        title: 'Name required',
        description: 'Preset packs need a name before they can be saved.',
      });
      return null;
    }

    let savedPack: ContentPoolPresetPack;
    if (presetPackEditId) {
      savedPack = await updatePresetMutation.mutateAsync({
        presetPackId: presetPackEditId,
        ...payload,
      });
      toast({ title: options?.successTitle ?? 'Preset pack updated' });
    } else {
      savedPack = await createPresetMutation.mutateAsync(payload);
      toast({ title: options?.successTitle ?? 'Preset pack created' });
    }

    setPresetPackOpen(false);
    setPresetPackEditId(null);
    setPresetPackForm(createEmptyPresetPackForm());

    if (options?.openGenerateDialog) {
      setGeneratePresetPackId(savedPack.id);
      setGenerateOpen(true);
    }

    return savedPack;
  }

  async function handleGenerate() {
    try {
      const count = Math.max(1, Math.min(200000, Number(generateCount) || 1));
      const selectedPack =
        generatePresetPackId === DEFAULT_PRESET_PACK_VALUE
          ? null
          : activePresetPacks.find((item) => item.id === generatePresetPackId) ?? null;
      const result = await generateMutation.mutateAsync({
        count,
        presetPackId: selectedPack?.id ?? null,
      });
      setLastGenerateResult(result);
      setLastGenerateSource(selectedPack?.name ?? 'Default Mixer');
      setGenerateOpen(false);
      const generationSource = selectedPack ? selectedPack.name : 'the default mixer';
      const summary =
        result.duplicates_skipped > 0
          ? `Inserted ${result.inserted.toLocaleString()} of ${result.requested.toLocaleString()} requested ${activeKind} using ${generationSource}. Attempted ${result.attempted.toLocaleString()} candidates and skipped ${result.duplicates_skipped.toLocaleString()} duplicates.`
          : `Inserted ${result.inserted.toLocaleString()} new ${activeKind} using ${generationSource}. Attempted ${result.attempted.toLocaleString()} candidates with no duplicate skips.`;
      toast({
        title: `${KIND_LABELS[activeKind]} generated`,
        description: summary,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Generation failed',
        description: error instanceof Error ? error.message : 'Unable to generate pool entries right now.',
      });
    }
  }

  async function handleImport() {
    try {
      const result = await importMutation.mutateAsync(importText);
      setImportOpen(false);
      setImportText('');
      toast({
        title: `${KIND_LABELS[activeKind]} imported`,
        description: `Inserted ${result.inserted} new ${activeKind}.`,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Import failed',
        description: error instanceof Error ? error.message : 'Unable to import pool entries right now.',
      });
    }
  }

  async function handleUpdate() {
    if (!editItem) return;
    try {
      await updateMutation.mutateAsync({
        itemId: editItem.id,
        text: editText,
        secondaryText: activeKind === 'openings' ? editSecondaryText : null,
      });
      setEditItem(null);
      toast({ title: `${KIND_LABELS[activeKind].slice(0, -1)} updated` });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Update failed',
        description: error instanceof Error ? error.message : 'Unable to update this pool item right now.',
      });
    }
  }

  async function handleDelete() {
    if (!deleteItem) return;
    try {
      await deleteMutation.mutateAsync(deleteItem.id);
      setDeleteItem(null);
      toast({ title: `${KIND_LABELS[activeKind].slice(0, -1)} deleted` });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Delete failed',
        description: error instanceof Error ? error.message : 'Unable to delete this pool item right now.',
      });
    }
  }

  async function handleClear() {
    try {
      await clearMutation.mutateAsync();
      setClearOpen(false);
      setOffsetByKind((current) => ({ ...current, [activeKind]: 0 }));
      toast({ title: `${KIND_LABELS[activeKind]} cleared` });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Clear failed',
        description: error instanceof Error ? error.message : 'Unable to clear this pool right now.',
      });
    }
  }

  async function handleSavePresetPack() {
    try {
      await savePresetPackFromForm(presetPackForm);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Preset pack save failed',
        description: error instanceof Error ? error.message : 'Unable to save this preset pack right now.',
      });
    }
  }

  async function handleGeneratePresetBanks() {
    try {
      const result = await generatePresetBanksMutation.mutateAsync({
        targetCount: MASSIVE_PRESET_TARGET_COUNT,
      });
      setPresetPackForm((current) => {
        const next = { ...current };
        PRESET_FIELDS[activeKind].forEach((field) => {
          next[field.key] = formatLines(result.banks[field.key] ?? []);
        });
        return next;
      });
      toast({
        title: 'Preset banks generated',
        description: `Filled ${MASSIVE_PRESET_TARGET_COUNT.toLocaleString()} entries for each visible ${KIND_LABELS[activeKind].toLowerCase()} field.`,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Preset bank generation failed',
        description: error instanceof Error ? error.message : 'Unable to generate large preset banks right now.',
      });
    }
  }

  async function handleGenerateAndSavePresetPack() {
    try {
      const result = await generatePresetBanksMutation.mutateAsync({
        targetCount: MASSIVE_PRESET_TARGET_COUNT,
      });

      const nextForm: PresetPackFormState = {
        ...presetPackForm,
        name: presetPackForm.name.trim() || buildMassivePresetPackName(activeKind),
        description: presetPackForm.description.trim() || buildMassivePresetPackDescription(activeKind),
      };

      PRESET_FIELDS[activeKind].forEach((field) => {
        nextForm[field.key] = formatLines(result.banks[field.key] ?? []);
      });

      setPresetPackForm(nextForm);
      await savePresetPackFromForm(nextForm, {
        allowGeneratedName: true,
        successTitle: presetPackEditId ? 'Massive preset pack updated' : 'Massive preset pack created',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Generate and save failed',
        description: error instanceof Error ? error.message : 'Unable to generate and save this massive preset pack right now.',
      });
    }
  }

  async function handleGenerateSaveAndOpenPresetPack() {
    try {
      const result = await generatePresetBanksMutation.mutateAsync({
        targetCount: MASSIVE_PRESET_TARGET_COUNT,
      });

      const nextForm: PresetPackFormState = {
        ...presetPackForm,
        name: presetPackForm.name.trim() || buildMassivePresetPackName(activeKind),
        description: presetPackForm.description.trim() || buildMassivePresetPackDescription(activeKind),
      };

      PRESET_FIELDS[activeKind].forEach((field) => {
        nextForm[field.key] = formatLines(result.banks[field.key] ?? []);
      });

      setPresetPackForm(nextForm);
      const savedPack = await savePresetPackFromForm(nextForm, {
        allowGeneratedName: true,
        successTitle: presetPackEditId ? 'Massive preset pack updated' : 'Massive preset pack created',
        openGenerateDialog: true,
      });

      if (savedPack) {
        toast({
          title: 'Generate dialog ready',
          description: `${savedPack.name} is selected and ready to generate ${KIND_LABELS[activeKind].toLowerCase()}.`,
        });
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Generate, save, and open failed',
        description:
          error instanceof Error
            ? error.message
            : 'Unable to prepare the generate dialog with this massive preset pack right now.',
      });
    }
  }

  async function handleDeletePresetPack() {
    if (!presetPackDeleteItem) return;
    try {
      await deletePresetMutation.mutateAsync(presetPackDeleteItem.id);
      if (generatePresetPackId === presetPackDeleteItem.id) {
        setGeneratePresetPackId(DEFAULT_PRESET_PACK_VALUE);
      }
      setPresetPackDeleteItem(null);
      toast({ title: 'Preset pack deleted' });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Preset pack delete failed',
        description: error instanceof Error ? error.message : 'Unable to delete this preset pack right now.',
      });
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Content Pools</h1>
        <p className="mt-1 text-sm text-slate-400">
          Manage shared title, album, and opening catalogs plus reusable preset packs for generation workflows.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {POOL_KINDS.map((kind) => {
          const stat = statsQuery.data?.[kind];
          return (
            <Card className="border-navy-700 bg-navy-900" key={kind}>
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-white">{KIND_LABELS[kind]}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {statsQuery.isLoading ? (
                  <Skeleton className="h-12 w-full" />
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Total</span>
                      <span className="text-lg font-semibold text-white">{formatCount(stat?.total)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Unused</span>
                      <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                        {formatCount(stat?.unused)}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Used</span>
                      <span className="text-sm text-slate-300">
                        {formatCount(stat ? Math.max(0, stat.total - stat.unused) : 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Reserved</span>
                      <Badge className="border-amber-500/30 bg-amber-500/10 text-amber-300">
                        {formatCount(stat?.reserved)}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Stale</span>
                      <Badge className="border-rose-500/30 bg-rose-500/10 text-rose-300">
                        {formatCount(stat?.stale_reserved)}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Available</span>
                      <span className="text-sm text-slate-300">{formatCount(stat?.available)}</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="border-navy-700 bg-navy-900">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-lg text-white">Pool Manager</CardTitle>
              <p className="mt-1 text-sm text-slate-400">
                The default preset mixer is still available, and admins can now save reusable preset packs per pool kind.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" className="gap-1.5" onClick={() => setGenerateOpen(true)}>
                <RefreshCcw className="h-4 w-4" />
                Generate
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setImportOpen(true)}>
                <Upload className="h-4 w-4" />
                Import
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5" onClick={openCreatePresetPackDialog}>
                <Plus className="h-4 w-4" />
                New Preset Pack
              </Button>
              <Button size="sm" variant="destructive" className="gap-1.5" onClick={() => setClearOpen(true)}>
                <Trash2 className="h-4 w-4" />
                Clear Pool
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeKind} onValueChange={(value) => setActiveKind(value as ContentPoolKind)}>
            <TabsList className="border border-navy-700 bg-navy-800">
              {POOL_KINDS.map((kind) => (
                <TabsTrigger
                  key={kind}
                  value={kind}
                  className="text-slate-400 data-[state=active]:bg-navy-600 data-[state=active]:text-white"
                >
                  {KIND_LABELS[kind]}
                </TabsTrigger>
              ))}
            </TabsList>

            {POOL_KINDS.map((kind) => (
              <TabsContent key={kind} value={kind} className="mt-4 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-navy-700 bg-navy-950/40 px-4 py-3">
                  <div className="text-sm text-slate-400">
                    {kind === activeKind && currentStats
                      ? `${formatCount(currentStats.total)} total entries, ${formatCount(Math.max(0, currentStats.total - currentStats.unused))} used, ${formatCount(currentStats.unused)} unused, ${formatCount(currentStats.reserved)} reserved, ${formatCount(currentStats.stale_reserved)} stale.`
                      : `Manage shared ${KIND_LABELS[kind].toLowerCase()} catalog entries.`}
                  </div>
                  <div className="text-sm text-slate-400">
                    Page {kind === activeKind ? currentPage : 1} / {kind === activeKind ? totalPages : 1}
                  </div>
                </div>

                {kind === activeKind ? (
                  <Card className="border-navy-700 bg-navy-950/50">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <CardTitle className="text-base text-white">Preset Packs</CardTitle>
                          <p className="mt-1 text-sm text-slate-400">
                            Save reusable word-bank mixes for {KIND_LABELS[kind].toLowerCase()} generation.
                          </p>
                        </div>
                        <Badge className="border-sky-500/30 bg-sky-500/10 text-sky-300">
                          {activePresetPacks.length} active
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {presetPacksQuery.isLoading ? (
                        <div className="space-y-3">
                          {Array.from({ length: 3 }).map((_, index) => (
                            <Skeleton className="h-14 w-full" key={index} />
                          ))}
                        </div>
                      ) : null}

                      {presetPacksQuery.isError ? (
                        <div className="rounded-md border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
                          Failed to load preset packs right now.
                        </div>
                      ) : null}

                      {!presetPacksQuery.isLoading && !presetPacksQuery.isError ? (
                        <Table>
                          <TableHeader>
                            <TableRow className="border-navy-700 hover:bg-transparent">
                              <TableHead>Name</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Config</TableHead>
                              <TableHead>Updated</TableHead>
                              <TableHead className="w-[140px]">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {presetPacks.length ? (
                              presetPacks.map((pack) => (
                                <TableRow className="border-navy-800" key={pack.id}>
                                  <TableCell>
                                    <div className="space-y-1">
                                      <div className="text-sm text-white">{pack.name}</div>
                                      <div className="text-xs text-slate-400">
                                        {pack.description || 'No description yet.'}
                                      </div>
                                    </div>
                                  </TableCell>
                                  <TableCell>
                                    <Badge
                                      className={
                                        pack.is_active
                                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                                          : 'border-slate-500/30 bg-slate-500/10 text-slate-300'
                                      }
                                    >
                                      {pack.is_active ? 'Active' : 'Inactive'}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-xs text-slate-400">
                                    {summarizePresetPack(kind, pack.config)}
                                  </TableCell>
                                  <TableCell className="text-slate-400">{formatDate(pack.updated_at)}</TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-2">
                                      <Button size="sm" variant="outline" onClick={() => openEditPresetPackDialog(pack)}>
                                        <Edit3 className="h-4 w-4" />
                                      </Button>
                                      <Button size="sm" variant="outline" onClick={() => setPresetPackDeleteItem(pack)}>
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))
                            ) : (
                              <TableRow className="border-navy-800">
                                <TableCell className="py-10 text-center text-slate-400" colSpan={5}>
                                  No preset packs saved for {KIND_LABELS[kind].toLowerCase()} yet.
                                </TableCell>
                              </TableRow>
                            )}
                          </TableBody>
                        </Table>
                      ) : null}
                    </CardContent>
                  </Card>
                ) : null}

                {kind === activeKind && itemsQuery.isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <Skeleton className="h-14 w-full" key={index} />
                    ))}
                  </div>
                ) : null}

                {kind === activeKind && itemsQuery.isError ? (
                  <div className="rounded-md border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
                    Failed to load {KIND_LABELS[kind].toLowerCase()} right now.
                  </div>
                ) : null}

                {kind === activeKind && !itemsQuery.isLoading && !itemsQuery.isError ? (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow className="border-navy-700 hover:bg-transparent">
                          <TableHead>ID</TableHead>
                          <TableHead>{kind === 'openings' ? 'Opening Pair' : 'Text'}</TableHead>
                          <TableHead>Used</TableHead>
                          <TableHead>Reservation</TableHead>
                          <TableHead>Created</TableHead>
                          <TableHead className="w-[140px]">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {itemsQuery.data?.items.length ? (
                          itemsQuery.data.items.map((item) => (
                            <TableRow className="border-navy-800" key={`${kind}-${item.id}`}>
                              <TableCell className="text-slate-300">{item.id}</TableCell>
                              <TableCell>
                                <div className="space-y-1">
                                  <div className="text-sm text-white">{item.text}</div>
                                  {item.secondary_text ? (
                                    <div className="text-xs text-slate-400">{item.secondary_text}</div>
                                  ) : null}
                                </div>
                              </TableCell>
                              <TableCell className="text-slate-300">{item.used_count}</TableCell>
                              <TableCell>
                                <div className="space-y-1">
                                  <Badge className={getReservationBadgeClass(item.reservation_state)}>
                                    {item.reservation_state === 'stale'
                                      ? 'Stale'
                                      : item.reservation_state === 'reserved'
                                        ? 'Reserved'
                                        : 'Available'}
                                  </Badge>
                                  {item.reserved_by ? (
                                    <div className="text-xs text-slate-400">
                                      {item.reserved_by}
                                      {item.reserved_at ? ` • ${formatDateTime(item.reserved_at)}` : ''}
                                    </div>
                                  ) : null}
                                </div>
                              </TableCell>
                              <TableCell className="text-slate-400">{formatDate(item.created_at)}</TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <Button size="sm" variant="outline" onClick={() => openEditDialog(item)}>
                                    <Edit3 className="h-4 w-4" />
                                  </Button>
                                  <Button size="sm" variant="outline" onClick={() => setDeleteItem(item)}>
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow className="border-navy-800">
                            <TableCell className="py-10 text-center text-slate-400" colSpan={6}>
                              No {KIND_LABELS[kind].toLowerCase()} found yet.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>

                    <div className="flex items-center justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={currentOffset === 0 || itemsQuery.isFetching}
                        onClick={() =>
                          setOffsetByKind((current) => ({
                            ...current,
                            [activeKind]: Math.max(0, current[activeKind] - PAGE_SIZE),
                          }))
                        }
                      >
                        Prev
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={itemsQuery.isFetching || currentOffset + PAGE_SIZE >= (itemsQuery.data?.total ?? 0)}
                        onClick={() =>
                          setOffsetByKind((current) => ({
                            ...current,
                            [activeKind]: current[activeKind] + PAGE_SIZE,
                          }))
                        }
                      >
                        Next
                      </Button>
                    </div>
                  </>
                ) : null}
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate {KIND_LABELS[activeKind]}</DialogTitle>
            <DialogDescription>
              Generate entries from the default mixer or one of the active preset packs for this pool.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="generate-count">Count</Label>
              <Input
                id="generate-count"
                min={1}
                max={200000}
                type="number"
                value={generateCount}
                onChange={(event) => setGenerateCount(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Preset Source</Label>
              <Select value={generatePresetPackId} onValueChange={setGeneratePresetPackId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a preset source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DEFAULT_PRESET_PACK_VALUE}>Default Mixer</SelectItem>
                  {activePresetPacks.map((pack) => (
                    <SelectItem key={pack.id} value={pack.id}>
                      {pack.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-400">
                Preset packs guide candidate mixing. Final uniqueness still depends on normalized insert checks.
              </p>
            </div>
            {lastGenerateResult ? (
              <div className="rounded-md border border-sky-500/20 bg-sky-500/5 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-sky-100">Latest Generate Result</div>
                    <div className="text-xs text-slate-300">
                      {lastGenerateSource} for {KIND_LABELS[activeKind].toLowerCase()}
                    </div>
                  </div>
                  <Badge className="border-sky-500/30 bg-sky-500/10 text-sky-200">
                    Requested {lastGenerateResult.requested.toLocaleString()}
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                  <div className="rounded-md border border-navy-700 bg-navy-950/40 px-3 py-2">
                    <div className="text-xs text-slate-400">Attempted</div>
                    <div className="mt-1 font-semibold text-white">
                      {lastGenerateResult.attempted.toLocaleString()}
                    </div>
                  </div>
                  <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
                    <div className="text-xs text-slate-400">Inserted</div>
                    <div className="mt-1 font-semibold text-emerald-300">
                      {lastGenerateResult.inserted.toLocaleString()}
                    </div>
                  </div>
                  <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2">
                    <div className="text-xs text-slate-400">Duplicates Skipped</div>
                    <div className="mt-1 font-semibold text-amber-300">
                      {lastGenerateResult.duplicates_skipped.toLocaleString()}
                    </div>
                  </div>
                  <div className="rounded-md border border-navy-700 bg-navy-950/40 px-3 py-2">
                    <div className="text-xs text-slate-400">Completion</div>
                    <div className="mt-1 font-semibold text-white">
                      {Math.round(
                        (lastGenerateResult.inserted / Math.max(1, lastGenerateResult.requested)) * 100,
                      )}
                      %
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-slate-300">
                  {lastGenerateResult.duplicates_skipped > 0
                    ? 'Duplicate pressure is rising for this source. Try another preset pack or expand the banks if you need more fresh rows.'
                    : 'This run filled the requested rows without duplicate skips.'}
                </p>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenerateOpen(false)}>
              Cancel
            </Button>
            <Button disabled={generateMutation.isPending} onClick={() => void handleGenerate()}>
              {generateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Import {KIND_LABELS[activeKind]}</DialogTitle>
            <DialogDescription>{importHelper}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="import-text">Entries</Label>
            <Textarea
              id="import-text"
              className="min-h-[260px]"
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)}>
              Cancel
            </Button>
            <Button disabled={importMutation.isPending || !importText.trim()} onClick={() => void handleImport()}>
              {importMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={presetPackOpen}
        onOpenChange={(open) => {
          setPresetPackOpen(open);
          if (!open) {
            setPresetPackEditId(null);
            setPresetPackForm(createEmptyPresetPackForm());
          }
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <DialogTitle>{presetPackEditId ? 'Edit Preset Pack' : 'Create Preset Pack'}</DialogTitle>
                <DialogDescription>
                  Save a reusable vocabulary mix for {KIND_LABELS[activeKind].toLowerCase()} generation.
                </DialogDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                className="gap-2 self-start"
                onClick={() => void handleGeneratePresetBanks()}
                disabled={presetPackGenerateSavePending}
              >
                {generatePresetBanksMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Generate 10,000
              </Button>
            </div>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-md border border-sky-500/20 bg-sky-500/5 px-4 py-3 text-xs text-sky-100">
              One click fills every visible field with {MASSIVE_PRESET_TARGET_COUNT.toLocaleString()} built-in starter entries.
            </div>
            <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="preset-name">Name</Label>
              <Input
                id="preset-name"
                value={presetPackForm.name}
                onChange={(event) => setPresetField('name', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={presetPackForm.isActive ? 'active' : 'inactive'}
                onValueChange={(value) => setPresetField('isActive', value === 'active')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="preset-description">Description</Label>
              <Textarea
                id="preset-description"
                value={presetPackForm.description}
                onChange={(event) => setPresetField('description', event.target.value)}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Vocabulary Mode</Label>
              <Select
                value={presetPackForm.includeDefaults ? 'merge' : 'replace'}
                onValueChange={(value) => setPresetField('includeDefaults', value === 'merge')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="merge">Merge With Defaults</SelectItem>
                  <SelectItem value="replace">Custom Banks Only</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-400">
                Merge keeps the built-in generator vocabulary and appends your custom lines. Custom only uses your banks whenever provided.
              </p>
            </div>
            {PRESET_FIELDS[activeKind].map((field) => (
              <div className="space-y-2" key={field.key}>
                <Label htmlFor={`preset-${field.key}`}>{field.label}</Label>
                <Textarea
                  id={`preset-${field.key}`}
                  className="min-h-[120px]"
                  placeholder={`One ${field.label.toLowerCase()} entry per line`}
                  value={presetPackForm[field.key]}
                  onChange={(event) => setPresetField(field.key, event.target.value)}
                />
                <p className="text-xs text-slate-400">{field.helper}</p>
              </div>
            ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPresetPackOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="outline"
              className="gap-2"
              disabled={presetPackGenerateSavePending}
              onClick={() => void handleGenerateAndSavePresetPack()}
            >
              {presetPackGenerateSavePending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate And Save Massive Pack
            </Button>
            <Button
              variant="outline"
              className="gap-2"
              disabled={presetPackGenerateSavePending}
              onClick={() => void handleGenerateSaveAndOpenPresetPack()}
            >
              {presetPackGenerateSavePending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCcw className="h-4 w-4" />
              )}
              Generate, Save, And Open
            </Button>
            <Button
              disabled={presetPackSavePending}
              onClick={() => void handleSavePresetPack()}
            >
              {presetPackSavePending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Save Preset Pack
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editItem !== null} onOpenChange={(open) => { if (!open) setEditItem(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit {KIND_LABELS[activeKind].slice(0, -1)}</DialogTitle>
            <DialogDescription>Update the stored pool content directly.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-text">{activeKind === 'openings' ? 'Line 1' : 'Text'}</Label>
              <Input id="edit-text" value={editText} onChange={(event) => setEditText(event.target.value)} />
            </div>
            {activeKind === 'openings' ? (
              <div className="space-y-2">
                <Label htmlFor="edit-secondary">Line 2</Label>
                <Input
                  id="edit-secondary"
                  value={editSecondaryText}
                  onChange={(event) => setEditSecondaryText(event.target.value)}
                />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditItem(null)}>
              Cancel
            </Button>
            <Button disabled={updateMutation.isPending} onClick={() => void handleUpdate()}>
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteItem !== null} onOpenChange={(open) => { if (!open) setDeleteItem(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete pool item</DialogTitle>
            <DialogDescription>
              Remove this entry from the shared {KIND_LABELS[activeKind].toLowerCase()} pool.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteItem(null)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={deleteMutation.isPending} onClick={() => void handleDelete()}>
              {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={presetPackDeleteItem !== null} onOpenChange={(open) => { if (!open) setPresetPackDeleteItem(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete preset pack</DialogTitle>
            <DialogDescription>
              Remove <span className="font-medium text-white">{presetPackDeleteItem?.name ?? 'this pack'}</span> from the{' '}
              {KIND_LABELS[activeKind].toLowerCase()} preset library.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPresetPackDeleteItem(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deletePresetMutation.isPending}
              onClick={() => void handleDeletePresetPack()}
            >
              {deletePresetMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={clearOpen} onOpenChange={setClearOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear {KIND_LABELS[activeKind]}</DialogTitle>
            <DialogDescription>
              This removes all entries from the selected pool and resets its IDs. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={clearMutation.isPending} onClick={() => void handleClear()}>
              {clearMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Clear Pool
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
