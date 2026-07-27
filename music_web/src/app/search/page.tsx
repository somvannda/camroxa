import { Suspense } from 'react';

import SearchPageClient from '@/components/search-page-client';

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-slate-400">Loading search…</p>}>
      <SearchPageClient />
    </Suspense>
  );
}
