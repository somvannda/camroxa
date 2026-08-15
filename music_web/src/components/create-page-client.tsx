'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Download, LoaderCircle, Mic2, Music2, Pause, Play, Shuffle, Sparkles } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { usePlayer } from '@/components/player-provider';
import {
  downloadWebMusicClip,
  generateWebMusic,
  getWebMusicGeneration,
  listWebMusicGenerations,
  fetchWebMusicQuota,
  type WebMusicGeneration,
  type WebMusicQuota,
} from '@/lib/web-music-api';
import { getWebsiteBaseUrl } from '@/lib/site-urls';
import type { StreamTrack } from '@/lib/streaming-api';

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
  if (status === 'success') return item.clips.some((clip) => !clip.ready);
  return true;
}

function clipToTrack(generation: WebMusicGeneration, variant: string): StreamTrack | null {
  const clip = generation.clips.find((item) => item.variant === variant);
  if (!clip?.ready) return null;
  return {
    id: `${generation.id}:${variant}`,
    title: `${generation.title} (${clip.label})`,
    artist_name: 'You',
    genre: generation.style,
    lyrics: generation.lyrics,
    play_url: clip.audio_url,
  };
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
  const [model, setModel] = useState<'V5' | 'V5_5'>('V5');
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [negativeTags, setNegativeTags] = useState('');
  const [vocalGender, setVocalGender] = useState<'m' | 'f' | ''>('');
  const [styleWeight, setStyleWeight] = useState<number | undefined>(undefined);
  const [weirdnessConstraint, setWeirdnessConstraint] = useState<number | undefined>(undefined);
  const [audioWeight, setAudioWeight] = useState<number | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quota, setQuota] = useState<WebMusicQuota | null>(null);
  const [items, setItems] = useState<WebMusicGeneration[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login?next=/create');
    }
  }, [loading, user, router]);

  async function refreshList() {
    const [nextQuota, list] = await Promise.all([
      fetchWebMusicQuota(),
      listWebMusicGenerations(40, 0),
    ]);
    setQuota(nextQuota);
    setItems(list.items);
  }

  useEffect(() => {
    if (!user) return;
    void refreshList().catch((err) => {
      setError(err instanceof Error ? err.message : 'Unable to load workspace');
    });
  }, [user]);

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

  const needsUpgrade = Boolean(quota && !quota.is_pro && (quota.requires_upgrade || quota.remaining <= 0));
  const upgradeHref = `${getWebsiteBaseUrl()}/pricing`;

  const canCreate = useMemo(() => {
    if (busy || needsUpgrade) return false;
    if (mode === 'simple') return prompt.trim().length > 0;
    return style.trim().length > 0 && lyrics.trim().length > 0;
  }, [busy, needsUpgrade, mode, prompt, style, lyrics]);

  async function onCreate() {
    if (needsUpgrade) {
      window.location.href = upgradeHref;
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await generateWebMusic({
        mode,
        lyrics,
        style,
        title,
        prompt,
        model,
        negative_tags: negativeTags || undefined,
        vocal_gender: vocalGender || undefined,
        style_weight: styleWeight,
        weirdness_constraint: weirdnessConstraint,
        audio_weight: audioWeight,
      });
      setQuota(created.quota);
      const loaded = await getWebMusicGeneration(created.task_id).catch(() => null);
      const pending: WebMusicGeneration = loaded ?? {
        id: created.task_id,
        title: created.title,
        lyrics,
        style: created.style,
        model: 'V5',
        instrumental: false,
        status: created.status,
        clips: [],
      };
      setItems((currentItems) => [
        pending,
        ...currentItems.filter((item) => item.id !== pending.id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed');
      void fetchWebMusicQuota()
        .then(setQuota)
        .catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return <p className="text-slate-400">Checking your session…</p>;
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,22rem)_1fr]">
      <section className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="inline-flex rounded-full border border-white/10 p-1 text-xs">
            {(['simple', 'advanced'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={`rounded-full px-3 py-1.5 capitalize ${
                  mode === value ? 'bg-white text-slate-950' : 'text-slate-300'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as 'V5' | 'V5_5')}
            className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-white outline-none"
          >
            <option value="V5">V5</option>
            <option value="V5_5">V5.5</option>
          </select>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <button type="button" disabled className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-500">
            + Audio
          </button>
          <button type="button" disabled className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-500">
            + Voice
          </button>
          <button type="button" disabled className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-500">
            + Inspo
          </button>
        </div>

        {mode === 'simple' ? (
          <label className="block space-y-2 text-sm text-slate-200">
            <span>Song description</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={8}
              placeholder="A rainy-night synthwave song about leaving the city..."
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-white outline-none focus:border-violet-400/50"
            />
          </label>
        ) : (
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 p-3">
              <div className="mb-2 text-sm font-medium text-white">Lyrics</div>
              <textarea
                value={lyrics}
                onChange={(event) => setLyrics(event.target.value)}
                rows={8}
                placeholder="Write lyrics, or paste a verse..."
                className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-white outline-none focus:border-violet-400/50"
              />
            </div>
            <div className="rounded-2xl border border-white/10 p-3">
              <div className="mb-2 text-sm font-medium text-white">Styles</div>
              <textarea
                value={style}
                onChange={(event) => setStyle(event.target.value)}
                rows={3}
                placeholder="urbano, electric guitar, upbeat rock"
                className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-white outline-none focus:border-violet-400/50"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                {STYLE_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() =>
                      setStyle((currentStyle) =>
                        currentStyle.toLowerCase().includes(chip)
                          ? currentStyle
                          : [currentStyle.trim(), chip].filter(Boolean).join(', '),
                      )
                    }
                    className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:bg-white/5"
                  >
                    {chip}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setStyle(STYLE_CHIPS[Math.floor(Math.random() * STYLE_CHIPS.length)])}
                  className="inline-flex items-center gap-1 rounded-full border border-violet-400/40 px-3 py-1 text-xs text-violet-200"
                >
                  <Shuffle className="h-3 w-3" />
                  Shuffle
                </button>
              </div>
            </div>
            <label className="block space-y-2 text-sm text-slate-200">
              <span>Song title (optional)</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="h-11 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              />
            </label>
          </div>
        )}

        {mode === 'advanced' && (
          <button
            type="button"
            disabled={generatingDraft}
            onClick={async () => {
              setGeneratingDraft(true);
              setError(null);
              try {
                const response = await fetch('/api/v1/web-music/generate-draft', {
                  method: 'POST',
                  credentials: 'include',
                  headers: {
                    'Content-Type': 'application/json',
                    'X-Portal-Context': 'user',
                  },
                  body: JSON.stringify({ prompt: style || 'Create a song' }),
                });
                if (!response.ok) throw new Error('Failed to generate draft');
                const data = await response.json();
                if (data.lyrics) setLyrics(data.lyrics);
                if (data.title) setTitle(data.title);
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Draft generation failed');
              } finally {
                setGeneratingDraft(false);
              }
            }}
            className="mt-4 inline-flex items-center gap-2 text-sm text-violet-300 hover:text-white disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {generatingDraft ? 'Generating...' : 'Auto-generate lyrics & title'}
          </button>
        )}
        <button
          type="button"
          onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
          className="mt-4 text-left text-sm text-slate-400 hover:text-white"
        >
          {showAdvancedOptions ? '− Hide' : '+'} Advanced Options
        </button>
        {showAdvancedOptions && (
          <div className="mt-4 space-y-3 rounded-2xl border border-white/10 bg-black/20 p-3">
            <label className="block space-y-1 text-sm">
              <span className="text-slate-300">Negative Tags</span>
              <input
                value={negativeTags}
                onChange={(e) => setNegativeTags(e.target.value)}
                placeholder="choir, backing vocals, falsetto"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-300">Vocal Gender</span>
              <select
                value={vocalGender}
                onChange={(e) => setVocalGender(e.target.value as 'm' | 'f' | '')}
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              >
                <option value="">Auto</option>
                <option value="m">Male</option>
                <option value="f">Female</option>
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-300">Style Weight (0-1)</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={styleWeight ?? ''}
                onChange={(e) => setStyleWeight(e.target.value ? Number(e.target.value) : undefined)}
                placeholder="0.65"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-300">Weirdness/Creativity (0-1)</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={weirdnessConstraint ?? ''}
                onChange={(e) => setWeirdnessConstraint(e.target.value ? Number(e.target.value) : undefined)}
                placeholder="0.65"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-300">Audio Weight (0-1)</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={audioWeight ?? ''}
                onChange={(e) => setAudioWeight(e.target.value ? Number(e.target.value) : undefined)}
                placeholder="0.65"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/50"
              />
            </label>
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">Save to… My Workspace</p>

        <div className="mt-6 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {quota
              ? quota.is_pro
                ? 'Pro — unlimited Create'
                : `${quota.used} of ${quota.limit} free songs`
              : 'Loading quota…'}
          </p>
          {needsUpgrade ? (
            <a
              href={upgradeHref}
              className="inline-flex h-11 min-w-[8rem] items-center justify-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-medium text-white"
            >
              Upgrade to Pro
            </a>
          ) : (
            <button
              type="button"
              disabled={!canCreate}
              onClick={() => void onCreate()}
              className="inline-flex h-11 min-w-[8rem] items-center justify-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? 'Creating…' : 'Create'}
            </button>
          )}
        </div>
        {needsUpgrade ? (
          <p className="mt-3 text-sm text-fuchsia-100/80">
            You have used your {quota?.limit ?? 5} free songs. Upgrade to Pro to keep creating.
          </p>
        ) : null}
        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
      </section>

      <section className="min-w-0">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Workspaces</p>
            <h1 className="font-display text-2xl font-semibold text-white">My Workspace</h1>
          </div>
          <Link href="/explore" className="text-sm text-fuchsia-200/80 hover:text-white">
            Explore catalog
          </Link>
        </div>
        <div className="space-y-2">
          {items.length ? (
            items.map((generation) => (
              <article
                key={generation.id}
                className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-medium text-white">{generation.title}</h2>
                    <p className="mt-1 text-xs text-slate-400">
                      {generation.style || 'Custom'} · {generation.status}
                    </p>
                  </div>
                  {isOpenGeneration(generation) ? (
                    <LoaderCircle className="h-4 w-4 animate-spin text-fuchsia-200" />
                  ) : null}
                </div>
                {(generation.status || '').toUpperCase() === 'FAILED' ? (
                  <p className="mt-2 text-sm text-rose-300">
                    {generation.error_message || 'Generation failed.'}
                  </p>
                ) : null}
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {(generation.clips.length ? generation.clips : [
                    { variant: 'ok', label: 'Version 1', audio_url: '', download_url: '', ready: false },
                    { variant: 'alt', label: 'Version 2', audio_url: '', download_url: '', ready: false },
                  ]).map((clip) => {
                    const track = clipToTrack(generation, clip.variant);
                    const isCurrent = current?.id === `${generation.id}:${clip.variant}`;
                    return (
                      <div
                        key={clip.variant}
                        className="flex items-center justify-between gap-3 rounded-xl border border-white/8 bg-black/20 px-3 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-violet-500/20 text-fuchsia-100">
                            {clip.variant === 'ok' ? <Music2 className="h-5 w-5" /> : <Mic2 className="h-5 w-5" />}
                          </div>
                          <div>
                            <p className="text-sm text-white">{clip.label}</p>
                            <p className="text-xs text-slate-500">{clip.ready ? 'Ready' : 'Waiting'}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
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
                            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-white disabled:text-slate-600"
                          >
                            {isCurrent && playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                          </button>
                          <button
                            type="button"
                            disabled={!clip.ready}
                            onClick={() =>
                              void downloadWebMusicClip(
                                generation.id,
                                clip.variant,
                                `${generation.title}-${clip.variant}.mp3`,
                              )
                            }
                            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-white disabled:text-slate-600"
                            title="Download MP3"
                          >
                            <Download className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            disabled
                            className="text-[10px] uppercase tracking-wide text-slate-600"
                            title="WAV coming soon"
                          >
                            WAV
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </article>
            ))
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
      </section>
    </div>
  );
}
