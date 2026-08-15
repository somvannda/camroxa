import HomeGate from '@/components/home-gate';
import { getStreamingHome } from '@/lib/streaming-api';

const emptyHome = { recent_tracks: [], albums: [] } as Awaited<ReturnType<typeof getStreamingHome>>;

export default async function HomePage() {
  let home: Awaited<ReturnType<typeof getStreamingHome>> = emptyHome;
  try {
    home = await getStreamingHome();
  } catch {
    home = emptyHome;
  }

  return <HomeGate tracks={home.recent_tracks} albums={home.albums} />;
}
