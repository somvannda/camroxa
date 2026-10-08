"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

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
  billed_count: number;
  free_count: number;
  failed_count: number;
  last_activity: string | null;
}

interface UserPage {
  rows: User[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 25;

function UsersInner() {
  const toast = useToast();
  const router = useRouter();
  const params = useSearchParams();

  const [qInput, setQInput] = useState(params.get("q") ?? "");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [statusFilter, setStatusFilter] = useState(params.get("status") ?? "");
  const [page, setPage] = useState(() => Math.max(1, Number(params.get("page")) || 1));

  const { data, loading, error, reload } = useResource<UserPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (q) p.set("q", q);
      if (statusFilter) p.set("status", statusFilter);
      return apiFetch<UserPage>(`/admin/users?${p.toString()}`);
    },
    [page, q, statusFilter],
  );

  // Reflect the filters in the URL so a view can be bookmarked/shared.
  useEffect(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (statusFilter) p.set("status", statusFilter);
    if (page > 1) p.set("page", String(page));
    const qs = p.toString();
    router.replace(qs ? `/admin/users?${qs}` : "/admin/users", { scroll: false });
  }, [q, statusFilter, page, router]);

  const users = data?.rows ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Credit adjustment dialog.
  const [creditsFor, setCreditsFor] = useState<User | null>(null);
  const [creditAmount, setCreditAmount] = useState("");
  const [savingCredits, setSavingCredits] = useState(false);

  // Suspend confirmation.
  const [pendingBan, setPendingBan] = useState<User | null>(null);

  // Rate-limit editor.
  const [limitsFor, setLimitsFor] = useState<User | null>(null);
  const [rpw, setRpw] = useState("");
  const [rpm, setRpm] = useState("");
  const [rpd, setRpd] = useState("");
  const [mcj, setMcj] = useState("");
  const [windowMs, setWindowMs] = useState(10_000);
  const [savingLimits, setSavingLimits] = useState(false);

  async function submitCredits(e: React.FormEvent) {
    e.preventDefault();
    if (!creditsFor) return;
    const amount = Number(creditAmount);
    if (Number.isNaN(amount) || amount === 0) {
      toast.error("Enter a non-zero credit amount (e.g. 100 or -50).");
      return;
    }
    setSavingCredits(true);
    try {
      await apiFetch(`/admin/users/${creditsFor.id}/credits`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      });
      toast.success(`${amount > 0 ? "Added" : "Removed"} ${Math.abs(amount)} credits.`);
      setCreditsFor(null);
      setCreditAmount("");
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to adjust credits");
    } finally {
      setSavingCredits(false);
    }
  }

  async function setStatus(u: User, next: "active" | "suspended") {
    try {
      await apiFetch(`/admin/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      toast.success(next === "active" ? "User reactivated." : "User suspended.");
      void reload();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to update status");
    }
  }

  async function openLimits(u: User) {
    setLimitsFor(u);
    setRpw("");
    setRpm("");
    setRpd("");
    setMcj("");
    try {
      const d = await apiFetch<{
        requests_per_window: number | null;
        requests_per_minute: number | null;
        requests_per_day: number | null;
        max_concurrent_jobs: number | null;
        window_ms?: number;
      }>(`/admin/users/${u.id}/rate-limits`);
      setRpw(d.requests_per_window?.toString() ?? "");
      setRpm(d.requests_per_minute?.toString() ?? "");
      setRpd(d.requests_per_day?.toString() ?? "");
      setMcj(d.max_concurrent_jobs?.toString() ?? "");
      if (d.window_ms) setWindowMs(d.window_ms);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load rate limits");
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
    const perWindow = parse(rpw);
    const perMinute = parse(rpm);
    const perDay = parse(rpd);
    const maxConcurrent = parse(mcj);
    if (
      perWindow === undefined ||
      perMinute === undefined ||
      perDay === undefined ||
      maxConcurrent === undefined
    ) {
      toast.error("Limits must be positive whole numbers, or left empty to clear.");
      return;
    }
    setSavingLimits(true);
    try {
      await apiFetch(`/admin/users/${limitsFor.id}/rate-limits`, {
        method: "PUT",
        body: JSON.stringify({
          requests_per_window: perWindow,
          requests_per_minute: perMinute,
          requests_per_day: perDay,
          max_concurrent_jobs: maxConcurrent,
        }),
      });
      toast.success("Rate limits saved.");
      setLimitsFor(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save rate limits");
    } finally {
      setSavingLimits(false);
    }
  }

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setQ(qInput.trim());
  }

  async function exportCsv() {
    const p = new URLSearchParams({ format: "csv" });
    if (q) p.set("q", q);
    if (statusFilter) p.set("status", statusFilter);
    try {
      const res = await fetch(`/backend/admin/users?${p.toString()}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "users.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Manage credits and account status · Requests counts every API call, including free and failed"
        actions={
          <Button variant="secondary" onClick={exportCsv}>
            Export CSV
          </Button>
        }
      />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="Search" htmlFor="user-q" className="w-full sm:w-72">
          <Input
            id="user-q"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="email or name…"
          />
        </Field>
        <Field label="Status" htmlFor="user-status">
          <Select
            id="user-status"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="active">active</option>
            <option value="suspended">suspended</option>
          </Select>
        </Field>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : users.length === 0 ? (
        <EmptyState
          title="No users found."
          description={total ? "No rows match your filters." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Email</th>
                <th scope="col" className="px-4 py-3">Role</th>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
                <th scope="col" className="px-4 py-3 text-right">Requests</th>
                <th scope="col" className="px-4 py-3">Last active</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="cursor-pointer border-t border-[var(--border)] hover:bg-white/[0.03]"
                  onClick={() => router.push(`/admin/users/${u.id}`)}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/users/${u.id}`}
                      className="font-medium text-[var(--violet)] hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {u.email}
                    </Link>
                    {u.name && <div className="text-xs text-[var(--muted)]">{u.name}</div>}
                  </td>
                  <td className="px-4 py-3 capitalize">{u.role}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(u.credits)}</td>
                  <td
                    className="px-4 py-3 text-right tabular-nums"
                    title="All API calls, including free and failed"
                  >
                    {num(u.request_count)}
                    <div className="text-xs font-normal text-[var(--muted)]">
                      {num(u.free_count)} free
                      {u.failed_count > 0 ? ` · ${num(u.failed_count)} failed` : ""}
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-[var(--muted)]">
                    {u.last_activity ? dateTime(u.last_activity) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={u.status === "active" ? "success" : "danger"}>{u.status}</Badge>
                  </td>
                  <td
                    className="px-4 py-3 text-right whitespace-nowrap"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button size="sm" variant="ghost" onClick={() => setCreditsFor(u)}>
                      Credits
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => openLimits(u)}>
                      Limits
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className={u.status === "active" ? "text-red-300" : ""}
                      onClick={() =>
                        u.status === "active" ? setPendingBan(u) : void setStatus(u, "active")
                      }
                    >
                      {u.status === "active" ? "Ban" : "Unban"}
                    </Button>
                  </td>
                </tr>
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

      {/* Credit adjustment */}
      <Modal
        open={!!creditsFor}
        onClose={() => setCreditsFor(null)}
        title="Adjust credits"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreditsFor(null)}>
              Cancel
            </Button>
            <Button form="credit-form" type="submit" disabled={savingCredits}>
              {savingCredits ? "Applying…" : "Apply"}
            </Button>
          </>
        }
      >
        <form id="credit-form" onSubmit={submitCredits} className="space-y-3">
          <p className="text-sm text-[var(--muted)]">{creditsFor?.email}</p>
          <Field label="Amount (positive adds, negative removes)" htmlFor="credit-amount">
            <Input
              id="credit-amount"
              inputMode="numeric"
              value={creditAmount}
              onChange={(e) => setCreditAmount(e.target.value)}
              placeholder="100 or -50"
            />
          </Field>
        </form>
      </Modal>

      {/* Rate limits */}
      <Modal
        open={!!limitsFor}
        onClose={() => setLimitsFor(null)}
        title="Rate limits"
        footer={
          <>
            <Button variant="ghost" onClick={() => setLimitsFor(null)}>
              Cancel
            </Button>
            <Button onClick={saveLimits} disabled={savingLimits}>
              {savingLimits ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--muted)]">{limitsFor?.email}</p>
        <Field label={`Requests per ${Math.round(windowMs / 1000)}s window`} htmlFor="rl-window">
          <Input
            id="rl-window"
            inputMode="numeric"
            value={rpw}
            onChange={(e) => setRpw(e.target.value)}
            placeholder="Unlimited"
          />
        </Field>
        <Field label="Requests per minute" htmlFor="rl-minute">
          <Input
            id="rl-minute"
            inputMode="numeric"
            value={rpm}
            onChange={(e) => setRpm(e.target.value)}
            placeholder="Unlimited"
          />
        </Field>
        <Field label="Requests per day" htmlFor="rl-day">
          <Input
            id="rl-day"
            inputMode="numeric"
            value={rpd}
            onChange={(e) => setRpd(e.target.value)}
            placeholder="Unlimited"
          />
        </Field>
        <Field
          label="Max concurrent jobs"
          htmlFor="rl-concurrent"
          hint="Leave a field empty for no limit (concurrent jobs falls back to the pool default)."
        >
          <Input
            id="rl-concurrent"
            inputMode="numeric"
            value={mcj}
            onChange={(e) => setMcj(e.target.value)}
            placeholder="Default"
          />
        </Field>
      </Modal>

      {/* Suspend confirmation */}
      <ConfirmDialog
        open={!!pendingBan}
        title="Suspend user"
        danger
        confirmLabel="Suspend"
        message={
          pendingBan
            ? `Suspend ${pendingBan.email}? They will lose API access until reactivated.`
            : ""
        }
        onConfirm={() => (pendingBan ? setStatus(pendingBan, "suspended") : Promise.resolve())}
        onClose={() => setPendingBan(null)}
      />
    </div>
  );
}

export default function UsersPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <UsersInner />
    </Suspense>
  );
}
