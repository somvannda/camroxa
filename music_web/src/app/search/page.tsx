'use client';

import { useState } from 'react';
import TrackRow from '@/components/track-row';
import type { StreamTrack } from '@/lib/streaming-api';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StreamTrack[]>([]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Search</h1>
      <input
        className="w-full max-w-xl rounded-xl border border-[hsl(var(--border))] bg-transparent px-4 py-3"
        placeholder="Search tracks, albums, artists"
        value={query}
        onChange={async (event) => {
          const value = event.target.value;
          setQuery(value);
          if (!value.trim()) {
            setResults([]);
            return;
          }
          const response = await fetch(
            `${API_BASE}/api/v1/public/streaming/search?q=${encodeURIComponent(value)}`,
          );
          if (!response.ok) return;
          const data = await response.json();
          setResults(data.items ?? []);
        }}
      />
      <div className="space-y-1">
        {results.map((track) => (
          <TrackRow key={track.id} track={track} />
        ))}
      </div>
    </div>
  );
}
