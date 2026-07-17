import { useEffect, useRef } from 'react'

type UseBufferedTemplatePatchOptions = {
  mergeRecords: (base: Record<string, unknown>, patch: Record<string, unknown>) => Record<string, unknown>
  flushPatch: (patch: Record<string, unknown>) => void
  onPatchQueued?: (patch: Record<string, unknown>) => void
  delayMs?: number
}

export function useBufferedTemplatePatch({
  mergeRecords,
  flushPatch,
  onPatchQueued,
  delayMs = 140,
}: UseBufferedTemplatePatchOptions): (patch: Record<string, unknown>) => void {
  const patchBufferRef = useRef<Record<string, unknown>>({})
  const patchTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (patchTimerRef.current != null) {
        window.clearTimeout(patchTimerRef.current)
      }
    }
  }, [])

  return (patch: Record<string, unknown>) => {
    onPatchQueued?.(patch)
    patchBufferRef.current = mergeRecords(patchBufferRef.current, patch)
    if (patchTimerRef.current != null) {
      window.clearTimeout(patchTimerRef.current)
    }
    patchTimerRef.current = window.setTimeout(() => {
      patchTimerRef.current = null
      const buffered = patchBufferRef.current
      patchBufferRef.current = {}
      if (Object.keys(buffered).length) {
        flushPatch(buffered)
      }
    }, delayMs)
  }
}
