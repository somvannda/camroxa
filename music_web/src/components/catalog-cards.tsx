import Link from 'next/link';

import type { WebMusicPublicPlaylist } from '@/lib/playlist-api';
import type { ExploreArtist } from '@/lib/explore-api';
import { exploreArtistStats } from '@/lib/explore-api';
import { getUserAvatarUrl } from '@/lib/auth-api';
import type { StreamAlbum } from '@/lib/streaming-api';

export { DiscoveryRail } from '@/components/now-playing-rail';

export function PlaylistCard({ playlist }: { playlist: WebMusicPublicPlaylist }) {
  return (
    <Link
      href={`/playlists/${playlist.id}`}
      className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 transition hover:bg-white/[0.06]"
    >
      {playlist.cover_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={playlist.cover_url}
          alt=""
          className="mb-4 aspect-square w-full rounded-xl object-cover"
        />
      ) : (
        <div className="mb-4 flex aspect-square w-full items-center justify-center rounded-xl bg-white/[0.06] text-slate-500">
          <span className="text-sm">Playlist</span>
        </div>
      )}
      <p className="truncate font-medium text-white">{playlist.name}</p>
      <p className="truncate text-sm text-slate-400">
        {playlist.creator_name} · {playlist.song_count ?? 0} track{playlist.song_count === 1 ? '' : 's'}
      </p>
    </Link>
  );
}

export function AlbumCard({ album }: { album: StreamAlbum }) {
  return (
    <Link
      href={`/albums/${album.id}`}
      className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 transition hover:bg-white/[0.06]"
    >
      {album.cover_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={album.cover_url}
          alt=""
          className="mb-4 aspect-square w-full rounded-xl object-cover"
        />
      ) : (
        <div className="mb-4 aspect-square w-full rounded-xl bg-white/[0.06]" />
      )}
      <p className="truncate font-medium text-white">{album.album_name}</p>
      <p className="truncate text-sm text-slate-400">
        {album.artist_name ?? 'Camxora Artist'} · {album.track_count ?? 0} tracks
      </p>
    </Link>
  );
}

export function ArtistCard({ artist }: { artist: ExploreArtist }) {
  const initial = (artist.artist_name || 'C').slice(0, 1).toUpperCase();
  const avatarSrc = artist.avatar_url ? getUserAvatarUrl(artist.user_id) : null;
  return (
    <Link
      href={`/artists/${artist.user_id}`}
      className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 transition hover:bg-white/[0.06]"
    >
      {avatarSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={avatarSrc}
          alt=""
          className="mb-4 aspect-square w-full rounded-full object-cover"
        />
      ) : (
        <div className="mb-4 flex aspect-square w-full items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 via-purple-500/20 to-fuchsia-500/30 font-display text-3xl font-semibold text-white">
          {initial}
        </div>
      )}
      <p className="truncate font-medium text-white">{artist.artist_name ?? 'Camxora Creator'}</p>
      <p className="truncate text-sm text-slate-400">{exploreArtistStats(artist)}</p>
    </Link>
  );
}
