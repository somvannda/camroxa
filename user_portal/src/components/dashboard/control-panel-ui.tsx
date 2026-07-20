"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { formatCredits } from "@/lib/credit-format";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { BillingPayment } from "@/lib/billing";
import type { ExistingProfile } from "@/lib/channel-setup";
import type { MusicHistoryBatch } from "@/lib/music-history";
import type { RedeemHistoryItem } from "@/lib/redeem-codes";

export function SectionTitle(props: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-xl font-semibold tracking-tight text-white">{props.title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-slate-400">{props.description}</p>
    </div>
  );
}

export function PanelSection(props: {
  title: string;
  description?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/40">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div>
          <h3 className="text-sm font-medium text-slate-100">{props.title}</h3>
          {props.description ? <p className="mt-0.5 text-xs text-slate-500">{props.description}</p> : null}
        </div>
        {props.actions}
      </div>
      <div className="p-4">{props.children}</div>
    </section>
  );
}

export function StatTile(props: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{props.label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{props.value}</div>
      {props.hint ? <div className="mt-1 text-xs text-slate-500">{props.hint}</div> : null}
    </div>
  );
}

export function MetricCard(props: {
  label: string;
  value: string;
  detail: string;
  tone: "violet" | "blue" | "sky" | "emerald";
  icon: LucideIcon;
}) {
  const toneClass =
    props.tone === "emerald"
      ? "from-emerald-400/18 to-emerald-300/8 text-emerald-300"
      : props.tone === "sky"
        ? "from-cyan-400/18 to-sky-300/8 text-sky-200"
        : props.tone === "blue"
          ? "from-sky-400/18 to-blue-300/8 text-sky-200"
          : "from-violet-400/18 to-fuchsia-300/8 text-violet-200";

  return (
    <div className={`rounded-[24px] border border-white/10 bg-gradient-to-br ${toneClass} p-5`}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{props.label}</div>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04]">
          <props.icon className="h-4 w-4" />
        </div>
      </div>
      <div className="mt-4 text-2xl font-semibold text-white">{props.value}</div>
      <div className="mt-2 text-sm text-slate-300/72">{props.detail}</div>
    </div>
  );
}

export function UsageBar(props: {
  day: { date: string; songs: number; images: number; videos: number };
  peakDay: number;
}) {
  const total = props.day.songs + props.day.images + props.day.videos;
  const peak = props.peakDay > 0 ? props.peakDay : 1;
  const songsHeight = `${Math.max((props.day.songs / peak) * 100, props.day.songs > 0 ? 10 : 0)}%`;
  const imagesHeight = `${Math.max((props.day.images / peak) * 100, props.day.images > 0 ? 10 : 0)}%`;
  const videosHeight = `${Math.max((props.day.videos / peak) * 100, props.day.videos > 0 ? 10 : 0)}%`;

  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
      <div className="flex h-36 items-end gap-1.5">
        <div className="flex-1 rounded-t-full bg-gradient-to-t from-violet-500/85 to-violet-300/80" style={{ height: songsHeight }} />
        <div className="flex-1 rounded-t-full bg-gradient-to-t from-sky-500/85 to-cyan-300/80" style={{ height: imagesHeight }} />
        <div className="flex-1 rounded-t-full bg-gradient-to-t from-emerald-500/85 to-emerald-300/80" style={{ height: videosHeight }} />
      </div>
      <div className="mt-3 text-center text-xs text-slate-400">{formatShortDate(props.day.date)}</div>
      <div className="mt-1 text-center text-sm font-medium text-white">{formatNumber(total)}</div>
    </div>
  );
}

export function SummaryRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="text-slate-400">{props.label}</div>
      <div className="text-right font-medium text-white">{props.value}</div>
    </div>
  );
}

export function SummaryGauge(props: {
  label: string;
  value: number;
  max: number;
  color: string;
  detail: string;
}) {
  const pct = props.max > 0 ? Math.min(100, Math.round((props.value / props.max) * 100)) : 0;
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-5">
      <svg width="96" height="96" viewBox="0 0 96 96" className="mb-3">
        <circle cx="48" cy="48" r={radius} fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth="8" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke={props.color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 48 48)"
        />
        <text x="48" y="52" textAnchor="middle" className="fill-white text-sm font-semibold">
          {pct}%
        </text>
      </svg>
      <div className="text-sm font-medium text-white">{props.label}</div>
      <div className="mt-1 text-xs text-slate-400">{props.detail}</div>
    </div>
  );
}

export function PaymentRow(props: { payment: BillingPayment }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="truncate font-medium text-white">{props.payment.plan_name}</div>
          <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${getStatusPillClass(props.payment.status)}`}>
            {props.payment.status}
          </span>
        </div>
        <div className="mt-1 text-xs text-slate-400">
          {formatMoney(props.payment.amount_cents)}
          {props.payment.redeem_code ? ` • ${props.payment.redeem_code}` : ""}
          {props.payment.provider ? ` • ${props.payment.provider}` : ""}
        </div>
      </div>
      <div className="whitespace-nowrap text-right">
        <div className="text-sm text-white">{formatDate(props.payment.created_at)}</div>
        <div className="text-xs text-slate-500">{formatTime(props.payment.created_at)}</div>
      </div>
    </div>
  );
}

export function RedeemHistoryRow(props: { item: RedeemHistoryItem }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="truncate font-medium text-white">{props.item.code}</div>
          <div className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${getRedeemStatusClass(props.item.status)}`}>
            {props.item.status}
          </div>
        </div>
        <div className="mt-1 text-xs text-slate-400">
          {props.item.reward_type === "credit_grant"
            ? `${formatCreditValue(props.item.credit_amount ?? 0)} added`
            : `${formatMoney(props.item.amount_cents)} checkout amount`}
          {props.item.plan_name ? ` • ${props.item.plan_name}` : " • Wallet credit"}
        </div>
      </div>
      <div className="whitespace-nowrap text-right">
        <div className="text-sm text-slate-200">{formatDate(props.item.created_at)}</div>
        <div className="text-xs text-slate-500">{formatTime(props.item.created_at)}</div>
      </div>
    </div>
  );
}

export function ProfileCard(props: { profile: ExistingProfile }) {
  const coverCount = getCoverCount(props.profile.image_config);
  const youtubeConnected = hasYouTubeConnection(props.profile.youtube_config);

  return (
    <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="truncate font-display text-2xl text-white">
              {props.profile.name}
            </CardTitle>
            <CardDescription className="mt-2 text-slate-300/72">
              Channel identity and production-ready asset state.
            </CardDescription>
          </div>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-base font-semibold text-violet-200">
            {getInitials(props.profile.name)}
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm text-slate-300/74">
        <div className="flex flex-wrap gap-2">
          <InlineBadge text={props.profile.logo_path ? "Logo ready" : "Logo pending"} tone={props.profile.logo_path ? "emerald" : "amber"} />
          <InlineBadge text={`${coverCount} covers`} tone="blue" />
          <InlineBadge text={youtubeConnected ? "YouTube linked" : "YouTube pending"} tone={youtubeConnected ? "emerald" : "amber"} />
        </div>
        <SummaryRow label="Resolution" value={props.profile.output_resolution ?? "1920x1080"} />
        <SummaryRow label="Folder" value={props.profile.folder_name ?? "Not configured"} />
        <SummaryRow label="Run prefix" value={props.profile.run_prefix ?? "Not configured"} />
        <SummaryRow label="Updated" value={formatDateTime(props.profile.updated_at)} />
      </CardContent>
    </Card>
  );
}

export function ActivityRow(props: { item: { timestamp: string; kind: string; detail: string; status: string } }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="font-medium text-white">{props.item.kind}</div>
          <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${getStatusPillClass(props.item.status)}`}>
            {props.item.status}
          </span>
        </div>
        <div className="truncate text-xs text-slate-400">{props.item.detail}</div>
      </div>
      <div className="whitespace-nowrap text-right text-xs text-slate-400">
        {formatDateTime(props.item.timestamp)}
      </div>
    </div>
  );
}

export function MusicBatchCard(props: { batch: MusicHistoryBatch }) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="font-medium text-white">
              {props.batch.ok_profile_name ?? "Primary profile"}
              {props.batch.alt_profile_name ? ` + ${props.batch.alt_profile_name}` : ""}
            </div>
            <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${getStatusPillClass(props.batch.status)}`}>
              {props.batch.status}
            </span>
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {props.batch.song_count} songs • {props.batch.planned_days} planned days • {formatDate(props.batch.created_at)}
          </div>
        </div>
        <div className="text-xs text-slate-500">{props.batch.batch_id.slice(0, 8)}</div>
      </div>
      <div className="mt-4 grid gap-2">
        {props.batch.songs.slice(0, 3).map((song) => (
          <div
            key={song.song_id}
            className="flex items-center justify-between gap-4 rounded-2xl border border-white/8 bg-black/10 px-3 py-3 text-sm"
          >
            <div className="min-w-0">
              <div className="truncate font-medium text-white">{song.title ?? `Song ${song.batch_index + 1}`}</div>
              <div className="truncate text-xs text-slate-400">
                {song.image_jobs_completed}/{song.image_jobs_total} image jobs
                {song.youtube_status ? ` • YouTube ${song.youtube_status}` : ""}
              </div>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${getStatusPillClass(song.status)}`}>
              {song.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function InlineBadge(props: {
  text: string;
  tone: "violet" | "blue" | "emerald" | "amber" | "rose";
}) {
  const className =
    props.tone === "emerald"
      ? "border-emerald-400/25 bg-emerald-500/10 text-emerald-300"
      : props.tone === "blue"
        ? "border-sky-400/25 bg-sky-500/10 text-sky-200"
        : props.tone === "amber"
          ? "border-amber-400/25 bg-amber-500/10 text-amber-200"
          : props.tone === "rose"
            ? "border-rose-400/25 bg-rose-500/10 text-rose-300"
            : "border-violet-400/25 bg-violet-500/10 text-violet-200";

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] ${className}`}>
      {props.text}
    </span>
  );
}

export function EmptyPanel(props: { text: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-slate-400">
      {props.text}
    </div>
  );
}

export function formatMoney(cents: number | null | undefined) {
  if (cents === null || cents === undefined) return "$0.00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

export function formatCreditValue(value: number | null | undefined) {
  return formatCredits(value);
}

export function formatNumber(value: number | null | undefined) {
  return Number(value ?? 0).toLocaleString();
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Date(value).toLocaleDateString();
}

export function formatTime(value: string | null | undefined) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString();
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Date(value).toLocaleString();
}

export function formatShortDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function getRedeemStatusClass(status: string) {
  if (status === "redeemed" || status === "paid") {
    return "border border-emerald-400/25 bg-emerald-500/10 text-emerald-300";
  }
  if (status === "failed" || status === "rejected") {
    return "border border-rose-400/25 bg-rose-500/10 text-rose-300";
  }
  return "border border-white/10 bg-white/[0.04] text-slate-300";
}

export function getStatusPillClass(status: string) {
  const normalized = status.trim().toLowerCase();
  if (["paid", "success", "completed", "active", "redeemed"].includes(normalized)) {
    return "border border-emerald-400/25 bg-emerald-500/10 text-emerald-300";
  }
  if (["pending", "processing", "running"].includes(normalized)) {
    return "border border-amber-400/25 bg-amber-500/10 text-amber-200";
  }
  if (["failed", "blocked", "expired", "cancelled", "rejected", "suspended"].includes(normalized)) {
    return "border border-rose-400/25 bg-rose-500/10 text-rose-300";
  }
  return "border border-white/10 bg-white/[0.04] text-slate-300";
}

export function getInitials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "CU";
}

export function titleCase(value: string) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function getCoverCount(imageConfig: Record<string, unknown> | undefined) {
  const covers = imageConfig?.cover_paths;
  return Array.isArray(covers) ? covers.length : 0;
}

function hasYouTubeConnection(youtubeConfig: Record<string, unknown> | undefined) {
  if (!youtubeConfig) return false;
  return Boolean(
    youtubeConfig.channel_id ||
      youtubeConfig.channel_name ||
      youtubeConfig.channel_title ||
      youtubeConfig.selected_channel_id,
  );
}

export { getCoverCount, hasYouTubeConnection };
