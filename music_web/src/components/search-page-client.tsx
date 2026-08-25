'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import TrackRow from '@/components/track-row';
import { getStreamingApiBase, type StreamTrack } from '@/lib/streaming-api';

const PAGE_SIZE = 24;

export default function SearchPageClient() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get('q') ?? '';
  const apiBase = useMemo(() => getStreamingApiBase(), []);
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<StreamTrack[]>([]);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    const value = query.trim();
    if (!value) {
      setResults([]);
      setTotal(0);
      setError('');
      return;
    }

    const handle = window.setTimeout(() => {
      void (async () => {
        setBusy(true);
        setError('');
        try {
          const response = await fetch(
            `${apiBase}/api/v3/public/streaming/search?q=${encodeURIComponent(value)}&limit=${PAGE_SIZE}&offset=0`,
          );
          if (!response.ok) throw new Error('Search failed');
          const data = (await response.json()) as { items?: StreamTrack[]; total?: number };
          setResults(data.items ?? []);
          setTotal(data.total ?? data.items?.length ?? 0);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Search failed');
        } finally {
          setBusy(false);
        }
      })();
    }, 280);

    return () => window.clearTimeout(handle);
  }, [apiBase, query]);

  async function loadMore() {
    const value = query.trim();
    if (!value) return;
    setBusy(true);
    try {
      const response = await fetch(
        `${apiBase}/api/v3/public/streaming/search?q=${encodeURIComponent(value)}&limit=${PAGE_SIZE}&offset=${results.length}`,
      );
      if (!response.ok) throw new Error('Search failed');
      const data = (await response.json()) as { items?: StreamTrack[]; total?: number };
      setResults((prev) => [...prev, ...(data.items ?? [])]);
      setTotal(data.total ?? total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Search</h1>
        <p className="mt-2 text-sm text-slate-400">Find tracks, albums, and artists</p>
      </div>
      <input
        className="w-full max-w-xl rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-white outline-none ring-violet-400/40 placeholder:text-slate-500 focus:ring-2"
        placeholder="Search tracks, albums, artists"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
        {results.map((track) => (
          <TrackRow key={track.id} track={track} />
        ))}
        {!results.length && query.trim() && !busy ? (
          <p className="px-3 py-6 text-sm text-slate-500">No matches.</p>
        ) : null}
        {!query.trim() ? (
          <p className="px-3 py-6 text-sm text-slate-500">Start typing to search the catalog.</p>
        ) : null}
      </div>
      {results.length < total ? (
        <button
          type="button"
          onClick={() => void loadMore()}
          disabled={busy}
          className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? 'Loading…' : `Show more (${results.length} of ${total})`}
        </button>
      ) : null}
    </div>
  );
}
