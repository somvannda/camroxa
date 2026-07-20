"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatNumber, formatShortDate } from "@/components/dashboard/control-panel-ui";

type UsageDay = {
  date: string;
  songs: number;
  images: number;
  videos: number;
  studio_exports?: number;
  manual_exports?: number;
  youtube_uploads?: number;
};

type SeriesKey = "songs" | "images" | "studio_exports" | "manual_exports" | "youtube_uploads";

const SERIES: Array<{ key: SeriesKey; label: string; color: string }> = [
  { key: "songs", label: "Songs", color: "#7466F1" },
  { key: "images", label: "Images", color: "#1ABCFE" },
  { key: "studio_exports", label: "Studio exports", color: "#0ACF83" },
  { key: "manual_exports", label: "Manual exports", color: "#F59E0B" },
  { key: "youtube_uploads", label: "YouTube uploads", color: "#EF4444" },
];

function UsageTooltip(props: {
  active?: boolean;
  label?: string;
  payload?: Array<{ dataKey?: string | number; value?: number; color?: string; name?: string }>;
}) {
  if (!props.active || !props.payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950/95 px-3 py-2 shadow-xl">
      <div className="text-xs font-medium text-slate-300">{props.label}</div>
      <div className="mt-2 space-y-1">
        {props.payload.map((entry) => (
          <div key={String(entry.dataKey)} className="flex items-center justify-between gap-6 text-xs">
            <span className="inline-flex items-center gap-2 text-slate-400">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name}
            </span>
            <span className="font-medium text-white">{formatNumber(entry.value ?? 0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsageCurveChart(props: {
  days: UsageDay[];
  activeKeys?: SeriesKey[];
}) {
  const active =
    props.activeKeys ??
    (["songs", "images", "studio_exports", "manual_exports", "youtube_uploads"] as const);
  const series = SERIES.filter((item) => active.includes(item.key));

  const data = React.useMemo(
    () =>
      props.days.map((day) => {
        const studio = day.studio_exports ?? 0;
        const manual = day.manual_exports ?? 0;
        const youtube = day.youtube_uploads ?? 0;
        // Older API rows may only have `videos` (studio+manual combined).
        const studioResolved = day.studio_exports != null ? studio : day.videos;
        const manualResolved = day.manual_exports != null ? manual : 0;
        return {
          label: formatShortDate(day.date),
          total: day.songs + day.images + studioResolved + manualResolved + youtube,
          songs: day.songs,
          images: day.images,
          studio_exports: studioResolved,
          manual_exports: manualResolved,
          youtube_uploads: youtube,
        };
      }),
    [props.days],
  );

  if (props.days.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-slate-800 bg-slate-950/40 text-sm text-slate-500">
        No usage data yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
        {series.map((item) => (
          <div key={item.key} className="inline-flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-3 md:p-4">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                {series.map((item) => (
                  <linearGradient key={item.key} id={`fill-${item.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={item.color} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={item.color} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="4 6" vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                dy={6}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={36}
                tick={{ fill: "#64748b", fontSize: 11 }}
              />
              <Tooltip content={<UsageTooltip />} cursor={{ stroke: "rgba(148,163,184,0.25)", strokeWidth: 1 }} />
              {series.map((item) => (
                <Area
                  key={item.key}
                  type="monotone"
                  dataKey={item.key}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={2.5}
                  fill={`url(#fill-${item.key})`}
                  dot={{ r: 3, strokeWidth: 2, fill: "#0B1220", stroke: item.color }}
                  activeDot={{ r: 5, strokeWidth: 2, fill: item.color, stroke: "#0B1220" }}
                  isAnimationActive={false}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div
          className="mt-2 grid gap-1 border-t border-slate-800/80 pt-2 text-center text-[11px] text-slate-500"
          style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
        >
          {data.map((day) => (
            <div key={day.label}>
              <div className="font-medium text-slate-300">{formatNumber(day.total)}</div>
              <div>items</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
