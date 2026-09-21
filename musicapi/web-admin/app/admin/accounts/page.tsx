"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Account {
  id: string;
  label: string;
  type: string;
  is_active: boolean;
  created_at: string;
  live_plan: string;
  live_credits: number;
  live_models: string[];
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ label: "", type: "free", client_cookie: "", device_id: "" });
  const [saving, setSaving] = useState(false);

  const [rules, setRules] = useState<{ id: string; model: string; policy: string }[]>([]);
  const [ruleForm, setRuleForm] = useState({ model: "", policy: "prefer_free" });
  const [savingRule, setSavingRule] = useState(false);

  function load() {
    setLoading(true);
    apiFetch<{ accounts: Account[] }>("/admin/accounts")
      .then((r) => setAccounts(r.accounts))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }

  function loadRules() {
    apiFetch<{ id: string; model: string; policy: string }[]>("/admin/routing")
      .then(setRules)
      .catch(() => {});
  }

  useEffect(() => { load(); loadRules(); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiFetch("/admin/accounts", { method: "POST", body: JSON.stringify(form) });
      setShowForm(false);
      setForm({ label: "", type: "free", client_cookie: "", device_id: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setSaving(false);
    }
  }

  async function saveRule(e: React.FormEvent) {
    e.preventDefault();
    setSavingRule(true);
    setError("");
    try {
      await apiFetch("/admin/routing", { method: "POST", body: JSON.stringify(ruleForm) });
      setRuleForm({ model: "", policy: "prefer_free" });
      loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rule");
    } finally {
      setSavingRule(false);
    }
  }

  async function deleteRule(id: string) {
    setError("");
    try {
      await apiFetch(`/admin/routing/${id}`, { method: "DELETE" });
      loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete rule");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Suno Accounts</h1>
          <p className="text-sm text-[var(--muted)]">Worker accounts used to serve generation requests</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">
          {showForm ? "Cancel" : "Add account"}
        </button>
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {showForm && (
        <form onSubmit={submit} className="glass space-y-4 rounded-xl p-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Label</label>
              <input
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
                placeholder="account-1"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Type</label>
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              >
                <option value="free">Free</option>
                <option value="paid">Paid</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Client cookie</label>
              <input
                value={form.client_cookie}
                onChange={(e) => setForm({ ...form, client_cookie: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
                placeholder="eyJ..."
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Device ID</label>
              <input
                value={form.device_id}
                onChange={(e) => setForm({ ...form, device_id: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
                placeholder="uuid"
              />
            </div>
          </div>
          <button disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save account"}
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
                <th className="px-4 py-3">Label</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Credits</th>
                <th className="px-4 py-3">Models</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{a.label}</td>
                  <td className="px-4 py-3 capitalize">{a.type}</td>
                  <td className="px-4 py-3 capitalize">{a.live_plan}</td>
                  <td className="px-4 py-3">{a.live_credits}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{a.live_models.join(", ") || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={a.is_active ? "text-[var(--emerald)]" : "text-red-300"}>
                      {a.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="glass rounded-xl p-5">
        <h2 className="text-sm font-semibold">Routing rules</h2>
        <p className="mt-1 text-xs text-[var(--muted)]">Map a model key (e.g. chirp-crow) to an account policy.</p>

        <form onSubmit={saveRule} className="mt-3 flex flex-wrap gap-2">
          <input
            value={ruleForm.model}
            onChange={(e) => setRuleForm({ ...ruleForm, model: e.target.value })}
            placeholder="Model key (e.g. chirp-crow)"
            className="rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
          />
          <select
            value={ruleForm.policy}
            onChange={(e) => setRuleForm({ ...ruleForm, policy: e.target.value })}
            className="rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
          >
            <option value="prefer_free">prefer_free</option>
            <option value="paid_only">paid_only</option>
            <option value="any">any</option>
          </select>
          <button disabled={savingRule} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {savingRule ? "Saving…" : "Add rule"}
          </button>
        </form>

        <div className="mt-4 space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2 text-sm">
              <span className="font-mono text-xs">{r.model}</span>
              <span className="flex items-center gap-3">
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-[var(--muted)]">{r.policy}</span>
                <button onClick={() => deleteRule(r.id)} className="text-xs text-red-300 hover:underline">Delete</button>
              </span>
            </div>
          ))}
          {rules.length === 0 && <p className="text-xs text-[var(--muted)]">No custom rules — using defaults.</p>}
        </div>
      </div>
    </div>
  );
}
