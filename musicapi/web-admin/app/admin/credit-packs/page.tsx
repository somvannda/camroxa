"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface PackRow {
  id: string;
  amount: number;
  price: string;
  currency: string;
  is_active: boolean;
}

const EMPTY_FORM = { amount: "", price: "", currency: "USD", is_active: true };

export default function CreditPacksPage() {
  const [rows, setRows] = useState<PackRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  function load() {
    setLoading(true);
    apiFetch<PackRow[]>("/admin/credit-packs")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = JSON.stringify({
        amount: Number(form.amount),
        price: Number(form.price),
        currency: form.currency || "USD",
        is_active: form.is_active,
      });
      if (editingId) {
        await apiFetch(`/admin/credit-packs/${editingId}`, { method: "PUT", body });
      } else {
        await apiFetch("/admin/credit-packs", { method: "POST", body });
      }
      resetForm();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
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

  async function remove(id: string) {
    setError("");
    try {
      await apiFetch(`/admin/credit-packs/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Credit Packs</h1>
          <p className="text-sm text-[var(--muted)]">Packs users can buy — credits (amount) for a price</p>
        </div>
        <button onClick={() => (showForm ? resetForm() : setShowForm(true))} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">
          {showForm ? "Cancel" : "Add pack"}
        </button>
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {showForm && (
        <form onSubmit={submit} className="glass grid grid-cols-1 gap-4 rounded-xl p-5 md:grid-cols-4">
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Credits (amount)</label>
            <input
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="1000"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Price</label>
            <input
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="5.00"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Currency</label>
            <input
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="USD"
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Active
            </label>
            <button disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {saving ? "Saving…" : editingId ? "Update" : "Save"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Credits</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Currency</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{r.amount}</td>
                  <td className="px-4 py-3">{r.price}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.currency}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.is_active ? "Active" : "Inactive"}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => edit(r)} className="mr-2 rounded px-2 py-1 text-xs text-[var(--violet)] hover:bg-white/5">Edit</button>
                    <button onClick={() => remove(r.id)} className="rounded px-2 py-1 text-xs text-red-300 hover:bg-white/5">Delete</button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-[var(--muted)]">No credit packs.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
