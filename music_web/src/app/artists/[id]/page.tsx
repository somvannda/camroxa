import Link from 'next/link';

import { AlbumCard, PlaylistCard } from '@/components/catalog-cards';
import { exploreArtistStats } from '@/lib/explore-api';
import { getUserAvatarUrl } from '@/lib/auth-api';
import { getPublicArtist } from '@/lib/playlist-api';

export default async function ArtistPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let artist: Awaited<ReturnType<typeof getPublicArtist>> | null = null;
  try {
    artist = await getPublicArtist(id);
  } catch {
    artist = null;
  }

  if (!artist) {
    return <p className="text-slate-400">Artist not found.</p>;
  }

  const stats = exploreArtistStats(artist);
  const avatarSrc = artist.avatar_url ? getUserAvatarUrl(artist.user_id) : null;

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-violet-600/30 via-purple-900/20 to-transparent p-8 md:p-10">
        <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-100/70">Artist</p>
        <div className="mt-3 flex items-center gap-5">
          {avatarSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarSrc}
              alt=""
              className="h-20 w-20 rounded-full object-cover md:h-24 md:w-24"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 via-purple-500/20 to-fuchsia-500/30 font-display text-3xl font-semibold text-white md:h-24 md:w-24">
              {(artist.artist_name || 'C').slice(0, 1).toUpperCase()}
            </div>
          )}
          <div>
            <h1 className="font-display text-4xl font-semibold text-white md:text-6xl">
              {artist.artist_name ?? 'Camxora Creator'}
            </h1>
            <p className="mt-3 text-slate-300/75">{stats}</p>
          </div>
        </div>
        <Link
          href="/artists"
          className="mt-6 inline-flex text-sm text-fuchsia-200/80 hover:text-white"
        >
          ← All artists
        </Link>
      </section>

      {artist.playlists.length ? (
        <section>
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Public playlists</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {artist.playlists.map((playlist) => (
              <PlaylistCard key={playlist.id} playlist={playlist} />
            ))}
          </div>
        </section>
      ) : null}

      {artist.albums?.length ? (
        <section>
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Published albums</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {artist.albums.map((album) => (
              <AlbumCard key={album.id} album={album} />
            ))}
          </div>
        </section>
      ) : null}

      {!artist.playlists.length && !artist.albums?.length ? (
        <p className="text-sm text-slate-500">No public music published yet.</p>
      ) : null}
    </div>
  );
}
