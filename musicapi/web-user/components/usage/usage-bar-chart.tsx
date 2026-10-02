"use client";

/**
 * Dependency-free bar chart mirroring sunoapi.org's `/usage` Recharts bars:
 * rounded-top blue bars, horizontal grid lines, compact axis ticks and a
 * hover tooltip. `metric` selects spend (USD) or credits.
 */

export type UsagePoint = {
  day: string;
  count?: number;
  credits: number;
  spend: number;
};

export type UsageMetric = "spend" | "credits";

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const plain = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function formatMetric(value: number, metric: UsageMetric): string {
  const n = Number.isFinite(value) ? value : 0;
  return metric === "spend" ? `$${plain.format(n)}` : plain.format(n);
}

export function formatMetricCompact(value: number, metric: UsageMetric): string {
  const n = Number.isFinite(value) ? value : 0;
  return metric === "spend" ? `$${compact.format(n)}` : compact.format(n);
}

export function usagePointValue(point: UsagePoint, metric: UsageMetric): number {
  return metric === "spend" ? Number(point.spend || 0) : Number(point.credits || 0);
}

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

/** Pick a "nice" axis maximum/step so the chart shows ~4-5 grid lines. */
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

export function UsageBarChart({ points, metric }: { points: UsagePoint[]; metric: UsageMetric }) {
  const values = points.map((p) => usagePointValue(p, metric));
  const { max, ticks } = niceScale(Math.max(0, ...values));
  const labelStep = points.length > 12 ? Math.ceil(points.length / 10) : 1;

  return (
    <div className="w-full">
      <div className="flex h-[250px] w-full">
        {/* Y axis */}
        <div className="relative w-10 shrink-0">
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute right-1.5 -translate-y-1/2 text-[11px] text-[#9ca3af] tabular-nums"
              style={{ bottom: `${(t / max) * 100}%` }}
            >
              {formatMetricCompact(t, metric)}
            </div>
          ))}
        </div>

        {/* Plot area */}
        <div className="relative min-w-0 flex-1">
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute inset-x-0 border-t border-white/[0.08]"
              style={{ bottom: `${(t / max) * 100}%` }}
            />
          ))}
          <div className="absolute inset-0 flex items-end gap-1">
            {points.map((p, i) => {
              const value = usagePointValue(p, metric);
              const height = value > 0 ? Math.max((value / max) * 100, 1) : 0;
              return (
                <div
                  key={`${p.day}-${i}`}
                  className="group relative flex h-full min-w-0 flex-1 items-end justify-center"
                >
                  <div
                    className="w-full max-w-[32px] rounded-t-lg bg-[#3b82f6] transition-[height] duration-300"
                    style={{ height: `${height}%` }}
                  />
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-xl border border-white/10 bg-[#1a1a1d] p-3 text-left shadow-lg group-hover:block">
                    <div className="text-sm font-semibold text-white">{fullDate(p.day)}</div>
                    <div className="mt-1 text-sm text-white/60">
                      {metric === "spend" ? "Total Spend" : "Total Credits"}:{" "}
                      <span className="font-semibold text-white">{formatMetric(value, metric)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* X axis */}
      <div className="ml-10 flex gap-1 pt-2">
        {points.map((p, i) => (
          <div
            key={`${p.day}-x-${i}`}
            className="min-w-0 flex-1 truncate text-center text-[11px] text-[#9ca3af]"
            title={p.day}
          >
            {i % labelStep === 0 || i === points.length - 1 ? shortDate(p.day) : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
