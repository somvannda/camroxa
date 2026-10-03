"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";

interface KeyRow {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  safe_spend_limit: number | null;
  safe_spend_hourly: number | null;
  safe_spend_daily: number | null;
  safe_spend_total: number | null;
  ip_whitelist: string[];
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

type ModalState =
  | { kind: "none" }
  | { kind: "create" }
  | { kind: "edit"; key: KeyRow }
  | { kind: "ip"; key: KeyRow }
  | { kind: "safe"; key: KeyRow }
  | { kind: "delete"; key: KeyRow };

function CopyIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}
function PencilIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}
function PlusIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function ShieldIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function WalletIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 12V8H6a2 2 0 0 1 0-4h12v4" />
      <path d="M4 6v12a2 2 0 0 0 2 2h14v-4" />
      <path d="M18 12a2 2 0 0 0 0 4h4v-4h-4z" />
    </svg>
  );
}
function CloseIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
function TrashIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}
function ClockIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function CalendarIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function InfoIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  );
}

function pad(n: number) { return n < 10 ? "0" + n : String(n); }
function formatDate(s: string) {
  const d = new Date(s);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function maskKey(prefix: string) {
  return `${prefix}${"\u2022".repeat(34)}`;
}
function limitsSummary(k: KeyRow): string | null {
  const parts: string[] = [];
  if (k.safe_spend_hourly != null) parts.push(`H ${k.safe_spend_hourly}`);
  if (k.safe_spend_daily != null) parts.push(`D ${k.safe_spend_daily}`);
  const total = k.safe_spend_total ?? k.safe_spend_limit;
  if (total != null) parts.push(`T ${total}`);
  return parts.length ? parts.join(" · ") : null;
}

function Modal({
  open, onClose, title, children, wide = false, darkBlue = false, iconBeforeTitle,
}: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode;
  wide?: boolean; darkBlue?: boolean; iconBeforeTitle?: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className={`relative w-full ${wide ? "max-w-2xl" : "max-w-lg"} rounded-2xl p-6 shadow-2xl border ${
          darkBlue ? "bg-[#131b2e] border-white/10" : "bg-[#14141c] border-white/10"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 rounded-md p-1.5 text-white/50 hover:text-white hover:bg-white/5"
        >
          <CloseIcon />
        </button>
        <h3 className="mb-4 text-base font-semibold text-white flex items-center gap-2">
          {iconBeforeTitle}
          {title}
        </h3>
        {children}
      </div>
    </div>
  );
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<KeyRow[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState<ModalState>({ kind: "none" });

  const load = useCallback(() => {
    apiFetch<KeyRow[]>("/me/keys")
      .then((list) => {
        setKeys(list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  useEffect(() => { load(); }, [load]);

  // create form state
  const [createName, setCreateName] = useState("");
  const openCreate = () => { setCreateName(""); setError(""); setModal({ kind: "create" }); };

  async function doCreate() {
    setCreating(true);
    setError("");
    try {
      const res = await apiFetch<{ key: string }>("/me/keys", {
        method: "POST",
        body: JSON.stringify({ name: createName || "default" }),
      });
      setNewKey(res.key);
      setModal({ kind: "none" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function copyToClipboard(text: string) {
    try { await navigator.clipboard.writeText(text); } catch { /* ignore */ }
  }

  // edit
  const [editName, setEditName] = useState("");
  const openEdit = (k: KeyRow) => { setEditName(k.name); setError(""); setModal({ kind: "edit", key: k }); };
  async function saveEdit(k: KeyRow) {
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/me/keys/${k.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: editName }),
      });
      setModal({ kind: "none" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // ip whitelist
  const [ipInput, setIpInput] = useState("");
  const [ipList, setIpList] = useState<string[]>([]);
  const openIp = (k: KeyRow) => {
    setIpList([...(k.ip_whitelist ?? [])]);
    setIpInput("");
    setError("");
    setModal({ kind: "ip", key: k });
  };
  const addIp = () => {
    const v = ipInput.trim();
    if (!v) return;
    if (ipList.length >= 10) return;
    if (ipList.includes(v)) return;
    setIpList([...ipList, v]);
    setIpInput("");
  };
  const removeIp = (v: string) => setIpList(ipList.filter((x) => x !== v));
  async function saveIp(k: KeyRow) {
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/me/keys/${k.id}`, {
        method: "PUT",
        body: JSON.stringify({ ip_whitelist: ipList }),
      });
      setModal({ kind: "none" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // safe-spend
  const [safeHourly, setSafeHourly] = useState("");
  const [safeDaily, setSafeDaily] = useState("");
  const [safeTotal, setSafeTotal] = useState("");
  const [safeInitial, setSafeInitial] = useState<{ h: string; d: string; t: string } | null>(null);
  function openSafe(k: KeyRow) {
    const h = k.safe_spend_hourly != null ? String(k.safe_spend_hourly) : "";
    const d = k.safe_spend_daily != null ? String(k.safe_spend_daily) : "";
    const t = (k.safe_spend_total ?? k.safe_spend_limit) != null ? String(k.safe_spend_total ?? k.safe_spend_limit) : "";
    setSafeInitial({ h, d, t });
    setSafeHourly(h);
    setSafeDaily(d);
    setSafeTotal(t);
    setError("");
    setModal({ kind: "safe", key: k });
  }
  const safeDirty = useMemo(() => {
    if (!safeInitial) return false;
    return (
      safeInitial.h !== safeHourly ||
      safeInitial.d !== safeDaily ||
      safeInitial.t !== safeTotal
    );
  }, [safeInitial, safeHourly, safeDaily, safeTotal]);
  async function saveSafe(k: KeyRow) {
    setSaving(true);
    setError("");
    try {
      const payload: { safe_spend_hourly: number | null; safe_spend_daily: number | null; safe_spend_total: number | null } = {
        safe_spend_hourly: safeHourly === "" ? null : Number(safeHourly),
        safe_spend_daily: safeDaily === "" ? null : Number(safeDaily),
        safe_spend_total: safeTotal === "" ? null : Number(safeTotal),
      };
      await apiFetch(`/me/keys/${k.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setModal({ kind: "none" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // delete (revoke)
  const [deleting, setDeleting] = useState(false);
  const openDelete = (k: KeyRow) => { setError(""); setModal({ kind: "delete", key: k }); };
  async function doDelete(k: KeyRow) {
    setDeleting(true);
    setError("");
    try {
      await apiFetch(`/me/keys/${k.id}`, { method: "DELETE" });
      setModal({ kind: "none" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete key");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-white">API Key</h1>
      <p className="mt-1 text-sm text-white/60">The key to the magic world of AI</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">API Keys</h2>
          <button
            onClick={openCreate}
            className="grad-bg inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white hover:opacity-95"
          >
            <PlusIcon className="w-4 h-4" />
            Create New Key
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-white/50">
                <th className="pb-3 pr-4 font-medium">Name</th>
                <th className="pb-3 pr-4 font-medium">Key</th>
                <th className="pb-3 pr-4 font-medium">Created Date</th>
                <th className="pb-3 pr-4 font-medium">IP Whitelist</th>
                <th className="pb-3 pr-4 font-medium">Safe-Spend Limits</th>
                <th className="pb-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => {
                const ips = k.ip_whitelist ?? [];
                const summary = limitsSummary(k);
                return (
                  <tr key={k.id} className="border-t border-white/5 align-middle">
                    <td className="py-3 pr-4 text-white font-medium">{k.name}</td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <code className="font-mono text-white/80">{maskKey(k.key_prefix)}</code>
                        <button
                          onClick={() => copyToClipboard(maskKey(k.key_prefix))}
                          className="rounded-md p-1 text-white/40 hover:text-white/80 hover:bg-white/5"
                          aria-label="Copy masked key"
                          title="Copy masked key"
                        >
                          <CopyIcon className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-white/70 font-mono text-xs">
                      <div className="flex items-center gap-2">
                        <CalendarIcon className="w-3.5 h-3.5 text-white/40" />
                        {formatDate(k.created_at)}
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5 text-white/50"
                          title={`All IPs allowed by default. Add up to 10 IP addresses to restrict access.\n\n${ips.length ? ips.join(", ") : "No IPs whitelisted yet"}`}
                          aria-label="IP whitelist"
                        >
                          <ShieldIcon className="w-3.5 h-3.5" />
                        </span>
                        <button
                          onClick={() => openIp(k)}
                          className="grad-bg inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          <PlusIcon className="w-3.5 h-3.5" />
                          Add IP
                        </button>
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      {!summary ? (
                        <button
                          onClick={() => openSafe(k)}
                          className="inline-flex items-center gap-1.5 rounded-md border border-violet-400/40 bg-violet-500/10 px-3 py-1.5 text-xs font-semibold text-violet-200 hover:bg-violet-500/20"
                        >
                          <WalletIcon className="w-3.5 h-3.5" />
                          Safe-Spend Limits
                        </button>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="text-xs text-white/80 font-mono">{summary}</div>
                          <button
                            onClick={() => openSafe(k)}
                            className="rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-white/80 hover:text-white hover:bg-white/10"
                          >
                            Manage
                          </button>
                        </div>
                      )}
                    </td>
                    <td className="py-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button
                          onClick={() => openEdit(k)}
                          aria-label="Edit key"
                          title="Edit key"
                          className="rounded-md p-2 text-white/50 hover:text-white hover:bg-white/5"
                        >
                          <PencilIcon />
                        </button>
                        {keys.length > 1 && (
                          <button
                            onClick={() => openDelete(k)}
                            aria-label="Delete key"
                            title="Delete key"
                            className="rounded-md p-2 text-white/50 hover:text-red-300 hover:bg-red-500/10"
                          >
                            <TrashIcon />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {keys.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-white/40">
                    No API keys yet. Click &ldquo;Create New Key&rdquo; to create one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create */}
      <Modal
        open={modal.kind === "create"}
        onClose={() => setModal({ kind: "none" })}
        title="Create API Key"
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-white">Name</label>
            <input
              autoFocus
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="Please enter API Key name"
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
              onKeyDown={(e) => { if (e.key === "Enter") doCreate(); }}
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setModal({ kind: "none" })}
              disabled={creating}
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              onClick={doCreate}
              disabled={creating}
              className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 min-w-[96px]"
            >
              {creating ? "Creating&hellip;" : "Create"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit */}
      {modal.kind === "edit" && (
        <Modal
          open
          onClose={() => setModal({ kind: "none" })}
          title="Edit API key"
        >
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-white">Name</label>
              <input
                autoFocus
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="Please enter API Key name"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
                onKeyDown={(e) => { if (e.key === "Enter") saveEdit(modal.key); }}
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setModal({ kind: "none" })}
                disabled={saving}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={() => saveEdit(modal.key)}
                disabled={saving}
                className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 min-w-[96px]"
              >
                {saving ? "Saving&hellip;" : "Save"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* IP Whitelist */}
      {modal.kind === "ip" && (
        <Modal
          open
          wide
          onClose={() => setModal({ kind: "none" })}
          title="Manage Whitelist"
        >
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5 min-h-[28px]">
              {ipList.length === 0 && (
                <span className="text-xs text-white/40 italic">No IPs whitelisted. All requests allowed.</span>
              )}
              {ipList.map((ip) => (
                <span
                  key={ip}
                  className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs font-mono text-white/85"
                >
                  {ip}
                  <button
                    onClick={() => removeIp(ip)}
                    className="rounded p-0.5 text-white/40 hover:text-red-300 hover:bg-red-500/10"
                    aria-label={`Remove ${ip}`}
                  >
                    <CloseIcon className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative">
              <input
                value={ipInput}
                onChange={(e) => setIpInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") addIp(); }}
                placeholder="Please enter IP address"
                className="w-full rounded-lg border border-white/10 bg-black/30 pr-12 pl-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
              />
              <button
                onClick={() => setIpInput("")}
                disabled={!ipInput}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-pink-300/80 hover:text-pink-200 hover:bg-pink-500/10 disabled:text-white/15 disabled:hover:bg-transparent"
                aria-label="Clear input"
                title="Clear input"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
            <button
              onClick={addIp}
              disabled={!ipInput.trim() || ipList.length >= 10 || ipList.includes(ipInput.trim())}
              className="grad-bg inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              <PlusIcon className="w-4 h-4" />
              Add IP address ({ipList.length}/10)
            </button>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setModal({ kind: "none" })}
                disabled={saving}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={() => saveIp(modal.key)}
                disabled={saving}
                className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 min-w-[96px]"
              >
                {saving ? "Saving&hellip;" : "Save"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Safe-Spend */}
      {modal.kind === "safe" && (
        <Modal
          open
          wide
          darkBlue
          onClose={() => setModal({ kind: "none" })}
          title="Safe-Spend Limits"
          iconBeforeTitle={
            <span className="inline-flex items-center gap-0.5">
              <ShieldIcon className="w-4 h-4" />
              <WalletIcon className="w-4 h-4 -ml-1.5" />
            </span>
          }
        >
          <p className="-mt-2 mb-4 text-xs text-white/50">
            Set hourly and daily credit limits to control API usage
          </p>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="inline-flex items-center gap-2 text-sm font-medium text-white">
                <ClockIcon className="w-4 h-4 text-white/50" />
                Hourly credit limit
                <span
                  className="text-white/35 hover:text-white/60"
                  title="Maximum credits that can be consumed in any rolling 60-minute window. Requests are paused once the cap is reached."
                >
                  <InfoIcon />
                </span>
              </label>
              <input
                type="number"
                min="0"
                value={safeHourly}
                onChange={(e) => setSafeHourly(e.target.value)}
                placeholder="Set to 0 for unlimited"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
              />
              <p className="text-xs text-white/40">Set to 0 for unlimited</p>
            </div>
            <div className="space-y-1.5">
              <label className="inline-flex items-center gap-2 text-sm font-medium text-white">
                <CalendarIcon className="w-4 h-4 text-white/50" />
                Daily credit limit
                <span
                  className="text-white/35 hover:text-white/60"
                  title="Maximum credits that can be consumed from 00:00-24:00 UTC. Counter resets at midnight."
                >
                  <InfoIcon />
                </span>
              </label>
              <input
                type="number"
                min="0"
                value={safeDaily}
                onChange={(e) => setSafeDaily(e.target.value)}
                placeholder="Set to 0 for unlimited"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
              />
              <p className="text-xs text-white/40">Set to 0 for unlimited</p>
            </div>
            <div className="space-y-1.5">
              <label className="inline-flex items-center gap-2 text-sm font-medium text-white">
                <WalletIcon className="w-4 h-4 text-white/50" />
                Total credit limit
                <span
                  className="text-white/35 hover:text-white/60"
                  title="Maximum total credits that this API key can consume after this limit is set. Once the limit is reached, the key will be disabled."
                >
                  <InfoIcon />
                </span>
              </label>
              <input
                type="number"
                min="0"
                value={safeTotal}
                onChange={(e) => setSafeTotal(e.target.value)}
                placeholder="Set to 0 for unlimited"
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-violet-400/70 placeholder:text-white/30"
              />
              <p className="text-xs text-white/40">Set to 0 for unlimited</p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-3">
              <button
                onClick={() => setModal({ kind: "none" })}
                disabled={saving}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={() => saveSafe(modal.key)}
                disabled={saving || !safeDirty}
                className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 min-w-[120px]"
              >
                {saving ? "Saving&hellip;" : "Save limits"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete */}
      {modal.kind === "delete" && (() => {
        const k = modal.key;
        const hasOther = keys.some((x) => x.id !== k.id);
        const blocked = k.credits > 0 && !hasOther;
        return (
          <Modal
            open
            onClose={() => setModal({ kind: "none" })}
            title="Confirm Delete"
            iconBeforeTitle={<TrashIcon className="w-4 h-4 text-red-300" />}
          >
            <div className="space-y-4">
              <p className="text-sm text-white/70">
                Are you sure you want to delete this API Key? This action cannot be undone.
              </p>
              {k.credits > 0 && (
                <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                  {hasOther
                    ? `This key holds ${k.credits} credits. They will be moved to another of your keys.`
                    : `This key holds ${k.credits} credits and is your only key. Create another key first \u2014 the balance moves to it \u2014 then delete this one.`}
                </p>
              )}
              {error && (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>
              )}
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setModal({ kind: "none" })}
                  disabled={deleting}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 disabled:opacity-60"
                >
                  Cancel
                </button>
                <button
                  onClick={() => doDelete(k)}
                  disabled={deleting || blocked}
                  className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-400 disabled:opacity-50 min-w-[96px]"
                >
                  {deleting ? "Deleting&hellip;" : "Delete"}
                </button>
              </div>
            </div>
          </Modal>
        );
      })()}

      {/* Create success — save this key (shown once) */}
      <Modal
        open={!!newKey}
        onClose={() => setNewKey(null)}
        title="API Key Created Successfully"
      >
        <div className="space-y-4">
          <p className="text-sm text-white/70">
            Please save this API key somewhere safe and easily accessible.
          </p>
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/30 p-3">
            <code className="min-w-0 flex-1 break-all font-mono text-sm text-white">{newKey}</code>
            <button
              onClick={() => newKey && copyToClipboard(newKey)}
              className="shrink-0 rounded-lg border border-white/10 bg-white/5 p-2 text-white/80 hover:bg-white/10 hover:text-white"
              aria-label="Copy full key"
              title="Copy full key"
            >
              <CopyIcon />
            </button>
          </div>
          <div className="flex justify-end">
            <button
              onClick={() => setNewKey(null)}
              className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white"
            >
              Done
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
