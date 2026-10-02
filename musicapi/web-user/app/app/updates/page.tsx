"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Post {
  id: string;
  title: string;
  slug: string;
  content: string;
  created_at: string;
}

export default function UpdatesPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Post[]>("/updates")
      .then(setPosts)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold">API Updates</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">Product changes and API announcements.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="mt-6 space-y-4">
        {posts.map((p) => (
          <article key={p.id} className="glass rounded-2xl p-6">
            <div className="text-xs text-[var(--muted)]">{new Date(p.created_at).toLocaleDateString()}</div>
            <h2 className="mt-1 text-lg font-semibold">{p.title}</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--muted)]">{p.content}</p>
          </article>
        ))}
        {posts.length === 0 && !error && (
          <div className="glass rounded-2xl p-8 text-center text-sm text-[var(--muted)]">No updates yet.</div>
        )}
      </div>
    </div>
  );
}
