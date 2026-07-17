import type { MutableRefObject } from 'react'

import type {
  PreviewDomPresentationDraft,
  PreviewLogoDrawDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import {
  resolveBackgroundPresentationState,
  type BackgroundPresentationState,
} from '@/features/video/domains/background/backgroundPreviewRuntime'
import {
  resolveLogoPresentationState,
  type LogoPresentationState,
} from '@/features/video/domains/logo/logoPreviewRuntime'
import type { PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'

type RenderPreviewCanvasCompositionOptions<TOverlay> = {
  activeTextOverlays: ReadonlyArray<TOverlay>
  backdropCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
  dpr: number
  drawBackgroundLayer: (
    context: CanvasRenderingContext2D,
    backgroundImage: HTMLImageElement | null,
    width: number,
    height: number,
    presentation: BackgroundPresentationState,
  ) => void
  drawLogoLayer: (
    context: CanvasRenderingContext2D,
    draft: PreviewLogoDrawDraft,
    logoImage: HTMLImageElement | null,
    presentation: LogoPresentationState,
  ) => void
  drawTextOverlays: (
    context: CanvasRenderingContext2D,
    overlays: ReadonlyArray<TOverlay>,
    width: number,
    height: number,
  ) => void
  logicalHeight: number
  logicalWidth: number
  logoImageRef: MutableRefObject<HTMLImageElement | null>
  motionState: PreviewReactiveMotionState
  overlayCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  scale: number
  showDomPreviewBackground: boolean
  showDomPreviewLogo: boolean
  presentationDraft: PreviewDomPresentationDraft
  timeSec: number
}

export type RenderPreviewCanvasCompositionResult = {
  backdropSource: CanvasImageSource | null
  overlaySource: CanvasImageSource | null
}

function resolveCanvas(
  canvasRef: MutableRefObject<HTMLCanvasElement | null>,
): HTMLCanvasElement | null {
  const current = canvasRef.current
  if (current) {
    return current
  }
  if (typeof document === 'undefined') {
    return null
  }
  const created = document.createElement('canvas')
  canvasRef.current = created
  return created
}

export function renderPreviewCanvasComposition<TOverlay>({
  activeTextOverlays,
  backdropCanvasRef,
  backgroundImageRef,
  dpr,
  drawBackgroundLayer,
  drawLogoLayer,
  drawTextOverlays,
  logicalHeight,
  logicalWidth,
  logoImageRef,
  motionState,
  overlayCanvasRef,
  scale,
  showDomPreviewBackground,
  showDomPreviewLogo,
  presentationDraft,
  timeSec,
}: RenderPreviewCanvasCompositionOptions<TOverlay>): RenderPreviewCanvasCompositionResult {
  let backdropSource: CanvasImageSource | null = null
  let overlaySource: CanvasImageSource | null = null

  if (!showDomPreviewBackground) {
    const backdropCanvas = resolveCanvas(backdropCanvasRef)
    if (backdropCanvas) {
      const backdropWidth = Math.max(1, Math.round(logicalWidth * dpr))
      const backdropHeight = Math.max(1, Math.round(logicalHeight * dpr))
      if (backdropCanvas.width !== backdropWidth || backdropCanvas.height !== backdropHeight) {
        backdropCanvas.width = backdropWidth
        backdropCanvas.height = backdropHeight
      }
      const backdropContext = backdropCanvas.getContext('2d')
      if (backdropContext) {
        backdropContext.setTransform(1, 0, 0, 1, 0, 0)
        backdropContext.clearRect(0, 0, backdropWidth, backdropHeight)
        const backgroundPresentation = resolveBackgroundPresentationState(
          presentationDraft,
          backdropWidth,
          backdropHeight,
          Math.max(
            1,
            backgroundImageRef.current?.naturalWidth || backgroundImageRef.current?.width || backdropWidth,
          ),
          Math.max(
            1,
            backgroundImageRef.current?.naturalHeight || backgroundImageRef.current?.height || backdropHeight,
          ),
          motionState.backgroundPulseDrive,
          timeSec,
        )
        drawBackgroundLayer(
          backdropContext,
          backgroundImageRef.current,
          backdropWidth,
          backdropHeight,
          backgroundPresentation,
        )
        backdropSource = backdropCanvas
      }
    }
  }

  if (activeTextOverlays.length > 0 || !showDomPreviewLogo) {
    const overlayCanvas = resolveCanvas(overlayCanvasRef)
    if (overlayCanvas) {
      const overlayWidth = Math.max(1, Math.round(logicalWidth * dpr))
      const overlayHeight = Math.max(1, Math.round(logicalHeight * dpr))
      if (overlayCanvas.width !== overlayWidth || overlayCanvas.height !== overlayHeight) {
        overlayCanvas.width = overlayWidth
        overlayCanvas.height = overlayHeight
      }
      const overlayContext = overlayCanvas.getContext('2d')
      if (overlayContext) {
        const compositorScale = scale * dpr
        overlayContext.setTransform(1, 0, 0, 1, 0, 0)
        overlayContext.clearRect(0, 0, overlayWidth, overlayHeight)
        if (!showDomPreviewLogo) {
          const logoPresentation = resolveLogoPresentationState(
            presentationDraft,
            overlayWidth,
            overlayHeight,
            compositorScale,
            motionState.logoPulseDrive,
            timeSec,
          )
          drawLogoLayer(overlayContext, presentationDraft, logoImageRef.current, logoPresentation)
        }
        drawTextOverlays(overlayContext, activeTextOverlays, overlayWidth, overlayHeight)
        overlaySource = overlayCanvas
      }
    }
  }

  return {
    backdropSource,
    overlaySource,
  }
}
