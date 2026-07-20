import { useDashboardOverviewQuery } from '@/features/shell/useDashboardOverviewQuery'
import { Card } from '@/shared/ui/card'

function SummaryField(props: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-[#081028] px-4 py-3">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{props.label}</p>
      <p className="mt-2 text-sm font-medium text-slate-100">{props.value}</p>
    </div>
  )
}

function formatOptional(value: string | null | undefined, fallback = '--'): string {
  const normalized = String(value ?? '').trim()
  return normalized || fallback
}

function formatCount(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '--'
}

function percentOf(part: number, total: number): number {
  if (total <= 0) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round((part / total) * 100)))
}

function MetricBar(props: {
  label: string
  value: string
  percent: number
  barClassName: string
}): React.JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-[#081028] p-4">
      <div className="flex items-end justify-between gap-3">
        <span className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.label}</span>
        <span className="text-sm font-semibold text-white">{props.value}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${props.barClassName}`} style={{ width: `${props.percent}%` }} />
      </div>
    </div>
  )
}

function getProfileAssetMode(profile: {
  image_config?: Record<string, unknown>
  youtube_config?: Record<string, unknown>
}): string {
  const mode = String((profile.image_config ?? {}).mode ?? 'bg_thumb')
  if (mode === 'bg_only') {
    return 'Background only'
  }
  if (mode === 'thumb_only') {
    return 'Thumbnail only'
  }
  return 'Background + Thumbnail'
}

export function ProfilePage(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardOverviewQuery()

  const me = data?.me
  const profiles = data?.profiles ?? []
  const license = data?.license
  const stats = data?.stats
  const allowance =
    me?.profile_allowance != null ? `${me.channel_profile_count} / ${me.profile_allowance}` : `${profiles.length}`
  const songQuota = Math.max(license?.monthly_song_quota ?? stats?.songs_quota ?? 0, 1)
  const songsRemaining = license?.songs_remaining ?? stats?.songs_remaining ?? 0
  const songsUsed = Math.max(songQuota - songsRemaining, 0)
  const profileAllowance = Math.max(me?.profile_allowance ?? profiles.length ?? 0, 1)
  const profileUsed = me?.channel_profile_count ?? profiles.length
  const walletBalance =
    license?.wallet_balance != null
      ? license.wallet_balance.toLocaleString()
      : typeof me?.credit_balance === 'number'
        ? me.credit_balance.toLocaleString()
        : '--'

  return (
    <div className="grid gap-5">
      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Account</p>
              <h2 className="mt-2 text-xl font-semibold text-white">{me?.display_name ?? 'Loading account...'}</h2>
              <p className="mt-1.5 text-sm text-slate-300">{me?.email ?? (isError ? 'Unable to load account information.' : 'Loading account email...')}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-[#081028] px-3 py-2 text-right">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Verification</p>
              <p className="mt-1 text-sm font-semibold text-white">{me?.email_confirmed ? 'Verified' : 'Pending'}</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <SummaryField label="User ID" value={me?.id ?? '--'} />
            <SummaryField label="Session" value={isError ? 'Needs attention' : 'Active'} />
          </div>
        </Card>

        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Membership</p>
          <div className="mt-4 grid gap-3">
            <MetricBar
              barClassName="bg-emerald-400"
              label="Monthly profiles"
              percent={percentOf(profileUsed, profileAllowance)}
              value={allowance}
            />
            <MetricBar
              barClassName="bg-sky-400"
              label="Monthly songs"
              percent={percentOf(songsUsed, songQuota)}
              value={license?.songs_remaining != null ? `${songsRemaining} remaining` : 'Not provided'}
            />
            <div className="grid gap-3 md:grid-cols-2">
              <SummaryField label="Plan" value={me?.plan_name ?? 'No active plan'} />
              <SummaryField label="Credits balance" value={walletBalance} />
              <SummaryField label="Song quota" value={license?.monthly_song_quota != null ? `${license.monthly_song_quota}` : 'Not provided'} />
              <SummaryField label="Plan expiry" value={formatOptional(license?.expiration_date, 'Not provided')} />
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.55fr_0.75fr]">
        <Card className="p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Channel Profiles</p>
              <p className="mt-1.5 text-sm text-slate-300">Profiles available for generation and publication workflows.</p>
            </div>
            <p className="text-sm font-semibold text-white">{allowance}</p>
          </div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Run Prefix</th>
                  <th className="px-4 py-3 font-medium">Output resolution</th>
                  <th className="px-4 py-3 font-medium">Image mode</th>
                  <th className="px-4 py-3 font-medium">Visibility</th>
                </tr>
              </thead>
              <tbody>
                {profiles.length > 0 ? (
                  profiles.map((profile) => (
                    <tr className="border-t border-white/10" key={profile.id}>
                      <td className="px-4 py-3 text-slate-100">{profile.name}</td>
                      <td className="px-4 py-3 text-slate-300">{formatOptional(profile.run_prefix)}</td>
                      <td className="px-4 py-3 text-slate-300">{profile.output_resolution || '--'}</td>
                      <td className="px-4 py-3 text-slate-300">{getProfileAssetMode(profile)}</td>
                      <td className="px-4 py-3 text-slate-400">
                        {formatOptional(String((profile.youtube_config ?? {}).visibility ?? 'Unlisted'), 'Unlisted')}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-4 py-4 text-slate-400" colSpan={5}>
                      {isLoading ? 'Loading profiles...' : 'No channel profiles found yet.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Activity</p>
          <div className="mt-4 grid gap-3">
            <SummaryField label="Songs generated" value={formatCount(stats?.songs_generated)} />
            <SummaryField label="Images generated" value={formatCount(stats?.images_generated)} />
            <SummaryField label="Studio exports" value={formatCount(stats?.studio_exports ?? stats?.videos_generated)} />
            <SummaryField label="Manual exports" value={formatCount(stats?.manual_exports)} />
            <SummaryField label="YouTube uploads" value={formatCount(stats?.youtube_uploads ?? stats?.videos_uploaded)} />
            <SummaryField label="Credits spent" value={formatCount(stats?.credits_spent)} />
          </div>
        </Card>
      </div>
    </div>
  )
}
