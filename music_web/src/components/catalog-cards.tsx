import Link from 'next/link';

import type { StreamAlbum, StreamArtist } from '@/lib/streaming-api';

export { DiscoveryRail } from '@/components/now-playing-rail';

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

export function ArtistCard({ artist }: { artist: StreamArtist }) {
  return (
    <Link
      href={`/artists/${artist.user_id}`}
      className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 transition hover:bg-white/[0.06]"
    >
      <div className="mb-4 flex aspect-square w-full items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 via-purple-500/20 to-fuchsia-500/30 font-display text-3xl font-semibold text-white">
        {(artist.artist_name || 'C').slice(0, 1).toUpperCase()}
      </div>
      <p className="truncate font-medium text-white">{artist.artist_name ?? 'Camxora Artist'}</p>
      <p className="truncate text-sm text-slate-400">
        {artist.album_count ?? 0} albums · {artist.track_count ?? 0} tracks
      </p>
    </Link>
  );
}
