"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, CircleDollarSign, FolderKanban, UserRound } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  InlineBadge,
  SectionTitle,
  SummaryRow,
  formatCreditValue,
  formatDate,
  titleCase,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { updateCurrentUser } from "@/lib/channel-setup";

export default function DashboardAccountPage() {
  const { state, setState, websiteBaseUrl } = useControlPanel();
  const [displayName, setDisplayName] = React.useState("");
  const [savingDisplayName, setSavingDisplayName] = React.useState(false);

  React.useEffect(() => {
    setDisplayName(String(state.user?.display_name ?? ""));
  }, [state.user?.display_name]);

  if (!state.user) {
    return null;
  }

  const currentDisplayName = state.user.display_name?.trim() || "CAMXORA user";
  const walletBalance = state.wallet?.balance ?? state.user.credit_balance ?? 0;

  async function handleDisplayNameSave() {
    const nextValue = displayName.trim();
    if (!nextValue) {
      toast({
        variant: "destructive",
        title: "Display name required",
        description: "Enter a display name before saving.",
      });
      return;
    }

    setSavingDisplayName(true);
    try {
      const updated = await updateCurrentUser({ display_name: nextValue });
      setState((current) => ({ ...current, user: updated }));
      setDisplayName(String(updated.display_name ?? ""));
      toast({
        title: "Account updated",
        description: "Your display name has been saved.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update your account.";
      toast({ variant: "destructive", title: "Update failed", description: message });
    } finally {
      setSavingDisplayName(false);
    }
  }

  return (
    <div className="grid gap-6">
      <SectionTitle
        title="Account And Profile"
        description="Manage the identity, plan context, and account summary shown across your CAMXORA workspace."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(340px,0.82fr)_minmax(0,1.18fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.96),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.38)]">
          <CardHeader className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/25 bg-violet-500/10">
                <UserRound className="h-5 w-5 text-violet-200" />
              </div>
              <div>
                <CardTitle className="font-display text-2xl text-white">{currentDisplayName}</CardTitle>
                <CardDescription className="text-slate-300/72">{state.user.email}</CardDescription>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <InlineBadge text={state.user.plan_name ?? "No active subscription"} tone="blue" />
              <InlineBadge
                text={state.user.email_confirmed ? "Email verified" : "Email pending"}
                tone={state.user.email_confirmed ? "emerald" : "amber"}
              />
              <InlineBadge text={titleCase(state.user.status ?? "active")} tone="violet" />
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-300/72">
            <SummaryRow label="Display name" value={currentDisplayName} />
            <SummaryRow label="Email" value={state.user.email} />
            <SummaryRow label="Role" value={titleCase(state.user.role ?? "user")} />
            <SummaryRow label="Member since" value={formatDate(state.user.created_at)} />
            <SummaryRow label="Wallet balance" value={formatCreditValue(walletBalance)} />
            <SummaryRow
              label="Profiles in use"
              value={
                state.user.profile_allowance
                  ? `${state.profiles.length} / ${state.user.profile_allowance}`
                  : String(state.profiles.length)
              }
            />
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Profile identity</CardTitle>
            <CardDescription className="text-slate-300/72">
              Update the account name shown throughout the signed-in user experience.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label className="text-slate-100" htmlFor="account_display_name">
                Display name
              </Label>
              <Input
                id="account_display_name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Your display name"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <div className="grid gap-2">
                <Label className="text-slate-100" htmlFor="account_email_readonly">
                  Account email
                </Label>
                <Input
                  id="account_email_readonly"
                  value={state.user.email}
                  readOnly
                  className="border-white/10 bg-white/[0.03] text-slate-300"
                />
              </div>
              <Button onClick={() => void handleDisplayNameSave()} disabled={savingDisplayName}>
                {savingDisplayName ? "Saving..." : "Save account"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Account actions</CardTitle>
          <CardDescription className="text-slate-300/72">
            Move directly into adjacent areas that affect your account and plan experience.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <Link
            href="/dashboard/security"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/25 hover:bg-violet-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Open security</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Update password, review verification state, and manage sign-out controls.
            </div>
            <div className="mt-4 flex items-center gap-2 text-sm text-violet-200">
              Go to security
              <ArrowRight className="h-4 w-4" />
            </div>
          </Link>
          <Link
            href="/dashboard/profiles"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-sky-400/25 hover:bg-sky-500/[0.08]"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <FolderKanban className="h-4 w-4 text-sky-200" />
              Review profiles
            </div>
            <div className="mt-2 text-sm text-slate-300/72">
              Check channel identity assets and per-profile production readiness.
            </div>
          </Link>
          <Link
            href={`${websiteBaseUrl}/pricing`}
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/25 hover:bg-emerald-500/[0.08]"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <CircleDollarSign className="h-4 w-4 text-emerald-200" />
              Review plans
            </div>
            <div className="mt-2 text-sm text-slate-300/72">
              Compare plan allowance and pricing before your next subscription change.
            </div>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
