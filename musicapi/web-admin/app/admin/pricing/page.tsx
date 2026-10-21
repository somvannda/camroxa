"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { num } from "@/lib/format";

interface PricingRow {
  id: string;
  endpoint: string;
  model: string | null;
  credit_cost: number;
}

const EMPTY_FORM = { endpoint: "", model: "", credit_cost: "" };

export default function PricingPage() {
  const toast = useToast();
  const { data, loading, error, reload } = useResource<PricingRow[]>(() =>
    apiFetch<PricingRow[]>("/admin/pricing"),
  );
  const rows = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PricingRow | null>(null);

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
        endpoint: form.endpoint,
        model: form.model || null,
        credit_cost: Number(form.credit_cost),
      });
      if (editingId) await apiFetch(`/admin/pricing/${editingId}`, { method: "PUT", body });
      else await apiFetch("/admin/pricing", { method: "POST", body });
      toast.success(editingId ? "Pricing updated." : "Pricing added.");
      resetForm();
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function edit(r: PricingRow) {
    setEditingId(r.id);
    setForm({ endpoint: r.endpoint, model: r.model ?? "", credit_cost: String(r.credit_cost) });
    setShowForm(true);
  }

  async function remove(r: PricingRow) {
    await apiFetch(`/admin/pricing/${r.id}`, { method: "DELETE" });
    toast.success("Pricing deleted.");
    void reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pricing"
        description="Credit cost per endpoint — used to charge each generation and download"
        actions={
          <Button onClick={() => (showForm ? resetForm() : setShowForm(true))}>
            {showForm ? "Cancel" : "Set / add price"}
          </Button>
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={submit} className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Field label="Endpoint" htmlFor="pricing-endpoint">
              <Input
                id="pricing-endpoint"
                value={form.endpoint}
                onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                placeholder="music / lyrics / extend"
              />
            </Field>
            <Field label="Model (optional)" htmlFor="pricing-model">
              <Input
                id="pricing-model"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                placeholder="chirp-hawk"
              />
            </Field>
            <Field label="Credit cost" htmlFor="pricing-cost">
              <Input
                id="pricing-cost"
                value={form.credit_cost}
                onChange={(e) => setForm({ ...form, credit_cost: e.target.value })}
                placeholder="9"
              />
            </Field>
            <div className="flex items-end">
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
        <EmptyState title="No pricing set." description="Add a credit cost per endpoint." />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Endpoint</th>
                <th scope="col" className="px-4 py-3">Model</th>
                <th scope="col" className="px-4 py-3 text-right">Credit cost</th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{r.endpoint}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.model ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(r.credit_cost)}</td>
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
        title="Delete pricing row"
        danger
        confirmLabel="Delete"
        message={
          pendingDelete
            ? `Delete the price for “${pendingDelete.endpoint}”${
                pendingDelete.model ? ` (${pendingDelete.model})` : ""
              }?`
            : ""
        }
        onConfirm={() => (pendingDelete ? remove(pendingDelete) : Promise.resolve())}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}
