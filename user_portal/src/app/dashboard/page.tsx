"use client";

import Link from "next/link";
import { ArrowRight, Coins, FolderKanban, Music4, UploadCloud } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  PanelSection,
  SectionTitle,
  StatTile,
  SummaryRow,
  formatCreditValue,
  formatDateTime,
  formatNumber,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";

export default function DashboardOverviewPage() {
  const { state } = useControlPanel();

  if (!state.user) {
    return null;
  }

  const walletBalance = state.wallet?.balance ?? state.user.credit_balance ?? 0;
  const planLabel = state.user.plan_name ?? "No active subscription";

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Overview"
        description="Plan quota, wallet credits, profiles, and recent production activity."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Plan" value={planLabel} hint={`${state.profiles.length} channel profile(s) active`} />
        <StatTile label="Wallet credits" value={formatCreditValue(walletBalance)} hint="Top up under Billing → Credits." />
        <StatTile
          label="Suno packages left"
          value={formatNumber(state.stats?.songs_remaining ?? 0)}
          hint={state.stats?.songs_quota ? `of ${formatNumber(state.stats.songs_quota)} this period` : "Plan quota"}
        />
        <StatTile
          label="Videos uploaded"
          value={formatNumber(state.stats?.videos_uploaded ?? 0)}
          hint="Successful YouTube upload jobs"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <PanelSection title="Quota snapshot">
          <div className="grid gap-2 text-sm">
            <SummaryRow label="Drafts remaining" value={formatNumber(state.quota?.drafts_remaining ?? state.stats?.drafts_remaining ?? 0)} />
            <SummaryRow label="Images remaining" value={formatNumber(state.quota?.images_remaining ?? state.stats?.images_remaining ?? 0)} />
            <SummaryRow label="Videos remaining" value={formatNumber(state.quota?.videos_remaining ?? 0)} />
            <SummaryRow label="Credits spent" value={formatCreditValue(state.stats?.credits_spent ?? 0)} />
          </div>
        </PanelSection>

        <PanelSection title="Quick links">
          <div className="grid gap-2">
            <Button variant="outline" className="justify-between border-slate-700 bg-slate-950/40" asChild>
              <Link href="/dashboard/profiles">
                Manage profiles
                <FolderKanban className="h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" className="justify-between border-slate-700 bg-slate-950/40" asChild>
              <Link href="/dashboard/billing?tab=credits">
                Buy / redeem credits
                <Coins className="h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" className="justify-between border-slate-700 bg-slate-950/40" asChild>
              <Link href="/dashboard/activity">
                Usage ledger
                <Music4 className="h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" className="justify-between border-slate-700 bg-slate-950/40" asChild>
              <Link href="/dashboard/profiles">
                YouTube connections
                <UploadCloud className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </PanelSection>
      </div>

      <PanelSection
        title="Last activity"
        description={
          state.stats?.recent_activity[0]?.timestamp
            ? formatDateTime(state.stats.recent_activity[0].timestamp)
            : "No generation activity recorded yet."
        }
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/activity">
              View all
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        }
      >
        {state.stats?.recent_activity?.length ? (
          <div className="grid gap-2 text-sm text-slate-300">
            {state.stats.recent_activity.slice(0, 6).map((item, index) => (
              <div key={`${item.timestamp}-${index}`} className="flex items-center justify-between rounded-md border border-slate-800 px-3 py-2">
                <span>
                  {item.kind}
                  {item.detail ? ` · ${item.detail}` : ""}
                </span>
                <span className="text-xs text-slate-500">{formatDateTime(item.timestamp)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Run a batch in the desktop app to populate activity here.</p>
        )}
      </PanelSection>
    </div>
  );
}
