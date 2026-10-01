"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  created_at: string;
  credits: number;
  key_count: number;
  request_count: number;
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [limitsFor, setLimitsFor] = useState<User | null>(null);
  const [rpm, setRpm] = useState("");
  const [rpd, setRpd] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<User[]>("/admin/users")
      .then(setUsers)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  async function adjustCredits(u: User) {
    const raw = window.prompt(`Add/remove credits for ${u.email} (e.g. 100 or -50):`);
    if (!raw) return;
    const amount = Number(raw);
    if (Number.isNaN(amount) || amount === 0) return;
    setError("");
    try {
      await apiFetch(`/admin/users/${u.id}/credits`, { method: "POST", body: JSON.stringify({ amount }) });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to adjust credits");
    }
  }

  async function toggleStatus(u: User) {
    const next = u.status === "active" ? "suspended" : "active";
    setError("");
    try {
      await apiFetch(`/admin/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    }
  }

  async function openLimits(u: User) {
    setError("");
    setLimitsFor(u);
    setRpm("");
    setRpd("");
    try {
      const data = await apiFetch<{ requests_per_minute: number | null; requests_per_day: number | null }>(
        `/admin/users/${u.id}/rate-limits`,
      );
      setRpm(data.requests_per_minute?.toString() ?? "");
      setRpd(data.requests_per_day?.toString() ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load rate limits");
    }
  }

  async function saveLimits() {
    if (!limitsFor) return;
    const parse = (v: string): number | null | undefined => {
      if (v.trim() === "") return null;
      const n = Number(v);
      if (!Number.isInteger(n) || n <= 0) return undefined;
      return n;
    };
    const perMinute = parse(rpm);
    const perDay = parse(rpd);
    if (perMinute === undefined || perDay === undefined) {
      setError("Limits must be positive whole numbers, or left empty to clear.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/admin/users/${limitsFor.id}/rate-limits`, {
        method: "PUT",
        body: JSON.stringify({ requests_per_minute: perMinute, requests_per_day: perDay }),
      });
      setLimitsFor(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save rate limits");
    } finally {
      setSaving(false);
    }
  }

  const filtered = users.filter((u) => u.email.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Users</h1>
          <p className="text-sm text-[var(--muted)]">Manage credits and account status</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by email…"
          className="rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
        />
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Credits</th>
                <th className="px-4 py-3">Requests</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.email}</div>
                    {u.name && <div className="text-xs text-[var(--muted)]">{u.name}</div>}
                  </td>
                  <td className="px-4 py-3 capitalize">{u.role}</td>
                  <td className="px-4 py-3">{u.credits}</td>
                  <td className="px-4 py-3">{u.request_count}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${u.status === "active" ? "bg-[var(--emerald)]/15 text-[var(--emerald)]" : "bg-red-500/15 text-red-300"}`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => adjustCredits(u)} className="mr-2 rounded px-2 py-1 text-xs text-[var(--violet)] hover:bg-white/5">Credits</button>
                    <button onClick={() => openLimits(u)} className="mr-2 rounded px-2 py-1 text-xs text-[var(--violet)] hover:bg-white/5">Limits</button>
                    <button onClick={() => toggleStatus(u)} className="rounded px-2 py-1 text-xs text-red-300 hover:bg-white/5">
                      {u.status === "active" ? "Ban" : "Unban"}
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">No users found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {limitsFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="glass w-full max-w-sm rounded-xl p-5">
            <h2 className="text-lg font-semibold">Rate limits</h2>
            <p className="mb-4 text-sm text-[var(--muted)]">{limitsFor.email}</p>
            <label className="mb-3 block text-sm">
              <span className="mb-1 block text-[var(--muted)]">Requests per minute</span>
              <input
                value={rpm}
                onChange={(e) => setRpm(e.target.value)}
                inputMode="numeric"
                placeholder="Unlimited"
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-[var(--muted)]">Requests per day</span>
              <input
                value={rpd}
                onChange={(e) => setRpd(e.target.value)}
                inputMode="numeric"
                placeholder="Unlimited"
                className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
              />
            </label>
            <p className="mt-3 text-xs text-[var(--muted)]">Leave a field empty for no limit.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setLimitsFor(null)}
                className="rounded-lg px-3 py-2 text-sm text-[var(--muted)] hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={saveLimits}
                disabled={saving}
                className="rounded-lg bg-[var(--violet)] px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
