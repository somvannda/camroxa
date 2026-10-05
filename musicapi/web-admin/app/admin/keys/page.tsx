"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AdminKey {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  is_active: boolean;
  user_id: string;
  email: string;
  account_credits: number;
  key_count: number;
}

interface KeyGroup {
  userId: string;
  email: string;
  accountCredits: number;
  keys: AdminKey[];
}

export default function KeysPage() {
  const [keys, setKeys] = useState<AdminKey[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    apiFetch<AdminKey[]>("/admin/keys")
      .then(setKeys)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const needle = q.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      keys.filter(
        (k) =>
          k.email.toLowerCase().includes(needle) ||
          k.key_prefix.toLowerCase().includes(needle) ||
          (k.name ?? "").toLowerCase().includes(needle),
      ),
    [keys, needle],
  );

  // Group keys by owner so the account-level (pooled) balance is shown once per
  // user. The per-key `credits` are only where the funds physically landed — a
  // key showing 0 can still spend the whole account balance.
  const groups = useMemo<KeyGroup[]>(() => {
    const byUser = new Map<string, KeyGroup>();
    for (const k of filtered) {
      const existing = byUser.get(k.user_id);
      if (existing) {
        existing.keys.push(k);
      } else {
        byUser.set(k.user_id, {
          userId: k.user_id,
          email: k.email,
          accountCredits: Number(k.account_credits ?? 0),
          keys: [k],
        });
      }
    }
    return Array.from(byUser.values());
  }, [filtered]);

  const totalKeys = filtered.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-sm text-[var(--muted)]">
            Every key across all accounts. Credits are pooled per account — any key spends the owner&apos;s total.
          </p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by email, prefix or name…"
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
                <th className="px-4 py-3">Key</th>
                <th className="px-4 py-3">Prefix</th>
                <th className="px-4 py-3 text-right">Key Balance</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <Fragment key={g.userId}>
                  <tr className="border-t border-[var(--border)] bg-white/[0.03]">
                    <td colSpan={2} className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{g.email}</span>
                        <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-[var(--muted)]">
                          {g.keys.length} {g.keys.length === 1 ? "key" : "keys"}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-xs text-[var(--muted)]">Account total </span>
                      <span className="font-semibold text-[var(--emerald)]">{g.accountCredits}</span>
                    </td>
                    <td className="px-4 py-2.5" />
                  </tr>
                  {g.keys.map((k) => (
                    <tr key={k.id} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 pl-8 text-[var(--muted)]">{k.name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">{k.key_prefix}…</td>
                      <td className="px-4 py-3 text-right tabular-nums">{k.credits}</td>
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
                </Fragment>
              ))}
              {totalKeys === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-[var(--muted)]">
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
