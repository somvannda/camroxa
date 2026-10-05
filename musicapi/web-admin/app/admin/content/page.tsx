"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateOnly } from "@/lib/format";

interface Post {
  id: string;
  title: string;
  slug: string;
  content: string;
  published: boolean;
  created_at: string;
}

const EMPTY_FORM = { title: "", slug: "", content: "", published: false };

export default function ContentPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useResource<Post[]>(() =>
    apiFetch<Post[]>("/admin/content"),
  );
  const posts = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Post | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Post | null>(null);

  function openNew() {
    setEditing(null);
    setForm(EMPTY_FORM);
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
    try {
      const body = JSON.stringify({ ...form, slug: form.slug || undefined });
      if (editing) await apiFetch(`/admin/content/${editing.id}`, { method: "PUT", body });
      else await apiFetch("/admin/content", { method: "POST", body });
      toast.success(editing ? "Post updated." : "Post created.");
      setShowForm(false);
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function remove(p: Post) {
    await apiFetch(`/admin/content/${p.id}`, { method: "DELETE" });
    toast.success("Post deleted.");
    void reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Updates"
        description="Blog posts shown in the user panel"
        actions={
          <Button onClick={() => (showForm ? setShowForm(false) : openNew())}>
            {showForm ? "Cancel" : "New post"}
          </Button>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Title" htmlFor="post-title">
                <Input
                  id="post-title"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="API update title"
                />
              </Field>
              <Field label="Slug (optional)" htmlFor="post-slug">
                <Input
                  id="post-slug"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="my-update"
                />
              </Field>
            </div>
            <Field label="Content" htmlFor="post-content">
              <Textarea
                id="post-content"
                rows={5}
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                placeholder="Update details…"
              />
            </Field>
            <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <input
                type="checkbox"
                checked={form.published}
                onChange={(e) => setForm({ ...form, published: e.target.checked })}
              />{" "}
              Published
            </label>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </form>
        </Card>
      )}

      {loading ? (
        <LoadingState />
      ) : posts.length === 0 ? (
        <EmptyState title="No posts yet." description="Publish an API update for your users." />
      ) : (
        <div className="space-y-3">
          {posts.map((p) => (
            <Card key={p.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="font-semibold">{p.title}</div>
                  <div className="mt-1 text-xs text-[var(--muted)]">
                    {dateOnly(p.created_at)} · {p.slug}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={p.published ? "success" : "neutral"}>
                    {p.published ? "published" : "draft"}
                  </Badge>
                  <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-red-300"
                    onClick={() => setPendingDelete(p)}
                  >
                    Delete
                  </Button>
                </div>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--muted)]">{p.content}</p>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete post"
        danger
        confirmLabel="Delete"
        message={pendingDelete ? `Delete “${pendingDelete.title}”?` : ""}
        onConfirm={() => (pendingDelete ? remove(pendingDelete) : Promise.resolve())}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}
