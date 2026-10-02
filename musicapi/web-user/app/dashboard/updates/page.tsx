"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Post {
  id: string;
  title: string;
  slug: string;
  content: string;
  created_at: string;
}

const PAGE_SIZE = 20;

/** Minimal inline markdown: **bold**, *italic*, `code`, [text](url). */
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    const key = `${keyPrefix}-${i++}`;
    if (tok.startsWith("**")) {
      nodes.push(<strong key={key} className="font-semibold text-white">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      nodes.push(<code key={key} className="rounded bg-white/10 px-1 py-0.5 text-[12px] text-white/90">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("[")) {
      const mm = tok.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (mm) {
        nodes.push(
          <a key={key} href={mm[2]} target="_blank" rel="noreferrer" className="text-[var(--violet)] hover:underline">
            {mm[1]}
          </a>,
        );
      }
    } else if (tok.startsWith("*")) {
      nodes.push(<em key={key}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function Markdown({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      blocks.push(
        <pre key={blocks.length} className="overflow-x-auto rounded-lg bg-black/40 p-3 text-[12px] leading-relaxed text-white/80">
          {buf.join("\n")}
        </pre>,
      );
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const cls = level === 1 ? "text-base font-semibold text-white" : level === 2 ? "text-sm font-semibold text-white" : "text-sm font-medium text-white/90";
      blocks.push(
        <div key={blocks.length} className={cls}>
          {renderInline(h[2], `h${blocks.length}`)}
        </div>,
      );
      i++;
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^[-*]\s+/, ""));
      blocks.push(
        <ul key={blocks.length} className="list-disc space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it, `ul${blocks.length}-${j}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) items.push(lines[i++].replace(/^\d+\.\s+/, ""));
      blocks.push(
        <ol key={blocks.length} className="list-decimal space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it, `ol${blocks.length}-${j}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    if (line.trim() === "") {
      i++;
      continue;
    }
    const buf: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,3}\s|[-*]\s|\d+\.\s|```)/.test(lines[i])
    ) {
      buf.push(lines[i++]);
    }
    blocks.push(
      <p key={blocks.length} className="leading-relaxed">
        {renderInline(buf.join(" "), `p${blocks.length}`)}
      </p>,
    );
  }
  return <div className="space-y-3 text-sm text-white/70">{blocks}</div>;
}

function formatDate(s: string): string {
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function UpdatesPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (query.trim()) params.set("q", query.trim());
      const res = await apiFetch<
        { posts?: Post[]; total?: number; page?: number; pages?: number } | Post[]
      >(`/updates?${params.toString()}`);
      const list = Array.isArray(res) ? res : res.posts ?? [];
      setPosts(list);
      setTotal(Array.isArray(res) ? res.length : res.total ?? list.length);
      setPages(Array.isArray(res) ? 1 : res.pages ?? 1);
      if (!Array.isArray(res) && res.page && res.page !== page) setPage(res.page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, query]);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

  return (
    <div className="pb-16">
      <h1 className="text-2xl font-bold text-white">API Updates</h1>
      <p className="mt-1 text-sm text-white/50">Product changes and API announcements.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="relative mt-5 max-w-xl">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setQuery(searchInput);
              setPage(1);
            }
          }}
          placeholder="Search for updates… (Press Enter to search)"
          className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.03] pl-9 pr-3 text-sm text-white placeholder:text-white/35 focus:border-white/20 focus:bg-white/[0.05] focus:outline-none"
        />
      </div>

      <div className="mt-6 space-y-4">
        {posts.map((p) => (
          <article key={p.id} className="glass rounded-2xl p-6">
            <div className="flex flex-wrap items-center gap-2 text-xs text-white/50">
              <span className="inline-flex items-center gap-1.5">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                {formatDate(p.created_at)}
              </span>
              <span className="rounded bg-[var(--violet)]/15 px-2 py-0.5 text-[11px] font-medium text-[var(--violet)]">API</span>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-white">{p.title}</h2>
            <div className="mt-3">
              <Markdown content={p.content} />
            </div>
          </article>
        ))}

        {!loading && posts.length === 0 && !error && (
          <div className="glass rounded-2xl p-8 text-center text-sm text-white/50">
            {query.trim() ? "Try adjusting your search or filter criteria." : "No API updates are available at the moment."}
          </div>
        )}
        {loading && posts.length === 0 && (
          <div className="glass rounded-2xl p-8 text-center text-sm text-white/40">Loading updates…</div>
        )}
      </div>

      {(pages > 1 || total > 0) && (
        <div className="mt-6 flex items-center justify-between gap-3 text-xs text-white/50">
          <span>{total} updates</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/80 transition hover:bg-white/10 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="tabular-nums">{page} / {pages}</span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages || loading}
              className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/80 transition hover:bg-white/10 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
