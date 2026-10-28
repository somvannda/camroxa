import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchView } from "@/components/SearchView";

export const metadata: Metadata = {
  title: "Search",
};

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="fine">Loading search…</p>}>
      <SearchView />
    </Suspense>
  );
}
