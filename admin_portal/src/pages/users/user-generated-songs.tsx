import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Download,
  FolderOpen,
  LoaderCircle,
  Mic2,
  Music2,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { AxiosError } from 'axios';

import {
  useUserWebMusicGenerations,
  useUserWebMusicWorkspaces,
  type AdminWebMusicClip,
  type AdminWebMusicGeneration,
} from '@/hooks/use-users';
import { apiClient } from '@/lib/http-client';
import { useToast } from '@/hooks/use-toast';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

type SelectedVersion = { song: AdminWebMusicGeneration; clip: AdminWebMusicClip };

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

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
  return key === 'V5_5' ? 'V5.5' : 'V5';
}

function clipTrackId(generation: AdminWebMusicGeneration, clip: AdminWebMusicClip): string {
  return `${generation.id}:${clip.variant}`;
}

function clipDisplayTitle(generation: AdminWebMusicGeneration, clip: AdminWebMusicClip): string {
  return String(clip.title || clip.label || generation.title || 'Untitled').trim() || 'Untitled';
}

function clipVersionLabel(variant: string | undefined): string {
  return variant === 'alt' ? 'Version 2' : 'Version 1';
}

function generationClips(generation: AdminWebMusicGeneration): AdminWebMusicClip[] {
  if (generation.clips.length) return generation.clips;
  return [
    { variant: 'ok', label: generation.title, audio_url: '', download_url: '', ready: false },
    { variant: 'alt', label: generation.title, audio_url: '', download_url: '', ready: false },
  ];
}

function clipWaitingLabel(generation: AdminWebMusicGeneration): string {
  return (generation.status || '').toUpperCase() === 'SUCCESS' ? 'Finishing' : 'Waiting';
}

async function readAxiosError(error: unknown, fallback: string): Promise<string> {
  if (!(error instanceof AxiosError)) {
    return error instanceof Error ? error.message : fallback;
  }
  const data = error.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text()) as { error?: { message?: string } };
      if (parsed.error?.message) return parsed.error.message;
    } catch {
      /* ignore */
    }
  } else if (data && typeof data === 'object' && 'error' in data) {
    const message = (data as { error?: { message?: string } }).error?.message;
    if (message) return message;
  }
  return error.message || fallback;
}

async function parseBlobMessage(blob: Blob, fallback: string): Promise<string> {
  try {
    const parsed = JSON.parse(await blob.text()) as { error?: { message?: string } };
    return parsed.error?.message || fallback;
  } catch {
    return fallback;
  }
}

async function downloadAuthenticated(url: string, filename: string): Promise<void> {
  const response = await apiClient.get(url, { responseType: 'blob' });
  const blob = response.data as Blob;
  if (blob.type.includes('json')) {
    throw new Error(await parseBlobMessage(blob, 'Download failed'));
  }
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

function ModelVersionTag({ model }: { model: string | null | undefined }) {
  return (
    <span className="shrink-0 rounded-full bg-violet-500/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-violet-300">
      {formatModelVersionTag(model)}
    </span>
  );
}

function CoverEqualizer({ playing }: { playing: boolean }) {
  const heights = [10, 18, 12, 16];
  return (
    <span className="relative z-10 flex h-[18px] w-[22px] items-end justify-center gap-[2px]" aria-hidden>
      {heights.map((height, index) => (
        <span
          key={index}
          className="block shrink-0 rounded-[1px] bg-[#e879f9] shadow-[0_0_6px_rgba(232,121,249,0.85)]"
          style={{
            width: 3,
            height,
            transformOrigin: 'bottom center',
            animation: playing ? 'admin-eq-bar 0.72s ease-in-out infinite' : undefined,
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
  clip: AdminWebMusicClip;
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
      className={`relative flex ${box} flex-shrink-0 items-center justify-center overflow-hidden bg-violet-500/20 text-fuchsia-100 disabled:cursor-not-allowed`}
    >
      {clip.image_url ? (
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

function ClipReadyLabel({
  clip,
  model,
  waitingLabel = 'Waiting',
  className = 'text-xs text-slate-500',
}: {
  clip: AdminWebMusicClip;
  model?: string | null;
  waitingLabel?: string;
  className?: string;
}) {
  const duration = formatDuration(clip.duration_seconds);
  const status = clip.ready ? 'Ready' : waitingLabel;
  return (
    <p className={`flex min-w-0 flex-nowrap items-center gap-1.5 ${className}`}>
      <span className="truncate">{duration ? `${duration} · ${status}` : status}</span>
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
      className={`relative inline-flex items-center justify-center ${box} bg-white/5 text-xs font-medium text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40`}
    >
      {showDownloadIcon ? <Download className={icon} /> : null}
      {loading ? <LoaderCircle className={`${icon} animate-spin`} /> : label}
    </button>
  );
}

export function UserGeneratedSongs({ userId }: { userId: string }) {
  const { toast } = useToast();
  const { data: workspaceData, isLoading: workspacesLoading } = useUserWebMusicWorkspaces(userId);
  const workspaces = workspaceData?.items ?? [];
  const defaultWorkspaceId =
    workspaces.find((item) => item.is_default)?.id ?? workspaces[0]?.id ?? '';
  const [activeWorkspaceId, setActiveWorkspaceId] = useState('');
  const resolvedWorkspaceId = activeWorkspaceId || defaultWorkspaceId;
  const { data, isLoading, isError, error, refetch } = useUserWebMusicGenerations(
    userId,
    resolvedWorkspaceId || undefined,
  );
  const items = data?.items ?? [];

  const [selectedVersion, setSelectedVersion] = useState<SelectedVersion | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.9);
  const [muted, setMuted] = useState(false);
  const [downloadingKeys, setDownloadingKeys] = useState<string[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const queueRef = useRef<SelectedVersion[]>([]);

  const readyQueue = useMemo(() => {
    const next: SelectedVersion[] = [];
    for (const song of items) {
      for (const clip of generationClips(song)) {
        if (clip.ready) next.push({ song, clip });
      }
    }
    return next;
  }, [items]);
  queueRef.current = readyQueue;

  useEffect(() => {
    if (!activeWorkspaceId && defaultWorkspaceId) {
      setActiveWorkspaceId(defaultWorkspaceId);
    }
  }, [activeWorkspaceId, defaultWorkspaceId]);

  useEffect(() => {
    if (!selectedVersion && readyQueue.length) {
      const first = readyQueue[0];
      if (first) setSelectedVersion(first);
    }
  }, [readyQueue, selectedVersion]);

  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;
    const onTime = () => setCurrentTime(audio.currentTime || 0);
    const onMeta = () => setDuration(audio.duration || 0);
    const onEnded = () => {
      setPlaying(false);
      void playRelative(1);
    };
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.pause();
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('ended', onEnded);
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = muted ? 0 : volume;
  }, [muted, volume]);

  async function loadAndPlay(version: SelectedVersion) {
    const audio = audioRef.current;
    if (!audio) return;
    const url = `/api/v3/users/${userId}/web-music/generations/${version.song.id}/audio?variant=${version.clip.variant}`;
    try {
      const response = await apiClient.get(url, { responseType: 'blob' });
      const blob = response.data as Blob;
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = URL.createObjectURL(blob);
      audio.src = blobUrlRef.current;
      await audio.play();
      setCurrentId(clipTrackId(version.song, version.clip));
      setSelectedVersion(version);
      setPlaying(true);
    } catch (err) {
      setPlaying(false);
      toast({
        variant: 'destructive',
        title: 'Playback failed',
        description: await readAxiosError(err, 'Unable to play this clip'),
      });
    }
  }

  function playWorkspaceClip(song: AdminWebMusicGeneration, clip: AdminWebMusicClip, forcePlay = false) {
    const id = clipTrackId(song, clip);
    if (currentId === id && !forcePlay) {
      const audio = audioRef.current;
      if (!audio) return;
      if (playing) {
        audio.pause();
        setPlaying(false);
      } else {
        void audio.play().then(() => setPlaying(true));
      }
      return;
    }
    void loadAndPlay({ song, clip });
  }

  function playRelative(delta: number) {
    const queue = queueRef.current;
    if (!queue.length) return;
    const index = queue.findIndex((item) => clipTrackId(item.song, item.clip) === currentId);
    const nextIndex = index < 0 ? 0 : index + delta;
    if (nextIndex < 0 || nextIndex >= queue.length) return;
    const next = queue[nextIndex];
    if (!next) return;
    void loadAndPlay(next);
  }

  async function onDownload(
    song: AdminWebMusicGeneration,
    clip: AdminWebMusicClip,
    kind: 'mp3' | 'lrc' | 'srt' | 'wav',
  ) {
    if (kind === 'wav') {
      toast({
        title: 'WAV not available here',
        description: 'Admin can play and download MP3. WAV conversion stays on music.camxora.com.',
      });
      return;
    }
    const key = `${song.id}:${clip.variant}:${kind}`;
    setDownloadingKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
    try {
      const title = clipDisplayTitle(song, clip);
      if (kind === 'mp3') {
        await downloadAuthenticated(
          `/api/v3/users/${userId}/web-music/generations/${song.id}/download?variant=${clip.variant}`,
          `${title}.mp3`,
        );
      } else {
        await downloadAuthenticated(
          `/api/v3/users/${userId}/web-music/generations/${song.id}/timed-lyrics?variant=${clip.variant}&format=${kind}`,
          `${title}.${kind}`,
        );
      }
    } catch (err) {
      toast({
        variant: 'destructive',
        title: `${kind.toUpperCase()} download failed`,
        description: await readAxiosError(err, 'Download failed'),
      });
    } finally {
      setDownloadingKeys((prev) => prev.filter((item) => item !== key));
    }
  }

  function clipDownloadButtons(
    song: AdminWebMusicGeneration,
    clip: AdminWebMusicClip,
    size: 'sm' | 'md',
  ) {
    const busy = (kind: string) => downloadingKeys.includes(`${song.id}:${clip.variant}:${kind}`);
    return (
      <>
        <ClipDownloadBadge
          label="LRC"
          size={size}
          disabled={!clip.ready || song.instrumental}
          loading={busy('lrc')}
          title={song.instrumental ? 'Timed lyrics not available for instrumentals' : 'Download LRC'}
          onClick={() => void onDownload(song, clip, 'lrc')}
        />
        <ClipDownloadBadge
          label="SRT"
          size={size}
          disabled={!clip.ready || song.instrumental}
          loading={busy('srt')}
          title={song.instrumental ? 'Timed lyrics not available for instrumentals' : 'Download SRT'}
          onClick={() => void onDownload(song, clip, 'srt')}
        />
        <ClipDownloadBadge
          label="MP3"
          size={size}
          showDownloadIcon
          disabled={!clip.ready}
          loading={busy('mp3')}
          title="Download MP3"
          onClick={() => void onDownload(song, clip, 'mp3')}
        />
        <ClipDownloadBadge
          label="WAV"
          size={size}
          showDownloadIcon
          disabled={!clip.ready}
          loading={false}
          title="WAV conversion is only on music.camxora.com"
          onClick={() => void onDownload(song, clip, 'wav')}
        />
      </>
    );
  }

  const currentVersion =
    readyQueue.find((item) => clipTrackId(item.song, item.clip) === currentId) ?? selectedVersion;
  const queueIndex = readyQueue.findIndex((item) => clipTrackId(item.song, item.clip) === currentId);
  const progressMax = duration > 0 ? duration : currentVersion?.clip.duration_seconds ?? 0;

  return (
    <div className="rounded-xl border border-slate-800 bg-[#070b1c]">
      <style>{`
        @keyframes admin-eq-bar {
          0%, 100% { transform: scaleY(0.35); }
          50% { transform: scaleY(1); }
        }
      `}</style>
      <div className="flex flex-col gap-4 p-5 lg:flex-row">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Workspaces
              </p>
              <div className="mt-2 flex items-center gap-2">
                <FolderOpen className="h-4 w-4 text-violet-300" />
                {workspacesLoading ? (
                  <Skeleton className="h-10 w-48" />
                ) : workspaces.length ? (
                  <Select value={resolvedWorkspaceId} onValueChange={setActiveWorkspaceId}>
                    <SelectTrigger className="h-10 w-56 border-white/10 bg-white/[0.04] font-semibold text-white">
                      <SelectValue placeholder="Select workspace" />
                    </SelectTrigger>
                    <SelectContent>
                      {workspaces.map((workspace) => (
                        <SelectItem key={workspace.id} value={workspace.id}>
                          {workspace.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-sm text-slate-400">My Workspace</p>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500">{data?.total ?? 0} generations</p>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : isError ? (
            <div className="rounded-xl border border-rose-400/20 bg-rose-500/5 p-4 text-sm text-rose-300">
              {error instanceof Error ? error.message : 'Unable to load generated songs.'}
              <button type="button" className="ml-2 underline" onClick={() => void refetch()}>
                Retry
              </button>
            </div>
          ) : items.length ? (
            <div className="space-y-2">
              {items.map((generation) => {
                if ((generation.status || '').toUpperCase() === 'FAILED') {
                  return (
                    <div
                      key={generation.id}
                      className="rounded-xl border border-rose-400/20 bg-rose-500/5 p-3"
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
                return generationClips(generation).map((clip) => {
                  const isCurrent = currentId === clipTrackId(generation, clip);
                  const isSelected =
                    selectedVersion?.song.id === generation.id &&
                    selectedVersion?.clip.variant === clip.variant;
                  return (
                    <div
                      key={`${generation.id}:${clip.variant}`}
                      className={`flex min-w-0 items-center gap-2 rounded-xl border p-2.5 transition-colors ${
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
                        onPlayToggle={() => playWorkspaceClip(generation, clip)}
                      />
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-center text-left"
                        onClick={() => setSelectedVersion({ song: generation, clip })}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-white">
                            {clipDisplayTitle(generation, clip)}
                            <span className="ml-1 text-slate-500">
                              · {clipVersionLabel(clip.variant)}
                            </span>
                          </p>
                          <ClipReadyLabel
                            clip={clip}
                            model={generation.model}
                            waitingLabel={clipWaitingLabel(generation)}
                          />
                        </div>
                      </button>
                      <div className="flex flex-shrink-0 items-center gap-1">
                        {clipDownloadButtons(generation, clip, 'sm')}
                      </div>
                    </div>
                  );
                });
              })}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center">
              <Music2 className="mx-auto h-6 w-6 text-fuchsia-200" />
              <p className="mt-3 text-white">No generated songs yet</p>
              <p className="mt-1 text-sm text-slate-400">
                Tracks from music.camxora.com will appear here with prompts and playback.
              </p>
            </div>
          )}
        </div>

        {selectedVersion ? (
          <div className="w-full flex-shrink-0 space-y-4 overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-5 lg:w-80">
            <div className="flex items-start gap-3 min-w-0">
              <ClipCoverControl
                clip={selectedVersion.clip}
                variant={selectedVersion.clip.variant}
                isCurrent={currentId === clipTrackId(selectedVersion.song, selectedVersion.clip)}
                playing={playing}
                size="md"
                onPlayToggle={() => playWorkspaceClip(selectedVersion.song, selectedVersion.clip)}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-lg font-semibold text-white">
                  {clipDisplayTitle(selectedVersion.song, selectedVersion.clip)}
                </p>
                <ClipReadyLabel
                  clip={selectedVersion.clip}
                  model={selectedVersion.song.model}
                  waitingLabel={clipWaitingLabel(selectedVersion.song)}
                  className="text-sm text-slate-400"
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Actions</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!selectedVersion.clip.ready}
                  onClick={() => playWorkspaceClip(selectedVersion.song, selectedVersion.clip)}
                  className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-violet-500/20 text-white hover:bg-violet-500/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {currentId === clipTrackId(selectedVersion.song, selectedVersion.clip) && playing ? (
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
              <div className="space-y-2 rounded-lg border border-white/8 bg-black/20 p-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Model</span>
                  <span className="text-white">{formatModelVersionTag(selectedVersion.song.model)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Type</span>
                  <span className="text-white">
                    {selectedVersion.song.instrumental ? 'Instrumental' : 'With Vocals'}
                  </span>
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
                  <span className="text-white">
                    {formatSliderSetting(selectedVersion.song.weirdness_constraint)}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Audio Weight</span>
                  <span className="text-white">{formatSliderSetting(selectedVersion.song.audio_weight)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-400">Status</span>
                  <span className="text-white">
                    {selectedVersion.clip.ready ? 'Ready' : clipWaitingLabel(selectedVersion.song)}
                  </span>
                </div>
              </div>
            </div>

            {selectedVersion.song.negative_tags ? (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Negative Tags
                </p>
                <div className="rounded-lg border border-white/8 bg-black/20 p-3">
                  <p className="text-sm text-slate-300">{selectedVersion.song.negative_tags}</p>
                </div>
              </div>
            ) : null}

            {selectedVersion.song.style ? (
              <div className="min-w-0 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Style</p>
                <div className="min-w-0 rounded-lg border border-white/8 bg-black/20 p-3">
                  <p className="break-words text-sm leading-relaxed text-slate-300">
                    {selectedVersion.song.style}
                  </p>
                </div>
              </div>
            ) : null}

            {selectedVersion.song.lyrics ? (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Lyrics</p>
                <div className="max-h-64 overflow-y-auto rounded-lg border border-white/8 bg-black/20 p-3">
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-300">
                    {selectedVersion.song.lyrics}
                  </pre>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="border-t border-white/8 bg-[rgba(5,8,18,0.94)] px-4 py-3">
        <div className="grid grid-cols-1 items-center gap-3 md:grid-cols-[1.2fr_1.4fr_1fr]">
          <div className="flex min-w-0 items-center gap-3">
            {currentVersion?.clip.image_url ? (
              <img
                src={currentVersion.clip.image_url}
                alt=""
                className="h-12 w-12 rounded-lg object-cover"
              />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/[0.06]">
                <Music2 className="h-4 w-4 text-slate-500" />
              </div>
            )}
            <div className="min-w-0">
              <p className="truncate font-medium text-white">
                {currentVersion
                  ? clipDisplayTitle(currentVersion.song, currentVersion.clip)
                  : 'Select a track to play'}
              </p>
              <p className="truncate text-sm text-slate-400">
                {currentVersion ? clipVersionLabel(currentVersion.clip.variant) : 'Generated songs'}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center justify-center gap-2">
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-white disabled:opacity-30"
                disabled={queueIndex <= 0}
                onClick={() => playRelative(-1)}
              >
                <SkipBack className="h-4 w-4" />
              </button>
              <button
                type="button"
                disabled={!currentVersion?.clip.ready}
                onClick={() =>
                  currentVersion
                    ? playWorkspaceClip(currentVersion.song, currentVersion.clip)
                    : undefined
                }
                className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white disabled:opacity-40"
              >
                {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
              </button>
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-white disabled:opacity-30"
                disabled={queueIndex < 0 || queueIndex >= readyQueue.length - 1}
                onClick={() => playRelative(1)}
              >
                <SkipForward className="h-4 w-4" />
              </button>
            </div>
            <div className="flex w-full max-w-xl items-center gap-2">
              <span className="w-10 shrink-0 text-right text-[11px] tabular-nums text-slate-500">
                {formatClock(currentTime)}
              </span>
              <input
                type="range"
                min={0}
                max={progressMax || 0}
                step={0.1}
                value={Math.min(currentTime, progressMax || 0)}
                disabled={!currentVersion}
                onChange={(event) => {
                  const audio = audioRef.current;
                  const next = Number(event.target.value);
                  if (audio) audio.currentTime = next;
                  setCurrentTime(next);
                }}
                className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/15 accent-fuchsia-400 disabled:opacity-40"
              />
              <span className="w-10 shrink-0 text-[11px] tabular-nums text-slate-500">
                {formatClock(progressMax)}
              </span>
            </div>
          </div>

          <div className="hidden items-center justify-end gap-2 md:flex">
            <button
              type="button"
              onClick={() => setMuted((value) => !value)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-white"
            >
              {muted || volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={muted ? 0 : volume}
              onChange={(event) => {
                setMuted(false);
                setVolume(Number(event.target.value));
              }}
              className="h-1.5 w-28 cursor-pointer appearance-none rounded-full bg-white/15 accent-fuchsia-400"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
