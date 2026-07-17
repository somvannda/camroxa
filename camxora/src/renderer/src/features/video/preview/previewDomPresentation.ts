import type { MutableRefObject } from 'react'

import type { PreviewDomPresentationDraft } from '@/features/video/core/contracts/previewDraftContracts'
import {
  resolveBackgroundPresentationState,
  type BackgroundPresentationState,
} from '@/features/video/domains/background/backgroundPreviewRuntime'
import {
  resolveLogoPresentationState,
  type LogoPresentationState,
} from '@/features/video/domains/logo/logoPreviewRuntime'
import type { PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'

type ApplyPreviewDomPresentationOptions = {
  applyDomBackgroundPresentation: (
    node: HTMLImageElement,
    presentation: BackgroundPresentationState,
  ) => void
  applyDomLogoPresentation: (
    node: HTMLDivElement,
    presentation: LogoPresentationState,
  ) => void
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
  bounds: { width: number; height: number }
  domBackgroundImageRef: MutableRefObject<HTMLImageElement | null>
  domLogoLayerRef: MutableRefObject<HTMLDivElement | null>
  motionState: PreviewReactiveMotionState
  scale: number
  showDomPreviewBackground: boolean
  showDomPreviewLogo: boolean
  presentationDraft: PreviewDomPresentationDraft
  timeSec: number
}

export function applyPreviewDomPresentation({
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
}: ApplyPreviewDomPresentationOptions): void {
  if (showDomPreviewBackground && domBackgroundImageRef.current) {
    const presentation = resolveBackgroundPresentationState(
      presentationDraft,
      bounds.width,
      bounds.height,
      Math.max(1, backgroundImageRef.current?.naturalWidth || backgroundImageRef.current?.width || bounds.width),
      Math.max(
        1,
        backgroundImageRef.current?.naturalHeight || backgroundImageRef.current?.height || bounds.height,
      ),
      motionState.backgroundPulseDrive,
      timeSec,
    )
    applyDomBackgroundPresentation(domBackgroundImageRef.current, presentation)
  }

  if (showDomPreviewLogo && domLogoLayerRef.current) {
    const presentation = resolveLogoPresentationState(
      presentationDraft,
      bounds.width,
      bounds.height,
      scale,
      motionState.logoPulseDrive,
      timeSec,
    )
    applyDomLogoPresentation(domLogoLayerRef.current, presentation)
  }
}
