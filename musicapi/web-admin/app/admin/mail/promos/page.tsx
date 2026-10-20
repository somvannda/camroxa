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

interface PromoRow {
  id: string;
  code: string;
  kind: string;
  value: string;
  user_id: string | null;
  redeemed_count: number;
  max_redemptions: number;
  expires_at: string | null;
  is_active: boolean;
  campaign_id: string | null;
  created_at: string;
}

export default function MailPromosPage() {
  const toast = useToast();
  const promos = useResource<{ rows: PromoRow[] }>(() =>
    apiFetch<{ rows: PromoRow[] }>("/admin/mail/promos"),
  );

  const [kind, setKind] = useState("percent");
  const [value, setValue] = useState("");
  const [expiresDays, setExpiresDays] = useState("14");
  const [maxRedemptions, setMaxRedemptions] = useState("100");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [lastCode, setLastCode] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await apiFetch<{ code: string }>("/admin/mail/promos", {
        method: "POST",
        body: JSON.stringify({
          mode: "public",
          kind,
          value: Number(value),
          expiresDays: Number(expiresDays) || 14,
          maxRedemptions: Number(maxRedemptions) || 100,
          note: note || null,
        }),
      });
      setLastCode(res.code);
      toast.success(`Created ${res.code}.`);
      setValue("");
      setNote("");
      void promos.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(row: PromoRow) {
    try {
      await apiFetch(`/admin/mail/promos/${row.id}/deactivate`, {
        method: "POST",
        body: "{}",
      });
      toast.success(`${row.code} deactivated.`);
      void promos.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Promo codes"
        description="Percent-off and bonus-credit codes redeemable at checkout. Campaign codes are generated per recipient."
      />

      <Card className="p-5">
        <h2 className="mb-1 font-semibold">Public code</h2>
        <p className="mb-3 text-xs text-[var(--muted)]">
          Anyone with the code can use it until the redemption cap. For campaigns, set the code on the
          campaign instead — that generates a single-use code per recipient.
        </p>
        <form onSubmit={create} className="grid gap-3 sm:grid-cols-5 sm:items-end">
          <Field label="Type">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="percent">Percent off</option>
              <option value="credit_bonus">Bonus credits</option>
            </Select>
          </Field>
          <Field label={kind === "percent" ? "Percent (1-99)" : "Credits"}>
            <Input
              required
              type="number"
              min={1}
              max={kind === "percent" ? 99 : undefined}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </Field>
          <Field label="Expires (days)">
            <Input
              type="number"
              min={1}
              max={90}
              value={expiresDays}
              onChange={(e) => setExpiresDays(e.target.value)}
            />
          </Field>
          <Field label="Max redemptions">
            <Input
              type="number"
              min={1}
              value={maxRedemptions}
              onChange={(e) => setMaxRedemptions(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={saving || !value}>
            {saving ? "Creating..." : "Create code"}
          </Button>
        </form>
        <Field className="mt-3" label="Note (internal)">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Water Festival promo" />
        </Field>
        {lastCode && (
          <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
            New code: <span className="font-mono font-bold">{lastCode}</span>
          </p>
        )}
      </Card>

      {promos.error && <ErrorState message={promos.error} onRetry={promos.reload} />}
      {promos.loading && <LoadingState />}

      {promos.data && promos.data.rows.length === 0 && (
        <EmptyState
          title="No codes yet"
          description="Create a public code above, or attach a promo preset to a campaign to generate one per recipient."
        />
      )}

      {promos.data && promos.data.rows.length > 0 && (
        <Card className="p-5">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-3 font-medium">Code</th>
                <th className="py-2 pr-3 font-medium">Reward</th>
                <th className="py-2 pr-3 font-medium">Scope</th>
                <th className="py-2 pr-3 text-right font-medium">Used</th>
                <th className="py-2 pr-3 font-medium">Expires</th>
                <th className="py-2 pr-3 font-medium">Created</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {promos.data.rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="py-2 pr-3 font-mono">{row.code}</td>
                  <td className="py-2 pr-3">
                    {row.kind === "percent"
                      ? `${Number(row.value)}% off`
                      : `+${Number(row.value)} credits`}
                  </td>
                  <td className="py-2 pr-3 text-xs text-[var(--muted)]">
                    {row.user_id ? "single user" : row.campaign_id ? "campaign" : "public"}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    {num(row.redeemed_count)}/{num(row.max_redemptions)}
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {row.expires_at ? dateTime(row.expires_at) : "never"}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--muted)]">
                    {dateTime(row.created_at)}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    {row.is_active ? (
                      <Button size="sm" variant="ghost" onClick={() => void deactivate(row)}>
                        Deactivate
                      </Button>
                    ) : (
                      <span className="text-[11px] text-[var(--muted)]">inactive</span>
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
