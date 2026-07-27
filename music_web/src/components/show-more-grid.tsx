'use client';

import { useState } from 'react';

type Props<T> = {
  initialItems: T[];
  total: number;
  pageSize: number;
  loadMore: (offset: number) => Promise<{ items: T[]; total: number }>;
  renderItem: (item: T) => React.ReactNode;
  className?: string;
};

export default function ShowMoreGrid<T extends { id?: string; user_id?: string }>({
  initialItems,
  total,
  pageSize,
  loadMore,
  renderItem,
  className,
}: Props<T>) {
  const [items, setItems] = useState(initialItems);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const hasMore = items.length < total;

  async function onShowMore() {
    setBusy(true);
    setError('');
    try {
      const next = await loadMore(items.length);
      setItems((prev) => {
        const seen = new Set(prev.map((item) => String(item.id ?? item.user_id)));
        const merged = [...prev];
        for (const item of next.items) {
          const key = String(item.id ?? item.user_id);
          if (!seen.has(key)) {
            seen.add(key);
            merged.push(item);
          }
        }
        return merged;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load more.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className={className}>{items.map((item) => renderItem(item))}</div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {hasMore ? (
        <button
          type="button"
          onClick={() => void onShowMore()}
          disabled={busy}
          className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm font-medium text-white transition hover:bg-white/[0.08] disabled:opacity-50"
        >
          {busy ? 'Loading…' : `Show more (${items.length} of ${total})`}
        </button>
      ) : items.length ? (
        <p className="text-sm text-slate-500">
          Showing all {total} result{total === 1 ? '' : 's'}
        </p>
      ) : null}
    </div>
  );
}
