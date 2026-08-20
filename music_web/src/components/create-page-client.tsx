'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, FolderOpen, LoaderCircle, Mic2, Music2, Pause, Pencil, Play, Plus, Shuffle, Sparkles, X } from 'lucide-react';

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
  updateWebMusicGenerationTitle,
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

function clipWaitingLabel(generation: WebMusicGeneration): string {
  return (generation.status || '').toUpperCase() === 'SUCCESS' ? 'Finishing' : 'Waiting';
}

function isGeneratingStatus(generation: WebMusicGeneration): boolean {
  const status = (generation.status || '').toLowerCase();
  return status === 'pending' || status === 'running';
}

function isOpenGeneration(item: WebMusicGeneration): boolean {
  const status = (item.status || '').toLowerCase();
  if (status === 'failed' || status === 'cancelled') return false;
  if (status === 'success') {
    if (item.clips.some((clip) => !clip.ready)) return true;
    return item.clips.some((clip) => clip.ready && !clip.image_url);
  }
  return true;
}

function clipTrackId(generation: WebMusicGeneration, clip: WebMusicClip): string {
  return `${generation.id}:${clip.variant}`;
}

function clipDisplayTitle(generation: WebMusicGeneration, clip: WebMusicClip): string {
  const fromClip = String(clip.title || '').trim();
  if (fromClip) return fromClip;
  const fromLabel = String(clip.label || '')
    .replace(/\s·\sVersion\s[12]\s*$/i, '')
    .trim();
  return fromLabel || generation.title || 'Untitled';
}

function generationClips(generation: WebMusicGeneration): WebMusicClip[] {
  if (generation.clips.length) return generation.clips;
  return [
    { variant: 'ok', label: generation.title, audio_url: '', download_url: '', ready: false },
    { variant: 'alt', label: generation.title, audio_url: '', download_url: '', ready: false },
  ];
}

function clipToTrack(generation: WebMusicGeneration, clip: WebMusicClip): StreamTrack | null {
  if (!clip?.ready) return null;
  return {
    id: clipTrackId(generation, clip),
    title: clipDisplayTitle(generation, clip),
    artist_name: 'You',
    genre: generation.style,
    lyrics: generation.lyrics,
    play_url: clip.audio_url,
    package_status: clip.package_status ?? 'none',
    subject_type: 'suno_task',
    cover_url: clip.image_url ?? null,
    duration_seconds: clip.duration_seconds ?? null,
  };
}

function findVersionForTrackId(
  items: WebMusicGeneration[],
  trackId: string | null | undefined,
): { song: WebMusicGeneration; clip: WebMusicClip } | null {
  if (!trackId) return null;
  for (const generation of items) {
    for (const clip of generationClips(generation)) {
      if (clipTrackId(generation, clip) === trackId) {
        return { song: generation, clip };
      }
    }
  }
  return null;
}

function workspaceReadyTracks(items: WebMusicGeneration[]): StreamTrack[] {
  const tracks: StreamTrack[] = [];
  for (const generation of items) {
    for (const clip of generationClips(generation)) {
      const track = clipToTrack(generation, clip);
      if (track) tracks.push(track);
    }
  }
  return tracks;
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

function ModelVersionTag({ model }: { model: string | null | undefined }) {
  return (
    <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wide text-violet-300">
      {formatModelVersionTag(model)}
    </span>
  );
}

function ClipReadyLabel({
  clip,
  generating,
  waitingLabel = 'Waiting',
  model,
  className = 'text-xs text-slate-500',
}: {
  clip: WebMusicClip;
  generating?: boolean;
  waitingLabel?: string;
  model?: string | null;
  className?: string;
}) {
  const duration = formatDuration(clip.duration_seconds);
  const status = clip.ready ? 'Ready' : waitingLabel;

  return (
    <p className={`flex min-w-0 flex-nowrap items-center gap-1.5 ${className}`}>
      <span className="truncate">
        {duration ? `${duration} · ${status}` : status}
        {generating ? ' · Generating…' : ''}
      </span>
      <ModelVersionTag model={model} />
    </p>
  );
}

function ClipDownloadBadge({
  label,
  title,
  disabled,
  loading,
  onClick,
  size = 'sm',
  showDownloadIcon = false,
}: {
  label: string;
  title: string;
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
  size?: 'sm' | 'md';
  showDownloadIcon?: boolean;
}) {
  const box = size === 'md' ? 'h-9 gap-1.5 rounded-lg px-3' : 'h-7 gap-1 rounded-md px-2';
  const icon = size === 'md' ? 'h-3.5 w-3.5' : 'h-3 w-3';

  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      title={title}
      aria-busy={loading}
      className={`relative inline-flex items-center justify-center ${box} bg-white/5 text-white hover:bg-white/10 ${
        loading ? 'cursor-wait' : 'disabled:cursor-not-allowed disabled:opacity-30'
      }`}
    >
      <span className={`inline-flex items-center justify-center gap-1 ${loading ? 'opacity-25' : ''}`}>
        {showDownloadIcon ? <Download className={icon} /> : null}
        <span className="text-xs">{label}</span>
      </span>
      {loading ? (
        <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <LoaderCircle className={`${icon} animate-spin text-white`} />
        </span>
      ) : null}
    </button>
  );
}

type DownloadKind = 'mp3' | 'wav' | 'lrc' | 'srt';

function downloadBusyKey(taskId: string, variant: string, kind: DownloadKind): string {
  return `${taskId}:${variant}:${kind}`;
}

function CoverEqualizer({ playing }: { playing: boolean }) {
  const heights = [10, 18, 12, 16];
  return (
    <span
      className="relative z-10 flex h-[18px] w-[22px] items-end justify-center gap-[2px]"
      aria-hidden
    >
      {heights.map((height, index) => (
        <span
          key={index}
          className="block shrink-0 rounded-[1px] bg-[#e879f9] shadow-[0_0_6px_rgba(232,121,249,0.85)]"
          style={{
            width: 3,
            height,
            transformOrigin: 'bottom center',
            animation: playing ? 'eq-bar 0.72s ease-in-out infinite' : undefined,
            animationDelay: playing ? `${index * 0.14}s` : undefined,
            opacity: playing ? 1 : 0.9,
          }}
        />
      ))}
    </span>
  );
}

function ClipCoverControl({
  clip,
  variant,
  isCurrent,
  playing,
  size = 'sm',
  onPlayToggle,
}: {
  clip: WebMusicClip;
  variant?: string;
  isCurrent: boolean;
  playing: boolean;
  size?: 'sm' | 'md';
  onPlayToggle: () => void;
}) {
  const ready = Boolean(clip.ready);
  const showPause = isCurrent && playing;
  const box = size === 'md' ? 'h-16 w-16 rounded-xl' : 'h-11 w-11 rounded-lg';
  const icon = size === 'md' ? 'h-5 w-5' : 'h-3.5 w-3.5';

  return (
    <button
      type="button"
      disabled={!ready}
      onClick={onPlayToggle}
      title={ready ? (showPause ? 'Pause' : 'Play') : 'Waiting for audio'}
      aria-label={ready ? (showPause ? 'Pause' : 'Play') : 'Waiting for audio'}
      className={`relative flex ${box} flex-shrink-0 items-center justify-center overflow-hidden bg-violet-500/20 text-fuchsia-100 disabled:cursor-not-allowed`}
    >
      {clip.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={clip.image_url} alt="" className="h-full w-full object-cover" />
      ) : variant === 'alt' ? (
        <Mic2 className={icon} />
      ) : (
        <Music2 className={icon} />
      )}
      <span className="absolute inset-0 z-10 flex items-center justify-center bg-black/50">
        {!ready ? (
          <LoaderCircle className={`${icon} animate-spin text-white`} />
        ) : isCurrent ? (
          <CoverEqualizer playing={playing} />
        ) : (
          <Play className={`${icon} text-white`} />
        )}
      </span>
    </button>
  );
}

function clipVersionLabel(variant: string | undefined): string {
  return variant === 'alt' ? 'Version 2' : 'Version 1';
}

function ClipTitleEditor({
  title,
  versionLabel,
  className = 'truncate text-sm font-medium text-white',
  onSelect,
  onSave,
}: {
  title: string;
  versionLabel: string;
  className?: string;
  onSelect: () => void;
  onSave: (next: string) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) setDraft(title);
  }, [title, editing]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  async function commit() {
    const next = draft.trim();
    setEditing(false);
    if (!next || next === title) {
      setDraft(title);
      return;
    }
    setSaving(true);
    try {
      await onSave(next);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        maxLength={200}
        aria-label="Song title"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => void commit()}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            event.currentTarget.blur();
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            setDraft(title);
            setEditing(false);
          }
        }}
        className={`min-w-0 flex-1 rounded bg-white/10 px-1.5 py-0.5 outline-none ring-1 ring-violet-400/50 ${className}`}
      />
    );
  }

  return (
    <button
      type="button"
      title="Click to rename"
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
        setEditing(true);
      }}
      className={`min-w-0 flex-1 text-left ${saving ? 'opacity-70' : ''}`}
    >
      <span className={className}>
        {title}
        <span className="font-normal text-slate-400"> · {versionLabel}</span>
      </span>
    </button>
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
  const [selectedVersion, setSelectedVersion] = useState<{
    song: WebMusicGeneration;
    clip: WebMusicClip;
  } | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [downloadingKeys, setDownloadingKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login?next=/create');
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (window.matchMedia('(max-width: 767px)').matches) {
      setMode('simple');
    }
  }, []);

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
  const workspaceQueue = useMemo(() => workspaceReadyTracks(items), [items]);

  useEffect(() => {
    const match = findVersionForTrackId(items, current?.id);
    if (!match) return;
    setSelectedVersion((prev) =>
      prev?.song.id === match.song.id && prev?.clip.variant === match.clip.variant && prev.clip === match.clip
        ? prev
        : match,
    );
  }, [current?.id, items]);

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
    const clip =
      generation.clips.find((item) => item.variant === variant) ??
      ({ variant, label: generation.title, audio_url: '', download_url: '', ready: false } as WebMusicClip);
    const key = downloadBusyKey(generation.id, variant, format);
    setCreateError(null);
    setDownloadingKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
    try {
      const safeTitle = clipDisplayTitle(generation, clip).trim() || 'camxora-track';
      await downloadWebMusicTimedLyrics(
        generation.id,
        variant,
        format,
        `${safeTitle}.${format}`,
      );
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Timed lyrics download failed');
    } finally {
      setDownloadingKeys((prev) => prev.filter((item) => item !== key));
    }
  }

  async function onDownloadAudio(
    generation: WebMusicGeneration,
    variant: string,
    kind: 'mp3' | 'wav',
    filename: string,
  ) {
    if (!canDownload) {
      promptDownloadUpgrade();
      return;
    }
    const key = downloadBusyKey(generation.id, variant, kind);
    setCreateError(null);
    setDownloadingKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
    try {
      if (kind === 'mp3') {
        await downloadWebMusicClip(generation.id, variant, filename);
      } else {
        await downloadWebMusicClipWav(generation.id, variant, filename);
      }
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : `${kind.toUpperCase()} download failed`);
    } finally {
      setDownloadingKeys((prev) => prev.filter((item) => item !== key));
    }
  }

  function isDownloading(taskId: string, variant: string, kind: DownloadKind): boolean {
    return downloadingKeys.includes(downloadBusyKey(taskId, variant, kind));
  }

  function canDownloadTimedLyrics(generation: WebMusicGeneration, clipReady: boolean): boolean {
    return clipReady && !generation.instrumental;
  }

  function clipDownloadButtons(
    generation: WebMusicGeneration,
    clip: WebMusicClip,
    size: 'sm' | 'md',
  ) {
    const timedTitle = (format: 'lrc' | 'srt') => {
      if (!canDownload) return `Upgrade to download ${format.toUpperCase()}`;
      if (generation.instrumental) return 'Timed lyrics not available for instrumentals';
      return format === 'lrc'
        ? 'Download LRC (karaoke timestamps)'
        : 'Download SRT subtitles for video editors';
    };

    return (
      <>
        <AddToPlaylistButton
          taskId={generation.id}
          variant={clip.variant}
          disabled={!clip.ready}
          compact={size === 'sm'}
        />
        <ClipDownloadBadge
          label="LRC"
          size={size}
          disabled={!canDownloadTimedLyrics(generation, clip.ready)}
          loading={isDownloading(generation.id, clip.variant, 'lrc')}
          title={timedTitle('lrc')}
          onClick={() => void onDownloadTimedLyrics(generation, clip.variant, 'lrc')}
        />
        <ClipDownloadBadge
          label="SRT"
          size={size}
          disabled={!canDownloadTimedLyrics(generation, clip.ready)}
          loading={isDownloading(generation.id, clip.variant, 'srt')}
          title={timedTitle('srt')}
          onClick={() => void onDownloadTimedLyrics(generation, clip.variant, 'srt')}
        />
        <ClipDownloadBadge
          label="MP3"
          size={size}
          showDownloadIcon
          disabled={!clip.ready}
          loading={isDownloading(generation.id, clip.variant, 'mp3')}
          title={canDownload ? 'Download MP3' : 'Upgrade to download MP3'}
          onClick={() =>
            void onDownloadAudio(generation, clip.variant, 'mp3', `${clipDisplayTitle(generation, clip)}.mp3`)
          }
        />
        <ClipDownloadBadge
          label="WAV"
          size={size}
          showDownloadIcon
          disabled={!clip.ready}
          loading={isDownloading(generation.id, clip.variant, 'wav')}
          title={canDownload ? 'Download WAV (High quality)' : 'Upgrade to download WAV'}
          onClick={() =>
            void onDownloadAudio(generation, clip.variant, 'wav', `${clipDisplayTitle(generation, clip)}.wav`)
          }
        />
      </>
    );
  }

  function playWorkspaceClip(generation: WebMusicGeneration, clip: WebMusicClip, toggleIfCurrent = false) {
    const track = clipToTrack(generation, clip);
    if (!track) return;
    setSelectedVersion({ song: generation, clip });
    if (current?.id === track.id) {
      if (toggleIfCurrent) toggle();
      return;
    }
    void playTrack(track, workspaceQueue);
  }

  function selectWorkspaceClip(generation: WebMusicGeneration, clip: WebMusicClip) {
    setSelectedVersion({ song: generation, clip });
  }

  async function saveClipTitle(generation: WebMusicGeneration, clip: WebMusicClip, nextTitle: string) {
    setCreateError(null);
    try {
      const updated = await updateWebMusicGenerationTitle(generation.id, nextTitle, clip.variant);
      setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedVersion((prev) => {
        if (!prev || prev.song.id !== updated.id) return prev;
        const nextClip = updated.clips.find((item) => item.variant === prev.clip.variant) ?? prev.clip;
        return { song: updated, clip: nextClip };
      });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Could not save title');
    }
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
      const message = err instanceof Error ? err.message : 'Create failed';
      if (message.toLowerCase().includes('insufficient credits')) {
        setShowUpgradeModal(true);
      }
      setCreateError(message);
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
      <section className="relative flex flex-col overflow-visible rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(10,12,24,0.92),rgba(6,8,18,0.96))] shadow-[0_24px_80px_rgba(15,22,58,0.28)] xl:sticky xl:top-0 xl:max-h-[calc(100dvh-var(--music-header-height)-var(--music-player-height)-2.75rem)] xl:overflow-hidden">
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
            <div className="space-y-1.5">
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(clampText(event.target.value, WEB_MUSIC_STYLE_MAX))}
                maxLength={WEB_MUSIC_STYLE_MAX}
                rows={8}
                placeholder="A rainy-night synthwave song about leaving the city..."
                className="min-h-[180px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-base text-white outline-none focus:border-violet-400/50 md:text-sm"
              />
              <MusicCharCount value={prompt} max={WEB_MUSIC_STYLE_MAX} />
            </div>
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
                    className="min-h-[168px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-base text-white outline-none focus:border-violet-400/50 md:text-sm"
                  />
                  <MusicCharCount value={lyrics} max={WEB_MUSIC_LYRICS_MAX} />
                </div>
              ) : lyricsMode === 'prompt' ? (
                <div className="space-y-1.5">
                  <textarea
                    value={prompt}
                    onChange={(event) => setPrompt(clampText(event.target.value, WEB_MUSIC_LYRICS_MAX))}
                    maxLength={WEB_MUSIC_LYRICS_MAX}
                    rows={7}
                    placeholder="Describe the song you want the lyrics to express..."
                    className="min-h-[168px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-base text-white outline-none focus:border-violet-400/50 md:text-sm"
                  />
                  <MusicCharCount value={prompt} max={WEB_MUSIC_LYRICS_MAX} />
                </div>
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
                  className="min-h-[148px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-base text-white outline-none focus:border-violet-400/50 md:text-sm"
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
                  className="h-11 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-base text-white outline-none focus:border-violet-400/50 md:text-sm"
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
          {createError ? (
            <p className="mb-2 text-left text-xs text-rose-300 md:mb-0 md:mt-2 md:text-center">
              {createError}
            </p>
          ) : null}
          {needsUpgrade ? (
            <button
              type="button"
              onClick={() => setShowUpgradeModal(true)}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-[7px] bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(118,77,255,0.4)] md:rounded-full md:shadow-[0_18px_44px_rgba(118,77,255,0.38)]"
            >
              <Sparkles className="h-4 w-4" />
              Upgrade to Pro
            </button>
          ) : (
            <button
              type="button"
              disabled={!canCreate}
              onClick={() => void onCreate()}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-[7px] bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(118,77,255,0.4)] disabled:opacity-50 md:rounded-full md:shadow-[0_18px_44px_rgba(118,77,255,0.38)]"
            >
              <Music2 className="h-4 w-4" />
              {busy ? 'Creating…' : 'Create'}
            </button>
          )}
          {needsUpgrade ? (
            <p className="mt-2 hidden text-center text-xs text-fuchsia-100/80 md:block">
              You have used today&apos;s free credits. Upgrade to Pro for more.
            </p>
          ) : null}
        </MusicFloatingActionBar>
      </section>

      <section className="flex min-w-0 flex-col gap-4 overflow-hidden music-scroll xl:flex-row">
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
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center gap-1.5 rounded-[7px] border border-violet-400/30 bg-violet-500/10 text-xs font-medium text-violet-200 transition hover:bg-violet-500/15 disabled:opacity-40 sm:w-auto sm:px-3"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">New workspace</span>
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

                const clips = generationClips(generation);

                return clips.map((clip) => {
                  const isCurrent = current?.id === clipTrackId(generation, clip);
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
                      <ClipCoverControl
                        clip={clip}
                        variant={clip.variant}
                        isCurrent={isCurrent}
                        playing={playing}
                        onPlayToggle={() => playWorkspaceClip(generation, clip, true)}
                      />
                      <div
                        className="flex min-w-0 flex-1 cursor-pointer items-center text-left"
                        onClick={() => selectWorkspaceClip(generation, clip)}
                      >
                        <div className="min-w-0 flex-1">
                          <ClipTitleEditor
                            title={clipDisplayTitle(generation, clip)}
                            versionLabel={clipVersionLabel(clip.variant)}
                            onSelect={() => selectWorkspaceClip(generation, clip)}
                            onSave={(next) => saveClipTitle(generation, clip, next)}
                          />
                          <ClipReadyLabel
                            clip={clip}
                            model={generation.model}
                            waitingLabel={clipWaitingLabel(generation)}
                            generating={isGeneratingStatus(generation)}
                          />
                        </div>
                      </div>
                      <div className="hidden flex-shrink-0 items-center gap-1 sm:flex">
                        {clipDownloadButtons(generation, clip, 'sm')}
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
          <div className="w-full max-w-full flex-shrink-0 space-y-4 overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-5 xl:w-80">
            <div className="flex min-w-0 items-start gap-3">
              <ClipCoverControl
                clip={selectedVersion.clip}
                variant={selectedVersion.clip.variant}
                isCurrent={current?.id === clipTrackId(selectedVersion.song, selectedVersion.clip)}
                playing={playing}
                size="md"
                onPlayToggle={() => playWorkspaceClip(selectedVersion.song, selectedVersion.clip, true)}
              />
              <div className="min-w-0 flex-1">
                <ClipTitleEditor
                  title={clipDisplayTitle(selectedVersion.song, selectedVersion.clip)}
                  versionLabel={clipVersionLabel(selectedVersion.clip.variant)}
                  className="truncate text-lg font-semibold text-white"
                  onSelect={() => undefined}
                  onSave={(next) => saveClipTitle(selectedVersion.song, selectedVersion.clip, next)}
                />
                <ClipReadyLabel
                  clip={selectedVersion.clip}
                  model={selectedVersion.song.model}
                  waitingLabel={clipWaitingLabel(selectedVersion.song)}
                  className="text-sm text-slate-400"
                />
              </div>
              <button
                type="button"
                onClick={() => setSelectedVersion(null)}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-white/10 hover:text-white xl:hidden"
                aria-label="Close details"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Playback & Download */}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Actions</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!selectedVersion.clip.ready}
                  onClick={() => playWorkspaceClip(selectedVersion.song, selectedVersion.clip, true)}
                  className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg bg-violet-500/20 text-white hover:bg-violet-500/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {current?.id === `${selectedVersion.song.id}:${selectedVersion.clip.variant}` && playing ? (
                    <Pause className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </button>
                {clipDownloadButtons(selectedVersion.song, selectedVersion.clip, 'md')}
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
                  <span className="text-white">{selectedVersion.clip.ready ? 'Ready' : clipWaitingLabel(selectedVersion.song)}</span>
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
