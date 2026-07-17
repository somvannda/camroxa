import { Maximize2, Minus, X } from 'lucide-react'

import { getDesktopApi } from '@/shared/api/desktop'
import { appLogoUrl } from '@/shared/assets'

export function DesktopHeader(): React.JSX.Element {
  const desktopApi = getDesktopApi()

  return (
    <div className="drag-region flex items-center justify-between border-b border-white/10 bg-[#060b20] px-5 py-3">
      <div className="flex items-center gap-3">
        <img alt="CAMXORA logo" className="h-8 w-8" src={appLogoUrl} />
        <div>
          <p className="text-sm font-semibold tracking-[0.18em] text-white">CAMXORA</p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Desktop Studio</p>
        </div>
      </div>
      <div className="no-drag flex items-center gap-1">
        <button
          aria-label="Minimize window"
          className="no-drag inline-flex h-8 w-10 items-center justify-center rounded-md text-slate-300 transition hover:bg-white/5 hover:text-white"
          type="button"
          onClick={() => desktopApi.windowControls.minimize()}
        >
          <Minus className="no-drag h-4 w-4" />
        </button>
        <button
          aria-label="Maximize or restore window"
          className="no-drag inline-flex h-8 w-10 items-center justify-center rounded-md text-slate-300 transition hover:bg-white/5 hover:text-white"
          type="button"
          onClick={() => desktopApi.windowControls.toggleMaximize()}
        >
          <Maximize2 className="no-drag h-4 w-4" />
        </button>
        <button
          aria-label="Close window"
          className="no-drag inline-flex h-8 w-10 items-center justify-center rounded-md text-slate-300 transition hover:bg-rose-500/20 hover:text-rose-200"
          type="button"
          onClick={() => desktopApi.windowControls.close()}
        >
          <X className="no-drag h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

