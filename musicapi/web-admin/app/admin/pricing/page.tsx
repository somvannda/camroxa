"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface PricingRow {
  id: string;
  endpoint: string;
  model: string | null;
  credit_cost: number;
}

export default function PricingPage() {
  const [rows, setRows] = useState<PricingRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ endpoint: "", model: "", credit_cost: "" });
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    apiFetch<PricingRow[]>("/admin/pricing")
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
      await apiFetch("/admin/pricing", {
        method: "POST",
        body: JSON.stringify({
          endpoint: form.endpoint,
          model: form.model || null,
          credit_cost: Number(form.credit_cost),
        }),
      });
      setShowForm(false);
      setForm({ endpoint: "", model: "", credit_cost: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function edit(r: PricingRow) {
    setForm({ endpoint: r.endpoint, model: r.model ?? "", credit_cost: String(r.credit_cost) });
    setShowForm(true);
  }

  async function remove(id: string) {
    setError("");
    try {
      await apiFetch(`/admin/pricing/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pricing</h1>
          <p className="text-sm text-[var(--muted)]">Credit cost per endpoint — used to charge each generation</p>
        </div>
        <button onClick={() => { setShowForm((v) => !v); if (showForm) setForm({ endpoint: "", model: "", credit_cost: "" }); }} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">
          {showForm ? "Cancel" : "Set / add price"}
        </button>
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {showForm && (
        <form onSubmit={submit} className="glass grid grid-cols-1 gap-4 rounded-xl p-5 md:grid-cols-3">
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Endpoint</label>
            <input
              value={form.endpoint}
              onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="music / lyrics / extend / cover / stems"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Model (optional)</label>
            <input
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="chirp-v5"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">Credit cost</label>
            <input
              value={form.credit_cost}
              onChange={(e) => setForm({ ...form, credit_cost: e.target.value })}
              className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              placeholder="9"
            />
          </div>
          <button disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Endpoint</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Credit cost</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{r.endpoint}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.model ?? "—"}</td>
                  <td className="px-4 py-3">{r.credit_cost}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => edit(r)} className="mr-2 rounded px-2 py-1 text-xs text-[var(--violet)] hover:bg-white/5">Edit</button>
                    <button onClick={() => remove(r.id)} className="rounded px-2 py-1 text-xs text-red-300 hover:bg-white/5">Delete</button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-[var(--muted)]">No pricing set.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
