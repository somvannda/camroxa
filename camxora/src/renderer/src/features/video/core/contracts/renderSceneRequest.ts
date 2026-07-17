import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import type {
  VideoExportMode,
  VideoRenderOutputSettings,
  VideoResolvedRenderAssets,
  VideoSerializableRenderSceneRequest,
  VideoWorkspaceState,
} from '@/shared/types/desktop'

const DEFAULT_OUTPUT_RESOLUTION = '1920x1080'
const DEFAULT_EXPORT_FPS = 60
const PREVIEW_REFERENCE_LONG_EDGE_PX = 1920

type AspectRatioReference = Pick<VideoWorkspaceState['previewAspectRatio'], 'width' | 'height'>

export type RenderSceneContext = {
  templateId: string | null
  branch: 'long' | 'reel' | null
  batchId: string | null
  role: string | null
  draftSource: 'live' | 'saved'
}

export type RenderSceneRequest = {
  mode: VideoExportMode
  template: Record<string, unknown>
  draft: VideoTemplateDraft
  assets: VideoResolvedRenderAssets
  output: VideoRenderOutputSettings
  context: RenderSceneContext
}

export function toVideoSerializableRenderSceneRequest(
  request: RenderSceneRequest,
): VideoSerializableRenderSceneRequest {
  return {
    mode: request.mode,
    template: request.template,
    draft: request.draft as Record<string, unknown>,
    assets: request.assets,
    output: request.output,
    context: request.context,
  }
}

export type ManualRenderSceneRequestOptions = {
  template: Record<string, unknown>
  templateDraft: VideoTemplateDraft
  workspace: Pick<VideoWorkspaceState, 'templateId' | 'outputResolution' | 'logoPath' | 'selectedMp3Path'>
  backgroundPath?: string | null
  selectedMp3Path?: string | null
  fps?: number
}

export type PipelineRenderSceneRequestOptions = {
  template: Record<string, unknown>
  workspace: Pick<VideoWorkspaceState, 'templateId' | 'outputResolution' | 'logoPath' | 'selectedMp3Path'>
  runDir: string
  backgroundPath: string
  branch: 'long' | 'reel'
  batchId: string
  role: string
  selectedMp3Path?: string | null
  fps?: number
}

export function parseRenderResolution(resolution: string): { width: number; height: number } {
  const trimmed = String(resolution || '').trim()
  const match = /^(\d+)\s*x\s*(\d+)$/i.exec(trimmed)
  if (!match) {
    return { width: 1920, height: 1080 }
  }

  const width = Number.parseInt(match[1] ?? '1920', 10)
  const height = Number.parseInt(match[2] ?? '1080', 10)
  return {
    width: Number.isFinite(width) && width > 0 ? width : 1920,
    height: Number.isFinite(height) && height > 0 ? height : 1080,
  }
}

export function buildVideoRenderOutputSettings(
  resolution: string,
  fps = DEFAULT_EXPORT_FPS,
): VideoRenderOutputSettings {
  const normalizedResolution = String(resolution || DEFAULT_OUTPUT_RESOLUTION).trim() || DEFAULT_OUTPUT_RESOLUTION
  const parsed = parseRenderResolution(normalizedResolution)
  return {
    resolution: normalizedResolution,
    width: parsed.width,
    height: parsed.height,
    fps: Number.isFinite(fps) && fps > 0 ? fps : DEFAULT_EXPORT_FPS,
  }
}

export function computePreviewSceneScale(
  bounds: { width: number; height: number },
  reference: AspectRatioReference,
): number {
  let safeWidth = Math.max(1, reference.width || 1)
  let safeHeight = Math.max(1, reference.height || 1)

  if (Math.max(safeWidth, safeHeight) <= 32) {
    if (safeWidth >= safeHeight) {
      safeHeight = (safeHeight / safeWidth) * PREVIEW_REFERENCE_LONG_EDGE_PX
      safeWidth = PREVIEW_REFERENCE_LONG_EDGE_PX
    } else {
      safeWidth = (safeWidth / safeHeight) * PREVIEW_REFERENCE_LONG_EDGE_PX
      safeHeight = PREVIEW_REFERENCE_LONG_EDGE_PX
    }
  }

  return Math.max(0.1, Math.min(bounds.width / safeWidth, bounds.height / safeHeight))
}

export function buildManualRenderSceneRequest({
  template,
  templateDraft,
  workspace,
  backgroundPath,
  selectedMp3Path,
  fps,
}: ManualRenderSceneRequestOptions): RenderSceneRequest {
  const resolvedLogoPath = String(templateDraft.logoPath || workspace.logoPath || '').trim() || null
  const resolvedAudioPath =
    String(selectedMp3Path || workspace.selectedMp3Path || '').trim() || null

  return {
    mode: 'manual',
    template,
    draft: templateDraft,
    assets: {
      backgroundPath: String(backgroundPath || '').trim() || null,
      logoPath: resolvedLogoPath,
      audioPath: resolvedAudioPath,
      runDir: null,
    },
    output: buildVideoRenderOutputSettings(workspace.outputResolution, fps),
    context: {
      templateId: workspace.templateId,
      branch: null,
      batchId: null,
      role: null,
      draftSource: 'live',
    },
  }
}

export function buildPipelineRenderSceneRequest({
  template,
  workspace,
  runDir,
  backgroundPath,
  branch,
  batchId,
  role,
  selectedMp3Path,
  fps,
}: PipelineRenderSceneRequestOptions): RenderSceneRequest {
  const draft = buildVideoTemplateDraft(template, { logoPath: workspace.logoPath })
  const resolvedAudioPath =
    String(selectedMp3Path || workspace.selectedMp3Path || '').trim() || null

  return {
    mode: 'pipeline',
    template,
    draft,
    assets: {
      backgroundPath: String(backgroundPath || '').trim() || null,
      logoPath: String(workspace.logoPath || '').trim() || null,
      audioPath: resolvedAudioPath,
      runDir: String(runDir || '').trim() || null,
    },
    output: buildVideoRenderOutputSettings(workspace.outputResolution, fps),
    context: {
      templateId: workspace.templateId,
      branch,
      batchId: String(batchId || '').trim() || null,
      role: String(role || '').trim() || null,
      draftSource: 'saved',
    },
  }
}
