import type { JSX, ReactNode } from 'react'

import {
  type PreviewProviderOptions,
  type PreviewProviderRenderState,
} from '@/features/video/preview/previewProviderContract'
import {
  usePreviewProviderState,
} from '@/features/video/preview/usePreviewProviderState'

type PreviewProviderProps<TOverlay> = PreviewProviderOptions<TOverlay> & {
  children: (state: PreviewProviderRenderState<TOverlay>) => ReactNode
}

export function PreviewProvider<TOverlay>({
  children,
  ...options
}: PreviewProviderProps<TOverlay>): JSX.Element {
  const previewState = usePreviewProviderState(options)

  return (
    <>
      {children(previewState)}
    </>
  )
}
