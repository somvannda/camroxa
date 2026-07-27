import AlbumHero from '@/components/album-hero';
import AlbumTrackList from '@/components/album-track-list';
import { getAlbum } from '@/lib/streaming-api';

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

  const tracks = (album.tracks ?? []).map((track) => ({
    ...track,
    album_id: track.album_id ?? album.id,
    album_name: track.album_name ?? album.album_name,
    artist_name: track.artist_name ?? album.artist_name,
    user_id: track.user_id ?? album.user_id,
    cover_url: track.cover_url ?? album.cover_url,
  }));
  const totalDuration = tracks.reduce((sum, track) => sum + (track.duration_seconds ?? 0), 0);
  const playCount =
    album.play_count ?? tracks.reduce((sum, track) => sum + (track.play_count ?? 0), 0);

  return (
    <div className="space-y-6">
      <AlbumHero
        album={album}
        tracks={tracks}
        totalDuration={totalDuration}
        playCount={playCount}
      />
      <AlbumTrackList tracks={tracks} />
    </div>
  );
}
