"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, usd } from "@/lib/format";

interface BrandSettings {
  name: string;
  docs_url: string;
  support_telegram_url: string;
  languages: string[];
}

interface AlertSettings {
  enabled: boolean;
  low_credits_threshold: number;
  captcha_balance_threshold: number;
  failure_rate_threshold: number;
  failure_rate_min_requests: number;
  window_minutes: number;
  queue_backlog_depth: number;
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
    captcha_required: number;
    captcha_balance: number | null;
    failure_rate: number | null;
    requests: number;
    failures: number;
    queue_backlog: number;
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

function initDraft(
  groups: IntegrationGroup[],
): Record<string, Record<string, string | number | boolean>> {
  const draft: Record<string, Record<string, string | number | boolean>> = {};
  for (const g of groups) {
    draft[g.key] = {};
    for (const f of g.fields) draft[g.key][f.key] = f.type === "secret" ? "" : f.value;
  }
  return draft;
}

const TABS = [
  { key: "brand", label: "Brand" },
  { key: "alerts", label: "Alerts" },
  { key: "integrations", label: "Integrations" },
  { key: "status", label: "Status" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function SettingsPage() {
  const toast = useToast();
  const [tab, setTab] = useState<TabKey>("brand");
  const [brand, setBrand] = useState<BrandSettings | null>(null);
  const [alerts, setAlerts] = useState<AlertSettings | null>(null);
  const [languagesText, setLanguagesText] = useState("");
  const [report, setReport] = useState<AlertReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);

  const [integrations, setIntegrations] = useState<IntegrationGroup[]>([]);
  const [integrationTab, setIntegrationTab] = useState<string>("suno");
  const [draft, setDraft] = useState<Record<string, Record<string, string | number | boolean>>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [savingIntegrations, setSavingIntegrations] = useState(false);

  const loadAlerts = useCallback(() => {
    apiFetch<AlertReport>("/admin/alerts")
      .then(setReport)
      .catch((e) => toast.error(e instanceof Error ? e.message : "Failed to evaluate alerts"))
      .finally(() => setChecking(false));
  }, [toast]);

  useEffect(() => {
    apiFetch<{ brand: BrandSettings; alerts: AlertSettings; integrations: IntegrationGroup[] }>(
      "/admin/settings",
    )
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
    try {
      const languages = languagesText.split(",").map((l) => l.trim()).filter(Boolean);
      const saved = await apiFetch<{ brand: BrandSettings }>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ brand: { ...brand, languages } }),
      });
      setBrand(saved.brand);
      setLanguagesText(saved.brand.languages.join(", "));
      toast.success("Brand saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function saveAlerts() {
    if (!alerts) return;
    setSaving(true);
    try {
      const saved = await apiFetch<{ alerts: AlertSettings }>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ alerts }),
      });
      setAlerts(saved.alerts);
      toast.success("Alert thresholds saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function saveIntegrations() {
    setSavingIntegrations(true);
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
      const saved = await apiFetch<{ integrations: IntegrationGroup[] }>(
        "/admin/settings/integrations",
        { method: "PUT", body: JSON.stringify({ values }) },
      );
      setIntegrations(saved.integrations);
      setDraft(initDraft(saved.integrations));
      setDirty({});
      toast.success("Integrations saved and applied.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save integrations");
    } finally {
      setSavingIntegrations(false);
    }
  }

  if (loading) return <LoadingState />;
  if (!brand || !alerts) {
    return (
      <div className="space-y-6">
        <PageHeader title="Settings" description="Branding, alerts and integration keys" />
        {error && <ErrorState message={error} />}
      </div>
    );
  }

  const s = report?.summary;
  const activeGroups = integrations.filter((g) => g.key === integrationTab);

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Branding, alerts and integration keys" />

      {error && <ErrorState message={error} />}

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[var(--border)]">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined}
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
        <Card className="space-y-4 p-5">
          <h2 className="text-sm font-semibold">Brand</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Brand name" htmlFor="brand-name">
              <Input
                id="brand-name"
                value={brand.name}
                onChange={(e) => setBrand({ ...brand, name: e.target.value })}
                placeholder="Camxora Music API"
              />
            </Field>
            <Field label="Docs URL" htmlFor="brand-docs">
              <Input
                id="brand-docs"
                value={brand.docs_url}
                onChange={(e) => setBrand({ ...brand, docs_url: e.target.value })}
                placeholder="https://docs.example.com"
              />
            </Field>
            <Field
              label="Telegram support link"
              htmlFor="brand-telegram"
              hint="Enter a full link or a bare handle — @your_support is saved as https://t.me/your_support."
            >
              <Input
                id="brand-telegram"
                value={brand.support_telegram_url}
                onChange={(e) => setBrand({ ...brand, support_telegram_url: e.target.value })}
                placeholder="https://t.me/your_support"
              />
            </Field>
            <Field label="Languages (comma-separated)" htmlFor="brand-languages">
              <Input
                id="brand-languages"
                value={languagesText}
                onChange={(e) => setLanguagesText(e.target.value)}
                placeholder="en, km"
              />
            </Field>
          </div>
          <Button onClick={saveBrand} disabled={saving}>
            {saving ? "Saving…" : "Save brand"}
          </Button>
        </Card>
      )}

      {tab === "alerts" && (
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Alerts</h2>
            <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={alerts.enabled}
                onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })}
              />
              Enabled
            </label>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field
              label="Low-credits threshold"
              htmlFor="alert-low"
              hint="Alert when a Suno account has this many credits or fewer."
            >
              <Input
                id="alert-low"
                type="number"
                min={0}
                value={alerts.low_credits_threshold}
                onChange={(e) =>
                  setAlerts({ ...alerts, low_credits_threshold: Number(e.target.value) })
                }
              />
            </Field>
            <Field
              label="2Captcha balance threshold ($)"
              htmlFor="alert-captcha"
              hint="Alert when the 2Captcha balance falls to this. 0 disables. Captcha accounts with no key are always flagged."
            >
              <Input
                id="alert-captcha"
                type="number"
                min={0}
                step="0.5"
                value={alerts.captcha_balance_threshold}
                onChange={(e) =>
                  setAlerts({ ...alerts, captcha_balance_threshold: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="Failure-rate threshold (%)" htmlFor="alert-failrate">
              <Input
                id="alert-failrate"
                type="number"
                min={0}
                max={100}
                step={1}
                value={Math.round(alerts.failure_rate_threshold * 100)}
                onChange={(e) =>
                  setAlerts({ ...alerts, failure_rate_threshold: Number(e.target.value) / 100 })
                }
              />
            </Field>
            <Field label="Minimum requests before alerting" htmlFor="alert-minreq">
              <Input
                id="alert-minreq"
                type="number"
                min={1}
                value={alerts.failure_rate_min_requests}
                onChange={(e) =>
                  setAlerts({ ...alerts, failure_rate_min_requests: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="Window (minutes)" htmlFor="alert-window">
              <Input
                id="alert-window"
                type="number"
                min={5}
                max={1440}
                value={alerts.window_minutes}
                onChange={(e) => setAlerts({ ...alerts, window_minutes: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Queue backlog depth"
              htmlFor="alert-queue"
              hint="Alert when this many jobs are waiting for a Suno slot. 0 disables."
            >
              <Input
                id="alert-queue"
                type="number"
                min={0}
                value={alerts.queue_backlog_depth}
                onChange={(e) =>
                  setAlerts({ ...alerts, queue_backlog_depth: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <Button onClick={saveAlerts} disabled={saving}>
            {saving ? "Saving…" : "Save alerts"}
          </Button>
        </Card>
      )}

      {tab === "integrations" && (
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Integrations</h2>
              <p className="text-xs text-[var(--muted)]">
                Keys are encrypted at rest and applied immediately. Leave a secret blank to keep its
                current value.
              </p>
            </div>
            <Button onClick={saveIntegrations} disabled={savingIntegrations}>
              {savingIntegrations ? "Saving…" : "Save integrations"}
            </Button>
          </div>

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
              These values are only the boot-seed / fallback credential. To run{" "}
              <strong>multiple accounts</strong> (free or paid), add and manage them on the{" "}
              <Link href="/admin/accounts" className="text-[var(--violet)] hover:underline">
                Suno Accounts
              </Link>{" "}
              page.
            </p>
          )}

          {activeGroups.map((g) => (
            <div
              key={g.key}
              className="grid grid-cols-1 gap-4 rounded-lg border border-[var(--border)] p-4 md:grid-cols-2"
            >
              {g.fields.map((f) => {
                const value = draft[g.key]?.[f.key];
                const setValue = (v: string | number | boolean) =>
                  setDraft((d) => ({ ...d, [g.key]: { ...d[g.key], [f.key]: v } }));
                const id = `int-${g.key}-${f.key}`;
                return (
                  <Field key={f.key} label={f.label} htmlFor={id} hint={f.help}>
                    {f.type === "boolean" ? (
                      <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => setValue(e.target.checked)}
                        />
                        Enabled
                      </label>
                    ) : (
                      <Input
                        id={id}
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
                          if (f.type === "secret") {
                            setDirty((d) => ({ ...d, [`${g.key}.${f.key}`]: true }));
                          }
                        }}
                      />
                    )}
                  </Field>
                );
              })}
            </div>
          ))}
        </Card>
      )}

      {tab === "status" && (
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Live alerts</h2>
              <p className="text-xs text-[var(--muted)]">
                {report ? `Checked ${dateTime(report.checked_at)}` : "Not checked yet"}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setChecking(true);
                void loadAlerts();
              }}
              disabled={checking}
            >
              {checking ? "Checking…" : "Re-check now"}
            </Button>
          </div>

          {report && !report.enabled && (
            <p className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)]">
              Alerts are disabled — evaluation is skipped.
            </p>
          )}

          {report?.enabled && (
            <>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
                <StatCard label="Low-credit accounts" value={String(s?.low_credits ?? 0)} />
                <StatCard label="Captcha accounts" value={String(s?.captcha_required ?? 0)} />
                <StatCard
                  label="2Captcha balance"
                  value={s?.captcha_balance == null ? "—" : usd(s.captcha_balance)}
                />
                <StatCard
                  label="Failure rate"
                  value={s?.failure_rate == null ? "—" : `${(s.failure_rate * 100).toFixed(1)}%`}
                />
                <StatCard
                  label="Requests / failures"
                  value={s ? `${s.requests} / ${s.failures}` : "—"}
                />
                <StatCard label="Queue backlog" value={String(s?.queue_backlog ?? 0)} />
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
                      <span className="mr-2 rounded bg-black/30 px-1.5 py-0.5 text-xs uppercase">
                        {a.severity}
                      </span>
                      {a.message}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
