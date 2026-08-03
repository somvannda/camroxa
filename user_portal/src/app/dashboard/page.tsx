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

function remainingOf(remaining: number | null | undefined, quota: number | null | undefined): string {
  if (remaining == null && quota == null) return "Not on plan";
  const left = formatNumber(remaining ?? 0);
  if (quota == null) return `${left} left`;
  return `${left} / ${formatNumber(quota)}`;
}

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

  const q = state.quota;
  const songsRemaining = q?.songs_remaining ?? state.stats?.songs_remaining ?? null;
  const songsQuota = q?.songs_quota ?? state.stats?.songs_quota ?? null;
  const draftsRemaining = q?.drafts_remaining ?? state.stats?.drafts_remaining ?? null;
  const draftsQuota = q?.drafts_quota ?? state.stats?.drafts_quota ?? null;
  const imagesRemaining = q?.images_remaining ?? state.stats?.images_remaining ?? null;
  const imagesQuota = q?.images_quota ?? state.stats?.images_quota ?? null;
  const videosRemaining = q?.videos_remaining ?? null;
  const videosQuota = q?.videos_quota ?? null;
  const mergesRemaining = q?.merges_remaining ?? null;
  const mergesQuota = q?.merges_quota ?? null;

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Overview"
        description="Your plan limits at a glance, plus 7-day production and recent studio activity."
      />

      <PanelSection
        title="Your limits"
        description="Remaining allowance vs plan cap. Track exports cover studio + manual renders (one shared pool)."
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
            label="Suno packages (month)"
            value={remainingOf(songsRemaining, songsQuota)}
            hint="Packages left this billing period"
          />
          <StatTile
            label="Images (month)"
            value={remainingOf(imagesRemaining, imagesQuota)}
            hint="Artwork generations left"
          />
          <StatTile
            label="Drafts (month)"
            value={remainingOf(draftsRemaining, draftsQuota)}
            hint="Draft creations left"
          />
          <StatTile
            label="Track exports (month)"
            value={remainingOf(videosRemaining, videosQuota)}
            hint="Studio + manual share this pool"
          />
          <StatTile
            label="Merges (month)"
            value={remainingOf(mergesRemaining, mergesQuota)}
            hint="Video merges left this period"
          />
          <StatTile
            label="Wallet credits"
            value={formatCreditValue(walletBalance)}
            hint={`${planLabel} · ${state.profiles.length} channel(s)`}
          />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <StatTile
            label="Track exports today"
            value={remainingOf(q?.daily_videos_remaining, q?.daily_videos_limit)}
            hint="Account daily cap (all channels)"
          />
          <StatTile
            label="Merges today"
            value={remainingOf(q?.daily_merges_remaining, q?.daily_merges_limit)}
            hint="Account daily merge cap"
          />
        </div>
        {q?.channels?.length ? (
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Daily per channel</div>
            <div className="mt-2 grid gap-2 text-sm">
              {q.channels.slice(0, 4).map((channel) => (
                <div
                  key={channel.profile_id}
                  className="flex flex-wrap items-center justify-between gap-2 text-slate-300"
                >
                  <span className="font-medium text-white">{channel.profile_name}</span>
                  <span className="text-slate-400">
                    Drafts {channel.daily_drafts_remaining ?? "—"}/
                    {channel.daily_drafts_limit ?? "—"} · Songs{" "}
                    {channel.daily_songs_remaining}/{channel.daily_songs_limit} · Images{" "}
                    {channel.daily_images_remaining}/{channel.daily_images_limit}
                  </span>
                </div>
              ))}
              {q.channels.length > 4 ? (
                <div className="text-xs text-slate-500">
                  +{q.channels.length - 4} more on Billing → Credits
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
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
              label="Track exports left (month)"
              value={remainingOf(videosRemaining, videosQuota)}
            />
            <SummaryRow
              label="Track exports left (today)"
              value={remainingOf(q?.daily_videos_remaining, q?.daily_videos_limit)}
            />
            <SummaryRow label="Merges left (month)" value={remainingOf(mergesRemaining, mergesQuota)} />
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
