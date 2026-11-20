import { useId, useState } from "react";
import { Card } from "../../components/card";
import { classNames, formatCount } from "../../lib/format";
import { chartY, gridLineYs, monotonePath } from "./chart";
import type { WeeklyDay } from "./dashboard-format";

const WIDTH = 640;
const HEIGHT = 260;
const AXIS_LEFT = 34;
const PLOT_RIGHT = WIDTH - 12;
const PLOT_PADDING = 18;
const SERIES = [
  { key: "songs", label: "Songs", color: "var(--series-songs)" },
  { key: "images", label: "Images", color: "var(--series-images)" },
  { key: "videos", label: "Videos", color: "var(--series-videos)" },
] as const;

interface WeeklyUsageCardProps {
  series: WeeklyDay[];
  loading: boolean;
  hasError: boolean;
}

export function WeeklyUsageCard({ series, loading, hasError }: WeeklyUsageCardProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  const totals = series.reduce(
    (sum, day) => ({
      songs: sum.songs + day.songs,
      images: sum.images + day.images,
      videos: sum.videos + day.videos,
    }),
    { songs: 0, images: 0, videos: 0 },
  );
  // One shared scale keeps the three lines comparable; per-series scaling made
  // a single image look as tall as a four-song day.
  const chartMax = Math.max(
    0,
    ...series.flatMap((day) => [day.songs, day.images, day.videos]),
  );
  const scaleMax = Math.max(1, chartMax);

  const plotX = (index: number): number =>
    series.length <= 1
      ? (AXIS_LEFT + PLOT_RIGHT) / 2
      : AXIS_LEFT + (index * (PLOT_RIGHT - AXIS_LEFT)) / (series.length - 1);

  const yTicks = gridLineYs(HEIGHT, PLOT_PADDING);
  const gridLines =
    scaleMax <= 5
      ? Array.from({ length: scaleMax + 1 }, (_, index) => {
          const value = scaleMax - index;
          return { value, y: chartY(value, scaleMax, HEIGHT, PLOT_PADDING) };
        })
      : yTicks.map((y, index) => ({
          y,
          value: Math.round(scaleMax * (1 - index / (yTicks.length - 1))),
        }));

  const active = hovered !== null ? series[hovered] : null;
  const readout = active
    ? `${active.label}: ${active.songs} songs, ${active.images} images, ${active.videos} videos`
    : "Hover or focus a day for values.";

  return (
    <Card className="flex flex-col p-4" data-testid="weekly-usage">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Weekly Usage</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Songs, images and videos generated over the recent 7-day window.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-4" data-testid="weekly-totals">
          <div className="text-right">
            <p className="text-caption text-text-muted">Songs</p>
            <p className="text-body font-medium text-text-primary text-tabular">
              {loading ? "--" : formatCount(totals.songs)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-caption text-text-muted">Images</p>
            <p className="text-body font-medium text-text-primary text-tabular">
              {loading ? "--" : formatCount(totals.images)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-caption text-text-muted">Videos</p>
            <p className="text-body font-medium text-text-primary text-tabular">
              {loading ? "--" : formatCount(totals.videos)}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex-1">
        {loading ? (
          <div className="h-[240px] rounded-control bg-surface-2" aria-hidden="true" />
        ) : hasError && series.length === 0 ? (
          <div className="h-[240px]" aria-hidden="true" />
        ) : series.length === 0 ? (
          <div className="flex h-[240px] items-center justify-center rounded-control border border-dashed border-border">
            <p className="text-body text-text-secondary">No usage data available yet.</p>
          </div>
        ) : (
          <>
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="h-[240px] w-full"
              role="img"
              aria-label={`Weekly usage chart: ${series.length} days, songs, images, and videos.`}
            >
              {gridLines.map((line) => (
                <g key={line.y}>
                  <line
                    x1={AXIS_LEFT}
                    x2={PLOT_RIGHT}
                    y1={line.y}
                    y2={line.y}
                    stroke="var(--border)"
                    strokeDasharray="4 6"
                    strokeWidth={1}
                  />
                  <text
                    x={AXIS_LEFT - 6}
                    y={line.y + 3}
                    textAnchor="end"
                    className="fill-[var(--text-muted)] text-[10px]"
                  >
                    {line.value}
                  </text>
                </g>
              ))}

              {hovered !== null ? (
                <line
                  x1={plotX(hovered)}
                  x2={plotX(hovered)}
                  y1={PLOT_PADDING}
                  y2={HEIGHT - PLOT_PADDING}
                  stroke="var(--border-strong)"
                  strokeDasharray="2 4"
                  strokeWidth={1}
                />
              ) : null}

              {SERIES.map((entry) => {
                const values = series.map((day) => day[entry.key]);
                const points = values.map((value, index) => ({
                  x: plotX(index),
                  y: chartY(value, scaleMax, HEIGHT, PLOT_PADDING),
                }));
                return (
                  <g key={entry.key}>
                    <path
                      d={monotonePath(points, PLOT_PADDING, HEIGHT - PLOT_PADDING)}
                      fill="none"
                      stroke={entry.color}
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    {values.map((value, index) => (
                      <circle
                        key={`${entry.key}-${index}`}
                        cx={plotX(index)}
                        cy={chartY(value, scaleMax, HEIGHT, PLOT_PADDING)}
                        r={hovered === index ? 4 : 2.5}
                        fill="var(--surface-1)"
                        stroke={entry.color}
                        strokeWidth={2}
                      />
                    ))}
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
                    {day.total} {day.total === 1 ? "item" : "items"}
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

