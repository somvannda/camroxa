'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
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
  Trash2,
  X,
} from 'lucide-react';

import AlbumPlaybackControls from '@/components/album-playback-controls';
import { useAuth } from '@/components/auth-provider';
import { MusicSelect } from '@/components/music-form-ui';
import PlayingEqualizer from '@/components/playing-equalizer';
import { usePlayer } from '@/components/player-provider';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/cn';
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

const SORT_OPTIONS: Array<{ value: SortKey; label: string }> = [
  { value: 'default', label: 'Playlist order' },
  { value: 'title', label: 'Title' },
  { value: 'added', label: 'Date added' },
];

function itemToTrack(item: WebMusicPlaylistItem): StreamTrack | null {
  if (!item.ready || !item.audio_url) return null;
  return {
    id: `${item.task_id}:${item.variant}`,
    title: item.title,
    artist_name: 'You',
    genre: item.style,
    play_url: item.audio_url,
    package_status: item.package_status ?? 'none',
    subject_type: 'suno_task',
    cover_url: item.image_url ?? null,
    duration_seconds: item.duration_seconds,
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

function PlaylistItemRow({
  item,
  index,
  track,
  queue,
  isOwner,
  onRemove,
}: {
  item: WebMusicPlaylistItem;
  index: number;
  track: StreamTrack | null;
  queue: StreamTrack[];
  isOwner: boolean;
  onRemove: (id: string) => void;
}) {
  const { current, playing, playTrack, toggle } = usePlayer();
  const isCurrent = Boolean(track && current?.id === track.id);
  const isPlaying = isCurrent && playing;

  function onPlay() {
    if (!track) return;
    if (isCurrent) {
      toggle();
      return;
    }
    void playTrack(track, queue);
  }

  return (
    <div
      className={cn(
        'group relative grid items-center gap-3 rounded-xl px-2 py-2 sm:px-3 sm:py-2.5',
        isOwner
          ? 'grid-cols-[minmax(0,1fr)_2.5rem] sm:grid-cols-[2.25rem_minmax(0,1fr)_6.5rem_2.5rem]'
          : 'grid-cols-1 sm:grid-cols-[2.25rem_minmax(0,1fr)_6.5rem]',
        isCurrent ? 'track-row-playing' : 'hover:bg-white/[0.045]',
      )}
    >
      {track ? (
        <button
          type="button"
          onClick={onPlay}
          className="absolute inset-0 rounded-xl"
          aria-label={isPlaying ? `Pause ${item.title}` : `Play ${item.title}`}
        />
      ) : null}

      <span className="relative z-10 hidden h-8 w-8 items-center justify-center sm:flex">
        {isCurrent ? (
          <>
            <span className="group-hover:opacity-0">
              <PlayingEqualizer playing={isPlaying} />
            </span>
            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100">
              {isPlaying ? (
                <Pause className="h-4 w-4 text-fuchsia-200" />
              ) : (
                <Play className="h-4 w-4 text-fuchsia-200" />
              )}
            </span>
          </>
        ) : (
          <>
            <span className="tabular-nums text-sm text-slate-500 group-hover:opacity-0">{index}</span>
            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100">
              <Play className="h-4 w-4 text-white" />
            </span>
          </>
        )}
      </span>

      <div className="pointer-events-none relative z-10 flex min-w-0 items-center gap-3">
        <span className="relative h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-violet-500/15 sm:h-10 sm:w-10">
          {item.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.image_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="flex h-full w-full items-center justify-center">
              <Music2 className="h-4 w-4 text-fuchsia-100" />
            </span>
          )}
          {isCurrent ? (
            <span className="absolute inset-0 flex items-center justify-center bg-black/50 sm:hidden">
              <PlayingEqualizer playing={isPlaying} />
            </span>
          ) : null}
        </span>
        <div className="min-w-0">
          <p className={cn('truncate font-medium', isCurrent ? 'text-fuchsia-200' : 'text-white')}>
            {item.title}
          </p>
          <p className={cn('truncate text-sm', isCurrent ? 'text-fuchsia-100/70' : 'text-slate-400')}>
            {item.style?.trim() || (track ? 'Ready to play' : 'Unavailable')}
            <span className="sm:hidden"> · {formatShortDate(item.added_at)}</span>
          </p>
        </div>
      </div>

      <span
        className={cn(
          'relative z-10 hidden text-right text-sm tabular-nums sm:block',
          isCurrent ? 'text-fuchsia-200/70' : 'text-slate-500',
        )}
      >
        {formatShortDate(item.added_at)}
      </span>

      {isOwner ? (
        <div className="relative z-10 justify-self-end">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label={`More options for ${item.title}`}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition hover:bg-white/10 hover:text-white sm:h-8 sm:w-8 sm:opacity-0 sm:group-hover:opacity-100 data-[state=open]:bg-white/10 data-[state=open]:text-white sm:data-[state=open]:opacity-100"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              {track ? (
                <DropdownMenuItem onSelect={onPlay}>
                  {isPlaying ? <Pause /> : <Play />}
                  {isPlaying ? 'Pause' : 'Play'}
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem disabled>Unavailable</DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-rose-300 focus:bg-rose-500/10 focus:text-rose-200"
                onSelect={() => onRemove(item.id)}
              >
                <Trash2 />
                Remove from playlist
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ) : null}
    </div>
  );
}

export default function PlaylistDetailPageClient({ playlistId }: { playlistId: string }) {
  const router = useRouter();
  const { user, loading } = useAuth();
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
  const addPanelRef = useRef<HTMLDivElement | null>(null);

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
    const rows: Array<{
      key: string;
      generation: WebMusicGeneration;
      variant: string;
      title: string;
      style: string;
      image_url?: string | null;
    }> = [];
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

  function openAddPanel() {
    setShowAddPanel(true);
    window.setTimeout(() => {
      addPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
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
  const owner = Boolean(playlist.is_owner);
  const listGridClass = owner
    ? 'grid-cols-[2.25rem_minmax(0,1fr)_6.5rem_2.5rem]'
    : 'grid-cols-[2.25rem_minmax(0,1fr)_6.5rem]';

  return (
    <div className="relative min-h-full">
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

        <div className="relative mx-auto max-w-6xl pt-1 pb-6 md:pt-2 md:pb-8">
          <Link
            href="/playlists"
            className="inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Playlists
          </Link>

          <div className="mt-5 flex flex-col gap-5 sm:mt-6 sm:flex-row sm:items-end sm:gap-7">
            <div className="flex h-36 w-36 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/[0.06] shadow-2xl sm:h-44 sm:w-44 md:h-52 md:w-52">
              {heroCover ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={heroCover} alt="" className="h-full w-full object-cover" />
              ) : (
                <Music2 className="h-12 w-12 text-violet-300/70" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
                Playlist
              </p>
              <h1 className="mt-1 break-words font-display text-3xl font-semibold leading-tight text-white sm:text-5xl md:text-6xl">
                {playlist.name}
              </h1>
              {playlist.description ? (
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300/90">
                  {playlist.description}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-300">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-100">
                  {creatorName.slice(0, 1).toUpperCase()}
                </span>
                <span className="truncate font-medium text-white">{creatorName}</span>
                <span className="text-slate-500">•</span>
                <span>
                  {playlist.song_count} song{playlist.song_count === 1 ? '' : 's'}
                </span>
                {playlist.is_public ? (
                  <>
                    <span className="text-slate-500">•</span>
                    <span className="inline-flex items-center gap-1 text-slate-400">
                      <Globe className="h-3.5 w-3.5" />
                      Public
                    </span>
                  </>
                ) : null}
              </div>

              <AlbumPlaybackControls
                tracks={playlistTracks}
                extraActions={
                  owner ? (
                    <>
                      <button
                        type="button"
                        onClick={() => void onTogglePublic()}
                        className="inline-flex h-12 items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 text-sm font-medium text-white transition hover:bg-white/10 sm:px-5"
                      >
                        {playlist.is_public ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
                        {playlist.is_public ? 'Make private' : 'Make public'}
                      </button>
                      <button
                        type="button"
                        onClick={openAddPanel}
                        className="inline-flex h-12 items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 text-sm font-medium text-white transition hover:bg-white/10 sm:px-5"
                      >
                        <Plus className="h-4 w-4" />
                        Add songs
                      </button>
                    </>
                  ) : null
                }
              />
            </div>
          </div>

          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search this playlist"
                aria-label="Search this playlist"
                className="h-11 w-full rounded-full border border-white/10 bg-white/[0.05] pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-violet-400/40"
              />
            </label>
            <label className="block w-full sm:w-[13.5rem]">
              <span className="sr-only">Sort playlist</span>
              <MusicSelect
                value={sortKey}
                onValueChange={(value) => setSortKey(value as SortKey)}
                options={SORT_OPTIONS}
                className="h-11 rounded-full border-white/10"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl">
        <div
          className={cn(
            'mt-1 hidden gap-3 border-b border-white/8 px-3 pb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500 sm:grid',
            listGridClass,
          )}
        >
          <span>#</span>
          <span>Title</span>
          <span className="text-right">Added</span>
          {owner ? <span className="sr-only">More</span> : null}
        </div>

        <div className="mt-1">
          {filteredItems.length ? (
            filteredItems.map((item, index) => (
              <PlaylistItemRow
                key={item.id}
                item={item}
                index={index + 1}
                track={itemToTrack(item)}
                queue={playlistTracks}
                isOwner={owner}
                onRemove={(id) => void onRemove(id)}
              />
            ))
          ) : (
            <div className="flex flex-col items-center px-4 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04]">
                <Music2 className="h-6 w-6 text-slate-500" />
              </div>
              <p className="mt-4 text-sm font-medium text-white">
                {search ? 'No songs match your search.' : 'This playlist is empty.'}
              </p>
              <p className="mt-1 max-w-sm text-sm text-slate-400">
                {search
                  ? 'Try a different title or style.'
                  : owner
                    ? 'Add songs you created to start listening.'
                    : 'Check back later for new songs.'}
              </p>
              {owner && !search ? (
                <button
                  type="button"
                  onClick={openAddPanel}
                  className="mt-5 inline-flex h-11 items-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-black hover:bg-white/90"
                >
                  <Plus className="h-4 w-4" />
                  Add songs
                </button>
              ) : null}
            </div>
          )}
        </div>

        {owner ? (
          <div ref={addPanelRef} className="mt-6 scroll-mt-4">
            {showAddPanel ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-white">Add songs</h2>
                    <p className="mt-1 text-sm text-slate-400">Pick from tracks you have created.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAddPanel(false)}
                    aria-label="Close add songs"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-white/10 hover:text-white"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <label className="relative mt-4 block">
                  <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <input
                    value={addSearch}
                    onChange={(event) => setAddSearch(event.target.value)}
                    placeholder="Search your songs"
                    aria-label="Search your songs"
                    className="h-11 w-full rounded-full border border-white/10 bg-black/20 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-violet-400/40"
                  />
                </label>
                <div className="mt-3 max-h-72 space-y-0.5 overflow-y-auto">
                  {availableTracks.length ? (
                    availableTracks.map((row) => (
                      <button
                        key={row.key}
                        type="button"
                        disabled={addingKey === row.key}
                        onClick={() => void onAddTrack(row.generation.id, row.variant)}
                        className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-white/[0.04] disabled:opacity-50"
                      >
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-violet-500/15 sm:h-10 sm:w-10">
                          {row.image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={row.image_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <Music2 className="h-4 w-4 text-fuchsia-100" />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-white">{row.title}</p>
                          {row.style ? (
                            <p className="truncate text-xs text-slate-500">{row.style}</p>
                          ) : null}
                        </div>
                        <span className="inline-flex items-center gap-1 rounded-full bg-white/8 px-2.5 py-1 text-xs font-medium text-slate-200">
                          {addingKey === row.key ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Plus className="h-3.5 w-3.5" />
                          )}
                          Add
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="px-2 py-8 text-center text-sm text-slate-500">
                      {addSearch ? 'No matching songs left to add.' : 'No more songs available to add.'}
                    </p>
                  )}
                </div>
              </div>
            ) : filteredItems.length ? (
              <button
                type="button"
                onClick={openAddPanel}
                className="flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 text-sm font-medium text-slate-300 transition hover:border-white/25 hover:bg-white/[0.03] hover:text-white"
              >
                <Plus className="h-4 w-4" />
                Add songs
              </button>
            ) : null}
          </div>
        ) : null}

        {playlist.created_at ? (
          <p className="mt-8 text-xs text-slate-500">Created {formatCreatedDate(playlist.created_at)}</p>
        ) : null}
      </div>
    </div>
  );
}
