'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Globe,
  Loader2,
  Lock,
  MoreHorizontal,
  Music2,
  Pause,
  Play,
  Plus,
  Search,
  Shuffle,
  Trash2,
} from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { usePlayer } from '@/components/player-provider';
import { listWebMusicGenerations, type WebMusicGeneration } from '@/lib/web-music-api';
import {
  addWebMusicPlaylistItem,
  getWebMusicPlaylist,
  listWebMusicPlaylistItems,
  removeWebMusicPlaylistItem,
  updateWebMusicPlaylist,
  type WebMusicPlaylist,
  type WebMusicPlaylistItem,
} from '@/lib/playlist-api';
import type { StreamTrack } from '@/lib/streaming-api';

type SortKey = 'default' | 'title' | 'added';

function itemToTrack(item: WebMusicPlaylistItem): StreamTrack | null {
  if (!item.ready || !item.audio_url) return null;
  return {
    id: `${item.task_id}:${item.variant}`,
    title: item.title,
    artist_name: 'You',
    genre: item.style,
    play_url: item.audio_url,
    cover_url: item.image_url ?? null,
  };
}

function formatShortDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatCreatedDate(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });
}

function shuffleTracks(tracks: StreamTrack[]): StreamTrack[] {
  const next = [...tracks];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1));
    [next[index], next[swap]] = [next[swap], next[index]];
  }
  return next;
}

export default function PlaylistDetailPageClient({ playlistId }: { playlistId: string }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { playTrack, current, playing, toggle } = usePlayer();
  const [playlist, setPlaylist] = useState<WebMusicPlaylist | null>(null);
  const [items, setItems] = useState<WebMusicPlaylistItem[]>([]);
  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('default');
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [addSearch, setAddSearch] = useState('');
  const [addingKey, setAddingKey] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?next=/playlists/${playlistId}`);
    }
  }, [loading, user, router, playlistId]);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      const [nextPlaylist, nextItems, nextGenerations] = await Promise.all([
        getWebMusicPlaylist(playlistId),
        listWebMusicPlaylistItems(playlistId),
        listWebMusicGenerations(100, 0).then((response) => response.items),
      ]);
      setPlaylist(nextPlaylist);
      setItems(nextItems.items);
      setGenerations(nextGenerations.filter((item) => item.status.toLowerCase() === 'success'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load playlist');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!user) return;
    void refresh();
  }, [user, playlistId]);

  const playlistTracks = useMemo(
    () => items.map((item) => itemToTrack(item)).filter((track): track is StreamTrack => Boolean(track)),
    [items],
  );

  const heroCover = useMemo(
    () => items.find((item) => item.image_url)?.image_url ?? null,
    [items],
  );

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    let next = items;
    if (query) {
      next = next.filter(
        (item) =>
          item.title.toLowerCase().includes(query) ||
          (item.style || '').toLowerCase().includes(query),
      );
    }
    const sorted = [...next];
    if (sortKey === 'title') {
      sorted.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sortKey === 'added') {
      sorted.sort((a, b) => String(b.added_at || '').localeCompare(String(a.added_at || '')));
    } else {
      sorted.sort((a, b) => a.position - b.position);
    }
    return sorted;
  }, [items, search, sortKey]);

  const playlistKeys = useMemo(
    () => new Set(items.map((item) => `${item.task_id}:${item.variant}`)),
    [items],
  );

  const availableTracks = useMemo(() => {
    const query = addSearch.trim().toLowerCase();
    const rows: Array<{ key: string; generation: WebMusicGeneration; variant: string; title: string; style: string; image_url?: string | null }> = [];
    for (const generation of generations) {
      for (const clip of generation.clips) {
        if (!clip.ready) continue;
        const key = `${generation.id}:${clip.variant}`;
        if (playlistKeys.has(key)) continue;
        const title = generation.title;
        const style = generation.style || '';
        if (query && !title.toLowerCase().includes(query) && !style.toLowerCase().includes(query)) {
          continue;
        }
        rows.push({
          key,
          generation,
          variant: clip.variant,
          title,
          style,
          image_url: clip.image_url,
        });
      }
    }
    return rows;
  }, [generations, playlistKeys, addSearch]);

  async function onTogglePublic() {
    if (!playlist?.is_owner) return;
    try {
      const updated = await updateWebMusicPlaylist(playlistId, { is_public: !playlist.is_public });
      setPlaylist(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update playlist');
    }
  }

  async function onAddTrack(taskId: string, variant: string) {
    setAddingKey(`${taskId}:${variant}`);
    setError(null);
    try {
      await addWebMusicPlaylistItem(playlistId, {
        task_id: taskId,
        variant: variant as 'ok' | 'alt',
      });
      const nextItems = await listWebMusicPlaylistItems(playlistId);
      setItems(nextItems.items);
      setPlaylist((current) =>
        current ? { ...current, song_count: nextItems.items.length } : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to add song');
    } finally {
      setAddingKey(null);
    }
  }

  async function onRemove(itemId: string) {
    setOpenMenuId(null);
    try {
      await removeWebMusicPlaylistItem(playlistId, itemId);
      setItems((current) => current.filter((item) => item.id !== itemId));
      setPlaylist((current) =>
        current ? { ...current, song_count: Math.max(0, current.song_count - 1) } : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to remove song');
    }
  }

  function onPlayAll(shuffled = false) {
    if (!playlistTracks.length) return;
    const queue = shuffled ? shuffleTracks(playlistTracks) : playlistTracks;
    void playTrack(queue[0], queue);
  }

  if (busy && !playlist) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
      </div>
    );
  }

  if (!playlist) {
    return <p className="px-4 py-10 text-center text-slate-400">{error || 'Playlist not found.'}</p>;
  }

  const creatorName = user?.display_name || user?.email || 'You';

  return (
    <div className="relative min-h-full pb-24">
      <div className="relative overflow-hidden">
        {heroCover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={heroCover}
            alt=""
            aria-hidden
            className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-35 blur-3xl"
          />
        ) : null}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg, rgba(88,40,160,0.35) 0%, rgba(5,8,18,0.88) 78%, rgba(5,8,18,1) 100%)',
          }}
        />

        <div className="relative mx-auto max-w-6xl px-0 pb-8 pt-2 sm:pt-6">
          <Link
            href="/playlists"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Playlists
          </Link>

          <div className="mt-6 flex flex-col gap-6 md:flex-row md:items-end">
            <div className="mx-auto flex h-36 w-36 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/[0.06] shadow-2xl sm:mx-0 md:h-52 md:w-52">
              {heroCover ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={heroCover} alt="" className="h-full w-full object-cover" />
              ) : (
                <Music2 className="h-12 w-12 text-violet-300/70" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-slate-400">Playlist</p>
              <h1 className="mt-2 truncate text-3xl font-semibold text-white md:text-5xl">{playlist.name}</h1>
              {playlist.description ? (
                <p className="mt-2 max-w-2xl text-sm text-slate-400">{playlist.description}</p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-400">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-100">
                  {creatorName.slice(0, 1).toUpperCase()}
                </span>
                <span className="truncate">{creatorName}</span>
                <span>•</span>
                <span>
                  {playlist.song_count} song{playlist.song_count === 1 ? '' : 's'}
                </span>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={!playlistTracks.length}
                  onClick={() => onPlayAll(false)}
                  className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-black disabled:opacity-40 sm:h-11 sm:w-auto"
                >
                  <Play className="h-4 w-4 fill-current" />
                  Play
                </button>
                <button
                  type="button"
                  disabled={!playlistTracks.length}
                  onClick={() => onPlayAll(true)}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/15 disabled:opacity-40"
                  title="Shuffle"
                >
                  <Shuffle className="h-4 w-4" />
                </button>
                {playlist.is_owner ? (
                  <button
                    type="button"
                    onClick={() => void onTogglePublic()}
                    className="inline-flex h-11 items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 text-sm text-slate-200 hover:bg-white/10"
                  >
                    {playlist.is_public ? <Globe className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                    {playlist.is_public ? 'Public' : 'Make public'}
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search for a song or style"
                className="h-11 w-full rounded-full border border-white/10 bg-white/[0.05] pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-violet-400/40"
              />
            </label>
            <select
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as SortKey)}
              className="h-11 rounded-full border border-white/10 bg-white/[0.05] px-4 text-sm text-white outline-none"
            >
              <option value="default">Default</option>
              <option value="title">Title</option>
              <option value="added">Date added</option>
            </select>
          </div>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl px-0">
        <div className="mt-2 hidden grid-cols-[3rem_minmax(0,1fr)_5rem_3rem] gap-3 border-b border-white/8 px-3 pb-2 text-xs uppercase tracking-wide text-slate-500 sm:grid">
          <span />
          <span>Title</span>
          <span className="text-right">Added</span>
          <span />
        </div>

        <div className="mt-1 divide-y divide-white/6">
          {filteredItems.length ? (
            filteredItems.map((item) => {
              const track = itemToTrack(item);
              const isCurrent = current?.id === `${item.task_id}:${item.variant}`;
              return (
                <div
                  key={item.id}
                  className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-2 py-3 sm:grid-cols-[3rem_minmax(0,1fr)_5rem_3rem]"
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-violet-500/15 text-fuchsia-100 sm:h-10 sm:w-10">
                    {item.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={item.image_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <Music2 className="h-4 w-4" />
                    )}
                  </div>

                  <button
                    type="button"
                    disabled={!track}
                    onClick={() => {
                      if (!track) return;
                      if (isCurrent) {
                        toggle();
                        return;
                      }
                      void playTrack(track, playlistTracks);
                    }}
                    className="min-w-0 text-left disabled:opacity-40"
                  >
                    <p className={`truncate font-medium ${isCurrent ? 'text-fuchsia-200' : 'text-white'}`}>
                      {item.title}
                    </p>
                  </button>

                  <div className="flex items-center justify-end gap-1 sm:contents">
                    <span className="hidden text-right text-xs text-slate-500 sm:block">
                      {formatShortDate(item.added_at)}
                    </span>
                    <button
                      type="button"
                      disabled={!track}
                      onClick={() => {
                        if (!track) return;
                        if (isCurrent) {
                          toggle();
                          return;
                        }
                        void playTrack(track, playlistTracks);
                      }}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/10 disabled:opacity-30 sm:h-8 sm:w-8"
                    >
                      {isCurrent && playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </button>
                    {playlist.is_owner ? (
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() =>
                            setOpenMenuId((current) => (current === item.id ? null : item.id))
                          }
                          className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-white/10 hover:text-white"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                        {openMenuId === item.id ? (
                          <div className="absolute right-0 top-9 z-20 min-w-[9rem] rounded-xl border border-white/10 bg-[rgba(8,12,28,0.98)] p-1 shadow-xl">
                            <button
                              type="button"
                              onClick={() => void onRemove(item.id)}
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-rose-300 hover:bg-white/5"
                            >
                              <Trash2 className="h-4 w-4" />
                              Remove
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="py-16 text-center text-sm text-slate-400">
              {search ? 'No songs match your search.' : 'No songs in this playlist yet.'}
            </div>
          )}
        </div>

        {playlist.is_owner ? (
          <div className="mt-8">
            {showAddPanel ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-medium text-white">Add songs from your library</h2>
                  <button
                    type="button"
                    onClick={() => setShowAddPanel(false)}
                    className="text-sm text-slate-400 hover:text-white"
                  >
                    Close
                  </button>
                </div>
                <label className="relative mt-3 block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <input
                    value={addSearch}
                    onChange={(event) => setAddSearch(event.target.value)}
                    placeholder="Search your created songs"
                    className="h-10 w-full rounded-full border border-white/10 bg-black/20 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-500"
                  />
                </label>
                <div className="mt-3 max-h-72 space-y-1 overflow-y-auto">
                  {availableTracks.length ? (
                    availableTracks.map((row) => (
                      <button
                        key={row.key}
                        type="button"
                        disabled={addingKey === row.key}
                        onClick={() => void onAddTrack(row.generation.id, row.variant)}
                        className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-white/[0.04] disabled:opacity-50"
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-violet-500/15">
                          {row.image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={row.image_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <Music2 className="h-4 w-4 text-fuchsia-100" />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-white">{row.title}</p>
                        </div>
                        <Plus className="h-4 w-4 shrink-0 text-slate-400" />
                      </button>
                    ))
                  ) : (
                    <p className="px-2 py-6 text-center text-sm text-slate-500">
                      No more songs available to add.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowAddPanel(true)}
                className="inline-flex h-11 items-center gap-2 rounded-full border border-white/15 bg-white px-5 text-sm font-medium text-black hover:bg-white/90"
              >
                <Plus className="h-4 w-4" />
                Add songs
              </button>
            )}
          </div>
        ) : null}

        {playlist.created_at ? (
          <p className="mt-8 text-xs text-slate-500">
            Created {formatCreatedDate(playlist.created_at)}
          </p>
        ) : null}
      </div>
    </div>
  );
}
