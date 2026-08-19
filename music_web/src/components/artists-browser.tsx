'use client';

import { useMemo } from 'react';

import { ArtistCard } from '@/components/catalog-cards';
import ShowMoreGrid from '@/components/show-more-grid';
import { mergeExploreArtists, type ExploreArtist } from '@/lib/explore-api';
import { getPlaylistApiBase, listPublicArtists } from '@/lib/playlist-api';
import { getStreamingApiBase, listArtists } from '@/lib/streaming-api';

const PAGE_SIZE = 48;

type Props = {
  initialItems: ExploreArtist[];
  total: number;
};

export default function ArtistsBrowser({ initialItems, total }: Props) {
  const streamingApiBase = useMemo(() => getStreamingApiBase(), []);
  const playlistApiBase = useMemo(() => getPlaylistApiBase(), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Artists</h1>
        <p className="mt-2 text-sm text-slate-400">
          {total} Camxora creator{total === 1 ? '' : 's'} with published music or public playlists
        </p>
      </div>
      <ShowMoreGrid
        initialItems={initialItems}
        total={total}
        pageSize={PAGE_SIZE}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        renderItem={(artist) => <ArtistCard key={artist.user_id} artist={artist} />}
        loadMore={async (offset) => {
          const [streamingPage, webMusicPage] = await Promise.all([
            fetch(`${streamingApiBase}/api/v1/public/streaming/artists?limit=${PAGE_SIZE}&offset=${offset}`).then(
              (response) => (response.ok ? response.json() : { items: [], total: 0 }),
            ),
            listPublicArtists(PAGE_SIZE, offset).catch(() => ({ items: [], total: 0 })),
          ]);
          const items = mergeExploreArtists(streamingPage.items ?? [], webMusicPage.items ?? []);
          return {
            items,
            total: Math.max(streamingPage.total ?? 0, webMusicPage.total ?? 0, items.length),
          };
        }}
      />
    </div>
  );
}
