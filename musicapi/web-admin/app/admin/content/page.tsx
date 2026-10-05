"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Post {
  id: string;
  title: string;
  slug: string;
  content: string;
  published: boolean;
  created_at: string;
}

export default function ContentPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Post | null>(null);
  const [form, setForm] = useState({ title: "", slug: "", content: "", published: false });
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    apiFetch<Post[]>("/admin/content")
      .then(setPosts)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  function openNew() {
    setEditing(null);
    setForm({ title: "", slug: "", content: "", published: false });
    setShowForm(true);
  }

  function openEdit(p: Post) {
    setEditing(p);
    setForm({ title: p.title, slug: p.slug, content: p.content, published: p.published });
    setShowForm(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = JSON.stringify({ ...form, slug: form.slug || undefined });
      if (editing) {
        await apiFetch(`/admin/content/${editing.id}`, { method: "PUT", body });
      } else {
        await apiFetch("/admin/content", { method: "POST", body });
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this post?")) return;
    setError("");
    try {
      await apiFetch(`/admin/content/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Updates</h1>
          <p className="text-sm text-[var(--muted)]">Blog posts shown in the user panel</p>
        </div>
        <button onClick={() => (showForm ? setShowForm(false) : openNew())} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">
          {showForm ? "Cancel" : "New post"}
        </button>
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {showForm && (
        <form onSubmit={submit} className="glass space-y-4 rounded-xl p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Title</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="API update title" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Slug (optional)</label>
              <input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="my-update" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Content</label>
            <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} rows={5} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="Update details…" />
          </div>
          <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <input type="checkbox" checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })} className="accent-[var(--violet)]" /> Published
          </label>
          <button disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : (
        <div className="space-y-3">
          {posts.map((p) => (
            <div key={p.id} className="glass rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold">{p.title}</div>
                  <div className="mt-1 text-xs text-[var(--muted)]">{new Date(p.created_at).toLocaleDateString()} · {p.slug}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${p.published ? "bg-[var(--emerald)]/15 text-[var(--emerald)]" : "bg-white/10 text-[var(--muted)]"}`}>
                    {p.published ? "published" : "draft"}
                  </span>
                  <button onClick={() => openEdit(p)} className="rounded px-2 py-1 text-xs text-[var(--violet)] hover:bg-white/5">Edit</button>
                  <button onClick={() => remove(p.id)} className="rounded px-2 py-1 text-xs text-red-300 hover:bg-white/5">Delete</button>
                </div>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--muted)]">{p.content}</p>
            </div>
          ))}
          {posts.length === 0 && (
            <div className="glass rounded-xl p-8 text-center text-sm text-[var(--muted)]">No posts yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
