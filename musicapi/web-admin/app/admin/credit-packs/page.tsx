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
import { num } from "@/lib/format";

interface PackRow {
  id: string;
  amount: number;
  price: string;
  currency: string;
  is_active: boolean;
}

const EMPTY_FORM = { amount: "", price: "", currency: "USD", is_active: true };

export default function CreditPacksPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useResource<PackRow[]>(() =>
    apiFetch<PackRow[]>("/admin/credit-packs"),
  );
  const rows = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PackRow | null>(null);

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const body = JSON.stringify({
        amount: Number(form.amount),
        price: Number(form.price),
        currency: form.currency || "USD",
        is_active: form.is_active,
      });
      if (editingId) await apiFetch(`/admin/credit-packs/${editingId}`, { method: "PUT", body });
      else await apiFetch("/admin/credit-packs", { method: "POST", body });
      toast.success(editingId ? "Pack updated." : "Pack added.");
      resetForm();
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function edit(r: PackRow) {
    setEditingId(r.id);
    setForm({
      amount: String(r.amount),
      price: String(r.price),
      currency: r.currency,
      is_active: r.is_active,
    });
    setShowForm(true);
  }

  async function remove(r: PackRow) {
    await apiFetch(`/admin/credit-packs/${r.id}`, { method: "DELETE" });
    toast.success("Pack deleted.");
    void reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Credit Packs"
        description="Packs users can buy — credits (amount) for a price"
        actions={
          <Button onClick={() => (showForm ? resetForm() : setShowForm(true))}>
            {showForm ? "Cancel" : "Add pack"}
          </Button>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Field label="Credits (amount)" htmlFor="pack-amount">
              <Input
                id="pack-amount"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                placeholder="1000"
              />
            </Field>
            <Field label="Price" htmlFor="pack-price">
              <Input
                id="pack-price"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                placeholder="5.00"
              />
            </Field>
            <Field label="Currency" htmlFor="pack-currency">
              <Input
                id="pack-currency"
                value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value })}
                placeholder="USD"
              />
            </Field>
            <div className="flex items-end gap-4">
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                Active
              </label>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : editingId ? "Update" : "Save"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState title="No credit packs." description="Add a pack users can buy." />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
                <th scope="col" className="px-4 py-3">Price</th>
                <th scope="col" className="px-4 py-3">Currency</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 text-right font-medium tabular-nums">{num(r.amount)}</td>
                  <td className="px-4 py-3">{r.price}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.currency}</td>
                  <td className="px-4 py-3">
                    <Badge tone={r.is_active ? "success" : "neutral"}>
                      {r.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button size="sm" variant="ghost" onClick={() => edit(r)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-300"
                      onClick={() => setPendingDelete(r)}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete credit pack"
        danger
        confirmLabel="Delete"
        message={
          pendingDelete
            ? `Delete the ${pendingDelete.amount} credit pack (${pendingDelete.currency} ${pendingDelete.price})?`
            : ""
        }
        onConfirm={() => (pendingDelete ? remove(pendingDelete) : Promise.resolve())}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}
