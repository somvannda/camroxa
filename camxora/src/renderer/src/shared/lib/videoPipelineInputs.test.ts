import { describe, expect, it } from 'vitest'

import type { ProfileResponse, ProgressRowResponse } from '@/shared/api/platformEndpoints'
import { resolveVideoPipelineInputs } from '@/shared/lib/videoPipelineInputs'

const profile: ProfileResponse = {
  id: 'profile-1',
  user_id: 'user-1',
  name: 'Primary',
  folder_name: 'Primary',
  run_prefix: 'PRI',
  logo_path: null,
  video_template_id: 'video-template-1',
  reel_template_id: 'reel-template-1',
  output_resolution: '1920x1080',
  image_config: {},
  youtube_config: {},
}

const row: ProgressRowResponse = {
  batch: 'Batch 1',
  run_date: '2026-06-29',
  channel: 'Primary',
  status: 'waiting',
  music: 'Ready',
  image: 'Ready',
  converter: 'Pending',
  merge: 'Pending',
  youtube: 'Pending',
  stage: 'Converter',
  notes: '',
  updated: '2026-06-29 12:00:00',
  meta: {
    batch_id: 'batch-1',
    profile_id: 'profile-1',
    role: 'ok',
    run_dir: 'D:/Music/Primary/2026-06-29',
    source_mode: 'manual',
    background_16x9_path: 'D:/Music/Primary/2026-06-29/background-16x9.png',
    background_9x16_path: 'D:/Music/Primary/2026-06-29/background-9x16.png',
    thumbnail_16x9_path: 'D:/Music/Primary/2026-06-29/thumbnail-16x9.png',
    thumbnail_9x16_path: 'D:/Music/Primary/2026-06-29/thumbnail-9x16.png',
    long_ready: true,
    reel_ready: true,
    expected: 1,
    saved: 1,
    download_ready: 1,
    download_pending: 0,
    bg_ready: 1,
    bg_total: 1,
    th_ready: 1,
    th_total: 1,
    bg_status: 'success',
    th_status: 'success',
    youtube_status: 'pending',
    youtube_url: null,
    youtube_success: 0,
    youtube_pending: 0,
    youtube_failed: 0,
    music_started_at: null,
    music_updated_at: null,
    image_started_at: null,
    image_updated_at: null,
    youtube_created_at: null,
    youtube_updated_at: null,
  },
}

describe('resolveVideoPipelineInputs', () => {
  it('maps long branch to 16:9 assets and long template', () => {
    const result = resolveVideoPipelineInputs(row, 'long', profile)

    expect(result.ready).toBe(true)
    expect(result.backgroundPath).toContain('background-16x9')
    expect(result.thumbnailPath).toContain('thumbnail-16x9')
    expect(result.recommendedTemplateId).toBe('video-template-1')
  })

  it('maps reel branch to 9:16 assets and reel template', () => {
    const result = resolveVideoPipelineInputs(row, 'reel', profile)

    expect(result.ready).toBe(true)
    expect(result.backgroundPath).toContain('background-9x16')
    expect(result.thumbnailPath).toContain('thumbnail-9x16')
    expect(result.recommendedTemplateId).toBe('reel-template-1')
  })
})
