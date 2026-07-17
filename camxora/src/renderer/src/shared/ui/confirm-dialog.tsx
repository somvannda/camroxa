import * as React from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, X } from 'lucide-react'

import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

type ConfirmDialogProps = {
  open: boolean
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'default' | 'danger'
  pending?: boolean
  onConfirm: () => void | Promise<void>
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'default',
  pending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps): React.JSX.Element | null {
  React.useEffect(() => {
    if (!open) {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !pending) {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, pending, onCancel])

  if (!open) {
    return null
  }

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-5">
      <button
        aria-label="Close confirmation dialog"
        className="absolute inset-0 bg-slate-950/75 backdrop-blur-sm"
        disabled={pending}
        type="button"
        onClick={onCancel}
      />
      <div
        aria-describedby={description ? 'camxora-confirm-dialog-description' : undefined}
        aria-labelledby="camxora-confirm-dialog-title"
        aria-modal="true"
        className="relative w-full max-w-md overflow-hidden rounded-[28px] border border-white/10 bg-[#081028] shadow-[0_30px_120px_-45px_rgba(124,58,237,0.8)]"
        role="dialog"
      >
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-fuchsia-400/70 to-transparent" />
        <div className="flex items-start gap-4 p-6">
          <div
            className={cn(
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border text-white',
              tone === 'danger'
                ? 'border-rose-400/30 bg-rose-500/15 text-rose-100'
                : 'border-violet-400/30 bg-violet-500/15 text-violet-100',
            )}
          >
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white" id="camxora-confirm-dialog-title">
                  {title}
                </h2>
                {description ? (
                  <p className="mt-2 text-sm leading-6 text-slate-300" id="camxora-confirm-dialog-description">
                    {description}
                  </p>
                ) : null}
              </div>
              <Button
                aria-label="Close confirmation dialog"
                className="h-9 w-9 rounded-xl p-0"
                disabled={pending}
                size="sm"
                type="button"
                variant="ghost"
                onClick={onCancel}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button disabled={pending} size="sm" type="button" variant="secondary" onClick={onCancel}>
                {cancelLabel}
              </Button>
              <Button
                className={cn(tone === 'danger' ? 'bg-gradient-to-r from-rose-600 to-fuchsia-600 hover:from-rose-500 hover:to-fuchsia-500' : '')}
                disabled={pending}
                size="sm"
                type="button"
                onClick={() => void onConfirm()}
              >
                {pending ? 'Working...' : confirmLabel}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
