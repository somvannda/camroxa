'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Download, FolderOpen, LoaderCircle, Mic2, Music2, Pause, Pencil, Play, Plus, Shuffle, Sparkles } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { usePlayer } from '@/components/player-provider';
import { UpgradeModal } from '@/components/upgrade-modal';
import { AddToPlaylistButton } from '@/components/add-to-playlist-button';
import {
  MusicCharCount,
  MusicCollapsibleSection,
  MusicFloatingActionBar,
  MusicHorizontalTickSlider,
  MusicModelSelect,
  MusicOptionCard,
  MusicPillTabs,
  MusicSectionError,
  MusicSelect,
  MusicSegmentedControl,
  WEB_MUSIC_LYRICS_MAX,
  WEB_MUSIC_STYLE_MAX,
} from '@/components/music-form-ui';

function clampText(value: string, max: number): string {
  return value.length <= max ? value : value.slice(0, max);
}
import {
  createWebMusicWorkspace,
  updateWebMusicWorkspace,
  downloadWebMusicClip,
  downloadWebMusicClipWav,
  downloadWebMusicTimedLyrics,
  generateWebMusic,
  generateWebMusicDraft,
  generateWebMusicStyles,
  getWebMusicGeneration,
  listWebMusicGenerations,
  listWebMusicWorkspaces,
  fetchWebMusicQuota,
  type WebMusicClip,
  type WebMusicGeneration,
  type WebMusicQuota,
  type WebMusicWorkspace,
} from '@/lib/web-music-api';
import { fetchCreditBalance, type CreditBalance } from '@/lib/subscription-api';
import { formatDuration, type StreamTrack } from '@/lib/streaming-api';

const STYLE_CHIPS = [
  'pop',
  'rock',
  'r&b',
  'electronic',
  'hip hop',
  'jazz',
  'lo-fi',
  'cinematic',
  'afrobeats',
  'indie',
];

function isOpenGeneration(item: WebMusicGeneration): boolean {
  const status = (item.status || '').toLowerCase();
  if (status === 'failed' || status === 'cancelled') return false;
  if (status === 'success') {
    if (item.clips.some((clip) => !clip.ready)) return true;
    return item.clips.some((clip) => clip.ready && !clip.image_url);
  }
  return true;
}

function clipToTrack(generation: WebMusicGeneration, clip: WebMusicGeneration['clips'][number]): StreamTrack | null {
  if (!clip?.ready) return null;
  return {
    id: `${generation.id}:${clip.variant}`,
    title: clip.label || generation.title,
    artist_name: 'You',
    genre: generation.style,
    lyrics: generation.lyrics,
    play_url: clip.audio_url,
    cover_url: clip.image_url ?? null,
    duration_seconds: clip.duration_seconds ?? null,
  };
}

const DEFAULT_SLIDER_VALUE = 0.5;

function formatVocalGender(value: string | null | undefined): string {
  if (value === 'm') return 'Male';
  if (value === 'f') return 'Female';
  if (value === 'both') return 'Both';
  return 'Not set';
}

function formatSliderSetting(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

function formatModelVersionTag(model: string | null | undefined): string {
  const key = String(model || 'V5_5').trim().toUpperCase().replace('.', '_');
  return key === 'V5_5' ? 'v5.5' : 'v5';
}

function ClipReadyLabel({
  clip,
  generating,
  waitingLabel = 'Waiting',
  className = 'text-xs text-slate-500',
}: {
  clip: WebMusicClip;
  generating?: boolean;
  waitingLabel?: string;
  className?: string;
}) {
  const [probedSeconds, setProbedSeconds] = useState<number | null>(null);

  useEffect(() => {
    if (clip.duration_seconds || !clip.ready || !clip.audio_url) {
      return;
    }
    const audio = new Audio();
    audio.preload = 'metadata';
    const onLoaded = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        setProbedSeconds(audio.duration);
      }
    };
    audio.addEventListener('loadedmetadata', onLoaded);
    audio.src = clip.audio_url;
    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded);
      audio.removeAttribute('src');
    };
  }, [clip.audio_url, clip.duration_seconds, clip.ready]);

  const duration = formatDuration(clip.duration_seconds ?? probedSeconds);
  const status = clip.ready ? 'Ready' : waitingLabel;

  return (
    <p className={className}>
      {duration ? `${duration} · ${status}` : status}
      {generating ? ' · Generating…' : ''}
    </p>
  );
}

function ModelVersionTag({ model }: { model: string | null | undefined }) {
  return (
    <span className="shrink-0 bg-gradient-to-r from-violet-400 via-purple-400 to-fuchsia-400 bg-clip-text text-[11px] font-semibold uppercase tracking-wide text-transparent">
      {formatModelVersionTag(model)}
    </span>
  );
}

export default function CreatePageClient() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { playTrack, current, playing, toggle } = usePlayer();
  const [mode, setMode] = useState<'simple' | 'advanced'>('advanced');
  const [lyrics, setLyrics] = useState('');
  const [style, setStyle] = useState('');
  const [title, setTitle] = useState('');
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState<'V5' | 'V5_5'>('V5_5');
  const [featureTab, setFeatureTab] = useState<'audio' | 'voice' | 'inspo' | null>(null);
  const [lyricsMode, setLyricsMode] = useState<'write' | 'prompt' | 'instrumental'>('write');
  const [negativeTags, setNegativeTags] = useState('');
  const [vocalGender, setVocalGender] = useState<'m' | 'f' | 'both' | null>(null);
  const [styleWeight, setStyleWeight] = useState<number | undefined>(undefined);
  const [weirdnessConstraint, setWeirdnessConstraint] = useState<number | undefined>(undefined);
  const [audioWeight, setAudioWeight] = useState<number | undefined>(undefined);
  const [workspaces, setWorkspaces] = useState<WebMusicWorkspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [generatingStyles, setGeneratingStyles] = useState(false);
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [renamingWorkspace, setRenamingWorkspace] = useState(false);
  const [showNewWorkspace, setShowNewWorkspace] = useState(false);
  const [showRenameWorkspace, setShowRenameWorkspace] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [renameWorkspaceName, setRenameWorkspaceName] = useState('');
  const [busy, setBusy] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [lyricsError, setLyricsError] = useState<string | null>(null);
  const [stylesError, setStylesError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [quota, setQuota] = useState<WebMusicQuota | null>(null);
  const [creditBalance, setCreditBalance] = useState<CreditBalance | null>(null);
  const [items, setItems] = useState<WebMusicGeneration[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<{ song: WebMusicGeneration; clip: any } | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login?next=/create');
    }
  }, [loading, user, router]);

  async function refreshList(workspaceId?: string | null) {
    const resolvedWorkspaceId = workspaceId ?? activeWorkspaceId ?? undefined;
    const [nextQuota, list, workspaceList, nextBalance] = await Promise.all([
      fetchWebMusicQuota(),
      listWebMusicGenerations(40, 0, resolvedWorkspaceId),
      listWebMusicWorkspaces().catch(() => ({ items: [] as WebMusicWorkspace[] })),
      fetchCreditBalance().catch(() => null),
    ]);
    setQuota(nextQuota);
    setCreditBalance(nextBalance);
    setItems(list.items);
    setWorkspaces(workspaceList.items);
    if (!activeWorkspaceId && workspaceList.items.length) {
      const defaultWorkspace =
        workspaceList.items.find((workspace) => workspace.is_default) ?? workspaceList.items[0];
      setActiveWorkspaceId(defaultWorkspace.id);
    }
  }

  useEffect(() => {
    if (!user) return;
    void refreshList().catch((err) => {
      setCreateError(err instanceof Error ? err.message : 'Unable to load workspace');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    if (!user || !activeWorkspaceId) return;
    void listWebMusicGenerations(40, 0, activeWorkspaceId)
      .then((list) => setItems(list.items))
      .catch((err) => {
        setCreateError(err instanceof Error ? err.message : 'Unable to load workspace');
      });
  }, [user, activeWorkspaceId]);

  useEffect(() => {
    const pending = items.filter(isOpenGeneration);
    if (!pending.length) return undefined;
    const timer = window.setInterval(() => {
      void Promise.all(pending.map((item) => getWebMusicGeneration(item.id)))
        .then((updated) => {
          setItems((currentItems) =>
            currentItems.map((item) => updated.find((row) => row.id === item.id) ?? item),
          );
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [items]);

  const creditsPerSong = quota?.credits_per_song ?? 10;
  const totalCredits = creditBalance?.total_credits ?? quota?.credits_remaining ?? 0;
  const needsUpgrade = Boolean(
    quota && !quota.is_pro && (quota.requires_upgrade || totalCredits < creditsPerSong),
  );
  const canDownload = Boolean(quota?.can_download ?? quota?.has_subscription ?? quota?.is_pro);

  function promptDownloadUpgrade() {
    setShowUpgradeModal(true);
  }

  async function onDownloadTimedLyrics(
    generation: WebMusicGeneration,
    variant: string,
    format: 'lrc' | 'srt',
  ) {
    if (!canDownload) {
      promptDownloadUpgrade();
      return;
    }
    setCreateError(null);
    try {
      const safeTitle = generation.title.trim() || 'camxora-track';
      await downloadWebMusicTimedLyrics(
        generation.id,
        variant,
        format,
        `${safeTitle}.${format}`,
      );
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Timed lyrics download failed');
    }
  }

  function canDownloadTimedLyrics(generation: WebMusicGeneration, clipReady: boolean): boolean {
    return clipReady && !generation.instrumental;
  }

  const canCreate = useMemo(() => {
    if (busy || needsUpgrade) return false;
    if (mode === 'simple') return prompt.trim().length > 0;
    if (lyricsMode === 'instrumental') return style.trim().length > 0;
    if (lyricsMode === 'prompt') return style.trim().length > 0 && prompt.trim().length > 0;
    return style.trim().length > 0 && lyrics.trim().length > 0;
  }, [busy, needsUpgrade, mode, prompt, style, lyrics, lyricsMode]);

  function buildLyricDraftPrompt(): string {
    return clampText(prompt.trim() || title.trim() || style.trim() || 'Create a song', WEB_MUSIC_LYRICS_MAX);
  }

  async function onAutoGenerateLyrics() {
    if (needsUpgrade) {
      setShowUpgradeModal(true);
      return;
    }

    const draftPrompt = buildLyricDraftPrompt();
    if (!draftPrompt.trim()) {
      setLyricsError('Add a song description, title, or style first.');
      return;
    }

    setGeneratingDraft(true);
    setLyricsError(null);
    try {
      const data = await generateWebMusicDraft(draftPrompt);
      if (data.lyrics) setLyrics(data.lyrics);
      if (data.title) setTitle(data.title);
    } catch (err) {
      setLyricsError(err instanceof Error ? err.message : 'Draft generation failed');
    } finally {
      setGeneratingDraft(false);
    }
  }

  async function onCreate() {
    if (needsUpgrade) {
      setShowUpgradeModal(true);
      return;
    }
    setBusy(true);
    setCreateError(null);
    try {
      const created = await generateWebMusic({
        mode,
        lyrics: lyricsMode === 'instrumental' ? undefined : lyricsMode === 'prompt' ? prompt : lyrics,
        style,
        title,
        prompt: lyricsMode === 'prompt' ? prompt : mode === 'simple' ? prompt : undefined,
        instrumental: lyricsMode === 'instrumental',
        model,
        negative_tags: negativeTags || undefined,
        vocal_gender:
          vocalGender === 'm' || vocalGender === 'f' || vocalGender === 'both' ? vocalGender : undefined,
        style_weight: styleWeight ?? DEFAULT_SLIDER_VALUE,
        weirdness_constraint: weirdnessConstraint ?? DEFAULT_SLIDER_VALUE,
        audio_weight: audioWeight ?? DEFAULT_SLIDER_VALUE,
        workspace_id: activeWorkspaceId || undefined,
      });
      setQuota(created.quota);
      void fetchCreditBalance()
        .then(setCreditBalance)
        .catch(() => undefined);
      const loaded = await getWebMusicGeneration(created.task_id).catch(() => null);
      const pending: WebMusicGeneration = loaded ?? {
        id: created.task_id,
        title: created.title,
        lyrics,
        style: created.style,
        model,
        instrumental: lyricsMode === 'instrumental',
        status: created.status,
        vocal_gender:
          vocalGender === 'm' || vocalGender === 'f' || vocalGender === 'both' ? vocalGender : null,
        style_weight: styleWeight ?? DEFAULT_SLIDER_VALUE,
        weirdness_constraint: weirdnessConstraint ?? DEFAULT_SLIDER_VALUE,
        audio_weight: audioWeight ?? DEFAULT_SLIDER_VALUE,
        negative_tags: negativeTags || null,
        clips: [],
      };
      setItems((currentItems) => [
        pending,
        ...currentItems.filter((item) => item.id !== pending.id),
      ]);
    } catch (err) {
      // Check if it's a quota exceeded error
      if (err instanceof Error && err.message.toLowerCase().includes('insufficient credits')) {
        setShowUpgradeModal(true);
      }
      setCreateError(err instanceof Error ? err.message : 'Create failed');
      void fetchWebMusicQuota()
        .then(setQuota)
        .catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  const activeWorkspace =
    workspaces.find((workspace) => workspace.id === activeWorkspaceId) ??
    workspaces.find((workspace) => workspace.is_default) ??
    workspaces[0] ??
    null;

  const workspaceOptions = useMemo(
    () => workspaces.map((workspace) => ({ value: workspace.id, label: workspace.name })),
    [workspaces],
  );

  async function onCreateWorkspace() {
    const name = newWorkspaceName.trim();
    if (!name) return;
    setCreatingWorkspace(true);
    setCreateError(null);
    try {
      const created = await createWebMusicWorkspace(name);
      setWorkspaces((current) => [...current, created]);
      setActiveWorkspaceId(created.id);
      setNewWorkspaceName('');
      setShowNewWorkspace(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Could not create workspace');
    } finally {
      setCreatingWorkspace(false);
    }
  }

  function openRenameWorkspace() {
    if (!activeWorkspace) return;
    setShowNewWorkspace(false);
    setRenameWorkspaceName(activeWorkspace.name);
    setShowRenameWorkspace(true);
  }

  async function onRenameWorkspace() {
    if (!activeWorkspaceId) return;
    const name = renameWorkspaceName.trim();
    if (!name) return;
    setRenamingWorkspace(true);
    setCreateError(null);
    try {
      const updated = await updateWebMusicWorkspace(activeWorkspaceId, name);
      setWorkspaces((current) =>
        current.map((workspace) => (workspace.id === updated.id ? updated : workspace)),
      );
      setShowRenameWorkspace(false);
      setRenameWorkspaceName('');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Could not rename workspace');
    } finally {
      setRenamingWorkspace(false);
    }
  }

  async function suggestStyles() {
    const hasContext = Boolean(style.trim() || lyrics.trim() || title.trim() || prompt.trim());
    if (!hasContext) {
      setStylesError('Add style tags, a title, lyrics, or a song description first.');
      return;
    }

    setGeneratingStyles(true);
    setStylesError(null);
    try {
      const result = await generateWebMusicStyles({
        style: style.trim(),
        lyrics: lyrics.trim(),
        title: title.trim(),
        description: prompt.trim(),
      });
      setStyle(result.style);
    } catch (err) {
      setStylesError(err instanceof Error ? err.message : 'Style generation failed');
    } finally {
      setGeneratingStyles(false);
    }
  }

  if (loading || !user) {
    return <p className="text-slate-400">Checking your session…</p>;
  }

  return (
    <div className="mx-auto grid max-w-[1600px] gap-6 xl:grid-cols-[minmax(0,28rem)_1fr]">
      <section className="relative flex max-h-[calc(100dvh-var(--music-header-height)-var(--music-player-height)-2.75rem)] flex-col overflow-hidden rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(10,12,24,0.92),rgba(6,8,18,0.96))] shadow-[0_24px_80px_rgba(15,22,58,0.28)] xl:sticky xl:top-0">
        <div className="shrink-0 space-y-2.5 px-3 pb-2 pt-3">
          <div className="flex items-center justify-between gap-2">
            <div className="inline-flex rounded-full border border-white/10 p-0.5 text-xs">
              {(['simple', 'advanced'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={`rounded-full px-2.5 py-1 capitalize ${
                    mode === value ? 'bg-white text-slate-950' : 'text-slate-300'
                  }`}
                >
                  {value}
                </button>
              ))}
            </div>
            <MusicModelSelect value={model} onChange={setModel} />
          </div>

          <MusicPillTabs
            value={featureTab}
            onChange={setFeatureTab}
            allowDeselect
            options={[
              { value: 'audio', label: '+ Audio' },
              { value: 'voice', label: '+ Voice' },
              { value: 'inspo', label: '+ Inspo' },
            ]}
          />
          {featureTab ? (
            <div className="rounded-2xl border border-dashed border-white/10 px-4 py-3 text-xs text-slate-400">
              {featureTab === 'audio'
                ? 'Reference audio uploads are coming soon.'
                : featureTab === 'voice'
                  ? 'Voice reference uploads are coming soon.'
                  : 'Inspiration references are coming soon.'}
            </div>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 pb-28 pt-1 music-scroll [scrollbar-width:thin]">
        {mode === 'simple' ? (
          <label className="block space-y-2 text-sm text-slate-200">
            <span>Song description</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={8}
              placeholder="A rainy-night synthwave song about leaving the city..."
              className="min-h-[180px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none focus:border-violet-400/50"
            />
          </label>
        ) : (
          <div className="space-y-3">
            <MusicCollapsibleSection
              title="Lyrics"
              action={
                lyricsMode === 'write' ? (
                  <button
                    type="button"
                    disabled={generatingDraft || needsUpgrade}
                    onClick={() => void onAutoGenerateLyrics()}
                    className="inline-flex items-center gap-1 rounded-full bg-violet-500/10 px-2.5 py-1 text-[11px] text-violet-300 hover:bg-violet-500/20 hover:text-white disabled:opacity-50"
                  >
                    <Sparkles className="h-3 w-3" />
                    {generatingDraft ? 'Generating...' : 'Auto-generate'}
                  </button>
                ) : null
              }
            >
              {lyricsMode === 'write' ? (
                <div className="space-y-1.5">
                  <textarea
                    value={lyrics}
                    onChange={(event) => setLyrics(clampText(event.target.value, WEB_MUSIC_LYRICS_MAX))}
                    maxLength={WEB_MUSIC_LYRICS_MAX}
                    rows={7}
                    placeholder="Write lyrics, or paste a verse..."
                    className="min-h-[168px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none focus:border-violet-400/50"
                  />
                  <MusicCharCount value={lyrics} max={WEB_MUSIC_LYRICS_MAX} />
                </div>
              ) : lyricsMode === 'prompt' ? (
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={7}
                  placeholder="Describe the song you want the lyrics to express..."
                  className="min-h-[168px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none focus:border-violet-400/50"
                />
              ) : (
                <p className="rounded-[7px] border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
                  Instrumental mode — no vocals. Set your style below and hit Create.
                </p>
              )}
              <MusicSectionError message={lyricsError} />
            </MusicCollapsibleSection>

            <MusicCollapsibleSection
              title="Styles"
              action={
                <button
                  type="button"
                  disabled={generatingStyles}
                  onClick={() => void suggestStyles()}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-[7px] bg-sky-500 text-white shadow-sm transition hover:bg-sky-400 disabled:opacity-50"
                  title="Enhance styles for Suno"
                >
                  {generatingStyles ? (
                    <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                </button>
              }
            >
              <div className="space-y-1.5">
                <textarea
                  value={style}
                  onChange={(event) => setStyle(clampText(event.target.value, WEB_MUSIC_STYLE_MAX))}
                  maxLength={WEB_MUSIC_STYLE_MAX}
                  rows={6}
                  placeholder="urbano, electric guitar, upbeat rock, 128 BPM, eurodance"
                  className="min-h-[148px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none focus:border-violet-400/50"
                />
                <MusicCharCount value={style} max={WEB_MUSIC_STYLE_MAX} />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {STYLE_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() =>
                      setStyle((currentStyle) =>
                        clampText(
                          currentStyle.toLowerCase().includes(chip)
                            ? currentStyle
                            : [currentStyle.trim(), chip].filter(Boolean).join(', '),
                          WEB_MUSIC_STYLE_MAX,
                        )
                      )
                    }
                    className="rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-300 transition hover:border-violet-400/30 hover:bg-violet-500/10 hover:text-white"
                  >
                    {chip}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setStyle(clampText(STYLE_CHIPS[Math.floor(Math.random() * STYLE_CHIPS.length)], WEB_MUSIC_STYLE_MAX))
                  }
                  className="inline-flex items-center gap-1 rounded-full border border-violet-400/40 px-3 py-1 text-[11px] text-violet-200"
                >
                  <Shuffle className="h-3 w-3" />
                  Shuffle
                </button>
              </div>
              <label className="block space-y-2 text-sm text-slate-200">
                <span>Negative tags (optional)</span>
                <input
                  value={negativeTags}
                  onChange={(e) => setNegativeTags(e.target.value)}
                  placeholder="choir, backing vocals, falsetto"
                  className="h-11 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none focus:border-violet-400/50"
                />
              </label>
              <MusicSectionError message={stylesError} />
            </MusicCollapsibleSection>

            <MusicCollapsibleSection title="More Options" defaultOpen={false}>
              <div className="space-y-2">
                <MusicOptionCard
                  label="Lyrics"
                  trailing={
                    <MusicSegmentedControl
                      value={lyricsMode}
                      onChange={setLyricsMode}
                      options={[
                        { value: 'write', label: 'Write' },
                        { value: 'prompt', label: 'Prompt' },
                        { value: 'instrumental', label: 'Instrumental' },
                      ]}
                    />
                  }
                />

                <MusicOptionCard
                  label="Vocal Gender"
                  hint="Preferred vocal tone when lyrics are used"
                  trailing={
                    <MusicPillTabs
                      value={vocalGender}
                      onChange={setVocalGender}
                      allowDeselect
                      options={[
                        { value: 'm', label: 'Male' },
                        { value: 'f', label: 'Female' },
                        { value: 'both', label: 'Both' },
                      ]}
                    />
                  }
                />

                <MusicHorizontalTickSlider
                  label="Style Influence"
                  hint="How closely the output follows your style tags"
                  value={styleWeight ?? 0.5}
                  onChange={setStyleWeight}
                />

                <MusicHorizontalTickSlider
                  label="Weirdness"
                  hint="Higher values produce more experimental results"
                  value={weirdnessConstraint ?? 0.5}
                  onChange={setWeirdnessConstraint}
                />

                <MusicHorizontalTickSlider
                  label="Audio Weight"
                  hint="How strongly the output adheres to reference audio consistency"
                  value={audioWeight ?? 0.5}
                  onChange={setAudioWeight}
                />
              </div>
            </MusicCollapsibleSection>

            <div className="overflow-hidden rounded-[7px] border border-white/10 bg-[rgba(12,14,28,0.72)]">
              <label className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
                <Music2 className="h-4 w-4 text-violet-200" />
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Song Title (Optional)"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
                />
              </label>
              <div className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-slate-300">
                <span className="inline-flex items-center gap-2">
                  <FolderOpen className="h-4 w-4 text-slate-500" />
                  Save to...
                </span>
                <MusicSelect
                  value={activeWorkspaceId ?? ''}
                  onValueChange={setActiveWorkspaceId}
                  options={workspaceOptions}
                  placeholder="Select workspace"
                  className="h-9 max-w-[11rem] text-xs"
                />
              </div>
            </div>
          </div>
        )}
        </div>

        <MusicFloatingActionBar>
          {needsUpgrade ? (
            <button
              type="button"
              onClick={() => setShowUpgradeModal(true)}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-semibold text-white shadow-[0_18px_44px_rgba(118,77,255,0.38)]"
            >
              <Sparkles className="h-4 w-4" />
              Upgrade to Pro
            </button>
          ) : (
            <button
              type="button"
              disabled={!canCreate}
              onClick={() => void onCreate()}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-semibold text-white shadow-[0_18px_44px_rgba(118,77,255,0.38)] disabled:opacity-50"
            >
              <Music2 className="h-4 w-4" />
              {busy ? 'Creating…' : 'Create'}
            </button>
          )}
          {needsUpgrade ? (
            <p className="mt-2 text-center text-xs text-fuchsia-100/80">
              You have used today&apos;s free credits. Upgrade to Pro for more.
            </p>
          ) : null}
          {createError ? <p className="mt-2 text-center text-xs text-rose-300">{createError}</p> : null}
        </MusicFloatingActionBar>
      </section>

      <section className="min-w-0 flex gap-4 overflow-hidden music-scroll">
        {/* Main List */}
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="mb-4">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Workspaces</p>
              <div className="mt-1 flex items-center gap-2">
                {showRenameWorkspace ? (
                  <input
                    value={renameWorkspaceName}
                    onChange={(event) => setRenameWorkspaceName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') void onRenameWorkspace();
                      if (event.key === 'Escape') setShowRenameWorkspace(false);
                    }}
                    placeholder="Workspace name"
                    autoFocus
                    className="h-10 min-w-0 flex-1 rounded-[7px] border border-violet-400/40 bg-white/[0.04] px-3 text-sm font-semibold text-white outline-none focus:border-violet-400/60"
                  />
                ) : showNewWorkspace ? (
                  <input
                    value={newWorkspaceName}
                    onChange={(event) => setNewWorkspaceName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') void onCreateWorkspace();
                      if (event.key === 'Escape') setShowNewWorkspace(false);
                    }}
                    placeholder="Workspace name"
                    autoFocus
                    className="h-10 min-w-0 flex-1 rounded-[7px] border border-violet-400/40 bg-white/[0.04] px-3 text-sm font-semibold text-white outline-none focus:border-violet-400/60"
                  />
                ) : (
                  <MusicSelect
                    value={activeWorkspaceId ?? ''}
                    onValueChange={setActiveWorkspaceId}
                    options={workspaceOptions}
                    placeholder="Select workspace"
                    className="min-w-0 flex-1 font-semibold"
                  />
                )}
                {showRenameWorkspace ? (
                  <>
                    <button
                      type="button"
                      disabled={renamingWorkspace || !renameWorkspaceName.trim()}
                      onClick={() => void onRenameWorkspace()}
                      className="inline-flex h-10 shrink-0 items-center rounded-[7px] border border-violet-400/30 bg-violet-500/10 px-3 text-xs font-medium text-violet-200 disabled:opacity-50"
                    >
                      {renamingWorkspace ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      type="button"
                      disabled={renamingWorkspace}
                      onClick={() => setShowRenameWorkspace(false)}
                      className="inline-flex h-10 shrink-0 items-center rounded-[7px] border border-white/10 px-3 text-xs font-medium text-slate-300 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </>
                ) : showNewWorkspace ? (
                  <>
                    <button
                      type="button"
                      disabled={creatingWorkspace || !newWorkspaceName.trim()}
                      onClick={() => void onCreateWorkspace()}
                      className="inline-flex h-10 shrink-0 items-center rounded-[7px] border border-violet-400/30 bg-violet-500/10 px-3 text-xs font-medium text-violet-200 disabled:opacity-50"
                    >
                      {creatingWorkspace ? 'Creating…' : 'Create'}
                    </button>
                    <button
                      type="button"
                      disabled={creatingWorkspace}
                      onClick={() => setShowNewWorkspace(false)}
                      className="inline-flex h-10 shrink-0 items-center rounded-[7px] border border-white/10 px-3 text-xs font-medium text-slate-300 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    disabled={!activeWorkspace}
                    onClick={openRenameWorkspace}
                    title="Rename workspace"
                    aria-label="Rename workspace"
                    className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[7px] border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] disabled:opacity-40"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  type="button"
                  disabled={showRenameWorkspace || showNewWorkspace}
                  onClick={() => {
                    setShowRenameWorkspace(false);
                    setShowNewWorkspace((value) => !value);
                    setNewWorkspaceName('');
                  }}
                  className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-[7px] border border-violet-400/30 bg-violet-500/10 px-3 text-xs font-medium text-violet-200 transition hover:bg-violet-500/15 disabled:opacity-40"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New workspace
                </button>
              </div>
            </div>
          </div>
          
          {items.length ? (
            <div className="space-y-2 min-w-0 overflow-hidden">
              {items.map((generation) => {
                if ((generation.status || '').toUpperCase() === 'FAILED') {
                  return (
                    <div
                      key={generation.id}
                      className="rounded-xl border border-rose-400/20 bg-rose-500/5 p-3 min-w-0"
                    >
                      <div className="flex min-w-0 items-center gap-1.5">
                        <p className="truncate font-medium text-white">{generation.title}</p>
                        <ModelVersionTag model={generation.model} />
                      </div>
                      <p className="mt-1 text-sm text-rose-300">
                        {generation.error_message || 'Generation failed.'}
                      </p>
                    </div>
                  );
                }

                const clips = generation.clips.length
                  ? generation.clips
                  : [
                      { variant: 'ok', label: generation.title, audio_url: '', download_url: '', ready: false },
                      { variant: 'alt', label: generation.title, audio_url: '', download_url: '', ready: false },
                    ];

                return clips.map((clip) => {
                  const track = clipToTrack(generation, clip);
                  const isCurrent = current?.id === `${generation.id}:${clip.variant}`;
                  const isSelected =
                    selectedVersion?.song.id === generation.id &&
                    selectedVersion?.clip.variant === clip.variant;

                  return (
                    <div
                      key={`${generation.id}:${clip.variant}`}
                      className={`flex min-w-0 items-center gap-2 rounded-xl border transition-colors p-2.5 ${
                        isSelected
                          ? 'border-violet-400/50 bg-violet-500/10'
                          : 'border-white/8 bg-white/[0.03] hover:bg-white/[0.05]'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedVersion({ song: generation, clip })}
                        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                      >
                        <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-violet-500/20 text-fuchsia-100">
                          {clip.image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={clip.image_url}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          ) : clip.variant === 'ok' ? (
                            <Music2 className="h-4 w-4" />
                          ) : (
                            <Mic2 className="h-4 w-4" />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex min-w-0 items-center gap-1.5">
                            <p className="truncate text-sm font-medium text-white">
                              {clip.label || generation.title}
                            </p>
                            <ModelVersionTag model={generation.model} />
                          </div>
                          <ClipReadyLabel
                            clip={clip}
                            generating={isOpenGeneration(generation)}
                          />
                        </div>
                      </button>
                      <div className="flex flex-shrink-0 items-center gap-1">
                        <button
                          type="button"
                          disabled={!track}
                          onClick={() => {
                            if (isCurrent) {
                              toggle();
                              return;
                            }
                            if (track) void playTrack(track);
                          }}
                          className="inline-flex h-7 w-7 items-center justify-center rounded-full text-white disabled:text-slate-600 hover:bg-white/10"
                        >
                          {isCurrent && playing ? (
                            <Pause className="h-3.5 w-3.5" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                        </button>
                        <button
                          type="button"
                          disabled={!clip.ready}
                          onClick={() => {
                            if (!canDownload) {
                              promptDownloadUpgrade();
                              return;
                            }
                            void downloadWebMusicClip(
                              generation.id,
                              clip.variant,
                              `${generation.title}.mp3`,
                            );
                          }}
                          className="inline-flex h-7 items-center justify-center gap-1 rounded-md bg-white/5 px-2 text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
                          title={canDownload ? 'Download MP3' : 'Upgrade to download MP3'}
                        >
                          <Download className="h-3 w-3" />
                          <span className="text-xs">MP3</span>
                        </button>
                        <AddToPlaylistButton
                          taskId={generation.id}
                          variant={clip.variant}
                          disabled={!clip.ready}
                          compact
                        />
                        <button
                          type="button"
                          disabled={!canDownloadTimedLyrics(generation, clip.ready)}
                          onClick={() => void onDownloadTimedLyrics(generation, clip.variant, 'lrc')}
                          className="inline-flex h-7 items-center justify-center rounded-md bg-white/5 px-2 text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
                          title={
                            !canDownload
                              ? 'Upgrade to download LRC'
                              : generation.instrumental
                                ? 'Timed lyrics not available for instrumentals'
                                : 'Download LRC (karaoke timestamps)'
                          }
                        >
                          <span className="text-xs">LRC</span>
                        </button>
                        <button
                          type="button"
                          disabled={!canDownloadTimedLyrics(generation, clip.ready)}
                          onClick={() => void onDownloadTimedLyrics(generation, clip.variant, 'srt')}
                          className="inline-flex h-7 items-center justify-center rounded-md bg-white/5 px-2 text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
                          title={
                            !canDownload
                              ? 'Upgrade to download SRT'
                              : generation.instrumental
                                ? 'Timed lyrics not available for instrumentals'
                                : 'Download SRT subtitles for video editors'
                          }
                        >
                          <span className="text-xs">SRT</span>
                        </button>
                        <button
                          type="button"
                          disabled={!clip.ready}
                          onClick={() => {
                            if (!canDownload) {
                              promptDownloadUpgrade();
                              return;
                            }
                            void downloadWebMusicClipWav(
                              generation.id,
                              clip.variant,
                              `${generation.title}.wav`,
                            );
                          }}
                          className="inline-flex h-7 items-center justify-center gap-1 rounded-md bg-white/5 px-2 text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
                          title={canDownload ? 'Download WAV (High quality)' : 'Upgrade to download WAV'}
                        >
                          <Download className="h-3 w-3" />
                          <span className="text-xs">WAV</span>
                        </button>
                      </div>
                    </div>
                  );
                });
              })}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center">
              <Sparkles className="mx-auto h-6 w-6 text-fuchsia-200" />
              <p className="mt-3 text-white">Your songs will land here</p>
              <p className="mt-1 text-sm text-slate-400">
                Write lyrics and a style, then hit Create. Two versions appear when Suno finishes.
              </p>
            </div>
          )}
        </div>

        {/* Right Sidebar - Version Details */}
        {selectedVersion && (
          <div className="w-80 max-w-full flex-shrink-0 rounded-2xl border border-white/8 bg-white/[0.03] p-5 space-y-4 overflow-hidden">
            <div className="flex items-start gap-3 min-w-0">
              <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-violet-500/20 text-fuchsia-100">
                {selectedVersion.clip.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={selectedVersion.clip.image_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Music2 className="h-6 w-6" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold text-white">
                  {selectedVersion.clip.label || selectedVersion.song.title}
                </h2>
                <ClipReadyLabel
                  clip={selectedVersion.clip}
                  waitingLabel="Processing"
                  className="text-sm text-slate-400"
                />
              </div>
            </div>

            {/* Playback & Download */}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Actions</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!selectedVersion.clip.ready}
                  onClick={() => {
                    const track = clipToTrack(selectedVersion.song, selectedVersion.clip);
                    const isCurrent = current?.id === `${selectedVersion.song.id}:${selectedVersion.clip.variant}`;
                    if (isCurrent) {
                      toggle();
                      return;
                    }
                    if (track) void playTrack(track);
                  }}
                  className="flex-1 inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-violet-500/20 text-white hover:bg-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {current?.id === `${selectedVersion.song.id}:${selectedVersion.clip.variant}` && playing ? (
                    <Pause className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </button>
                <button
                  type="button"
                  disabled={!selectedVersion.clip.ready}
                  onClick={() => {
                    if (!canDownload) {
                      promptDownloadUpgrade();
                      return;
                    }
                    void downloadWebMusicClip(
                      selectedVersion.song.id,
                      selectedVersion.clip.variant,
                      `${selectedVersion.song.title}-${selectedVersion.clip.variant}.mp3`,
                    );
                  }}
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 text-white hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={canDownload ? 'Download MP3' : 'Upgrade to download MP3'}
                >
                  <Download className="h-3.5 w-3.5" />
                  <span className="text-xs">MP3</span>
                </button>
                <button
                  type="button"
                  disabled={!selectedVersion.clip.ready}
                  onClick={() => {
                    if (!canDownload) {
                      promptDownloadUpgrade();
                      return;
                    }
                    void downloadWebMusicClipWav(
                      selectedVersion.song.id,
                      selectedVersion.clip.variant,
                      `${selectedVersion.song.title}-${selectedVersion.clip.variant}.wav`,
                    );
                  }}
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 text-white hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={canDownload ? 'Download WAV (High quality)' : 'Upgrade to download WAV'}
                >
                  <Download className="h-3.5 w-3.5" />
                  <span className="text-xs">WAV</span>
                </button>
                <AddToPlaylistButton
                  taskId={selectedVersion.song.id}
                  variant={selectedVersion.clip.variant}
                  disabled={!selectedVersion.clip.ready}
                />
                <button
                  type="button"
                  disabled={!canDownloadTimedLyrics(selectedVersion.song, selectedVersion.clip.ready)}
                  onClick={() =>
                    void onDownloadTimedLyrics(
                      selectedVersion.song,
                      selectedVersion.clip.variant,
                      'lrc',
                    )
                  }
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 text-white hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={
                    !canDownload
                      ? 'Upgrade to download LRC'
                      : 'Download LRC (karaoke timestamps)'
                  }
                >
                  <span className="text-xs">LRC</span>
                </button>
                <button
                  type="button"
                  disabled={!canDownloadTimedLyrics(selectedVersion.song, selectedVersion.clip.ready)}
                  onClick={() =>
                    void onDownloadTimedLyrics(
                      selectedVersion.song,
                      selectedVersion.clip.variant,
                      'srt',
                    )
                  }
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 text-white hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={!canDownload ? 'Upgrade to download SRT' : 'Download SRT subtitles'}
                >
                  <span className="text-xs">SRT</span>
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Settings</p>
              <div className="rounded-lg border border-white/8 bg-black/20 p-3 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Model</span>
                  <span className="text-white">{selectedVersion.song.model === 'V5_5' ? 'V5.5' : selectedVersion.song.model || 'V5'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Type</span>
                  <span className="text-white">{selectedVersion.song.instrumental ? 'Instrumental' : 'With Vocals'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Vocal Gender</span>
                  <span className="text-white">{formatVocalGender(selectedVersion.song.vocal_gender)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Style Influence</span>
                  <span className="text-white">{formatSliderSetting(selectedVersion.song.style_weight)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Weirdness</span>
                  <span className="text-white">{formatSliderSetting(selectedVersion.song.weirdness_constraint)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Audio Weight</span>
                  <span className="text-white">{formatSliderSetting(selectedVersion.song.audio_weight)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Status</span>
                  <span className="text-white">{selectedVersion.clip.ready ? 'Ready' : 'Processing'}</span>
                </div>
              </div>
            </div>

            {/* Negative Tags */}
            {selectedVersion.song.negative_tags && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Negative Tags</p>
                <div className="rounded-lg border border-white/8 bg-black/20 p-3">
                  <p className="text-sm text-slate-300">{selectedVersion.song.negative_tags}</p>
                </div>
              </div>
            )}

            {/* Style/Prompt */}
            {selectedVersion.song.style && (
              <div className="space-y-2 min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Style</p>
                <div className="rounded-lg border border-white/8 bg-black/20 p-3 min-w-0">
                  <p className="break-words text-sm text-slate-300 leading-relaxed">{selectedVersion.song.style}</p>
                </div>
              </div>
            )}

            {/* Lyrics */}
            {selectedVersion.song.lyrics && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Lyrics</p>
                <div className="rounded-lg border border-white/8 bg-black/20 p-3 max-h-64 overflow-y-auto">
                  <pre className="whitespace-pre-wrap text-sm text-slate-300 font-sans leading-relaxed">
                    {selectedVersion.song.lyrics}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
      <UpgradeModal isOpen={showUpgradeModal} onClose={() => setShowUpgradeModal(false)} />
    </div>
  );
}
