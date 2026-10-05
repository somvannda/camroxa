"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";

interface Account {
  id: string;
  label: string;
  type: string;
  is_active: boolean;
  created_at: string;
  live_plan: string;
  live_credits: number;
  live_models: string[];
  health: {
    disabled: boolean;
    low_credits: boolean;
    captcha_required: boolean;
    captcha_solver: boolean;
  };
}

interface RoutingRule {
  id: string;
  model: string;
  policy: string;
}

function healthBadges(a: Account): { label: string; tone: BadgeTone }[] {
  const badges: { label: string; tone: BadgeTone }[] = [];
  if (a.health.disabled) badges.push({ label: "Disabled", tone: "danger" });
  if (a.health.low_credits) badges.push({ label: "Low credits", tone: "warning" });
  // An enabled, funded account stays healthy even when Suno challenges its
  // captcha — the worker solves it automatically at generation time.
  const captchaBlocks = a.health.captcha_required && !a.health.captcha_solver;
  if (!a.health.disabled && !a.health.low_credits && !captchaBlocks) {
    badges.push({ label: "Healthy", tone: "success" });
  }
  if (a.health.captcha_required && a.health.captcha_solver) {
    badges.push({ label: "Captcha auto-solved", tone: "info" });
  } else if (captchaBlocks) {
    badges.push({ label: "Captcha required", tone: "warning" });
  }
  return badges;
}

const EMPTY_FORM = { label: "", type: "free", client_cookie: "", device_id: "" };

export default function AccountsPage() {
  const toast = useToast();
  const accountsRes = useResource<{ accounts: Account[] }>(() =>
    apiFetch<{ accounts: Account[] }>("/admin/accounts"),
  );
  const rulesRes = useResource<RoutingRule[]>(() => apiFetch<RoutingRule[]>("/admin/routing"));
  const accounts = accountsRes.data?.accounts ?? [];
  const rules = rulesRes.data ?? [];
  const error = accountsRes.error || rulesRes.error;

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [editing, setEditing] = useState<Account | null>(null);
  const [editForm, setEditForm] = useState({
    label: "",
    type: "free",
    client_cookie: "",
    device_id: "",
    is_active: true,
  });
  const [savingEdit, setSavingEdit] = useState(false);

  const [pendingDelete, setPendingDelete] = useState<Account | null>(null);

  const [ruleForm, setRuleForm] = useState({ model: "", policy: "prefer_free" });
  const [savingRule, setSavingRule] = useState(false);
  const [pendingRule, setPendingRule] = useState<RoutingRule | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/admin/accounts", { method: "POST", body: JSON.stringify(form) });
      toast.success("Account added.");
      setShowForm(false);
      setForm(EMPTY_FORM);
      void accountsRes.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setSaving(false);
    }
  }

  function startEdit(a: Account) {
    setEditing(a);
    setEditForm({
      label: a.label,
      type: a.type,
      client_cookie: "",
      device_id: "",
      is_active: a.is_active,
    });
  }

  async function submitEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSavingEdit(true);
    try {
      const body: Record<string, unknown> = {
        label: editForm.label,
        type: editForm.type,
        is_active: editForm.is_active,
      };
      // Cookie/device are only sent when the operator retypes them.
      if (editForm.client_cookie.trim()) body.client_cookie = editForm.client_cookie;
      if (editForm.device_id.trim()) body.device_id = editForm.device_id;
      await apiFetch(`/admin/accounts/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
      toast.success("Account updated.");
      setEditing(null);
      void accountsRes.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSavingEdit(false);
    }
  }

  async function removeAccount(a: Account) {
    try {
      await apiFetch(`/admin/accounts/${a.id}`, { method: "DELETE" });
      if (editing?.id === a.id) setEditing(null);
      toast.success("Account removed.");
      void accountsRes.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove");
    }
  }

  async function saveRule(e: React.FormEvent) {
    e.preventDefault();
    setSavingRule(true);
    try {
      await apiFetch("/admin/routing", { method: "POST", body: JSON.stringify(ruleForm) });
      toast.success("Routing rule saved.");
      setRuleForm({ model: "", policy: "prefer_free" });
      void rulesRes.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save rule");
    } finally {
      setSavingRule(false);
    }
  }

  async function deleteRule(r: RoutingRule) {
    try {
      await apiFetch(`/admin/routing/${r.id}`, { method: "DELETE" });
      toast.success("Routing rule deleted.");
      void rulesRes.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete rule");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Suno Accounts"
        description={
          <>
            Worker accounts used to serve generation requests. Each Suno login is one account with
            its own <code className="mx-1 rounded bg-black/30 px-1">__client</code> cookie — add as
            many (free or paid) as you need.
          </>
        }
        actions={
          <Button onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "Add account"}
          </Button>
        }
      />

      {error && (
        <ErrorState
          message={error}
          onRetry={() => {
            void accountsRes.reload();
            void rulesRes.reload();
          }}
        />
      )}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Label" htmlFor="acct-label">
                <Input
                  id="acct-label"
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="account-1"
                />
              </Field>
              <Field label="Type" htmlFor="acct-type">
                <Select
                  id="acct-type"
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value })}
                >
                  <option value="free">Free</option>
                  <option value="paid">Paid</option>
                </Select>
              </Field>
              <Field
                label="Client cookie"
                htmlFor="acct-cookie"
                hint="Log in to suno.com, then copy the __client cookie value from auth.suno.com (DevTools → Application → Cookies). One cookie per account."
              >
                <Input
                  id="acct-cookie"
                  value={form.client_cookie}
                  onChange={(e) => setForm({ ...form, client_cookie: e.target.value })}
                  placeholder="eyJ..."
                />
              </Field>
              <Field
                label="Device ID"
                htmlFor="acct-device"
                hint="Optional — a unique id is generated for you when left blank."
              >
                <Input
                  id="acct-device"
                  value={form.device_id}
                  onChange={(e) => setForm({ ...form, device_id: e.target.value })}
                  placeholder="leave blank to auto-generate"
                />
              </Field>
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save account"}
            </Button>
          </form>
        </Card>
      )}

      {editing && (
        <Card className="p-5">
          <form onSubmit={submitEdit} className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Edit “{editing.label}”</h2>
              <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                Cancel
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Label" htmlFor="edit-label">
                <Input
                  id="edit-label"
                  value={editForm.label}
                  onChange={(e) => setEditForm({ ...editForm, label: e.target.value })}
                />
              </Field>
              <Field label="Type" htmlFor="edit-type">
                <Select
                  id="edit-type"
                  value={editForm.type}
                  onChange={(e) => setEditForm({ ...editForm, type: e.target.value })}
                >
                  <option value="free">Free</option>
                  <option value="paid">Paid</option>
                </Select>
              </Field>
              <Field label="Client cookie" htmlFor="edit-cookie">
                <Input
                  id="edit-cookie"
                  value={editForm.client_cookie}
                  onChange={(e) => setEditForm({ ...editForm, client_cookie: e.target.value })}
                  placeholder="Leave blank to keep current"
                />
              </Field>
              <Field label="Device ID" htmlFor="edit-device">
                <Input
                  id="edit-device"
                  value={editForm.device_id}
                  onChange={(e) => setEditForm({ ...editForm, device_id: e.target.value })}
                  placeholder="Leave blank to keep current"
                />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editForm.is_active}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
              />
              Active
            </label>
            <Button type="submit" disabled={savingEdit}>
              {savingEdit ? "Saving…" : "Save changes"}
            </Button>
          </form>
        </Card>
      )}

      {accountsRes.loading ? (
        <LoadingState />
      ) : accounts.length === 0 ? (
        <EmptyState
          title="No Suno accounts configured."
          description="Add at least one account so generation requests can be served."
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Label</th>
                <th scope="col" className="px-4 py-3">Type</th>
                <th scope="col" className="px-4 py-3">Plan</th>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
                <th scope="col" className="px-4 py-3">Models</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3 font-medium">{a.label}</td>
                  <td className="px-4 py-3 capitalize">{a.type}</td>
                  <td className="px-4 py-3 capitalize">{a.live_plan}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{a.live_credits}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {a.live_models.join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">
                      {healthBadges(a).map((b) => (
                        <Badge key={b.label} tone={b.tone}>
                          {b.label}
                        </Badge>
                      ))}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <Button size="sm" variant="ghost" onClick={() => startEdit(a)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-300"
                      onClick={() => setPendingDelete(a)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Card className="p-5">
        <h2 className="text-sm font-semibold">Routing rules</h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          Map a model key (e.g. chirp-hawk) to an account policy.
        </p>
        <form onSubmit={saveRule} className="mt-3 flex flex-wrap gap-2">
          <Input
            value={ruleForm.model}
            onChange={(e) => setRuleForm({ ...ruleForm, model: e.target.value })}
            placeholder="Model key (e.g. chirp-hawk)"
            aria-label="Model key"
            className="w-full sm:w-64"
          />
          <Select
            value={ruleForm.policy}
            onChange={(e) => setRuleForm({ ...ruleForm, policy: e.target.value })}
            aria-label="Routing policy"
          >
            <option value="prefer_free">prefer_free</option>
            <option value="paid_only">paid_only</option>
            <option value="any">any</option>
          </Select>
          <Button type="submit" disabled={savingRule}>
            {savingRule ? "Saving…" : "Add rule"}
          </Button>
        </form>

        <div className="mt-4 space-y-2">
          {rules.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            >
              <span className="font-mono text-xs">{r.model}</span>
              <span className="flex items-center gap-3">
                <Badge tone="neutral">{r.policy}</Badge>
                <Button size="sm" variant="ghost" className="text-red-300" onClick={() => setPendingRule(r)}>
                  Delete
                </Button>
              </span>
            </div>
          ))}
          {rules.length === 0 && (
            <p className="text-xs text-[var(--muted)]">No custom rules — using defaults.</p>
          )}
        </div>
      </Card>

      <ConfirmDialog
        open={!!pendingDelete}
        title="Remove Suno account"
        danger
        confirmLabel="Remove"
        message={pendingDelete ? `Remove account “${pendingDelete.label}”? This cannot be undone.` : ""}
        onConfirm={() => (pendingDelete ? removeAccount(pendingDelete) : Promise.resolve())}
        onClose={() => setPendingDelete(null)}
      />

      <ConfirmDialog
        open={!!pendingRule}
        title="Delete routing rule"
        danger
        confirmLabel="Delete"
        message={pendingRule ? `Delete the routing rule for “${pendingRule.model}”?` : ""}
        onConfirm={() => (pendingRule ? deleteRule(pendingRule) : Promise.resolve())}
        onClose={() => setPendingRule(null)}
      />
    </div>
  );
}
