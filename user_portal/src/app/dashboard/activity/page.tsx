"use client";

import * as React from "react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  ActivityRow,
  EmptyPanel,
  PanelSection,
  SectionTitle,
  StatTile,
  SummaryRow,
  UsageBar,
  formatCreditValue,
  formatDateTime,
  formatNumber,
  titleCase,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import {
  formatUsageTransactionLabel,
  resolveBillingMode,
  type BillingMode,
  type WalletTransaction,
} from "@/lib/credits";

function billingBadgeClass(mode: BillingMode): string {
  if (mode === "plan_allowance") return "text-sky-300";
  if (mode === "platform_absorb") return "text-amber-300";
  if (mode === "wallet") return "text-rose-300";
  return "text-emerald-300";
}

function amountClass(mode: BillingMode, direction: string): string {
  if (mode === "plan_allowance") return "text-sky-300";
  if (mode === "platform_absorb") return "text-amber-300";
  if (direction === "credit") return "text-emerald-300";
  return "text-rose-300";
}

function formatLedgerAmount(transaction: WalletTransaction, mode: BillingMode): string {
  if (mode === "plan_allowance" || mode === "platform_absorb") {
    return "0";
  }
  return `${transaction.direction === "credit" ? "+" : "−"}${formatCreditValue(transaction.amount)}`;
}

export default function DashboardActivityPage() {
  const { state } = useControlPanel();
  const [resourceFilter, setResourceFilter] = React.useState<"all" | "songs" | "images" | "videos">("all");
  const [statusFilter, setStatusFilter] = React.useState<"all" | "success" | "pending" | "failed">("all");
  const [billingFilter, setBillingFilter] = React.useState<"all" | BillingMode>("all");

  const batches = state.musicHistory?.batches ?? [];
  const totalSongsInBatches = batches.reduce((sum, batch) => sum + batch.song_count, 0);
  const totalImageJobs = batches.reduce(
    (sum, batch) => sum + batch.songs.reduce((songSum, song) => songSum + song.image_jobs_total, 0),
    0,
  );
  const completedUploads = batches.reduce(
    (sum, batch) =>
      sum +
      batch.songs.filter(
        (song) => song.youtube_status?.toLowerCase() === "uploaded" || song.youtube_status?.toLowerCase() === "published",
      ).length,
    0,
  );
  const usageByDay = state.stats?.usage_by_day ?? [];
  const peakDay = usageByDay.reduce((max, day) => Math.max(max, day.songs + day.images + day.videos), 0);
  const walletLoaded = state.wallet != null;
  const recentTransactions = (state.wallet?.recent_transactions ?? []).filter((tx) => {
    if (billingFilter === "all") return true;
    return resolveBillingMode(tx) === billingFilter;
  });

  const filteredUsage = usageByDay.map((day) => ({
    ...day,
    songs: resourceFilter === "all" || resourceFilter === "songs" ? day.songs : 0,
    images: resourceFilter === "all" || resourceFilter === "images" ? day.images : 0,
    videos: resourceFilter === "all" || resourceFilter === "videos" ? day.videos : 0,
  }));

  const filteredActivity = (state.stats?.recent_activity ?? []).filter((item) => {
    const kind = item.kind.toLowerCase();
    const status = item.status.toLowerCase();
    const resourceMatch =
      resourceFilter === "all" ||
      (resourceFilter === "songs" && kind === "song") ||
      (resourceFilter === "images" && kind === "image") ||
      (resourceFilter === "videos" && kind === "video");
    const statusMatch =
      statusFilter === "all" ||
      (statusFilter === "success" && ["paid", "success", "completed", "active", "redeemed"].includes(status)) ||
      (statusFilter === "pending" && ["pending", "processing", "running"].includes(status)) ||
      (statusFilter === "failed" && ["failed", "blocked", "expired", "cancelled", "rejected", "suspended"].includes(status));
    return resourceMatch && statusMatch;
  });

  const filteredBatches = batches.filter((batch) => {
    if (resourceFilter === "images") {
      return batch.songs.some((song) => song.image_jobs_total > 0);
    }
    if (resourceFilter === "videos") {
      return batch.songs.some((song) => Boolean(song.youtube_status));
    }
    return true;
  });

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Usage"
        description="Billing ledger, production metrics, and recent batch output."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Songs" value={formatNumber(totalSongsInBatches)} hint="In loaded batch history" />
        <StatTile label="Image jobs" value={formatNumber(totalImageJobs)} hint="Cover and asset generation" />
        <StatTile label="Uploads done" value={formatNumber(completedUploads)} hint="YouTube marked complete" />
        <StatTile label="Videos total" value={formatNumber(state.stats?.videos_generated ?? 0)} hint="Recorded video jobs" />
      </div>

      <PanelSection
        title="Filters"
        description="Narrow ledger rows and analytics by resource, status, and billing mode."
      >
        <div className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            {(["all", "songs", "images", "videos"] as const).map((value) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={resourceFilter === value ? "default" : "outline"}
                className="h-8"
                onClick={() => setResourceFilter(value)}
              >
                {titleCase(value)}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {(["all", "success", "pending", "failed"] as const).map((value) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={statusFilter === value ? "default" : "outline"}
                className="h-8"
                onClick={() => setStatusFilter(value)}
              >
                {titleCase(value)}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["all", "All billing"],
                ["plan_allowance", "Plan"],
                ["wallet", "Wallet"],
                ["platform_absorb", "Absorbed"],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={billingFilter === value ? "default" : "outline"}
                className="h-8"
                onClick={() => setBillingFilter(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>
      </PanelSection>

      <PanelSection title="Usage ledger" description="Plan allowance, wallet charges, and platform-absorbed rows.">
        {!walletLoaded ? (
          <EmptyPanel text="Unable to load usage history." />
        ) : recentTransactions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Operation</th>
                  <th className="px-3 py-2">Billing</th>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {recentTransactions.map((transaction) => {
                  const mode = resolveBillingMode(transaction);
                  return (
                    <tr key={transaction.id} className="border-b border-slate-800/70">
                      <td className="px-3 py-2 text-slate-200">
                        {transaction.purpose || transaction.reason}
                      </td>
                      <td className={`px-3 py-2 text-xs ${billingBadgeClass(mode)}`}>
                        {formatUsageTransactionLabel(transaction)}
                      </td>
                      <td className="px-3 py-2 text-slate-400">{formatDateTime(transaction.created_at)}</td>
                      <td className={`px-3 py-2 text-right font-medium ${amountClass(mode, transaction.direction)}`}>
                        {formatLedgerAmount(transaction, mode)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyPanel text="No ledger rows for this filter yet." />
        )}
      </PanelSection>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
        <PanelSection title="7-day trend" description={`Filtered by ${titleCase(resourceFilter)}.`}>
          <div className="grid gap-3 md:grid-cols-7">
            {filteredUsage.length > 0 ? (
              filteredUsage.map((day) => <UsageBar key={day.date} day={day} peakDay={peakDay} />)
            ) : (
              <EmptyPanel text="No usage data yet." />
            )}
          </div>
        </PanelSection>

        <PanelSection title="Summary">
          <div className="grid gap-2 text-sm">
            <SummaryRow label="Filtered events" value={formatNumber(filteredActivity.length)} />
            <SummaryRow label="Batches in view" value={formatNumber(filteredBatches.length)} />
            <SummaryRow label="Songs generated" value={formatNumber(state.stats?.songs_generated ?? 0)} />
            <SummaryRow label="Images generated" value={formatNumber(state.stats?.images_generated ?? 0)} />
            <SummaryRow label="Credits spent" value={formatCreditValue(state.stats?.credits_spent ?? 0)} />
          </div>
        </PanelSection>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <PanelSection title="Recent activity" description="Latest song, image, and video events.">
          {filteredActivity.length > 0 ? (
            <div className="grid gap-2">
              {filteredActivity.slice(0, 10).map((item, index) => (
                <ActivityRow key={`${item.timestamp}-${item.kind}-${index}`} item={item} />
              ))}
            </div>
          ) : (
            <EmptyPanel text="No activity matches the current filters." />
          )}
        </PanelSection>

        <PanelSection title="Recent batches" description="Output sets from the desktop app.">
          {filteredBatches.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Profile</th>
                    <th className="px-3 py-2">Songs</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBatches.map((batch) => (
                    <tr key={batch.batch_id} className="border-b border-slate-800/70">
                      <td className="px-3 py-2 text-slate-200">
                        {batch.ok_profile_name ?? "Primary"}
                        {batch.alt_profile_name ? ` + ${batch.alt_profile_name}` : ""}
                      </td>
                      <td className="px-3 py-2 text-slate-400">{batch.song_count}</td>
                      <td className="px-3 py-2 text-slate-400">{titleCase(batch.status)}</td>
                      <td className="px-3 py-2 text-slate-400">{formatDateTime(batch.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyPanel text="No batches match the current filters." />
          )}
        </PanelSection>
      </div>
    </div>
  );
}
