'use client';

import { useMemo } from 'react';

import { ArtistCard } from '@/components/catalog-cards';
import ShowMoreGrid from '@/components/show-more-grid';
import { getStreamingApiBase, type StreamArtist } from '@/lib/streaming-api';

const PAGE_SIZE = 48;

type Props = {
  initialItems: StreamArtist[];
  total: number;
};

export default function ArtistsBrowser({ initialItems, total }: Props) {
  const apiBase = useMemo(() => getStreamingApiBase(), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Artists</h1>
        <p className="mt-2 text-sm text-slate-400">
          {total} Camxora creator{total === 1 ? '' : 's'} with published music
        </p>
      </div>
      <ShowMoreGrid
        initialItems={initialItems}
        total={total}
        pageSize={PAGE_SIZE}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        renderItem={(artist) => <ArtistCard key={artist.user_id} artist={artist} />}
        loadMore={async (offset) => {
          const response = await fetch(
            `${apiBase}/api/v1/public/streaming/artists?limit=${PAGE_SIZE}&offset=${offset}`,
          );
          if (!response.ok) throw new Error('Failed to load artists');
          return response.json();
        }}
      />
    </div>
  );
}
