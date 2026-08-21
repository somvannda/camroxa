'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { useAuth } from '@/components/auth-provider';
import {
  listWebMusicPlaylistMemberships,
  listWebMusicPlaylists,
  type WebMusicPlaylist,
  type WebMusicPlaylistMembership,
} from '@/lib/playlist-api';

export type ClipPlaylistRef = {
  id: string;
  name: string;
};

type PlaylistMembershipsState = {
  playlists: WebMusicPlaylist[];
  loading: boolean;
  playlistsForClip: (taskId: string, variant: string) => ClipPlaylistRef[];
  isInPlaylist: (taskId: string, variant: string, playlistId: string) => boolean;
  markAdded: (taskId: string, variant: string, playlist: Pick<WebMusicPlaylist, 'id' | 'name'>) => void;
  rememberPlaylist: (playlist: WebMusicPlaylist) => void;
  refresh: () => Promise<void>;
};

const PlaylistMembershipsContext = createContext<PlaylistMembershipsState | null>(null);

function clipKey(taskId: string, variant: string): string {
  return `${taskId}:${variant || 'ok'}`;
}

export function PlaylistMembershipsProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [playlists, setPlaylists] = useState<WebMusicPlaylist[]>([]);
  const [memberships, setMemberships] = useState<WebMusicPlaylistMembership[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user || user.email_confirmed === false) {
      setPlaylists([]);
      setMemberships([]);
      return;
    }
    setLoading(true);
    try {
      const [nextPlaylists, nextMemberships] = await Promise.all([
        listWebMusicPlaylists().catch(() => ({ items: [] as WebMusicPlaylist[] })),
        listWebMusicPlaylistMemberships().catch(() => ({ items: [] as WebMusicPlaylistMembership[] })),
      ]);
      setPlaylists(nextPlaylists.items);
      setMemberships(nextMemberships.items);
    } catch {
      setPlaylists([]);
      setMemberships([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading) return;
    void refresh();
  }, [authLoading, refresh]);

  const value = useMemo<PlaylistMembershipsState>(
    () => ({
      playlists,
      loading,
      playlistsForClip(taskId, variant) {
        const key = clipKey(taskId, variant);
        const seen = new Set<string>();
        const items: ClipPlaylistRef[] = [];
        for (const row of memberships) {
          if (clipKey(row.task_id, row.variant) !== key) continue;
          if (seen.has(row.playlist_id)) continue;
          seen.add(row.playlist_id);
          items.push({ id: row.playlist_id, name: row.playlist_name });
        }
        return items;
      },
      isInPlaylist(taskId, variant, playlistId) {
        const key = clipKey(taskId, variant);
        return memberships.some(
          (row) => clipKey(row.task_id, row.variant) === key && row.playlist_id === playlistId,
        );
      },
      markAdded(taskId, variant, playlist) {
        setMemberships((current) => {
          if (
            current.some(
              (row) =>
                row.playlist_id === playlist.id &&
                clipKey(row.task_id, row.variant) === clipKey(taskId, variant),
            )
          ) {
            return current;
          }
          return [
            {
              playlist_id: playlist.id,
              playlist_name: playlist.name,
              task_id: taskId,
              variant: variant || 'ok',
            },
            ...current,
          ];
        });
      },
      rememberPlaylist(playlist) {
        setPlaylists((current) => {
          if (current.some((item) => item.id === playlist.id)) return current;
          return [playlist, ...current];
        });
      },
      refresh,
    }),
    [playlists, memberships, loading, refresh],
  );

  return (
    <PlaylistMembershipsContext.Provider value={value}>{children}</PlaylistMembershipsContext.Provider>
  );
}

export function usePlaylistMemberships() {
  const ctx = useContext(PlaylistMembershipsContext);
  if (!ctx) throw new Error('usePlaylistMemberships must be used within PlaylistMembershipsProvider');
  return ctx;
}

export function useOptionalPlaylistMemberships() {
  return useContext(PlaylistMembershipsContext);
}
