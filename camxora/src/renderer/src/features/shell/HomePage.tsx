import { useMemo } from 'react'
import { Image, Music4, Video, Youtube } from 'lucide-react'

import { useDashboardOverviewQuery } from '@/features/shell/useDashboardOverviewQuery'
import { Card } from '@/shared/ui/card'

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

function formatShortDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function percentOf(part: number, total: number): number {
  if (total <= 0) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round((part / total) * 100)))
}

function buildPolylinePoints(values: number[], width: number, height: number, padding: number): string {
  if (values.length === 0) {
    return ''
  }

  const max = Math.max(...values, 1)
  const xStep = values.length > 1 ? (width - padding * 2) / (values.length - 1) : 0

  return values
    .map((value, index) => {
      const x = padding + index * xStep
      const y = height - padding - (value / max) * (height - padding * 2)
      return `${x},${y}`
    })
    .join(' ')
}

function KpiCard(props: {
  title: string
  value: string
  icon: React.ComponentType<{ className?: string }>
  accentClassName: string
}): React.JSX.Element {
  const Icon = props.icon

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{props.title}</p>
          <p className="mt-3 text-2xl font-semibold text-white">{props.value}</p>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 ${props.accentClassName}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
      </div>
    </Card>
  )
}

function ProgressSummaryRow(props: {
  label: string
  value: number
  total: number
  barClassName: string
}): React.JSX.Element {
  const percentage = percentOf(props.value, props.total)

  return (
    <div className="rounded-xl border border-white/10 bg-[#081028] p-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{props.label}</p>
          <p className="mt-2 text-lg font-semibold text-white">
            {formatCompactNumber(props.value)} / {formatCompactNumber(props.total)}
          </p>
        </div>
        <p className="text-sm font-medium text-slate-300">{percentage}%</p>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${props.barClassName}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  )
}

export function HomePage(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardOverviewQuery()

  const usageData = data?.stats.usage_by_day ?? []
  const songValues = usageData.map((entry) => entry.songs)
  const imageValues = usageData.map((entry) => entry.images)
  const videoValues = usageData.map((entry) => entry.videos)

  const chartPoints = useMemo(
    () => ({
      songs: buildPolylinePoints(songValues, 620, 240, 20),
      images: buildPolylinePoints(imageValues, 620, 240, 20),
      videos: buildPolylinePoints(videoValues, 620, 240, 20),
    }),
    [imageValues, songValues, videoValues],
  )

  const kpis = [
    {
      title: 'Credits Spent',
      value: isLoading ? '--' : formatCompactNumber(data?.stats.credits_spent ?? 0),
      icon: Music4,
      accentClassName: 'bg-violet-500/20',
    },
    {
      title: 'Songs Generated',
      value: isLoading ? '--' : formatCompactNumber(data?.stats.songs_generated ?? 0),
      icon: Music4,
      accentClassName: 'bg-sky-500/20',
    },
    {
      title: 'Images Generated',
      value: isLoading ? '--' : formatCompactNumber(data?.stats.images_generated ?? 0),
      icon: Image,
      accentClassName: 'bg-emerald-500/20',
    },
    {
      title: 'Videos Generated',
      value: isLoading ? '--' : formatCompactNumber(data?.stats.videos_generated ?? 0),
      icon: Video,
      accentClassName: 'bg-amber-500/20',
    },
    {
      title: 'YouTube Uploaded',
      value: isLoading ? '--' : formatCompactNumber(data?.stats.videos_generated ?? 0),
      icon: Youtube,
      accentClassName: 'bg-rose-500/20',
    },
  ]

  return (
    <div className="grid gap-6">
      {isError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-6">
          <p className="text-sm text-rose-200">
            Unable to load dashboard statistics right now. The shell still works, but dashboard data
            needs the backend stats endpoint to respond successfully.
          </p>
        </Card>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {kpis.map((item) => (
          <KpiCard
            key={item.title}
            accentClassName={item.accentClassName}
            icon={item.icon}
            title={item.title}
            value={item.value}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Weekly Usage</p>
              <p className="mt-2 text-sm text-slate-300">Songs, images, and videos generated over the recent 7-day window.</p>
            </div>
            <div className="grid min-w-[170px] gap-1 rounded-xl border border-white/10 bg-[#081028] px-4 py-3 text-right">
              <span className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Current Plan</span>
              <span className="text-sm font-medium text-white">{data?.license?.plan_type ?? data?.me.plan_name ?? 'No plan'}</span>
              <span className="text-xs text-slate-400">
                {data?.license?.expiration_date ? `Expires ${formatShortDate(data.license.expiration_date)}` : 'Expiration not provided'}
              </span>
            </div>
          </div>
          <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-[#081028] p-4">
            <svg className="h-[240px] w-full" preserveAspectRatio="none" viewBox="0 0 620 240">
              {[0, 1, 2, 3].map((line) => (
                <line
                  key={line}
                  stroke="rgba(255,255,255,0.06)"
                  strokeDasharray="4 6"
                  x1="20"
                  x2="600"
                  y1={20 + line * 50}
                  y2={20 + line * 50}
                />
              ))}
              {chartPoints.songs ? (
                <polyline fill="none" points={chartPoints.songs} stroke="#7466F1" strokeWidth="3" />
              ) : null}
              {chartPoints.images ? (
                <polyline fill="none" points={chartPoints.images} stroke="#1ABCFE" strokeWidth="3" />
              ) : null}
              {chartPoints.videos ? (
                <polyline fill="none" points={chartPoints.videos} stroke="#0ACF83" strokeWidth="3" />
              ) : null}
            </svg>
            <div className="mt-4 grid grid-cols-7 gap-2">
              {usageData.length > 0 ? (
                usageData.map((entry) => (
                  <div className="text-center" key={entry.date}>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{formatShortDate(entry.date)}</p>
                    <p className="mt-1 text-xs text-slate-300">
                      {entry.songs + entry.images + entry.videos} items
                    </p>
                  </div>
                ))
              ) : (
                <div className="col-span-7 text-sm text-slate-400">No usage data available yet.</div>
              )}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#7466F1]" />
                Songs
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#1ABCFE]" />
                Images
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#0ACF83]" />
                Videos
              </span>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Remaining This Month</p>
          <div className="mt-5 grid gap-4">
            <ProgressSummaryRow
              barClassName="bg-violet-400"
              label="Credits"
              total={Math.max(data?.stats.credits_total ?? 0, 1)}
              value={data?.stats.credits_remaining ?? 0}
            />
            <ProgressSummaryRow
              barClassName="bg-sky-400"
              label="Songs"
              total={Math.max(data?.license?.monthly_song_quota ?? data?.stats.songs_quota ?? 0, 1)}
              value={data?.license?.songs_remaining ?? data?.stats.songs_remaining ?? 0}
            />
            <ProgressSummaryRow barClassName="bg-emerald-400" label="Images" total={1} value={0} />
          </div>
          <div className="mt-5 grid gap-3 rounded-2xl border border-white/10 bg-[#081028] p-4">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-400">Credits balance</span>
              <span className="font-medium text-white">
                {typeof data?.license?.wallet_balance === 'number'
                  ? formatCompactNumber(data.license.wallet_balance)
                  : typeof data?.me?.credit_balance === 'number'
                    ? formatCompactNumber(data.me.credit_balance)
                    : '--'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-400">Song quota</span>
              <span className="font-medium text-white">
                {data?.license?.monthly_song_quota != null ? formatCompactNumber(data.license.monthly_song_quota) : 'Not provided'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-400">Image quota</span>
              <span className="font-medium text-white">0</span>
            </div>
          </div>
        </Card>
      </div>

      <Card className="p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Recent Activity</p>
            <p className="mt-2 text-sm text-slate-300">Latest events returned by the dashboard stats API.</p>
          </div>
          <div className="text-right text-xs text-slate-500">
            <p>{data?.license?.plan_type ?? data?.me.plan_name ?? 'No plan'}</p>
            <p>
              Expires:{' '}
              {data?.license?.expiration_date ? formatDateTime(data.license.expiration_date) : 'Not provided'}
            </p>
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-white/5 text-slate-400">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Batch</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Stage</th>
                <th className="px-4 py-3 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data?.stats.recent_activity && data.stats.recent_activity.length > 0 ? (
                data.stats.recent_activity.map((activity, index) => (
                  <tr className="border-t border-white/10" key={`${activity.timestamp}-${activity.kind}-${index}`}>
                    <td className="px-4 py-3 text-slate-300">{formatDateTime(activity.timestamp)}</td>
                    <td className="px-4 py-3 text-slate-100">{activity.kind}</td>
                    <td className="px-4 py-3 text-slate-500">--</td>
                    <td className="px-4 py-3 text-slate-500">--</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200">
                        {activity.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{activity.detail}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={6}>
                    {isLoading ? 'Loading recent activity...' : 'No recent activity found.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
