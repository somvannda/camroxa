export type ShellStatusTone = 'neutral' | 'success' | 'error'

export type ShellStatusPayload = {
  message: string
  tone?: ShellStatusTone
  ttlMs?: number
}

const SHELL_STATUS_EVENT = 'camxora:shell-status'

export function emitShellStatus(payload: ShellStatusPayload): void {
  if (typeof window === 'undefined') {
    return
  }

  window.dispatchEvent(new CustomEvent<ShellStatusPayload>(SHELL_STATUS_EVENT, { detail: payload }))
}

export function subscribeShellStatus(handler: (payload: ShellStatusPayload) => void): () => void {
  if (typeof window === 'undefined') {
    return () => undefined
  }

  const listener: EventListener = (event) => {
    if (!(event instanceof CustomEvent)) {
      return
    }
    handler(event.detail as ShellStatusPayload)
  }

  window.addEventListener(SHELL_STATUS_EVENT, listener)
  return () => window.removeEventListener(SHELL_STATUS_EVENT, listener)
}

