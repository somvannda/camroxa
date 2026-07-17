import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { appLogoUrl } from '@/shared/assets'
import { getDesktopApi } from '@/shared/api/desktop'
import { runBootstrap } from '@/shared/auth/bootstrap'

export function StartupPage(): React.JSX.Element {
  const navigate = useNavigate()
  const desktopApi = getDesktopApi()
  const [currentStep, setCurrentStep] = useState({
    label: 'Starting CAMXORA',
    detail: 'Launching the desktop studio.',
    progress: 10,
  })

  useEffect(() => {
    if (desktopApi.isSplash) {
      return desktopApi.bootstrap.onProgress(setCurrentStep)
    }

    let cancelled = false
    const report = (payload: { label: string; detail: string; progress: number }) => {
      setCurrentStep(payload)
      desktopApi.bootstrap.reportProgress(payload)
    }

    void (async () => {
      const result = await runBootstrap({ report })
      if (cancelled) {
        return
      }
      navigate(result.redirectTo, { replace: true })
      desktopApi.bootstrap.done()
    })()

    return () => {
      cancelled = true
    }
  }, [desktopApi, navigate])

  return (
    <div
      className={`h-screen w-screen bg-[#0a0e27] text-slate-50 ${
        desktopApi.isSplash ? '' : 'flex items-center justify-center'
      }`}
    >
      <div
        className={`rounded-[10px] border border-white/10 bg-[#060b20] px-5 py-4 overflow-hidden ${
          desktopApi.isSplash ? 'h-full w-full' : 'w-[420px]'
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Loading</p>
          <img alt="CAMXORA splash logo" className="h-10 w-10 shrink-0" src={appLogoUrl} />
        </div>
        <p className="mt-2 truncate text-[16px] font-semibold leading-none text-white">
          {currentStep.label}
        </p>
        <p className="mt-2 text-sm leading-5 text-slate-400">{currentStep.detail}</p>

        <div className="mt-4 h-2 w-full shrink-0 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500 transition-all duration-500"
            style={{ width: `${currentStep.progress}%` }}
          />
        </div>
      </div>
    </div>
  )
}
