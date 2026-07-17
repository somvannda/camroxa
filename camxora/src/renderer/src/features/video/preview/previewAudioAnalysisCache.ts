import {
  deserializePreviewAudioReactiveFeatureTimeline,
  serializePreviewAudioReactiveFeatureTimeline,
  type PreviewAudioReactiveFeatureTimeline,
  type SerializedPreviewAudioReactiveFeatureTimeline,
} from '@/features/video/preview/audioReactiveTimeline'
import { getDesktopApi } from '@/shared/api/desktop'

type PreviewAudioAnalysisCacheDocument = {
  version: 1
  sourcePath: string
  timeline: SerializedPreviewAudioReactiveFeatureTimeline
}

export async function loadCachedPreviewAudioReactiveTimeline(
  sourcePath: string,
): Promise<PreviewAudioReactiveFeatureTimeline | null> {
  const normalizedSourcePath = String(sourcePath || '').trim()
  if (!normalizedSourcePath) {
    return null
  }

  const payload = await getDesktopApi().video.getAudioAnalysisCache({
    sourcePath: normalizedSourcePath,
  })
  if (!payload) {
    return null
  }

  try {
    const parsed = JSON.parse(payload) as PreviewAudioAnalysisCacheDocument
    if (parsed?.version !== 1 || parsed.sourcePath !== normalizedSourcePath) {
      return null
    }
    return deserializePreviewAudioReactiveFeatureTimeline(parsed.timeline)
  } catch {
    return null
  }
}

export async function storeCachedPreviewAudioReactiveTimeline(
  sourcePath: string,
  timeline: PreviewAudioReactiveFeatureTimeline | null,
): Promise<boolean> {
  const normalizedSourcePath = String(sourcePath || '').trim()
  if (!normalizedSourcePath || !timeline) {
    return false
  }

  const payload = JSON.stringify({
    version: 1,
    sourcePath: normalizedSourcePath,
    timeline: serializePreviewAudioReactiveFeatureTimeline(timeline),
  } satisfies PreviewAudioAnalysisCacheDocument)

  return getDesktopApi().video.setAudioAnalysisCache({
    sourcePath: normalizedSourcePath,
    payload,
  })
}
