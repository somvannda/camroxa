import { useId, useState } from "react";
import { Card } from "../../components/card";
import { classNames } from "../../lib/format";
import { CHART_PADDING, chartX, chartY, gridLineYs, seriesPoints } from "./chart";
import type { WeeklyDay } from "./dashboard-format";

const WIDTH = 640;
const HEIGHT = 220;
const SERIES = [
  { key: "songs", label: "Songs", color: "var(--series-songs)" },
  { key: "images", label: "Images", color: "var(--series-images)" },
  { key: "videos", label: "Videos", color: "var(--series-videos)" },
] as const;

interface WeeklyUsageCardProps {
  series: WeeklyDay[];
  plan: string;
  expiry: string;
  loading: boolean;
  hasError: boolean;
}

export function WeeklyUsageCard({
  series,
  plan,
  expiry,
  loading,
  hasError,
}: WeeklyUsageCardProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  const active = hovered !== null ? series[hovered] : null;
  const readout = active
    ? `${active.label}: ${active.songs} songs, ${active.images} images, ${active.videos} videos`
    : "Hover or focus a day for values.";

  return (
    <Card className="flex flex-col p-5" data-testid="weekly-usage">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Weekly Usage</h2>
          <p className="mt-1 text-body text-text-secondary">
            Songs, images, and videos generated over the recent 7-day window.
          </p>
        </div>
        <div className="shrink-0 rounded-control border border-border bg-surface-2 px-3 py-2 text-right">
          <p className="text-caption text-text-muted">Current plan</p>
          <p className="text-body font-medium text-text-primary">{plan}</p>
          <p className="text-caption text-text-secondary">{expiry}</p>
        </div>
      </div>

      <div className="mt-4 flex-1">
        {loading ? (
          <div className="h-[220px] rounded-control bg-surface-2" aria-hidden="true" />
        ) : hasError && series.length === 0 ? (
          <div className="h-[220px]" aria-hidden="true" />
        ) : series.length === 0 ? (
          <div className="flex h-[220px] items-center justify-center rounded-control border border-dashed border-border">
            <p className="text-body text-text-secondary">No usage data available yet.</p>
          </div>
        ) : (
          <>
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="h-[220px] w-full"
              role="img"
              aria-label={`Weekly usage chart: ${series.length} days, songs, images, and videos.`}
            >
              {gridLineYs(HEIGHT).map((y) => (
                <line
                  key={y}
                  x1={CHART_PADDING}
                  x2={WIDTH - CHART_PADDING}
                  y1={y}
                  y2={y}
                  stroke="var(--border)"
                  strokeDasharray="4 6"
                  strokeWidth={1}
                />
              ))}

              {hovered !== null ? (
                <line
                  x1={chartX(hovered, series.length, WIDTH)}
                  x2={chartX(hovered, series.length, WIDTH)}
                  y1={CHART_PADDING}
                  y2={HEIGHT - CHART_PADDING}
                  stroke="var(--border-strong)"
                  strokeDasharray="2 4"
                  strokeWidth={1}
                />
              ) : null}

              {SERIES.map((entry) => {
                const values = series.map((day) => day[entry.key]);
                const max = Math.max(0, ...values);
                return (
                  <g key={entry.key}>
                    <polyline
                      points={seriesPoints(values, WIDTH, HEIGHT)}
                      fill="none"
                      stroke={entry.color}
                      strokeWidth={3}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    {hovered !== null ? (
                      <circle
                        cx={chartX(hovered, series.length, WIDTH)}
                        cy={chartY(values[hovered], max, HEIGHT)}
                        r={3.5}
                        fill={entry.color}
                      />
                    ) : null}
                  </g>
                );
              })}
            </svg>

            <div className="mt-2 grid grid-cols-7 gap-2">
              {series.map((day, index) => (
                <button
                  key={day.date}
                  type="button"
                  className={classNames(
                    "rounded-control px-1 py-2 text-center transition-colors hover:bg-surface-hover",
                    hovered === index ? "bg-surface-hover" : "",
                  )}
                  onMouseEnter={() => setHovered(index)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(index)}
                  onBlur={() => setHovered(null)}
                  aria-label={`${day.label}: ${day.songs} songs, ${day.images} images, ${day.videos} videos`}
                >
                  <span className="block text-caption text-text-muted">{day.label}</span>
                  <span className="block text-meta text-text-secondary text-tabular">
                    {day.total} items
                  </span>
                </button>
              ))}
            </div>

            <p
              className="mt-2 h-4 text-caption text-text-secondary text-tabular"
              aria-live="polite"
            >
              {readout}
            </p>

            <div className="mt-2 flex items-center justify-between gap-4">
              <ul className="flex items-center gap-4" aria-label="Chart legend">
                {SERIES.map((entry) => (
                  <li key={entry.key} className="flex items-center gap-1.5 text-caption text-text-secondary">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: entry.color }}
                      aria-hidden="true"
                    />
                    {entry.label}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="rounded-control px-2 py-1 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={() => setShowTable((value) => !value)}
                aria-expanded={showTable}
                aria-controls={tableId}
              >
                {showTable ? "Hide data" : "View data"}
              </button>
            </div>

            {showTable ? (
              <div id={tableId} className="mt-3 overflow-auto rounded-control border border-border">
                <table className="w-full border-collapse text-meta">
                  <thead>
                    <tr className="bg-surface-2 text-text-muted">
                      <th scope="col" className="h-8 px-3 text-left font-medium">Day</th>
                      <th scope="col" className="h-8 px-3 text-right font-medium">Songs</th>
                      <th scope="col" className="h-8 px-3 text-right font-medium">Images</th>
                      <th scope="col" className="h-8 px-3 text-right font-medium">Videos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.map((day) => (
                      <tr key={day.date} className="border-t border-border text-text-secondary">
                        <th scope="row" className="h-8 px-3 text-left font-normal">{day.label}</th>
                        <td className="h-8 px-3 text-right text-tabular">{day.songs}</td>
                        <td className="h-8 px-3 text-right text-tabular">{day.images}</td>
                        <td className="h-8 px-3 text-right text-tabular">{day.videos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}
