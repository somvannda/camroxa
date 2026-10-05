"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  PanelSection,
  SectionTitle,
  SummaryRow,
  formatDateTime,
  titleCase,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { updateCurrentUser } from "@/lib/channel-setup";

export default function DashboardSecurityPage() {
  return (
    <React.Suspense fallback={null}>
      <DashboardSecurityContent />
    </React.Suspense>
  );
}

function DashboardSecurityContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { state, setState, refreshSecurity } = useControlPanel();
  const [displayName, setDisplayName] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setDisplayName(String(state.user?.display_name ?? ""));
    void refreshSecurity();
  }, [refreshSecurity, state.user?.display_name]);

  if (!state.user) return null;

  const sessions = state.security?.sessions ?? [];
  const events = (state.security?.events ?? []).slice(0, 12);

  async function handleSaveDisplayName() {
    const nextValue = displayName.trim();
    if (!nextValue) {
      toast({ variant: "destructive", title: "Display name required", description: "Enter a name before saving." });
      return;
    }
    setSaving(true);
    try {
      const updated = await updateCurrentUser({ display_name: nextValue });
      setState((current) => ({ ...current, user: updated }));
      toast({ title: "Profile updated", description: "Display name saved." });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Update failed",
        description: err instanceof Error ? err.message : "Unable to update profile.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Account & security"
        description="Profile identity, sign-in activity, and desktop sync status."
      />

      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3 text-sm">
        <Button
          type="button"
          variant={searchParams.get("tab") === "security" ? "default" : "ghost"}
          size="sm"
          onClick={() => router.replace("/dashboard/security?tab=security")}
        >
          Security
        </Button>
        <Button type="button" variant="ghost" size="sm" asChild>
          <Link href="/dashboard/account">Account summary</Link>
        </Button>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <PanelSection title="Profile" description="Shown in the desktop app and portal.">
          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="display-name">Display name</Label>
              <Input
                id="display-name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className="border-slate-700 bg-slate-950/60"
              />
            </div>
            <Button type="button" disabled={saving} onClick={() => void handleSaveDisplayName()}>
              {saving ? "Saving…" : "Save profile"}
            </Button>
          </div>
        </PanelSection>

        <PanelSection title="Sign-in footprint" description="Recent portal and desktop activity.">
          <div className="grid gap-2 text-sm text-slate-300">
            <SummaryRow label="Desktop last seen" value={formatDateTime(state.security?.desktop_last_seen)} />
            <SummaryRow label="Web last seen" value={formatDateTime(state.security?.web_last_seen)} />
            <SummaryRow label="Email" value={state.user.email_confirmed ? "Verified" : "Pending verification"} />
          </div>
        </PanelSection>
      </div>

      <PanelSection title="Active sessions" description="Grouped by client and IP.">
        {sessions.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Client</th>
                  <th className="px-3 py-2">IP</th>
                  <th className="px-3 py-2">Last seen</th>
                  <th className="px-3 py-2">Activity</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={`${session.client_id}-${session.source_ip}`} className="border-b border-slate-800/70">
                    <td className="px-3 py-2 text-slate-200">{session.client_id || "Unknown"}</td>
                    <td className="px-3 py-2 text-slate-400">{session.source_ip || "—"}</td>
                    <td className="px-3 py-2 text-slate-400">{formatDateTime(session.last_seen)}</td>
                    <td className="px-3 py-2 text-slate-400">
                      {session.successful_logins} ok · {session.failed_attempts} failed
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyPanel text="No session history yet." />
        )}
      </PanelSection>

      <PanelSection title="Recent security events" description="Auth outcomes from the control panel API.">
        {events.length ? (
          <div className="grid gap-2">
            {events.map((event) => (
              <div
                key={event.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2 text-slate-200">
                  <ShieldCheck className="h-4 w-4 text-slate-500" />
                  {titleCase(event.action_type.replace(/_/g, " "))}
                </div>
                <div className="text-xs text-slate-500">
                  {titleCase(event.outcome)} · {formatDateTime(event.created_at)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyPanel text="No security events recorded yet." />
        )}
      </PanelSection>
    </div>
  );
}
