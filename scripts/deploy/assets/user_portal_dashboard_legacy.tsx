"use client";

import Link from "next/link";
import { ArrowRight, Coins, FolderKanban, Receipt } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  ActivityRow,
  EmptyPanel,
  PanelSection,
  QuotaMeter,
  SectionTitle,
  StatTile,
  SummaryGauge,
  SummaryRow,
  formatCreditValue,
  formatNumber,
} from "@/components/dashboard/control-panel-ui";
import { UsageCurveChart } from "@/components/dashboard/usage-curve-chart";
import { ChannelDailyQuotaTable, PipelineOrderHint } from "@/components/dashboard/channel-daily-quota-table";
import { Button } from "@/components/ui/button";
import { packagesToTracks } from "@/lib/quota";
import QuotaRenewalCard from "@/components/quota-renewal-card";
import { RenewalReminderBanner } from "@/components/dashboard/renewal-reminder-banner";

function usedFrom(
  used: number | null | undefined,
  remaining: number | null | undefined,
  limit: number | null | undefined,
): number | null {
  if (used != null) return used;
  if (remaining != null && limit != null) return Math.max(0, limit - remaining);
  return null;
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
  const songsLeft = q?.songs_remaining ?? state.stats?.songs_remaining ?? null;
  const songsLimit = q?.songs_quota ?? state.stats?.songs_quota ?? null;
  const draftsLeft = q?.drafts_remaining ?? state.stats?.drafts_remaining ?? null;
  const draftsLimit = q?.drafts_quota ?? state.stats?.drafts_quota ?? null;
  const imagesLeft = q?.images_remaining ?? state.stats?.images_remaining ?? null;
  const imagesLimit = q?.images_quota ?? state.stats?.images_quota ?? null;
  const videosLeft = q?.videos_remaining ?? null;
  const videosLimit = q?.videos_quota ?? null;
  const mergesLeft = q?.merges_remaining ?? null;
  const mergesLimit = q?.merges_quota ?? null;
  const channelCount = q?.channels?.length ?? state.profiles.length;

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Overview"
        description="Big number = how many you have left. Below it: used and your limit."
      />

      <RenewalReminderBanner />

      <QuotaRenewalCard />

      <PanelSection
        title="Credits"
        description="Total wallet credits and roughly what they cover. Video export and merge are free."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/billing?tab=credits">
              Credits
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Total credits"
            value={formatCreditValue(walletBalance)}
            hint={`${planLabel} · plan grant + packs`}
          />
          <StatTile
            label="≈ Songs"
            value={formatNumber(Math.floor(walletBalance / 10))}
            hint="10 credits per Suno request (2 versions)"
          />
          <StatTile
            label="≈ Images"
            value={formatNumber(Math.floor(walletBalance / 5))}
            hint="5 credits per image"
          />
          <StatTile label="Video / merge" value="Free" hint="0 credits" />
        </div>
      </PanelSection>

      <PanelSection
        title="This month"
        description={`${planLabel}${channelCount ? ` · ${channelCount} channels` : ""}. Resets on your next billing renewal.`}
        actions={
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/quota">
                Full quota plan
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/billing?tab=credits">
                Credits
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </div>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <QuotaMeter
            label="Drafts"
            left={draftsLeft}
            used={usedFrom(q?.drafts_used, draftsLeft, draftsLimit)}
            limit={draftsLimit}
          />
          <QuotaMeter
            label="Suno packages"
            left={songsLeft}
            used={usedFrom(q?.songs_used, songsLeft, songsLimit)}
            limit={songsLimit}
            footnote={
              songsLeft != null && songsLimit != null
                ? `≈${formatNumber(packagesToTracks(songsLeft) ?? 0)} / ${formatNumber(packagesToTracks(songsLimit) ?? 0)} song versions (1 pkg = 2 versions)`
                : "1 package = 1 Suno request = 2 song versions"
            }
          />
          <QuotaMeter
            label="Images"
            left={imagesLeft}
            used={usedFrom(q?.images_used, imagesLeft, imagesLimit)}
            limit={imagesLimit}
            footnote="Background + thumbnail share this pool"
          />
          <QuotaMeter
            label="Export video"
            left={videosLeft}
            used={usedFrom(q?.videos_used, videosLeft, videosLimit)}
            limit={videosLimit}
            footnote="Account-wide pool (not per channel)"
          />
          <QuotaMeter
            label="Merge video"
            left={mergesLeft}
            used={usedFrom(q?.merges_used, mergesLeft, mergesLimit)}
            limit={mergesLimit}
            footnote="Account-wide pool (not per channel)"
          />
          <StatTile
            label="Wallet credits"
            value={formatCreditValue(walletBalance)}
            hint="Bought credits (separate from plan)"
          />
        </div>
      </PanelSection>

      <PanelSection
        title="Today pipeline"
        description="Draft → Song → Image (per channel) → Export video → Merge video (account-wide). Resets every billing day."
      >
        <div className="mb-3">
          <PipelineOrderHint />
        </div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Steps 1—3 · per channel
        </h3>
        <ChannelDailyQuotaTable profiles={state.profiles} quota={q} />
        <h3 className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-slate-500">
          Steps 4—5 · account-wide
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <QuotaMeter
            label="4. Export video today"
            left={q?.daily_videos_remaining}
            used={usedFrom(
              q?.daily_videos_used,
              q?.daily_videos_remaining,
              q?.daily_videos_limit,
            )}
            limit={q?.daily_videos_limit}
          />
          <QuotaMeter
            label="5. Merge video today"
            left={q?.daily_merges_remaining}
            used={usedFrom(
              q?.daily_merges_used,
              q?.daily_merges_remaining,
              q?.daily_merges_limit,
            )}
            limit={q?.daily_merges_limit}
          />
        </div>
      </PanelSection>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Studio exports (all time)"
          value={formatNumber(studioExports)}
          hint="Progress / pipeline renders"
        />
        <StatTile
          label="Manual exports (all time)"
          value={formatNumber(manualExports)}
          hint="Video-page Manual Export"
        />
        <StatTile
          label="YouTube uploads (all time)"
          value={formatNumber(youtubeUploads)}
          hint="Successful publishes"
        />
      </div>

      <PanelSection
        title="7-day trend"
        description="Songs, images, studio exports, manual exports, and YouTube uploads."
      >
        <UsageCurveChart days={usageByDay} />
      </PanelSection>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <PanelSection title="Summary" description="Share of generated output.">
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
              label="Images left this month"
              value={
                imagesLeft != null
                  ? `${formatNumber(imagesLeft)}${
                      imagesLimit != null ? ` of ${formatNumber(imagesLimit)}` : ""
                    }`
                  : "–"
              }
            />
            <SummaryRow
              label="Merges left this month"
              value={
                mergesLeft != null
                  ? `${formatNumber(mergesLeft)}${
                      mergesLimit != null ? ` of ${formatNumber(mergesLimit)}` : ""
                    }`
                  : "–"
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
