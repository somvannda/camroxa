"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface BrandSettings {
  name: string;
  docs_url: string;
  support_telegram_url: string;
  languages: string[];
}

interface AlertSettings {
  enabled: boolean;
  low_credits_threshold: number;
  captcha_locked: boolean;
  failure_rate_threshold: number;
  failure_rate_min_requests: number;
  window_minutes: number;
}

interface AlertItem {
  id: string;
  type: string;
  severity: "warning" | "critical";
  message: string;
  details: Record<string, unknown>;
}

interface AlertReport {
  enabled: boolean;
  checked_at: string;
  thresholds: AlertSettings;
  alerts: AlertItem[];
  summary: {
    low_credits: number;
    captcha_locked: boolean;
    failure_rate: number | null;
    requests: number;
    failures: number;
  };
}

interface IntegrationField {
  key: string;
  label: string;
  type: "string" | "secret" | "number" | "boolean";
  value: string | number | boolean;
  configured: boolean;
  help?: string;
}
interface IntegrationGroup {
  key: string;
  label: string;
  fields: IntegrationField[];
}

function initDraft(groups: IntegrationGroup[]): Record<string, Record<string, string | number | boolean>> {
  const draft: Record<string, Record<string, string | number | boolean>> = {};
  for (const g of groups) {
    draft[g.key] = {};
    for (const f of g.fields) draft[g.key][f.key] = f.type === "secret" ? "" : f.value;
  }
  return draft;
}

const inputClass =
  "w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]";
const labelClass = "text-xs text-[var(--muted)]";

const TABS = [
  { key: "brand", label: "Brand" },
  { key: "alerts", label: "Alerts" },
  { key: "integrations", label: "Integrations" },
  { key: "status", label: "Status" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("brand");
  const [brand, setBrand] = useState<BrandSettings | null>(null);
  const [alerts, setAlerts] = useState<AlertSettings | null>(null);
  const [languagesText, setLanguagesText] = useState("");
  const [report, setReport] = useState<AlertReport | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);

  const [integrations, setIntegrations] = useState<IntegrationGroup[]>([]);
  const [integrationTab, setIntegrationTab] = useState<string>("suno");
  const [draft, setDraft] = useState<Record<string, Record<string, string | number | boolean>>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [savingIntegrations, setSavingIntegrations] = useState(false);
  const [integrationsNotice, setIntegrationsNotice] = useState("");

  const loadAlerts = useCallback(() => {
    setChecking(true);
    apiFetch<AlertReport>("/admin/alerts")
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to evaluate alerts"))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ brand: BrandSettings; alerts: AlertSettings; integrations: IntegrationGroup[] }>("/admin/settings")
      .then((s) => {
        setBrand(s.brand);
        setLanguagesText(s.brand.languages.join(", "));
        setAlerts(s.alerts);
        setIntegrations(s.integrations ?? []);
        setDraft(initDraft(s.integrations ?? []));
        if (s.integrations?.length && !s.integrations.some((g) => g.key === "suno")) {
          setIntegrationTab(s.integrations[0].key);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load settings"))
      .finally(() => setLoading(false));
    loadAlerts();
  }, [loadAlerts]);

  async function saveBrand() {
    if (!brand) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const languages = languagesText.split(",").map((l) => l.trim()).filter(Boolean);
      const saved = await apiFetch<{ brand: BrandSettings }>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ brand: { ...brand, languages } }),
      });
      setBrand(saved.brand);
      setLanguagesText(saved.brand.languages.join(", "));
      setNotice("Brand saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function saveAlerts() {
    if (!alerts) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const saved = await apiFetch<{ alerts: AlertSettings }>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ alerts }),
      });
      setAlerts(saved.alerts);
      setNotice("Alert thresholds saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function saveIntegrations() {
    setSavingIntegrations(true);
    setError("");
    setIntegrationsNotice("");
    try {
      const values: Record<string, Record<string, string | number | boolean>> = {};
      for (const g of integrations) {
        const groupValues: Record<string, string | number | boolean> = {};
        for (const f of g.fields) {
          const key = `${g.key}.${f.key}`;
          const value = draft[g.key]?.[f.key];
          if (f.type === "secret") {
            // Only send a secret the operator actually typed; omit otherwise so
            // the stored value is left untouched (never cleared implicitly).
            if (dirty[key] && String(value ?? "") !== "") groupValues[f.key] = value;
          } else if (value !== undefined) {
            groupValues[f.key] = value;
          }
        }
        if (Object.keys(groupValues).length) values[g.key] = groupValues;
      }
      const saved = await apiFetch<{ integrations: IntegrationGroup[] }>("/admin/settings/integrations", {
        method: "PUT",
        body: JSON.stringify({ values }),
      });
      setIntegrations(saved.integrations);
      setDraft(initDraft(saved.integrations));
      setDirty({});
      setIntegrationsNotice("Integrations saved and applied.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integrations");
    } finally {
      setSavingIntegrations(false);
    }
  }

  if (loading) return <p className="text-[var(--muted)]">Loading…</p>;
  if (!brand || !alerts) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
      </div>
    );
  }

  const s = report?.summary;
  const activeGroups = integrations.filter((g) => g.key === integrationTab);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-[var(--muted)]">Branding, alerts and integration keys</p>
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
      {notice && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">{notice}</p>}

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[var(--border)]">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px rounded-t-lg border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === t.key
                ? "border-[var(--violet)] text-white"
                : "border-transparent text-[var(--muted)] hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "brand" && (
        <section className="glass space-y-4 rounded-xl p-5">
          <h2 className="text-sm font-semibold">Brand</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className={labelClass}>Brand name</label>
              <input value={brand.name} onChange={(e) => setBrand({ ...brand, name: e.target.value })} className={inputClass} placeholder="Camxora Music API" />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Docs URL</label>
              <input value={brand.docs_url} onChange={(e) => setBrand({ ...brand, docs_url: e.target.value })} className={inputClass} placeholder="https://docs.example.com" />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Telegram support link</label>
              <input value={brand.support_telegram_url} onChange={(e) => setBrand({ ...brand, support_telegram_url: e.target.value })} className={inputClass} placeholder="https://t.me/your_support" />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Languages (comma-separated)</label>
              <input value={languagesText} onChange={(e) => setLanguagesText(e.target.value)} className={inputClass} placeholder="en, km" />
            </div>
          </div>
          <button onClick={saveBrand} disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save brand"}
          </button>
        </section>
      )}

      {tab === "alerts" && (
        <section className="glass space-y-4 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Alerts</h2>
            <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
              <input type="checkbox" checked={alerts.enabled} onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })} />
              Enabled
            </label>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className={labelClass}>Low-credits threshold</label>
              <input type="number" min={0} value={alerts.low_credits_threshold} onChange={(e) => setAlerts({ ...alerts, low_credits_threshold: Number(e.target.value) })} className={inputClass} />
              <p className="text-xs text-[var(--muted)]">Alert when a Suno account has this many credits or fewer.</p>
            </div>
            <div className="space-y-1 md:pt-5">
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                <input type="checkbox" checked={alerts.captcha_locked} onChange={(e) => setAlerts({ ...alerts, captcha_locked: e.target.checked })} />
                Alert when Suno is captcha-locked
              </label>
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Failure-rate threshold (%)</label>
              <input type="number" min={0} max={100} step={1} value={Math.round(alerts.failure_rate_threshold * 100)} onChange={(e) => setAlerts({ ...alerts, failure_rate_threshold: Number(e.target.value) / 100 })} className={inputClass} />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Minimum requests before alerting</label>
              <input type="number" min={1} value={alerts.failure_rate_min_requests} onChange={(e) => setAlerts({ ...alerts, failure_rate_min_requests: Number(e.target.value) })} className={inputClass} />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Window (minutes)</label>
              <input type="number" min={5} max={1440} value={alerts.window_minutes} onChange={(e) => setAlerts({ ...alerts, window_minutes: Number(e.target.value) })} className={inputClass} />
            </div>
          </div>
          <button onClick={saveAlerts} disabled={saving} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save alerts"}
          </button>
        </section>
      )}

      {tab === "integrations" && (
        <section className="glass space-y-4 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Integrations</h2>
              <p className="text-xs text-[var(--muted)]">
                Keys are encrypted at rest and applied immediately. Leave a secret blank to keep its current value.
              </p>
            </div>
            <button onClick={saveIntegrations} disabled={savingIntegrations} className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {savingIntegrations ? "Saving…" : "Save integrations"}
            </button>
          </div>

          {integrationsNotice && (
            <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
              {integrationsNotice}
            </p>
          )}

          {/* Group sub-tabs */}
          <div className="flex flex-wrap gap-1">
            {integrations.map((g) => (
              <button
                key={g.key}
                onClick={() => setIntegrationTab(g.key)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  integrationTab === g.key
                    ? "border-[var(--violet)] bg-[var(--violet)]/15 text-white"
                    : "border-[var(--border)] text-[var(--muted)] hover:text-white"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>

          {integrationTab === "suno" && (
            <p className="rounded-lg border border-[var(--border)] bg-white/[0.03] px-3 py-2 text-xs text-[var(--muted)]">
              These values are only the boot-seed / fallback credential. To run <strong>multiple accounts</strong>{" "}
              (free or paid), add and manage them on the{" "}
              <Link href="/admin/accounts" className="text-[var(--violet)] hover:underline">
                Suno Accounts
              </Link>{" "}
              page.
            </p>
          )}

          {activeGroups.map((g) => (
            <div key={g.key} className="grid grid-cols-1 gap-4 rounded-lg border border-[var(--border)] p-4 md:grid-cols-2">
              {g.fields.map((f) => {
                const value = draft[g.key]?.[f.key];
                const setValue = (v: string | number | boolean) =>
                  setDraft((d) => ({ ...d, [g.key]: { ...d[g.key], [f.key]: v } }));
                return (
                  <div key={f.key} className="space-y-1">
                    <label className={labelClass}>{f.label}</label>
                    {f.type === "boolean" ? (
                      <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                        <input type="checkbox" checked={Boolean(value)} onChange={(e) => setValue(e.target.checked)} />
                        Enabled
                      </label>
                    ) : (
                      <input
                        type={f.type === "secret" ? "password" : f.type === "number" ? "number" : "text"}
                        value={String(value ?? "")}
                        placeholder={
                          f.type === "secret"
                            ? f.configured
                              ? "•••••••• (configured — type to replace)"
                              : "not set"
                            : undefined
                        }
                        autoComplete={f.type === "secret" ? "new-password" : undefined}
                        onChange={(e) => {
                          const v = f.type === "number" ? Number(e.target.value) : e.target.value;
                          setValue(v);
                          if (f.type === "secret") setDirty((d) => ({ ...d, [`${g.key}.${f.key}`]: true }));
                        }}
                        className={inputClass}
                      />
                    )}
                    {f.help && <p className="text-[11px] leading-snug text-[var(--muted)]">{f.help}</p>}
                  </div>
                );
              })}
            </div>
          ))}
        </section>
      )}

      {tab === "status" && (
        <section className="glass space-y-4 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Live alerts</h2>
              <p className="text-xs text-[var(--muted)]">
                {report ? `Checked ${new Date(report.checked_at).toLocaleString()}` : "Not checked yet"}
              </p>
            </div>
            <button onClick={loadAlerts} disabled={checking} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-60">
              {checking ? "Checking…" : "Re-check now"}
            </button>
          </div>

          {report && !report.enabled && (
            <p className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)]">
              Alerts are disabled — evaluation is skipped.
            </p>
          )}

          {report?.enabled && (
            <>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <Stat label="Low-credit accounts" value={String(s?.low_credits ?? 0)} />
                <Stat label="Captcha locked" value={s?.captcha_locked ? "Yes" : "No"} />
                <Stat label="Failure rate" value={s?.failure_rate == null ? "—" : `${(s.failure_rate * 100).toFixed(1)}%`} />
                <Stat label="Requests / failures" value={s ? `${s.requests} / ${s.failures}` : "—"} />
              </div>

              {report.alerts.length === 0 ? (
                <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
                  All clear — no active alerts.
                </p>
              ) : (
                <ul className="space-y-2">
                  {report.alerts.map((a) => (
                    <li
                      key={a.id}
                      className={`rounded-lg border px-3 py-2 text-sm ${
                        a.severity === "critical"
                          ? "border-red-500/30 bg-red-500/10 text-red-300"
                          : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                      }`}
                    >
                      <span className="mr-2 rounded bg-black/30 px-1.5 py-0.5 text-xs uppercase">{a.severity}</span>
                      {a.message}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] px-4 py-3">
      <p className="text-xs text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}
