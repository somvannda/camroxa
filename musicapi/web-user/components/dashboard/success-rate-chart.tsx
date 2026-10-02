"use client";

/**
 * Real-time success-rate line chart mirroring sunoapi.org's dashboard chart:
 * 0–100% y-axis, minute x-axis, dashed grid, dots on each point.
 */

export type SuccessRatePoint = { timestamp: number; successRate: number };

const Y_TICKS = [0, 25, 50, 75, 100];

function timeLabel(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit" });
}

export function SuccessRateChart({ points }: { points: SuccessRatePoint[] }) {
  if (points.length === 0) {
    return (
      <div className="flex h-80 w-full items-center justify-center text-sm text-white/40">
        No traffic in the last 15 minutes.
      </div>
    );
  }

  const minT = points[0].timestamp;
  const maxT = points[points.length - 1].timestamp;
  const span = Math.max(1, maxT - minT);
  const x = (t: number) => ((t - minT) / span) * 100;
  const y = (rate: number) => 100 - Math.max(0, Math.min(100, rate));
  const path = points.map((p) => `${x(p.timestamp).toFixed(2)},${y(p.successRate).toFixed(2)}`).join(" ");
  const labelStep = points.length > 8 ? Math.ceil(points.length / 6) : 1;

  return (
    <div className="relative h-80 w-full pl-12 pb-8 pr-3 pt-2">
      {/* Y axis labels */}
      <div className="absolute inset-y-2 left-0 w-11">
        {Y_TICKS.map((t) => (
          <div
            key={t}
            className="absolute right-2 -translate-y-1/2 text-[11px] text-[#9ca3af] tabular-nums"
            style={{ top: `${y(t)}%` }}
          >
            {t}
          </div>
        ))}
      </div>

      {/* Plot */}
      <div className="relative h-full w-full">
        <svg className="absolute inset-0 h-full w-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
          {Y_TICKS.map((t) => (
            <line
              key={t}
              x1="0"
              x2="100"
              y1={y(t)}
              y2={y(t)}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <polyline
            points={path}
            fill="none"
            stroke="var(--violet)"
            strokeWidth={1.5}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>

        {/* Dots */}
        {points.map((p, i) => (
          <div
            key={`${p.timestamp}-${i}`}
            className="group absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--violet)] ring-2 ring-[#161618]"
            style={{ left: `${x(p.timestamp)}%`, top: `${y(p.successRate)}%` }}
          >
            <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/10 bg-[#1a1a1d] px-2 py-1 text-xs shadow-lg group-hover:block">
              <span className="text-white/50">{timeLabel(p.timestamp)} · </span>
              <span className="font-medium text-[var(--violet)]">Success Rate: {p.successRate}%</span>
            </div>
          </div>
        ))}

        {/* X axis labels */}
        {points.map((p, i) =>
          i % labelStep === 0 || i === points.length - 1 ? (
            <div
              key={`${p.timestamp}-x-${i}`}
              className="absolute top-full mt-1 -translate-x-1/2 text-[11px] text-[#9ca3af] tabular-nums"
              style={{ left: `${x(p.timestamp)}%` }}
            >
              {timeLabel(p.timestamp)}
            </div>
          ) : null,
        )}
      </div>

      {/* Axis titles */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[11px] text-white/40">Time (min)</div>
      <div className="absolute left-1 top-1/2 -translate-y-1/2 -rotate-90 text-[11px] text-white/40">Success Rate (%)</div>
    </div>
  );
}
