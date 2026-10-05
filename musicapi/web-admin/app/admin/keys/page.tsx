"use client";

import { Fragment, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Field";
import { num } from "@/lib/format";

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
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useResource<AdminKey[]>(() =>
    apiFetch<AdminKey[]>("/admin/keys"),
  );
  const keys = useMemo(() => data ?? [], [data]);

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
  // user. The per-key balance is only where funds physically landed — a key
  // showing 0 can still spend the whole account balance.
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Keys"
        description="Every key across all accounts. Credits are pooled per account — any key spends the owner's total."
        actions={
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by email, prefix or name…"
            aria-label="Search API keys"
            className="w-full sm:w-72"
          />
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No keys found."
          description={keys.length ? "No rows match your search." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Key</th>
                <th scope="col" className="px-4 py-3">Prefix</th>
                <th scope="col" className="px-4 py-3 text-right">Key Balance</th>
                <th scope="col" className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <Fragment key={g.userId}>
                  <tr className="border-t border-[var(--border)] bg-white/[0.03]">
                    <td colSpan={2} className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{g.email}</span>
                        <Badge tone="neutral">
                          {g.keys.length} {g.keys.length === 1 ? "key" : "keys"}
                        </Badge>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-xs text-[var(--muted)]">Account total </span>
                      <span className="font-semibold text-[var(--emerald)]">
                        {num(g.accountCredits)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5" />
                  </tr>
                  {g.keys.map((k) => (
                    <tr key={k.id} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 pl-8 text-[var(--muted)]">{k.name}</td>
                      <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">
                        {k.key_prefix}…
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{num(k.credits)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={k.is_active ? "success" : "danger"}>
                          {k.is_active ? "active" : "inactive"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
