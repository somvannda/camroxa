"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AdminKey {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  is_active: boolean;
  email: string;
}

export default function KeysPage() {
  const [keys, setKeys] = useState<AdminKey[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<AdminKey[]>("/admin/keys")
      .then(setKeys)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const needle = q.toLowerCase();
  const filtered = keys.filter(
    (k) => k.email.toLowerCase().includes(needle) || k.key_prefix.toLowerCase().includes(needle),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-sm text-[var(--muted)]">Every key across all accounts</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by email or prefix…"
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
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Prefix</th>
                <th className="px-4 py-3">Credits</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((k) => (
                <tr key={k.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3">{k.email}</td>
                  <td className="px-4 py-3">{k.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">{k.key_prefix}…</td>
                  <td className="px-4 py-3">{k.credits}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        k.is_active ? "bg-[var(--emerald)]/15 text-[var(--emerald)]" : "bg-red-500/15 text-red-300"
                      }`}
                    >
                      {k.is_active ? "active" : "inactive"}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-[var(--muted)]">
                    No keys found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
