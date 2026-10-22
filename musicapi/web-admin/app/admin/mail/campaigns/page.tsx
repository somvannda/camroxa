"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

interface TemplateRow {
  id: string;
  name: string;
  subject: string;
  is_active: boolean;
}

interface CampaignRow {
  id: string;
  name: string;
  status: string;
  template_name: string;
  recipient_count: number;
  queued: number;
  opened: number;
  clicked: number;
  sent_at: string | null;
  created_at: string;
}

interface Preset {
  key: string;
  label: string;
  count: number;
}

interface Audience {
  lifecycle: string;
  spendTier: string;
  language: string;
  excludeRecentPayers: boolean;
}

const EMPTY_AUDIENCE: Audience = {
  lifecycle: "",
  spendTier: "",
  language: "",
  excludeRecentPayers: false,
};

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-white/10 text-[var(--muted)]",
  sending: "bg-amber-500/15 text-amber-300",
  sent: "bg-emerald-500/15 text-emerald-300",
  cancelled: "bg-white/10 text-[var(--muted)]",
};

export default function MailCampaignsPage() {
  const toast = useToast();
  const campaigns = useResource<{ rows: CampaignRow[] }>(() =>
    apiFetch<{ rows: CampaignRow[] }>("/admin/mail/campaigns"),
  );
  const templates = useResource<{ rows: TemplateRow[] }>(() =>
    apiFetch<{ rows: TemplateRow[] }>("/admin/mail/templates"),
  );
  const segments = useResource<{ presets: Preset[]; cooldownDays: number }>(() =>
    apiFetch<{ presets: Preset[]; cooldownDays: number }>("/admin/mail/segments"),
  );

  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [audience, setAudience] = useState<Audience>(EMPTY_AUDIENCE);
  const [promoKind, setPromoKind] = useState("");
  const [promoValue, setPromoValue] = useState("");
  const [promoExpires, setPromoExpires] = useState("7");
  const [count, setCount] = useState<number | null>(null);
  const [counting, setCounting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pendingSend, setPendingSend] = useState<string | null>(null);

  function audiencePayload() {
    return {
      lifecycle: audience.lifecycle || null,
      spendTier: audience.spendTier || null,
      language: audience.language || null,
      excludeRecentPayers: audience.excludeRecentPayers,
    };
  }

  function applyPreset(preset: Preset) {
    const [lifecycle, spendTier] = preset.key.split("-");
    setAudience({ ...audience, lifecycle, spendTier });
    setCount(preset.count);
  }

  async function countAudience() {
    setCounting(true);
    try {
      const res = await apiFetch<{ count: number }>("/admin/mail/audience/count", {
        method: "POST",
        body: JSON.stringify({ audience: audiencePayload() }),
      });
      setCount(res.count);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Count failed");
    } finally {
      setCounting(false);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/admin/mail/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name,
          templateId,
          audience: audiencePayload(),
          promoPreset:
            promoKind && promoValue
              ? { kind: promoKind, value: Number(promoValue), expiresDays: Number(promoExpires) || 7 }
              : null,
        }),
      });
      toast.success("Campaign created. Review the audience count before sending.");
      setName("");
      setTemplateId("");
      setPromoKind("");
      setPromoValue("");
      setCount(null);
      void campaigns.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  async function send(row: CampaignRow) {
    if (pendingSend !== row.id) {
      setPendingSend(row.id);
      return;
    }
    setPendingSend(null);
    try {
      const res = await apiFetch<{ queued: number; skipped: number; audience: number }>(
        `/admin/mail/campaigns/${row.id}/send`,
        { method: "POST", body: "{}" },
      );
      toast.success(
        `Queued ${num(res.queued)} of ${num(res.audience)} recipients (${num(res.skipped)} skipped). Delivery runs in the background.`,
      );
      void campaigns.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Send failed");
    }
  }

  async function test(row: CampaignRow) {
    try {
      const res = await apiFetch<{ to: string }>(`/admin/mail/campaigns/${row.id}/test`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      toast.success(`Test copy sent to ${res.to}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test send failed");
    }
  }

  async function cancel(row: CampaignRow) {
    try {
      await apiFetch(`/admin/mail/campaigns/${row.id}/cancel`, { method: "POST", body: "{}" });
      toast.success("Campaign cancelled; queued messages were dropped.");
      void campaigns.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mail campaigns"
        description="Pick a template, narrow the audience, confirm the count, then send. Delivery is queued and paced."
      />

      {segments.error && <ErrorState message={segments.error} onRetry={segments.reload} />}

      {segments.data && (
        <Card className="p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">Strategy segments</h2>
            <p className="text-xs text-[var(--muted)]">
              A user is skipped if they received marketing mail in the last{" "}
              {segments.data.cooldownDays} days.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {segments.data.presets.map((preset) => (
              <button
                key={preset.key}
                onClick={() => applyPreset(preset)}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-white/5"
              >
                {preset.label}
                <span className="ml-2 font-semibold">{num(preset.count)}</span>
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">New campaign</h2>
        <form onSubmit={create} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Campaign name">
              <Input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Pack ladder — active never-paid"
              />
            </Field>
            <Field label="Template">
              <Select
                required
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Select a template</option>
                {(templates.data?.rows ?? [])
                  .filter((t) => t.is_active)
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </Select>
            </Field>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Lifecycle">
              <Select
                value={audience.lifecycle}
                onChange={(e) => {
                  setAudience({ ...audience, lifecycle: e.target.value });
                  setCount(null);
                }}
              >
                <option value="">Any</option>
                <option value="active">Active (7d)</option>
                <option value="warm">Warm (8-30d)</option>
                <option value="dormant">Dormant (30d+)</option>
              </Select>
            </Field>
            <Field label="Spend tier">
              <Select
                value={audience.spendTier}
                onChange={(e) => {
                  setAudience({ ...audience, spendTier: e.target.value });
                  setCount(null);
                }}
              >
                <option value="">Any</option>
                <option value="never">Never paid</option>
                <option value="small">Small payer</option>
                <option value="big">Big payer</option>
              </Select>
            </Field>
            <Field label="Language">
              <Select
                value={audience.language}
                onChange={(e) => {
                  setAudience({ ...audience, language: e.target.value });
                  setCount(null);
                }}
              >
                <option value="">Any</option>
                <option value="en">en</option>
                <option value="km">km</option>
              </Select>
            </Field>
          </div>

          <label className="flex items-start gap-2 text-xs text-[var(--muted)]">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={audience.excludeRecentPayers}
              onChange={(e) => {
                setAudience({ ...audience, excludeRecentPayers: e.target.checked });
                setCount(null);
              }}
            />
            <span>
              Exclude anyone who paid in the last 14 days. Keep this on for discount mail:
              mailing a full-price buyer a coupon teaches them to wait for the next sale.
            </span>
          </label>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field
              label="Promo code (optional)"
              hint="Needed if the template prints {{code}}. One single-use code per recipient."
            >
              <Select value={promoKind} onChange={(e) => setPromoKind(e.target.value)}>
                <option value="">No code</option>
                <option value="percent">Percent off</option>
                <option value="credit_bonus">Bonus credits</option>
                <option value="credit">Redeem for credits</option>
              </Select>
            </Field>
            <Field
              label={
                promoKind === "percent"
                  ? "Percent (1-99)"
                  : promoKind === "credit"
                    ? "Credits to grant"
                    : "Bonus credits"
              }
              hint={
                promoKind === "percent"
                  ? "20 = 20% off the pack price"
                  : promoKind === "credit"
                    ? "500 = 500 credits claimed on the site, with no purchase"
                    : "500 = 500 extra credits on a pack purchase"
              }
            >
              <Input
                type="number"
                min={1}
                max={promoKind === "percent" ? 99 : undefined}
                value={promoValue}
                onChange={(e) => setPromoValue(e.target.value)}
                disabled={!promoKind}
              />
            </Field>
            <Field label="Code expires in (days)">
              <Input
                type="number"
                min={1}
                max={90}
                value={promoExpires}
                onChange={(e) => setPromoExpires(e.target.value)}
                disabled={!promoKind}
              />
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" onClick={countAudience} disabled={counting}>
              {counting ? "Counting..." : "Count audience"}
            </Button>
            {count !== null && (
              <span className="text-sm">
                <span className="font-semibold">{num(count)}</span>{" "}
                <span className="text-[var(--muted)]">recipients after consent, suppression and cooldown</span>
              </span>
            )}
            <Button type="submit" disabled={saving || !templateId || !name}>
              {saving ? "Creating..." : "Create draft"}
            </Button>
          </div>
        </form>
      </Card>

      {campaigns.error && <ErrorState message={campaigns.error} onRetry={campaigns.reload} />}
      {campaigns.loading && <LoadingState />}

      {campaigns.data && campaigns.data.rows.length === 0 && (
        <EmptyState
          title="No campaigns yet"
          description="Create a draft above. Nothing is sent until you press Send and confirm."
        />
      )}

      {campaigns.data && campaigns.data.rows.length > 0 && (
        <Card className="p-5">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-3 font-medium">Campaign</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 text-right font-medium">Queued</th>
                <th className="py-2 pr-3 text-right font-medium">Opened</th>
                <th className="py-2 pr-3 text-right font-medium">Clicked</th>
                <th className="py-2 pr-3 font-medium">Created</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {campaigns.data.rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="py-2 pr-3">
                    <div>{row.name}</div>
                    <div className="text-[11px] text-[var(--muted)]">{row.template_name}</div>
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        STATUS_STYLE[row.status] ?? "bg-white/10"
                      }`}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">{num(row.queued)}</td>
                  <td className="py-2 pr-3 text-right">{num(row.opened)}</td>
                  <td className="py-2 pr-3 text-right">{num(row.clicked)}</td>
                  <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--muted)]">
                    {dateTime(row.created_at)}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-right">
                    <Button size="sm" variant="ghost" onClick={() => void test(row)}>
                      Test
                    </Button>
                    {row.status !== "sent" && row.status !== "cancelled" && (
                      <>
                        <Button
                          size="sm"
                          variant={pendingSend === row.id ? "danger" : "secondary"}
                          onClick={() => void send(row)}
                        >
                          {pendingSend === row.id ? "Confirm send" : "Send"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => void cancel(row)}>
                          Cancel
                        </Button>
                      </>
                    )}
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
