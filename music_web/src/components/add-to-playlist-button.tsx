'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Check, ListMusic, LoaderCircle, Plus } from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useOptionalPlaylistMemberships } from '@/components/playlist-memberships-provider';
import {
  addWebMusicPlaylistItem,
  createWebMusicPlaylist,
  listWebMusicPlaylists,
  type WebMusicPlaylist,
} from '@/lib/playlist-api';

type AddToPlaylistButtonProps = {
  taskId: string;
  variant: string;
  disabled?: boolean;
  compact?: boolean;
  className?: string;
};

export function AddToPlaylistButton({
  taskId,
  variant,
  disabled = false,
  compact = false,
  className = '',
}: AddToPlaylistButtonProps) {
  const memberships = useOptionalPlaylistMemberships();
  const [open, setOpen] = useState(false);
  const [playlists, setPlaylists] = useState<WebMusicPlaylist[]>([]);
  const [loading, setLoading] = useState(false);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<string | null>(null);
  const [tick, setTick] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setFeedback(null);
    if (memberships?.playlists.length) {
      setPlaylists(memberships.playlists);
    }
    void listWebMusicPlaylists()
      .then((response) => setPlaylists(response.items))
      .catch(() => {
        if (!memberships?.playlists.length) setPlaylists([]);
      });
  }, [open, memberships?.playlists]);

  useEffect(() => {
    if (!justAddedId) return undefined;
    const timer = window.setTimeout(() => setJustAddedId(null), 1400);
    return () => window.clearTimeout(timer);
  }, [justAddedId]);

  useEffect(() => {
    if (!tick) return undefined;
    const timer = window.setTimeout(() => setTick(false), 1600);
    return () => window.clearTimeout(timer);
  }, [tick]);

  useEffect(() => {
    if (!feedback) return undefined;
    const timer = window.setTimeout(() => setFeedback(null), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  const inPlaylists = memberships?.playlistsForClip(taskId, variant) ?? [];
  const inCount = inPlaylists.length;

  async function onAdd(playlist: WebMusicPlaylist) {
    if (memberships?.isInPlaylist(taskId, variant, playlist.id)) {
      setJustAddedId(playlist.id);
      return;
    }
    setAddingId(playlist.id);
    setFeedback(null);
    try {
      await addWebMusicPlaylistItem(playlist.id, {
        task_id: taskId,
        variant: variant as 'ok' | 'alt',
      });
      memberships?.markAdded(taskId, variant, playlist);
      memberships?.rememberPlaylist(playlist);
      setPlaylists((current) =>
        current.some((item) => item.id === playlist.id) ? current : [playlist, ...current],
      );
      setJustAddedId(playlist.id);
      setTick(true);
      setFeedback(`Added to ${playlist.name}`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Unable to add to playlist');
    } finally {
      setAddingId(null);
    }
  }

  async function onCreatePlaylist() {
    const name = window.prompt('Playlist name');
    if (!name?.trim()) return;
    setLoading(true);
    setFeedback(null);
    try {
      const created = await createWebMusicPlaylist({ name: name.trim() });
      await addWebMusicPlaylistItem(created.id, {
        task_id: taskId,
        variant: variant as 'ok' | 'alt',
      });
      memberships?.rememberPlaylist(created);
      memberships?.markAdded(taskId, variant, created);
      setPlaylists((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setJustAddedId(created.id);
      setTick(true);
      setFeedback(`Added to ${created.name}`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Unable to create playlist');
    } finally {
      setLoading(false);
    }
  }

  const showingTick = tick || Boolean(feedback?.startsWith('Added to'));
  const failed = Boolean(feedback && !feedback.startsWith('Added to'));
  const iconClass = compact ? 'h-3.5 w-3.5' : 'h-4 w-4';

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled || loading}
          title={feedback || (inCount ? `In ${inPlaylists.map((item) => item.name).join(', ')}` : 'Add to playlist')}
          aria-label={feedback || 'Add to playlist'}
          className={`relative inline-flex shrink-0 items-center justify-center rounded-md bg-white/5 text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30 ${
            compact ? 'h-7 w-7' : 'h-9 gap-1.5 px-3'
          } ${
            showingTick
              ? 'text-emerald-300 ring-1 ring-emerald-400/50'
              : inCount
                ? 'text-violet-200 ring-1 ring-violet-400/30'
                : ''
          } ${className}`}
        >
          {loading ? (
            <LoaderCircle className={`${iconClass} animate-spin`} />
          ) : showingTick ? (
            <Check className={`${iconClass} playlist-tick-pop`} />
          ) : (
            <ListMusic className={iconClass} />
          )}
          {!compact ? (
            <span className="text-xs">{showingTick ? 'Added' : inCount ? 'Saved' : 'Playlist'}</span>
          ) : null}
          {compact && inCount && !showingTick ? (
            <span className="absolute -right-1 -top-1 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-violet-500 px-0.5 text-[9px] font-semibold leading-none text-white">
              {inCount > 9 ? '9+' : inCount}
            </span>
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Add to playlist</DropdownMenuLabel>
        <p className="px-2 pb-1 text-[11px] leading-snug text-slate-500">
          You can add this song to more than one playlist.
        </p>
        <DropdownMenuSeparator />
        {playlists.length ? (
          playlists.map((playlist) => {
            const checked = Boolean(memberships?.isInPlaylist(taskId, variant, playlist.id));
            const busy = addingId === playlist.id;
            return (
              <DropdownMenuCheckboxItem
                key={playlist.id}
                checked={checked}
                disabled={busy || loading}
                className={justAddedId === playlist.id ? 'playlist-row-flash' : ''}
                onSelect={(event) => {
                  event.preventDefault();
                  void onAdd(playlist);
                }}
              >
                <span className="flex min-w-0 flex-1 items-center gap-2">
                  <span className="truncate">{playlist.name}</span>
                  {busy ? <LoaderCircle className="h-3.5 w-3.5 shrink-0 animate-spin text-slate-400" /> : null}
                  {justAddedId === playlist.id && !busy ? (
                    <Check className="h-3.5 w-3.5 shrink-0 playlist-tick-pop text-emerald-300" />
                  ) : null}
                </span>
              </DropdownMenuCheckboxItem>
            );
          })
        ) : (
          <DropdownMenuItem disabled>No playlists yet</DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={loading}
          onSelect={(event) => {
            event.preventDefault();
            void onCreatePlaylist();
          }}
        >
          <Plus className="h-4 w-4" />
          New playlist
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/playlists">Manage playlists</Link>
        </DropdownMenuItem>
        {failed ? (
          <p className="px-2 py-1.5 text-[11px] text-rose-300">{feedback}</p>
        ) : feedback?.startsWith('Added to') ? (
          <p className="px-2 py-1.5 text-[11px] text-emerald-300">{feedback}</p>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ClipPlaylistNames({
  taskId,
  variant,
  className = '',
}: {
  taskId: string;
  variant: string;
  className?: string;
}) {
  const memberships = useOptionalPlaylistMemberships();
  const playlists = memberships?.playlistsForClip(taskId, variant) ?? [];
  if (!playlists.length) return null;
  const shown = playlists.slice(0, 3);
  const extra = playlists.length - shown.length;

  return (
    <div className={`flex min-w-0 flex-wrap items-center gap-1 ${className}`}>
      {shown.map((playlist) => (
        <Link
          key={playlist.id}
          href={`/playlists/${playlist.id}`}
          title={playlist.name}
          onClick={(event) => event.stopPropagation()}
          className="playlist-chip-in max-w-[7.5rem] truncate rounded-full border border-violet-400/25 bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-medium text-violet-200 transition hover:border-violet-300/40 hover:bg-violet-500/20"
        >
          {playlist.name}
        </Link>
      ))}
      {extra > 0 ? (
        <span className="text-[10px] text-slate-500">+{extra}</span>
      ) : null}
    </div>
  );
}
