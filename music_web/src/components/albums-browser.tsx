'use client';

import { useMemo } from 'react';

import { AlbumCard } from '@/components/catalog-cards';
import ShowMoreGrid from '@/components/show-more-grid';
import { getStreamingApiBase, type StreamAlbum } from '@/lib/streaming-api';

const PAGE_SIZE = 24;

type Props = {
  initialItems: StreamAlbum[];
  total: number;
};

export default function AlbumsBrowser({ initialItems, total }: Props) {
  const apiBase = useMemo(() => getStreamingApiBase(), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Albums</h1>
        <p className="mt-2 text-sm text-slate-400">
          {total} published album{total === 1 ? '' : 's'}
        </p>
      </div>
      <ShowMoreGrid
        initialItems={initialItems}
        total={total}
        pageSize={PAGE_SIZE}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        renderItem={(album) => <AlbumCard key={album.id} album={album} />}
        loadMore={async (offset) => {
          const response = await fetch(
            `${apiBase}/api/v1/public/streaming/albums?limit=${PAGE_SIZE}&offset=${offset}`,
          );
          if (!response.ok) throw new Error('Failed to load albums');
          return response.json();
        }}
      />
    </div>
  );
}
