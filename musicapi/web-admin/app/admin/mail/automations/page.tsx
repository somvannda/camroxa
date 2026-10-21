"use client";

import { useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

interface TriggerDef {
  key: string;
  label: string;
  description: string;
  paramLabel?: string;
  defaultParam?: number;
  defaultCooldownDays: number;
}

interface AutomationRow {
  id: string;
  key: string;
  name: string;
  trigger: string;
  trigger_value: number | null;
  cooldown_days: number;
  is_active: boolean;
  last_run_at: string | null;
  eligible: number;
  subject: string;
}

interface TemplateRow {
  id: string;
  name: string;
  is_active: boolean;
  send_mode: string;
}

export default function MailAutomationsPage() {
  const toast = useToast();
  const automations = useResource<{ rows: AutomationRow[] }>(() =>
    apiFetch<{ rows: AutomationRow[] }>("/admin/mail/automations"),
  );
  const triggers = useResource<{ triggers: TriggerDef[] }>(() =>
    apiFetch<{ triggers: TriggerDef[] }>("/admin/mail/triggers"),
  );
  const templates = useResource<{ rows: TemplateRow[] }>(() =>
    apiFetch<{ rows: TemplateRow[] }>("/admin/mail/templates"),
  );

  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [trigger, setTrigger] = useState("welcome");
  const [param, setParam] = useState("");
  const [cooldown, setCooldown] = useState("");
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<string | null>(null);

  const activeTrigger = useMemo(
    () => triggers.data?.triggers.find((t) => t.key === trigger),
    [triggers.data, trigger],
  );

  function resetForm() {
    setName("");
    setTemplateId("");
    setTrigger("welcome");
    setParam("");
    setCooldown("");
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/admin/mail/automations", {
        method: "POST",
        body: JSON.stringify({
          name,
          templateId,
          trigger,
          cooldownDays: cooldown ? Number(cooldown) : undefined,
          audience: { triggerValue: param ? Number(param) : undefined },
        }),
      });
      toast.success("Journey created. It stays inactive until you enable it.");
      resetForm();
      void automations.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(row: AutomationRow) {
    try {
      await apiFetch(`/admin/mail/automations/${row.id}`, {
        method: "PUT",
        body: JSON.stringify({ isActive: !row.is_active }),
      });
      void automations.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function run(row: AutomationRow) {
    setRunning(row.id);
    try {
      const res = await apiFetch<{ queued: number }>(`/admin/mail/automations/${row.id}/run`, {
        method: "POST",
        body: "{}",
      });
      toast.success(`Queued ${num(res.queued)} message(s) for this journey.`);
      void automations.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(null);
    }
  }

  async function remove(row: AutomationRow) {
    if (!window.confirm(`Delete the "${row.name}" journey? Queued mail already sent stays in the ledger.`)) {
      return;
    }
    try {
      await apiFetch(`/admin/mail/automations/${row.id}`, { method: "DELETE" });
      toast.success("Journey deleted.");
      void automations.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mail automations"
        description="State-triggered journeys, evaluated every few minutes against live user state."
      />

      {triggers.error && <ErrorState message={triggers.error} onRetry={triggers.reload} />}

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">New journey</h2>
        <form onSubmit={create} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Journey name">
              <Input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Win-back — inactive 30 days"
              />
            </Field>
            <Field
              label="Template"
              hint="Manual-only templates (discount, seasonal) are excluded — use a campaign for those."
            >
              <Select required value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                <option value="">Select a template</option>
                {(templates.data?.rows ?? [])
                  .filter((t) => t.is_active && t.send_mode !== "manual")
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </Select>
            </Field>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Trigger" hint={activeTrigger?.description}>
              <Select
                value={trigger}
                onChange={(e) => {
                  setTrigger(e.target.value);
                  setParam("");
                  setCooldown("");
                }}
              >
                {(triggers.data?.triggers ?? []).map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label={activeTrigger?.paramLabel ?? "Threshold"}
              hint={`Default ${activeTrigger?.defaultParam ?? 0}`}
            >
              <Input
                type="number"
                min={0}
                value={param}
                placeholder={String(activeTrigger?.defaultParam ?? "")}
                onChange={(e) => setParam(e.target.value)}
              />
            </Field>
            <Field
              label="Cooldown (days)"
              hint={`Default ${activeTrigger?.defaultCooldownDays ?? 30}. One-shot journeys use a very large value.`}
            >
              <Input
                type="number"
                min={1}
                value={cooldown}
                placeholder={String(activeTrigger?.defaultCooldownDays ?? 30)}
                onChange={(e) => setCooldown(e.target.value)}
              />
            </Field>
          </div>

          <Button type="submit" disabled={saving || !templateId || !name}>
            {saving ? "Creating..." : "Create journey"}
          </Button>
        </form>
      </Card>

      {automations.error && <ErrorState message={automations.error} onRetry={automations.reload} />}
      {automations.loading && <LoadingState />}

      {automations.data && automations.data.rows.length === 0 && (
        <EmptyState
          title="No journeys yet"
          description="Start with 'Signed up, never generated': it targets free users who already showed up but never made a song."
        />
      )}

      {automations.data && automations.data.rows.length > 0 && (
        <Card className="p-5">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-3 font-medium">Journey</th>
                <th className="py-2 pr-3 font-medium">Trigger</th>
                <th className="py-2 pr-3 text-right font-medium">Eligible now</th>
                <th className="py-2 pr-3 font-medium">Cooldown</th>
                <th className="py-2 pr-3 font-medium">Last run</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {automations.data.rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="py-2 pr-3">
                    <div>{row.name}</div>
                    <div className="text-[11px] text-[var(--muted)]">{row.subject}</div>
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {triggers.data?.triggers.find((t) => t.key === row.trigger)?.label ?? row.trigger}
                    {row.trigger_value !== null && (
                      <span className="ml-1 text-[var(--muted)]">({row.trigger_value})</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-right">{num(row.eligible)}</td>
                  <td className="py-2 pr-3">{row.cooldown_days}d</td>
                  <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--muted)]">
                    {row.last_run_at ? dateTime(row.last_run_at) : "never"}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-right">
                    <Button
                      size="sm"
                      variant={row.is_active ? "secondary" : "primary"}
                      onClick={() => void toggle(row)}
                    >
                      {row.is_active ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void run(row)}
                      disabled={running === row.id || !row.is_active}
                    >
                      {running === row.id ? "Running..." : "Run now"}
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => void remove(row)}>
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
