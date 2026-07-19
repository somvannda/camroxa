import AlbumTrackList from '@/components/album-track-list';
import { formatDuration, getAlbum } from '@/lib/streaming-api';

export default async function AlbumPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let album: Awaited<ReturnType<typeof getAlbum>> | null = null;
  try {
    album = await getAlbum(id);
  } catch {
    album = null;
  }

  if (!album) {
    return <p className="text-[hsl(var(--muted-foreground))]">Album not found.</p>;
  }

  const totalDuration = (album.tracks ?? []).reduce(
    (sum, track) => sum + (track.duration_seconds ?? 0),
    0,
  );

  return (
    <div className="space-y-6">
      <div className="flex gap-6">
        {album.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={album.cover_url} alt="" className="h-48 w-48 rounded-2xl object-cover" />
        ) : (
          <div className="h-48 w-48 rounded-2xl bg-[hsl(var(--secondary))]" />
        )}
        <div>
          <p className="text-sm uppercase tracking-wide text-[hsl(var(--muted-foreground))]">Album</p>
          <h1 className="mt-2 text-4xl font-semibold">{album.album_name}</h1>
          <p className="mt-2 text-[hsl(var(--muted-foreground))]">{album.artist_name}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {(album.genres?.length ? album.genres : album.genre ? [album.genre] : []).map((item) => (
              <span
                key={item}
                className="rounded-full bg-[hsl(var(--primary))]/20 px-3 py-1 text-xs font-medium text-[hsl(var(--primary))]"
              >
                {item}
              </span>
            ))}
            {totalDuration > 0 ? (
              <span className="text-sm text-[hsl(var(--muted-foreground))]">
                {formatDuration(totalDuration)} total
              </span>
            ) : null}
          </div>
        </div>
      </div>
      <AlbumTrackList tracks={album.tracks ?? []} />
    </div>
  );
}
