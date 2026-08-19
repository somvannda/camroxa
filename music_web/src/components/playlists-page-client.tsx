'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Globe, ListMusic, Loader2, Lock, Plus, Trash2 } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import {
  createWebMusicPlaylist,
  deleteWebMusicPlaylist,
  listWebMusicPlaylists,
  type WebMusicPlaylist,
} from '@/lib/playlist-api';

export default function PlaylistsPageClient() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [items, setItems] = useState<WebMusicPlaylist[]>([]);
  const [busy, setBusy] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login?next=/playlists');
    }
  }, [loading, user, router]);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      const data = await listWebMusicPlaylists();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load playlists');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!user) return;
    void refresh();
  }, [user]);

  const empty = useMemo(() => !busy && items.length === 0, [busy, items.length]);

  async function onCreate() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createWebMusicPlaylist({
        name: trimmed,
        description: description.trim() || undefined,
        is_public: isPublic,
      });
      setShowCreate(false);
      setName('');
      setDescription('');
      setIsPublic(false);
      router.push(`/playlists/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create playlist');
    } finally {
      setCreating(false);
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm('Delete this playlist?')) return;
    try {
      await deleteWebMusicPlaylist(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete playlist');
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Library</p>
          <h1 className="mt-1 text-3xl font-semibold text-white">Playlists</h1>
          <p className="mt-2 text-sm text-slate-400">
            Create collections of your songs and share them publicly or keep them private.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((value) => !value)}
          className="inline-flex h-11 items-center gap-2 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 px-5 text-sm font-semibold text-white"
        >
          <Plus className="h-4 w-4" />
          New playlist
        </button>
      </div>

      {showCreate ? (
        <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block space-y-2">
              <span className="text-sm text-slate-300">Name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="My favorites"
                className="h-11 w-full rounded-[7px] border border-white/10 bg-white/[0.04] px-3 text-white outline-none focus:border-violet-400/40"
              />
            </label>
            <label className="block space-y-2 md:col-span-2">
              <span className="text-sm text-slate-300">Description (optional)</span>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                placeholder="What is this playlist about?"
                className="w-full rounded-[7px] border border-white/10 bg-white/[0.04] px-3 py-2 text-white outline-none focus:border-violet-400/40"
              />
            </label>
          </div>
          <label className="mt-4 flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(event) => setIsPublic(event.target.checked)}
              className="rounded border-white/20 bg-transparent"
            />
            Make this playlist public
          </label>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              disabled={creating || !name.trim()}
              onClick={() => void onCreate()}
              className="rounded-[7px] bg-violet-500/20 px-4 py-2 text-sm font-medium text-violet-100 disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create playlist'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-[7px] border border-white/10 px-4 py-2 text-sm text-slate-300"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {error ? <p className="mb-4 text-sm text-rose-300">{error}</p> : null}

      {busy ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
        </div>
      ) : empty ? (
        <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center">
          <ListMusic className="mx-auto h-8 w-8 text-fuchsia-200" />
          <p className="mt-3 text-white">No playlists yet</p>
          <p className="mt-1 text-sm text-slate-400">Create your first playlist to organize songs from Create.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((playlist) => (
            <div
              key={playlist.id}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/20"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link
                    href={`/playlists/${playlist.id}`}
                    className="text-lg font-semibold text-white hover:text-fuchsia-100"
                  >
                    {playlist.name}
                  </Link>
                  {playlist.description ? (
                    <p className="mt-1 line-clamp-2 text-sm text-slate-400">{playlist.description}</p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span>{playlist.song_count} songs</span>
                    {playlist.is_public ? (
                      <span className="inline-flex items-center gap-1 text-emerald-300">
                        <Globe className="h-3.5 w-3.5" />
                        Public
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1">
                        <Lock className="h-3.5 w-3.5" />
                        Private
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void onDelete(playlist.id)}
                  className="rounded-md p-2 text-slate-500 hover:bg-white/5 hover:text-rose-300"
                  aria-label={`Delete ${playlist.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
