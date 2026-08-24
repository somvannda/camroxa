"use client";

import Link from "next/link";
import { ArrowRight, Coins, FolderKanban, Receipt } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  ActivityRow,
  EmptyPanel,
  PanelSection,
  SectionTitle,
  StatTile,
  SummaryGauge,
  SummaryRow,
  formatCreditValue,
  formatNumber,
} from "@/components/dashboard/control-panel-ui";
import { UsageCurveChart } from "@/components/dashboard/usage-curve-chart";
import { Button } from "@/components/ui/button";

export default function DashboardOverviewPage() {
  const { state } = useControlPanel();

  if (!state.user) {
    return null;
  }

  const walletBalance = state.wallet?.balance ?? state.user.credit_balance ?? 0;
  const planLabel = state.user.plan_name ?? "No active subscription";
  const usageByDay = state.stats?.usage_by_day ?? [];
  const recentActivity = state.stats?.recent_activity ?? [];
  const songsGenerated = state.stats?.songs_generated ?? 0;
  const imagesGenerated = state.stats?.images_generated ?? 0;
  const studioExports = state.stats?.studio_exports ?? 0;
  const manualExports = state.stats?.manual_exports ?? 0;
  const youtubeUploads = state.stats?.youtube_uploads ?? state.stats?.videos_uploaded ?? 0;
  const videosGenerated = studioExports + manualExports || state.stats?.videos_generated || 0;
  const generationPeak = Math.max(songsGenerated, imagesGenerated, videosGenerated, youtubeUploads, 1);

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Overview"
        description="One credit wallet plus 7-day production and recent studio activity."
      />

      <PanelSection
        title="Credits"
        description="Generate spends the wallet. Song / draft / image meters are not the balance."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/billing?tab=credits">
              Full credits
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <StatTile
            label="Wallet credits"
            value={formatCreditValue(walletBalance)}
            hint={`${planLabel} · ${state.profiles.length} channel(s)`}
          />
          <StatTile
            label="Credits spent"
            value={formatCreditValue(state.stats?.credits_spent ?? 0)}
            hint="This billing period"
          />
        </div>
      </PanelSection>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Studio exports"
          value={formatNumber(studioExports)}
          hint="Progress / pipeline track renders"
        />
        <StatTile
          label="Manual exports"
          value={formatNumber(manualExports)}
          hint="Video-page Manual Export button"
        />
        <StatTile
          label="YouTube uploads"
          value={formatNumber(youtubeUploads)}
          hint="Successful YouTube publish jobs"
        />
      </div>

      <PanelSection
        title="7-day trend"
        description="Songs, images, studio exports, manual exports, and YouTube uploads."
      >
        <UsageCurveChart days={usageByDay} />
      </PanelSection>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <PanelSection title="Summary" description="Share of generated output this period.">
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryGauge
              label="Songs"
              value={songsGenerated}
              max={generationPeak}
              color="#7466F1"
              detail={`${formatNumber(songsGenerated)} generated`}
            />
            <SummaryGauge
              label="Images"
              value={imagesGenerated}
              max={generationPeak}
              color="#1ABCFE"
              detail={`${formatNumber(imagesGenerated)} generated`}
            />
            <SummaryGauge
              label="Track exports"
              value={videosGenerated}
              max={generationPeak}
              color="#0ACF83"
              detail={`${formatNumber(studioExports)} studio · ${formatNumber(manualExports)} manual`}
            />
          </div>
          <div className="mt-5 grid gap-2 text-sm">
            <SummaryRow label="Credits spent" value={formatCreditValue(state.stats?.credits_spent ?? 0)} />
            <SummaryRow
              label="Avg studio export (7d)"
              value={
                state.stats?.avg_studio_export_ms != null
                  ? `${(state.stats.avg_studio_export_ms / 1000).toFixed(1)}s`
                  : "—"
              }
            />
            <SummaryRow
              label="Avg manual export (7d)"
              value={
                state.stats?.avg_manual_export_ms != null
                  ? `${(state.stats.avg_manual_export_ms / 1000).toFixed(1)}s`
                  : "—"
              }
            />
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
                <Receipt className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </PanelSection>
      </div>

      <PanelSection
        title="Recent activity"
        description="Latest song, image, and video events."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/activity">
              Open ledger
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        }
      >
        {recentActivity.length > 0 ? (
          <div className="grid gap-2">
            {recentActivity.slice(0, 10).map((item, index) => (
              <ActivityRow key={`${item.timestamp}-${item.kind}-${index}`} item={item} />
            ))}
          </div>
        ) : (
          <EmptyPanel text="Run a batch in the desktop app to populate activity here." />
        )}
      </PanelSection>
    </div>
  );
}
