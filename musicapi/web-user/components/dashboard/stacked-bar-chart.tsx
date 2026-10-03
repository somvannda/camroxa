"use client";

/**
 * Stacked Success / Failure / Other bar chart for the dashboard, mirroring
 * sunoapi.org's recharts time-record chart (green / red / gray, rounded top).
 */

export type TimelineDay = {
  date: string;
  success: number;
  failure: number;
  other: number;
};

export const STATUS_COLORS = {
  success: "#10b981",
  failure: "#ff4444",
  other: "#6b7280",
} as const;

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function shortDate(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  return Number.isNaN(d.getTime()) ? day : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fullDate(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? day
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function niceScale(max: number): { max: number; ticks: number[] } {
  if (!(max > 0)) return { max: 1, ticks: [0, 0.25, 0.5, 0.75, 1] };
  const rough = max / 4;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / pow;
  const factor = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  const step = factor * pow;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) ticks.push(Number(v.toFixed(6)));
  return { max: top, ticks };
}

export function StackedBarChart({ days }: { days: TimelineDay[] }) {
  const totals = days.map((d) => d.success + d.failure + d.other);
  const { max, ticks } = niceScale(Math.max(0, ...totals));
  const labelStep = days.length > 12 ? Math.ceil(days.length / 10) : 1;

  return (
    <div className="w-full">
      <div className="flex h-[240px] w-full">
        {/* Y axis */}
        <div className="relative w-9 shrink-0">
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute right-1.5 -translate-y-1/2 text-[11px] text-[#9ca3af] tabular-nums"
              style={{ bottom: `${(t / max) * 100}%` }}
            >
              {compact.format(t)}
            </div>
          ))}
        </div>

        {/* Plot */}
        <div className="relative min-w-0 flex-1">
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute inset-x-0 border-t border-white/[0.08]"
              style={{ bottom: `${(t / max) * 100}%` }}
            />
          ))}
          <div className="absolute inset-0 flex items-end gap-1">
            {days.map((d) => {
              const total = d.success + d.failure + d.other;
              const height = total > 0 ? Math.max((total / max) * 100, 1) : 0;
              const pct = (v: number) => (total > 0 ? (v / total) * 100 : 0);
              return (
                <div key={d.date} className="group relative flex h-full min-w-0 flex-1 items-end justify-center">
                  {total > 0 && (
                    <div
                      className="flex w-full max-w-[24px] flex-col-reverse overflow-hidden rounded-t"
                      style={{ height: `${height}%` }}
                    >
                      <div style={{ height: `${pct(d.success)}%`, backgroundColor: STATUS_COLORS.success }} />
                      <div style={{ height: `${pct(d.failure)}%`, backgroundColor: STATUS_COLORS.failure }} />
                      <div style={{ height: `${pct(d.other)}%`, backgroundColor: STATUS_COLORS.other }} />
                    </div>
                  )}
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-xl border border-white/10 bg-[#1a1a1d] p-3 text-left shadow-lg group-hover:block">
                    <div className="mb-1 text-sm font-semibold text-white">{fullDate(d.date)}</div>
                    {(["success", "failure", "other"] as const).map((k) => (
                      <div key={k} className="flex items-center justify-between gap-4 text-xs">
                        <span className="inline-flex items-center gap-1.5 capitalize text-white/60">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: STATUS_COLORS[k] }} />
                          {k}
                        </span>
                        <span className="font-mono font-medium text-white">{d[k]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* X axis */}
      <div className="ml-9 flex gap-1 pt-2">
        {days.map((d, i) => (
          <div
            key={`${d.date}-x-${i}`}
            className="min-w-0 flex-1 truncate text-center text-[11px] text-[#9ca3af]"
            title={d.date}
          >
            {i % labelStep === 0 || i === days.length - 1 ? shortDate(d.date) : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
