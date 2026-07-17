import type { ProfileResponse, ProgressRowResponse } from '@/shared/api/platformEndpoints'
import { buildVideoPipelineRunKey, resolveVideoPipelineInputs, type VideoPipelineBranch } from '@/shared/lib/videoPipelineInputs'
import type { ProgressRuntimePresentation, VideoRunInspection } from '@/shared/lib/videoRuntimeInspection'
import type { UserSettingsResponse } from '@/shared/api/platformEndpoints'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

export type AutoVideoCandidate = {
  key: string
  branch: VideoPipelineBranch
  batchId: string
  role: string
  runDir: string
  backgroundPath: string
  templateId: string
  outputResolution: string | null
  profileId: string | null
  expectedTracks: number
}

export type AutoYouTubeCandidate = {
  key: string
  batchId: string
  profileId: string
  role: string
  mergedMp4Path: string
}

function readBooleanSetting(settings: UserSettingsResponse | undefined, key: string, fallback = false): boolean {
  const value = settings?.[key]
  return typeof value === 'boolean' ? value : fallback
}

function isTerminalStage(stage: string): boolean {
  const normalized = String(stage || '').trim().toLowerCase()
  return normalized === 'youtube' || normalized === 'done' || normalized === 'error'
}

function normalizeYouTubeStatus(value: string | null | undefined): string {
  return String(value || '').trim().toUpperCase()
}

function hasExpectedOutputs(paths: string[] | undefined, expected: number): boolean {
  return (paths?.length ?? 0) >= Math.max(1, expected)
}

function hasDownloadedAudioReady(row: ProgressRowResponse): boolean {
  const expected = Math.max(1, Number(row.meta.expected || 0))
  const downloadedCount = Math.max(0, Number(row.meta.saved || 0))
  const downloadReadyCount = Math.max(0, Number(row.meta.download_ready || 0))
  const pendingDownloadCount = Math.max(0, Number(row.meta.download_pending || 0))
  return downloadedCount >= expected && downloadReadyCount >= expected && pendingDownloadCount <= 0
}

function workspaceHasTemplate(workspace: VideoWorkspaceState | null | undefined, templateId: string): boolean {
  const normalizedTemplateId = String(templateId || '').trim()
  if (!normalizedTemplateId) {
    return false
  }
  return Boolean(workspace?.templates.some((template) => String(template.id || '').trim() === normalizedTemplateId))
}

export function selectNextAutoVideoCandidate(input: {
  rows: ProgressRowResponse[]
  profiles: ProfileResponse[]
  settings: UserSettingsResponse | undefined
  inspections: Record<string, VideoRunInspection>
  runtimeByKey: Record<string, ProgressRuntimePresentation>
  workspace: VideoWorkspaceState | null | undefined
}): AutoVideoCandidate | null {
  if (!readBooleanSetting(input.settings, 'autoVideoAfterSuno', false)) {
    return null
  }
  if (input.workspace?.export.running || input.workspace?.export.mergeRunning) {
    return null
  }

  const profilesById = new Map(input.profiles.map((profile) => [profile.id, profile]))
  const autoReelEnabled = readBooleanSetting(input.settings, 'autoReelAfterVideo', false)

  for (const row of input.rows) {
    const key = buildVideoPipelineRunKey(row)
    const runtime = input.runtimeByKey[key]
    const effectiveStage = runtime?.stage ?? row.stage
    if (isTerminalStage(effectiveStage)) {
      continue
    }

    const profile = profilesById.get(row.meta.profile_id)
    if (!profile) {
      continue
    }

    const expected = Math.max(1, Number(row.meta.expected || 0))
    if (!hasDownloadedAudioReady(row)) {
      continue
    }

    const inspection = input.inspections[key]
    const longInputs = resolveVideoPipelineInputs(row, 'long', profile)
    const reelInputs = resolveVideoPipelineInputs(row, 'reel', profile)
    const longOutputsReady = hasExpectedOutputs(inspection?.longOutputPaths, expected)
    const reelOutputsReady = hasExpectedOutputs(inspection?.reelOutputPaths, expected)

    if (
      longInputs.ready &&
      longInputs.runDir &&
      longInputs.backgroundPath &&
      longInputs.recommendedTemplateId &&
      workspaceHasTemplate(input.workspace, longInputs.recommendedTemplateId) &&
      !longOutputsReady
    ) {
      return {
        key,
        branch: 'long',
        batchId: row.meta.batch_id,
        role: row.meta.role,
        runDir: longInputs.runDir,
        backgroundPath: longInputs.backgroundPath,
        templateId: longInputs.recommendedTemplateId,
        outputResolution: profile.output_resolution ?? null,
        profileId: String(row.meta.profile_id || '').trim() || null,
        expectedTracks: expected,
      }
    }

    if (
      autoReelEnabled &&
      reelInputs.ready &&
      reelInputs.runDir &&
      reelInputs.backgroundPath &&
      reelInputs.recommendedTemplateId &&
      workspaceHasTemplate(input.workspace, reelInputs.recommendedTemplateId) &&
      longOutputsReady &&
      !reelOutputsReady
    ) {
      return {
        key,
        branch: 'reel',
        batchId: row.meta.batch_id,
        role: row.meta.role,
        runDir: reelInputs.runDir,
        backgroundPath: reelInputs.backgroundPath,
        templateId: reelInputs.recommendedTemplateId,
        outputResolution: null,
        profileId: String(row.meta.profile_id || '').trim() || null,
        expectedTracks: expected,
      }
    }
  }

  return null
}

export function selectNextAutoYouTubeCandidate(input: {
  rows: ProgressRowResponse[]
  profiles: ProfileResponse[]
  settings: UserSettingsResponse | undefined
  inspections: Record<string, VideoRunInspection>
  runtimeByKey: Record<string, ProgressRuntimePresentation>
}): AutoYouTubeCandidate | null {
  if (!readBooleanSetting(input.settings, 'autoUploadYouTube', false)) {
    return null
  }

  const profileIds = new Set(input.profiles.map((profile) => profile.id))

  for (const row of input.rows) {
    const key = buildVideoPipelineRunKey(row)
    const runtime = input.runtimeByKey[key]
    const effectiveStage = String(runtime?.stage ?? row.stage).trim().toLowerCase()
    const effectiveStatus = String(runtime?.status ?? row.status).trim().toLowerCase()
    const youtubeStatus = normalizeYouTubeStatus(row.meta.youtube_status)
    const mergedMp4Path = input.inspections[key]?.mergedLongPaths?.[0] ?? ''

    if (!mergedMp4Path) {
      continue
    }
    if (!profileIds.has(row.meta.profile_id)) {
      continue
    }
    if (effectiveStage === 'error' || effectiveStage === 'done') {
      continue
    }
    if (effectiveStage === 'merger' && effectiveStatus === 'merging') {
      continue
    }
    if (row.meta.youtube_success > 0 || Boolean(row.meta.youtube_url)) {
      continue
    }
    if (row.meta.youtube_pending > 0) {
      continue
    }
    if (row.meta.youtube_failed > 0 || youtubeStatus === 'FAILED' || youtubeStatus === 'BLOCKED') {
      continue
    }
    if (youtubeStatus === 'PENDING' || youtubeStatus === 'RUNNING' || youtubeStatus === 'PROCESSING' || youtubeStatus === 'SUCCESS') {
      continue
    }

    return {
      key,
      batchId: row.meta.batch_id,
      profileId: row.meta.profile_id,
      role: row.meta.role,
      mergedMp4Path,
    }
  }

  return null
}
