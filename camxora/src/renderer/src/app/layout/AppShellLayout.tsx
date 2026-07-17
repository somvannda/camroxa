import { LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { DesktopHeader } from '@/app/layout/DesktopHeader'
import { DesktopMusicDownloadCoordinator } from '@/features/music/DesktopMusicDownloadCoordinator'
import { DesktopVideoPipelineCoordinator } from '@/features/video/DesktopVideoPipelineCoordinator'
import { ShellVideoWorkspaceSync } from '@/features/video/ShellVideoWorkspaceSync'
import { getShellRouteMeta, shellRoutes } from '@/features/shell/shellNavigation'
import { logoutCurrentUser } from '@/shared/auth/logout'
import { subscribeShellStatus } from '@/shared/lib/shellStatus'
import { useShellSummaryQuery } from '@/features/shell/useShellSummaryQuery'
import { cn } from '@/shared/lib/utils'
import { formatCredits } from '@/shared/lib/formatCredits'

export function AppShellLayout(): React.JSX.Element {
  const location = useLocation()
  const navigate = useNavigate()
  const { data, isLoading, isError } = useShellSummaryQuery()
  const routeMeta = getShellRouteMeta(location.pathname)
  const isVideoWorkspace = routeMeta.key === 'video' || routeMeta.key === 'videoPy'
  const [shellStatus, setShellStatus] = useState<{ message: string; tone: 'neutral' | 'success' | 'error' } | null>(null)
  const shellStatusTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return subscribeShellStatus((payload) => {
      if (shellStatusTimerRef.current != null) {
        window.clearTimeout(shellStatusTimerRef.current)
      }

      const message = String(payload?.message ?? '').trim()
      if (!message) {
        setShellStatus(null)
        return
      }

      setShellStatus({
        message,
        tone: payload.tone ?? 'neutral',
      })

      const ttl = Number(payload.ttlMs ?? 3500)
      const ttlMs = Number.isFinite(ttl) ? Math.max(800, Math.min(20_000, ttl)) : 3500
      shellStatusTimerRef.current = window.setTimeout(() => {
        shellStatusTimerRef.current = null
        setShellStatus(null)
      }, ttlMs)
    })
  }, [])

  const me = data?.me
  const profiles = data?.profiles ?? []
  const displayName = me?.display_name?.trim() || me?.email?.trim() || 'User'
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((value) => value[0]?.toUpperCase() ?? '')
    .join('') || 'U'
  const planLabel = me?.plan_name?.trim() || null
  const creditsLabel = me ? `${formatCredits(me.credit_balance)} credits` : 'Credits: --'
  const profileUsage = me?.channel_profile_count ?? profiles.length
  const profileAllowance = me?.profile_allowance ?? null
  const profileUsagePercent =
    profileAllowance && profileAllowance > 0 ? Math.min((profileUsage / profileAllowance) * 100, 100) : 0
  const allowanceText =
    profileAllowance != null ? `${profileUsage} / ${profileAllowance} profiles` : `${profiles.length} profiles`
  const workspaceRoutes = shellRoutes.filter((route) => route.key !== 'settings' && route.key !== 'log')
  const utilityRoutes = shellRoutes.filter((route) => route.key === 'settings' || route.key === 'log')

  return (
    <div className="h-screen w-screen bg-[#081028] text-slate-50">
      <DesktopMusicDownloadCoordinator />
      <DesktopVideoPipelineCoordinator />
      <ShellVideoWorkspaceSync />
      <div className="flex h-full w-full flex-col overflow-hidden border border-white/10 bg-[#081028]">
        <DesktopHeader />
        <div className="flex flex-1 overflow-hidden bg-slate-950 text-slate-50">
          <aside className="flex w-[258px] flex-col border-r border-white/10 bg-[#050a1d] px-3 py-3">
            <div className="rounded-3xl border border-white/10 bg-[#081028] p-3 shadow-[0_20px_60px_-40px_rgba(124,58,237,0.45)]">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-xl font-bold text-white shadow-[0_16px_36px_-22px_rgba(217,70,239,0.8)]">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-semibold text-white">{displayName}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {planLabel ? (
                      <div className="rounded-lg bg-amber-300 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-950">
                        {planLabel}
                      </div>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-slate-400">{isLoading ? 'Loading account...' : creditsLabel}</p>
                </div>
              </div>
            </div>

            <nav className="mt-4 flex-1">
              <div>
                <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace</p>
                <div className="mt-2.5 space-y-1.5">
                  {workspaceRoutes.map(({ to, label, icon: Icon }) => (
                    <NavLink
                      key={to}
                      to={to}
                      className={({ isActive }) =>
                        cn(
                          'group flex items-center gap-3 rounded-2xl border px-3 py-2.5 text-sm font-medium transition',
                          isActive
                            ? 'border-violet-400/30 bg-gradient-to-r from-violet-500/20 to-fuchsia-500/15 text-white shadow-[0_18px_40px_-26px_rgba(217,70,239,0.85)]'
                            : 'border-transparent text-slate-300 hover:border-white/10 hover:bg-white/[0.03] hover:text-white',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <div
                            className={cn(
                              'flex h-8 w-8 items-center justify-center rounded-xl border transition',
                              isActive
                                ? 'border-violet-300/30 bg-white/10 text-white'
                                : 'border-white/10 bg-white/[0.03] text-slate-400 group-hover:border-white/15 group-hover:text-white',
                            )}
                          >
                            <Icon className="h-4 w-4" />
                          </div>
                          <span>{label}</span>
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>
              </div>

              <div className="mt-5">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">System</p>
                <div className="mt-2.5 space-y-1.5">
                  {utilityRoutes.map(({ to, label, icon: Icon }) => (
                    <NavLink
                      key={to}
                      to={to}
                      className={({ isActive }) =>
                        cn(
                          'group flex items-center gap-3 rounded-2xl border px-3 py-2.5 text-sm font-medium transition',
                          isActive
                            ? 'border-violet-400/30 bg-gradient-to-r from-violet-500/20 to-fuchsia-500/15 text-white shadow-[0_18px_40px_-26px_rgba(217,70,239,0.85)]'
                            : 'border-transparent text-slate-300 hover:border-white/10 hover:bg-white/[0.03] hover:text-white',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <div
                            className={cn(
                              'flex h-8 w-8 items-center justify-center rounded-xl border transition',
                              isActive
                                ? 'border-violet-300/30 bg-white/10 text-white'
                                : 'border-white/10 bg-white/[0.03] text-slate-400 group-hover:border-white/15 group-hover:text-white',
                            )}
                          >
                            <Icon className="h-4 w-4" />
                          </div>
                          <span>{label}</span>
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>
              </div>
            </nav>

            <div className="mt-3 border-t border-white/10 pt-3">
              <button
                className="flex w-full items-center gap-3 rounded-2xl border border-transparent px-3 py-2.5 text-sm font-medium text-rose-300 transition hover:border-rose-500/10 hover:bg-rose-500/10 hover:text-rose-200"
                type="button"
                onClick={async () => {
                  await logoutCurrentUser()
                  navigate('/auth/login')
                }}
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-rose-500/15 bg-rose-500/10">
                  <LogOut className="h-4 w-4" />
                </div>
                Logout
              </button>
            </div>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col">
            <main className={cn('flex-1', isVideoWorkspace ? 'overflow-hidden' : 'overflow-y-auto')}>
              <div
                className={cn(
                  'flex w-full flex-col px-4 py-4',
                  isVideoWorkspace ? 'h-full min-h-0 gap-4' : 'min-h-full gap-4',
                )}
              >
                {!isVideoWorkspace ? (
                  <header className="flex items-center justify-between rounded-3xl border border-white/10 bg-white/5 px-4 py-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">
                        {routeMeta.eyebrow}
                      </p>
                      <h1 className="mt-1.5 text-xl font-semibold text-white">{routeMeta.title}</h1>
                      <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-300 line-clamp-2">
                        {routeMeta.description}
                      </p>
                    </div>
                    <div className="min-w-[120px] rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2">
                      {isLoading ? (
                        <div className="text-xs text-emerald-100">Loading</div>
                      ) : isError ? (
                        <div className="text-xs text-amber-200">Limited</div>
                      ) : (
                        <div className="space-y-1.5">
                          <div className="flex items-end justify-between gap-3">
                            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200/80">
                              Monthly
                            </span>
                            <span className="text-xs font-semibold text-emerald-100">
                              {profileAllowance != null ? `${profileUsage}/${profileAllowance}` : `${profileUsage}`}
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                            <div
                              className="h-full rounded-full bg-emerald-400 transition-[width]"
                              style={{ width: `${profileAllowance != null ? profileUsagePercent : 100}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </header>
                ) : null}
                <Outlet />
              </div>
            </main>
            <footer className="flex items-center gap-4 border-t border-white/10 bg-[#060b20] px-6 py-2 text-xs text-slate-400">
              <span
                className={cn(
                  'min-w-0 truncate',
                  shellStatus?.tone === 'error'
                    ? 'text-rose-200'
                    : shellStatus?.tone === 'success'
                      ? 'text-emerald-200'
                      : 'text-slate-400',
                )}
                title={shellStatus?.message ?? undefined}
              >
                {shellStatus?.message ?? (isLoading ? 'Loading workspace...' : `Ready: ${routeMeta.label}`)}
              </span>
              <span className="ml-auto">{creditsLabel}</span>
              <span>{allowanceText}</span>
            </footer>
          </div>
        </div>
      </div>
    </div>
  )
}
