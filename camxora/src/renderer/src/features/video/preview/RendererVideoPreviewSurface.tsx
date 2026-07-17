import { useCallback, useEffect, useMemo, useRef, useState, type JSX, type PointerEvent as ReactPointerEvent } from 'react'

import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { PreviewProviderRenderState } from '@/features/video/preview/previewProviderContract'
import { cn } from '@/shared/lib/utils'

type RendererVideoPreviewSurfaceProps<TOverlay> = PreviewProviderRenderState<TOverlay> & {
  enableSpectrumPositionEditing?: boolean
  onLifecycleStateChange?: (state: PreviewLifecycleState) => void
  onSpectrumPositionChange?: (patch: {
    anchor: string
    positionX: number
    positionY: number
    spectrumAttachToLogo: boolean
  }) => void
}

type SpectrumDragState = {
  rect: DOMRect
  scale: number
  pointerId: number
  startClientX: number
  startClientY: number
  startDisplayX: number
  startDisplayY: number
  pendingDisplayX: number
  pendingDisplayY: number
  latestClientX: number
  latestClientY: number
  rafId: number | null
  lastEmittedPositionX: number | null
  lastEmittedPositionY: number | null
}

function resolveAnchorPoint(anchor: string, width: number, height: number): { x: number; y: number } {
  switch (anchor) {
    case 'top-left':
      return { x: 0, y: 0 }
    case 'top-right':
      return { x: width, y: 0 }
    case 'bottom-left':
      return { x: 0, y: height }
    case 'bottom-right':
      return { x: width, y: height }
    case 'top-center':
      return { x: width / 2, y: 0 }
    case 'bottom-center':
      return { x: width / 2, y: height }
    case 'center-left':
      return { x: 0, y: height / 2 }
    case 'center-right':
      return { x: width, y: height / 2 }
    case 'center':
    default:
      return { x: width / 2, y: height / 2 }
  }
}

export function RendererVideoPreviewSurface<TOverlay>({
  containerRef,
  domBackgroundImageRef,
  domLogoLayerRef,
  enableSpectrumPositionEditing = false,
  lifecycleState,
  onLifecycleStateChange,
  onSpectrumPositionChange,
  scene,
  webgpuCanvasRef,
}: RendererVideoPreviewSurfaceProps<TOverlay>): JSX.Element {
  const spectrumDragStateRef = useRef<SpectrumDragState | null>(null)
  const spectrumContainerRef = useRef<HTMLDivElement | null>(null)
  const [localSpectrumPosition, setLocalSpectrumPosition] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    onLifecycleStateChange?.(lifecycleState)
  }, [lifecycleState, onLifecycleStateChange])

  const overlayStatusItems = useMemo(() => {
    const items: Array<{ tone: 'neutral' | 'warning'; label: string }> = []

    if (scene.viewport.showFallbackScene) {
      items.push({ tone: 'warning', label: 'Fallback scene active' })
    }
    if (scene.backgroundNode.enabled && !scene.backgroundNode.src) {
      items.push({ tone: 'warning', label: 'Select a background to preview the compositor output.' })
    } else if (scene.backgroundNode.enabled && scene.backgroundNode.loadStatus === 'error') {
      items.push({ tone: 'warning', label: 'Background asset failed to decode for preview.' })
    }
    if (scene.logoNode.enabled && !scene.logoNode.src) {
      items.push({ tone: 'warning', label: 'Logo layer is enabled but no logo file is selected.' })
    } else if (scene.logoNode.enabled && scene.logoNode.loadStatus === 'error') {
      items.push({ tone: 'warning', label: 'Logo asset failed to decode for preview.' })
    }
    if (lifecycleState.lastError) {
      items.push({ tone: 'warning', label: lifecycleState.lastError })
    }

    return items
  }, [lifecycleState.lastError, scene.backgroundNode.enabled, scene.backgroundNode.loadStatus, scene.backgroundNode.src, scene.logoNode.enabled, scene.logoNode.loadStatus, scene.logoNode.src, scene.viewport.showFallbackScene])

  const spectrumHandlePosition = useMemo(() => {
    if (!enableSpectrumPositionEditing || !onSpectrumPositionChange || !scene.spectrumNode?.enabled) {
      return null
    }

    const bounds = scene.viewport?.bounds
    const positionDraft = scene.runtimeNode?.positionDraft
    if (!bounds || !positionDraft) {
      return null
    }

    const anchorPoint = resolveAnchorPoint(
      positionDraft.anchor,
      bounds.width ?? 0,
      bounds.height ?? 0,
    )
    return {
      x:
        anchorPoint.x +
        (positionDraft.positionX ?? 0) * (scene.viewport?.scale ?? 1) +
        (scene.spectrumNode.attachment?.centerOffsetX ?? 0),
      y:
        anchorPoint.y +
        (positionDraft.positionY ?? 0) * (scene.viewport?.scale ?? 1) +
        (scene.spectrumNode.attachment?.centerOffsetY ?? 0),
    }
  }, [enableSpectrumPositionEditing, onSpectrumPositionChange, scene.runtimeNode, scene.spectrumNode, scene.viewport])

  const displaySpectrumPosition = localSpectrumPosition ?? spectrumHandlePosition

  const flushSpectrumDragFrame = useCallback(() => {
    const dragState = spectrumDragStateRef.current
    if (!dragState || !onSpectrumPositionChange) {
      return
    }

    dragState.rafId = null
    const displayX = dragState.pendingDisplayX
    const displayY = dragState.pendingDisplayY
    setLocalSpectrumPosition({
      x: displayX,
      y: displayY,
    })
    const offsetX = displayX - dragState.rect.width * 0.5
    const offsetY = displayY - dragState.rect.height * 0.5
    const safeScale = Math.max(0.0001, dragState.scale)
    const positionX = Number((offsetX / safeScale).toFixed(2))
    const positionY = Number((offsetY / safeScale).toFixed(2))
    if (
      dragState.lastEmittedPositionX === positionX &&
      dragState.lastEmittedPositionY === positionY
    ) {
      return
    }

    dragState.lastEmittedPositionX = positionX
    dragState.lastEmittedPositionY = positionY
    onSpectrumPositionChange({
      anchor: 'center',
      positionX,
      positionY,
      spectrumAttachToLogo: false,
    })
  }, [onSpectrumPositionChange])

  const handleSpectrumPointerMove = useCallback((event: PointerEvent) => {
    const dragState = spectrumDragStateRef.current
    if (!dragState) {
      return
    }

    dragState.latestClientX = event.clientX
    dragState.latestClientY = event.clientY
    dragState.pendingDisplayX = dragState.startDisplayX + (event.clientX - dragState.startClientX)
    dragState.pendingDisplayY = dragState.startDisplayY + (event.clientY - dragState.startClientY)
    if (dragState.rafId === null) {
      dragState.rafId = window.requestAnimationFrame(() => {
        flushSpectrumDragFrame()
      })
    }
  }, [flushSpectrumDragFrame])

  const stopSpectrumDrag = useCallback(() => {
    const dragState = spectrumDragStateRef.current
    if (dragState && dragState.rafId !== null) {
      window.cancelAnimationFrame(dragState.rafId)
    }
    if (dragState) {
      dragState.pendingDisplayX = dragState.startDisplayX + (dragState.latestClientX - dragState.startClientX)
      dragState.pendingDisplayY = dragState.startDisplayY + (dragState.latestClientY - dragState.startClientY)
    }
    flushSpectrumDragFrame()
    spectrumDragStateRef.current = null
    if (dragState && spectrumContainerRef.current?.hasPointerCapture?.(dragState.pointerId)) {
      spectrumContainerRef.current.releasePointerCapture(dragState.pointerId)
    }
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('pointermove', handleSpectrumPointerMove)
    window.removeEventListener('pointerup', stopSpectrumDrag)
    window.removeEventListener('pointercancel', stopSpectrumDrag)
  }, [flushSpectrumDragFrame, handleSpectrumPointerMove])

  const handleSpectrumPointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!enableSpectrumPositionEditing || !onSpectrumPositionChange || !containerRef.current) {
      return
    }
    if (event.button !== 0) {
      return
    }

    const currentDisplayPosition = displaySpectrumPosition
    if (!currentDisplayPosition || !scene.spectrumNode?.enabled) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    const rect = containerRef.current.getBoundingClientRect()
    spectrumDragStateRef.current = {
      rect,
      scale: scene.viewport?.scale ?? 1,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startDisplayX: currentDisplayPosition.x,
      startDisplayY: currentDisplayPosition.y,
      pendingDisplayX: currentDisplayPosition.x,
      pendingDisplayY: currentDisplayPosition.y,
      latestClientX: event.clientX,
      latestClientY: event.clientY,
      rafId: null,
      lastEmittedPositionX: null,
      lastEmittedPositionY: null,
    }
    spectrumContainerRef.current = event.currentTarget
    event.currentTarget.setPointerCapture?.(event.pointerId)
    document.body.style.cursor = 'grabbing'
    document.body.style.userSelect = 'none'
    setLocalSpectrumPosition(currentDisplayPosition)
    window.addEventListener('pointermove', handleSpectrumPointerMove)
    window.addEventListener('pointerup', stopSpectrumDrag)
    window.addEventListener('pointercancel', stopSpectrumDrag)
  }, [containerRef, displaySpectrumPosition, enableSpectrumPositionEditing, handleSpectrumPointerMove, onSpectrumPositionChange, scene.spectrumNode, scene.viewport, stopSpectrumDrag])

  useEffect(() => {
    if (!enableSpectrumPositionEditing) {
      stopSpectrumDrag()
      setLocalSpectrumPosition(null)
    }
  }, [enableSpectrumPositionEditing, stopSpectrumDrag])

  useEffect(() => {
    if (!spectrumDragStateRef.current && localSpectrumPosition && spectrumHandlePosition) {
      const deltaX = Math.abs(localSpectrumPosition.x - spectrumHandlePosition.x)
      const deltaY = Math.abs(localSpectrumPosition.y - spectrumHandlePosition.y)
      if (deltaX <= 1 && deltaY <= 1) {
        setLocalSpectrumPosition(null)
      }
    }
  }, [localSpectrumPosition, spectrumHandlePosition])

  useEffect(() => stopSpectrumDrag, [stopSpectrumDrag])

  return (
    <div
      className={cn(
        'absolute inset-0 overflow-hidden rounded-2xl bg-[linear-gradient(180deg,rgba(8,16,40,0.96),rgba(3,7,18,1))]',
        enableSpectrumPositionEditing && scene.spectrumNode?.enabled ? 'cursor-grab' : undefined,
      )}
      data-testid="renderer-preview-surface"
      ref={containerRef}
      onPointerDown={handleSpectrumPointerDown}
    >
      {scene.viewport.showDomPreviewBackground && scene.backgroundNode.src ? (
        <div className="pointer-events-none absolute inset-0 overflow-hidden" data-testid="renderer-dom-background-layer">
          <img
            alt=""
            className="absolute inset-0 h-full w-full select-none"
            draggable={false}
            ref={domBackgroundImageRef}
            src={scene.backgroundNode.src}
            style={scene.backgroundNode.domStyle}
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.06),rgba(2,6,23,0.36))]" />
        </div>
      ) : null}
      <canvas
        className="pointer-events-none absolute inset-0 h-full w-full"
        data-testid="renderer-webgpu-spectrum-layer"
        ref={webgpuCanvasRef}
      />
      {scene.viewport.showDomPreviewLogo && scene.logoNode.src ? (
        <div
          className="pointer-events-none absolute overflow-hidden"
          data-testid="renderer-dom-logo-layer"
          ref={domLogoLayerRef}
          style={scene.logoNode.domStyle}
        >
          <img alt="" className="h-full w-full select-none object-cover" draggable={false} src={scene.logoNode.src} />
        </div>
      ) : null}

      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
          {scene.capability.label}
        </span>
      </div>

      <div className="pointer-events-none absolute bottom-3 left-3 right-3 space-y-2">
        {lifecycleState.status !== 'running' ? (
          <p className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-[11px] leading-5 text-slate-200">
            {lifecycleState.message}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {scene.backgroundNode.enabled && scene.backgroundNode.loadStatus === 'loading' ? (
            <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[10px] font-medium text-cyan-100">
              Loading background...
            </span>
          ) : null}
          {overlayStatusItems.map((item) => (
            <span
              className={cn(
                'rounded-full border px-2 py-1 text-[10px] font-medium',
                item.tone === 'warning'
                  ? 'border-amber-500/20 bg-amber-500/10 text-amber-200'
                  : 'border-slate-500/20 bg-slate-500/10 text-slate-200',
              )}
              key={item.label}
            >
              {item.label}
            </span>
          ))}
          {scene.statusBadges.map((label) => (
            <span
              className={cn(
                'rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[10px] font-medium text-cyan-100',
              )}
              key={label}
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
