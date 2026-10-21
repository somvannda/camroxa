"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime } from "@/lib/format";

interface TemplateRow {
  id: string;
  name: string;
  subject: string;
  locale: string;
  var_count: number;
  is_active: boolean;
  send_mode: string;
  updated_at: string;
}

interface TemplateDetail {
  id: string;
  name: string;
  subject: string;
  html: string;
  text: string | null;
  locale: string;
  vars: string[];
  is_active: boolean;
}

interface PreviewResponse {
  subject: string;
  html: string;
  text: string;
  vars: Record<string, string>;
  missing: string[];
}

const EMPTY = {
  name: "",
  locale: "en",
  subject: "",
  html: "",
  text: "",
};

/** Starter body: the pack-ladder email, driven entirely by database values. */
const STARTER_HTML = `<div style="max-width:560px;margin:0 auto;padding:24px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#111827;">
  <h1 style="font-size:22px;margin:0 0 12px;">More songs, same budget</h1>
  <p style="font-size:14px;line-height:1.65;margin:0 0 16px;">
    Hi {{first_name}}, you have {{credits}} credits left. Here is what each pack buys
    at the current generation price:
  </p>
  {{packs_html}}
  <p style="font-size:14px;line-height:1.65;margin:16px 0;">
    The {{best_pack_price}} pack is the best value: {{best_pack_songs}} songs,
    {{best_pack_bonus}}% more credits per dollar than the smallest pack.
  </p>
  <a href="{{app_url}}/dashboard" style="display:inline-block;background:#7466F1;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600;">
    Top up credits
  </a>
  <p style="font-size:12px;color:#6b7280;margin-top:24px;">
    <a href="{{unsubscribe_url}}" style="color:#6b7280;">Unsubscribe</a>
  </p>
</div>`;

export default function MailTemplatesPage() {
  const toast = useToast();
  const list = useResource<{ rows: TemplateRow[] }>(() =>
    apiFetch<{ rows: TemplateRow[] }>("/admin/mail/templates"),
  );

  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  function startNew() {
    setEditingId(null);
    setForm({ ...EMPTY, html: STARTER_HTML });
    setPreview(null);
  }

  async function edit(row: TemplateRow) {
    try {
      const detail = await apiFetch<TemplateDetail>(`/admin/mail/templates/${row.id}`);
      setEditingId(detail.id);
      setForm({
        name: detail.name,
        locale: detail.locale,
        subject: detail.subject,
        html: detail.html,
        text: detail.text ?? "",
      });
      setPreview(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load template");
    }
  }

  async function runPreview() {
    setPreviewing(true);
    try {
      const result = await apiFetch<PreviewResponse>("/admin/mail/templates/preview", {
        method: "POST",
        body: JSON.stringify({ subject: form.subject, html: form.html, text: form.text }),
      });
      setPreview(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewing(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const body = JSON.stringify({
        name: form.name,
        locale: form.locale,
        subject: form.subject,
        html: form.html,
        text: form.text || null,
      });
      if (editingId) {
        await apiFetch(`/admin/mail/templates/${editingId}`, { method: "PUT", body });
        toast.success("Template updated.");
      } else {
        await apiFetch("/admin/mail/templates", { method: "POST", body });
        toast.success("Template created.");
      }
      setEditingId(null);
      setForm(EMPTY);
      setPreview(null);
      void list.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function remove(row: TemplateRow) {
    if (!window.confirm(`Delete "${row.name}"?`)) return;
    try {
      await apiFetch(`/admin/mail/templates/${row.id}`, { method: "DELETE" });
      toast.success("Template deleted.");
      void list.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mail templates"
        description="Subject and body with {{variables}}. Preview renders real numbers from your own account."
        actions={<Button onClick={startNew}>New template</Button>}
      />

      {list.error && <ErrorState message={list.error} onRetry={list.reload} />}
      {list.loading && <LoadingState />}

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">{editingId ? "Edit template" : "New template"}</h2>
        <form onSubmit={save} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
            <Field label="Name">
              <Input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Pack ladder upsell"
              />
            </Field>
            <Field label="Locale">
              <Select
                value={form.locale}
                onChange={(e) => setForm({ ...form, locale: e.target.value })}
              >
                <option value="en">en</option>
                <option value="km">km</option>
              </Select>
            </Field>
          </div>

          <Field label="Subject" hint="Variables allowed here too, e.g. Hi {{first_name}}.">
            <Input
              required
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
            />
          </Field>

          <Field
            label="HTML body"
            hint="Available: {{first_name}} {{name}} {{email}} {{credits}} {{songs}} {{app_url}} {{unsubscribe_url}} {{packs_html}} {{best_pack_price}} {{best_pack_songs}} {{best_pack_bonus}}"
          >
            <Textarea
              required
              rows={16}
              className="font-mono text-xs"
              value={form.html}
              onChange={(e) => setForm({ ...form, html: e.target.value })}
            />
          </Field>

          <Field label="Plain-text body (optional)" hint="Generated from the HTML when left blank.">
            <Textarea
              rows={5}
              className="font-mono text-xs"
              value={form.text}
              onChange={(e) => setForm({ ...form, text: e.target.value })}
            />
          </Field>

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : editingId ? "Save changes" : "Create template"}
            </Button>
            <Button variant="secondary" onClick={runPreview} disabled={previewing}>
              {previewing ? "Rendering..." : "Preview"}
            </Button>
            {editingId && (
              <Button
                variant="ghost"
                onClick={() => {
                  setEditingId(null);
                  setForm(EMPTY);
                  setPreview(null);
                }}
              >
                Cancel
              </Button>
            )}
          </div>
        </form>

        {preview && (
          <div className="mt-4 space-y-2">
            <p className="text-sm">
              <span className="text-[var(--muted)]">Subject: </span>
              {preview.subject}
            </p>
            {preview.missing.length > 0 && (
              <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                Unknown variables (left as-is when sent): {preview.missing.join(", ")}
              </p>
            )}
            <iframe
              title="Template preview"
              srcDoc={preview.html}
              sandbox=""
              className="h-[520px] w-full rounded-lg border border-[var(--border)] bg-white"
            />
          </div>
        )}
      </Card>

      {list.data && list.data.rows.length === 0 && (
        <EmptyState
          title="No templates yet"
          description="Start with the pack ladder: it explains why bigger packs are cheaper using live prices."
          action={<Button onClick={startNew}>Create the first one</Button>}
        />
      )}

      {list.data && list.data.rows.length > 0 && (
        <Card className="p-5">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Subject</th>
                <th className="py-2 pr-3 font-medium">Vars</th>
                <th className="py-2 pr-3 font-medium">Updated</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {list.data.rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="py-2 pr-3">
                    {row.name}
                    {row.send_mode === "manual" && (
                      <span
                        className="ml-2 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
                        title="Campaign only — cannot be attached to an automation"
                      >
                        manual
                      </span>
                    )}
                    {!row.is_active && (
                      <span className="ml-2 text-[11px] text-[var(--muted)]">inactive</span>
                    )}
                  </td>
                  <td className="max-w-[20rem] truncate py-2 pr-3" title={row.subject}>
                    {row.subject}
                  </td>
                  <td className="py-2 pr-3">{row.var_count}</td>
                  <td className="py-2 pr-3 text-xs text-[var(--muted)]">
                    {dateTime(row.updated_at)}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <Button size="sm" variant="ghost" onClick={() => void edit(row)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => void remove(row)}>
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
