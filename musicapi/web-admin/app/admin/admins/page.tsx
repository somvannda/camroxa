"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateOnly } from "@/lib/format";

interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  status: string;
  created_at: string;
  has_google: boolean;
  has_password: boolean;
}

const EMPTY_FORM = { email: "", name: "", password: "" };
type Pending = { admin: AdminUser; action: "suspend" | "demote" | "activate" };

export default function AdminsPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useResource<AdminUser[]>(() =>
    apiFetch<AdminUser[]>("/admin/admins"),
  );
  const admins = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/admin/admins", { method: "POST", body: JSON.stringify(form) });
      toast.success("Administrator created.");
      setForm(EMPTY_FORM);
      setShowForm(false);
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create administrator");
    } finally {
      setSaving(false);
    }
  }

  async function apply(a: AdminUser, action: Pending["action"]) {
    const body =
      action === "demote"
        ? { role: "user" }
        : { status: action === "suspend" ? "suspended" : "active" };
    try {
      await apiFetch(`/admin/admins/${a.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      toast.success(
        action === "demote"
          ? "Administrator demoted to user."
          : action === "suspend"
            ? "Administrator suspended."
            : "Administrator reactivated.",
      );
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update administrator");
    }
  }

  const confirmMessage = (p: Pending): string => {
    if (p.action === "demote") {
      return `Demote ${p.admin.email} to a regular user? They immediately lose console access.`;
    }
    if (p.action === "suspend") {
      return `Suspend ${p.admin.email}? They lose console access until reactivated.`;
    }
    return `Reactivate ${p.admin.email}?`;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administrators"
        description="Console operators. Remove access before offboarding."
        actions={
          <Button onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "Add administrator"}
          </Button>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={create} className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Field label="Email" htmlFor="admin-email">
              <Input
                id="admin-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="ops@example.com"
              />
            </Field>
            <Field label="Name (optional)" htmlFor="admin-name">
              <Input
                id="admin-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ops"
              />
            </Field>
            <Field label="Password (min 8 chars)" htmlFor="admin-password">
              <Input
                id="admin-password"
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
              />
            </Field>
            <div className="flex items-end">
              <Button type="submit" disabled={saving}>
                {saving ? "Creating…" : "Create"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loading ? (
        <LoadingState />
      ) : admins.length === 0 ? (
        <EmptyState title="No administrators found." />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Email</th>
                <th scope="col" className="px-4 py-3">Name</th>
                <th scope="col" className="px-4 py-3">Login</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">Created</th>
                <th scope="col" className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((a) => (
                <tr key={a.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{a.email}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{a.name ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {[a.has_google ? "Google" : null, a.has_password ? "Password" : null]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={a.status === "active" ? "success" : "danger"}>{a.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {dateOnly(a.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setPending({
                          admin: a,
                          action: a.status === "active" ? "suspend" : "activate",
                        })
                      }
                    >
                      {a.status === "active" ? "Suspend" : "Activate"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-300"
                      onClick={() => setPending({ admin: a, action: "demote" })}
                    >
                      Demote
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!pending}
        title={
          pending?.action === "demote"
            ? "Demote administrator"
            : pending?.action === "activate"
              ? "Reactivate administrator"
              : "Suspend administrator"
        }
        danger={pending?.action !== "activate"}
        confirmLabel={
          pending?.action === "demote"
            ? "Demote"
            : pending?.action === "activate"
              ? "Activate"
              : "Suspend"
        }
        message={pending ? confirmMessage(pending) : ""}
        onConfirm={() =>
          pending ? apply(pending.admin, pending.action) : Promise.resolve()
        }
        onClose={() => setPending(null)}
      />
    </div>
  );
}
