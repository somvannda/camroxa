import { RefreshCw, Square, Play } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getDesktopApi } from '@/shared/api/desktop'
import type { VideoPyWorkspaceEventPayload, VideoPyWorkspaceState } from '@/shared/types/desktop'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'

const idleState: VideoPyWorkspaceState = {
  running: false,
  embedded: false,
  pid: null,
}

export function VideoPyWorkspacePage(): React.JSX.Element {
  const desktopApi = useMemo(() => getDesktopApi(), [])
  const hostRef = useRef<HTMLDivElement | null>(null)
  const [workspaceState, setWorkspaceState] = useState<VideoPyWorkspaceState>(idleState)
  const [lastEvent, setLastEvent] = useState<VideoPyWorkspaceEventPayload | null>(null)
  const [busy, setBusy] = useState(false)

  const syncHostBounds = useCallback(async () => {
    const host = hostRef.current
    if (!host) {
      return
    }

    const rect = host.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) {
      return
    }

    await desktopApi.videoPy.setHostBounds({
      x: Math.round(rect.left),
      y: Math.round(rect.top),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      dpr: window.devicePixelRatio || 1,
    })
  }, [desktopApi])

  const refreshState = useCallback(async () => {
    const nextState = await desktopApi.videoPy.getState()
    setWorkspaceState(nextState)
    return nextState
  }, [desktopApi])

  const startWorkspace = useCallback(async () => {
    setBusy(true)
    try {
      const nextState = await desktopApi.videoPy.start()
      setWorkspaceState(nextState)
      window.setTimeout(() => {
        void syncHostBounds()
      }, 40)
    } finally {
      setBusy(false)
    }
  }, [desktopApi, syncHostBounds])

  const stopWorkspace = useCallback(async () => {
    setBusy(true)
    try {
      const nextState = await desktopApi.videoPy.stop()
      setWorkspaceState(nextState)
    } finally {
      setBusy(false)
    }
  }, [desktopApi])

  const restartWorkspace = useCallback(async () => {
    setBusy(true)
    try {
      await desktopApi.videoPy.stop()
      const nextState = await desktopApi.videoPy.start()
      setWorkspaceState(nextState)
      window.setTimeout(() => {
        void syncHostBounds()
      }, 40)
    } finally {
      setBusy(false)
    }
  }, [desktopApi, syncHostBounds])

  useEffect(() => {
    let disposed = false
    const unsubscribe = desktopApi.videoPy.onEvent((payload) => {
      setLastEvent(payload)
      void refreshState()
    })

    void (async () => {
      const state = await refreshState()
      if (disposed) {
        return
      }
      if (!state.running) {
        await startWorkspace()
      } else {
        await syncHostBounds()
      }
    })()

    return () => {
      disposed = true
      unsubscribe()
      void desktopApi.videoPy.stop()
    }
  }, [desktopApi, refreshState, startWorkspace, syncHostBounds])

  useEffect(() => {
    const host = hostRef.current
    if (!host) {
      return
    }

    const handleWindowResize = () => {
      void syncHostBounds()
    }

    window.addEventListener('resize', handleWindowResize)

    let observer: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        void syncHostBounds()
      })
      observer.observe(host)
    }

    void syncHostBounds()

    return () => {
      window.removeEventListener('resize', handleWindowResize)
      observer?.disconnect()
    }
  }, [syncHostBounds])

  const statusText =
    lastEvent?.message ??
    (workspaceState.running
      ? workspaceState.embedded
        ? 'Native Python video workspace is embedded and ready.'
        : 'Native Python video workspace is running and waiting for embed bounds.'
      : 'Native Python video workspace is stopped.')

  const statusToneClass =
    lastEvent?.status === 'error'
      ? 'border-rose-400/20 bg-rose-500/10 text-rose-100'
      : workspaceState.running
        ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
        : 'border-white/10 bg-white/5 text-slate-200'

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Native Python Workspace</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Video (Py)</h2>
          <p className="mt-1 text-sm text-slate-300">
            This page hosts the original native Python video workspace directly inside CAMXORA.
          </p>
        </div>
        <div className={`rounded-2xl border px-3 py-2 text-xs ${statusToneClass}`}>
          <div className="font-semibold uppercase tracking-[0.16em]">{lastEvent?.status ?? (workspaceState.running ? 'running' : 'idle')}</div>
          <div className="mt-1">
            PID: {workspaceState.pid ?? 'n/a'} · {workspaceState.embedded ? 'embedded' : 'detached'}
          </div>
        </div>
        <Button disabled={busy || workspaceState.running} onClick={() => void startWorkspace()} size="sm">
          <Play className="h-4 w-4" />
          Start
        </Button>
        <Button disabled={busy} onClick={() => void restartWorkspace()} size="sm" variant="secondary">
          <RefreshCw className="h-4 w-4" />
          Restart
        </Button>
        <Button disabled={busy || !workspaceState.running} onClick={() => void stopWorkspace()} size="sm" variant="secondary">
          <Square className="h-4 w-4" />
          Stop
        </Button>
      </Card>

      <Card className="min-h-0 flex-1 overflow-hidden p-2">
        <div ref={hostRef} className="relative h-full min-h-0 w-full overflow-hidden rounded-[22px] border border-white/10 bg-[#020617]">
          {!workspaceState.running ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-950/70 px-6 text-center text-sm text-slate-300">
              {busy ? 'Starting native Python video workspace…' : 'The native Python video workspace is stopped.'}
            </div>
          ) : null}
        </div>
      </Card>

      <Card className="px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Runtime Status</p>
        <p className="mt-2 text-sm text-slate-200">{statusText}</p>
      </Card>
    </div>
  )
}
