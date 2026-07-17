import type { ProfileResponse, ProgressRowResponse } from '@/shared/api/platformEndpoints'

export type VideoPipelineBranch = 'long' | 'reel'

export type ResolvedVideoPipelineInputs = {
  branch: VideoPipelineBranch
  ready: boolean
  runDir: string | null
  sourceMode: string | null
  backgroundPath: string | null
  thumbnailPath: string | null
  recommendedTemplateId: string | null
  recommendedTemplateLabel: string
}

export function buildVideoPipelineRunKey(row: ProgressRowResponse): string {
  return `${row.meta.batch_id}:${row.meta.profile_id}:${row.meta.role}`
}

export function resolveVideoPipelineInputs(
  row: ProgressRowResponse | null,
  branch: VideoPipelineBranch,
  profile: ProfileResponse | null | undefined,
): ResolvedVideoPipelineInputs {
  const meta = row?.meta
  const isLong = branch === 'long'
  const backgroundPath = isLong ? meta?.background_16x9_path ?? null : meta?.background_9x16_path ?? null
  const thumbnailPath = isLong ? meta?.thumbnail_16x9_path ?? null : meta?.thumbnail_9x16_path ?? null
  const recommendedTemplateId = isLong ? profile?.video_template_id ?? null : profile?.reel_template_id ?? null

  return {
    branch,
    ready: isLong ? Boolean(meta?.long_ready) : Boolean(meta?.reel_ready),
    runDir: meta?.run_dir ?? null,
    sourceMode: meta?.source_mode ?? null,
    backgroundPath,
    thumbnailPath,
    recommendedTemplateId,
    recommendedTemplateLabel: isLong ? 'Long template' : 'Reel template',
  }
}
