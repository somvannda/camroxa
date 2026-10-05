"use client";

import { Fragment, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
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

interface KeyPage {
  rows: AdminKey[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 50;

function KeysInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [qInput, setQInput] = useState(params.get("q") ?? "");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [page, setPage] = useState(() => Math.max(1, Number(params.get("page")) || 1));

  const { data, loading, error, reload } = useResource<KeyPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (q) p.set("q", q);
      return apiFetch<KeyPage>(`/admin/keys?${p.toString()}`);
    },
    [page, q],
  );

  // Reflect the search in the URL so a view can be bookmarked/shared.
  useEffect(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (page > 1) p.set("page", String(page));
    const qs = p.toString();
    router.replace(qs ? `/admin/keys?${qs}` : "/admin/keys", { scroll: false });
  }, [q, page, router]);

  const keys = useMemo(() => data?.rows ?? [], [data]);
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Group keys by owner so the account-level (pooled) balance is shown once per
  // user. The per-key balance is only where funds physically landed — a key
  // showing 0 can still spend the whole account balance.
  const groups = useMemo<KeyGroup[]>(() => {
    const byUser = new Map<string, KeyGroup>();
    for (const k of keys) {
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
  }, [keys]);

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setQ(qInput.trim());
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Keys"
        description="Every key across all accounts. Credits are pooled per account — any key spends the owner's total."
      />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="Search" htmlFor="key-q" className="w-full sm:w-72">
          <Input
            id="key-q"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="email, prefix or name…"
          />
        </Field>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : keys.length === 0 ? (
        <EmptyState
          title="No keys found."
          description={total ? "No rows match your search." : undefined}
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

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-[var(--muted)]">
          <span>{num(total)} total</span>
          <span className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <span>
              Page {page} / {pages}
            </span>
            <Button
              size="sm"
              variant="secondary"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next
            </Button>
          </span>
        </div>
      )}
    </div>
  );
}

export default function KeysPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <KeysInner />
    </Suspense>
  );
}
