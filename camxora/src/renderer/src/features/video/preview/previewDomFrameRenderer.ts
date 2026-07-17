import type { MutableRefObject } from 'react'

import type {
  PreviewDomPresentationDraft,
  PreviewLogoDrawDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import { renderPreviewCanvasComposition } from '@/features/video/preview/previewCanvasCompositor'
import { applyPreviewDomPresentation } from '@/features/video/preview/previewDomPresentation'
import type { BackgroundPresentationState } from '@/features/video/domains/background/backgroundPreviewRuntime'
import {
  resolveLogoPresentationState,
  type LogoPresentationState,
} from '@/features/video/domains/logo/logoPreviewRuntime'
import type { PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'

type RenderPreviewDomFrameOptions<TOverlay> = {
  activeTextOverlays: ReadonlyArray<TOverlay>
  applyDomBackgroundPresentation: (
    node: HTMLImageElement,
    presentation: BackgroundPresentationState,
  ) => void
  applyDomLogoPresentation: (
    node: HTMLDivElement,
    presentation: LogoPresentationState,
  ) => void
  backdropCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
  bounds: { width: number; height: number }
  domBackgroundImageRef: MutableRefObject<HTMLImageElement | null>
  domLogoLayerRef: MutableRefObject<HTMLDivElement | null>
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

export type RenderPreviewDomFrameResult = {
  backdropSource: CanvasImageSource | null
  overlaySource: CanvasImageSource | null
  logoPresentationState: LogoPresentationState | null
}

export function renderPreviewDomFrame<TOverlay>({
  activeTextOverlays,
  applyDomBackgroundPresentation,
  applyDomLogoPresentation,
  backdropCanvasRef,
  backgroundImageRef,
  bounds,
  domBackgroundImageRef,
  domLogoLayerRef,
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
}: RenderPreviewDomFrameOptions<TOverlay>): RenderPreviewDomFrameResult {
  applyPreviewDomPresentation({
    applyDomBackgroundPresentation,
    applyDomLogoPresentation,
    backgroundImageRef,
    bounds,
    domBackgroundImageRef,
    domLogoLayerRef,
    motionState,
    scale,
    showDomPreviewBackground,
    showDomPreviewLogo,
    presentationDraft,
    timeSec,
  })

  let logoPresentationState: LogoPresentationState | null = null
  if (showDomPreviewLogo) {
    logoPresentationState = resolveLogoPresentationState(
      presentationDraft,
      bounds.width,
      bounds.height,
      scale,
      motionState.logoPulseDrive,
      timeSec,
    )
  }

  const compositionResult = renderPreviewCanvasComposition({
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
  })

  return {
    ...compositionResult,
    logoPresentationState,
  }
}
