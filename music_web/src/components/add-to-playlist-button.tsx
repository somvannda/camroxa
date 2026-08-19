'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Check, ListMusic, Plus } from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  const [open, setOpen] = useState(false);
  const [playlists, setPlaylists] = useState<WebMusicPlaylist[]>([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setFeedback(null);
    void listWebMusicPlaylists()
      .then((response) => setPlaylists(response.items))
      .catch(() => setPlaylists([]));
  }, [open]);

  useEffect(() => {
    if (!feedback) return undefined;
    const timer = window.setTimeout(() => setFeedback(null), 2500);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  async function onAdd(playlist: WebMusicPlaylist) {
    setLoading(true);
    setFeedback(null);
    try {
      await addWebMusicPlaylistItem(playlist.id, {
        task_id: taskId,
        variant: variant as 'ok' | 'alt',
      });
      setFeedback(`Added to ${playlist.name}`);
      setOpen(false);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Unable to add to playlist');
    } finally {
      setLoading(false);
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
      setFeedback(`Added to ${created.name}`);
      setOpen(false);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Unable to create playlist');
    } finally {
      setLoading(false);
    }
  }

  const added = Boolean(feedback?.startsWith('Added to'));

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled || loading}
          title={feedback || 'Add to playlist'}
          aria-label={feedback || 'Add to playlist'}
          className={`inline-flex shrink-0 items-center justify-center rounded-md bg-white/5 text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30 ${
            compact
              ? `h-7 w-7 ${added ? 'text-emerald-300 ring-1 ring-emerald-400/40' : ''}`
              : `h-9 gap-1.5 px-3 ${added ? 'text-emerald-300 ring-1 ring-emerald-400/40' : ''}`
          } ${className}`}
        >
          {added ? (
            <Check className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
          ) : (
            <ListMusic className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
          )}
          {!compact ? <span className="text-xs">{added ? 'Added' : 'Playlist'}</span> : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Add to playlist</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {playlists.length ? (
          playlists.map((playlist) => (
            <DropdownMenuItem key={playlist.id} disabled={loading} onClick={() => void onAdd(playlist)}>
              <span className="truncate">{playlist.name}</span>
            </DropdownMenuItem>
          ))
        ) : (
          <DropdownMenuItem disabled>No playlists yet</DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={loading} onClick={() => void onCreatePlaylist()}>
          <Plus className="h-4 w-4" />
          New playlist
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/playlists">Manage playlists</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
