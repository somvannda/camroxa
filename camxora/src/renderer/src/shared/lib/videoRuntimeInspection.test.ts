import { describe, expect, it } from 'vitest'

import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { DirectoryEntry, VideoWorkspaceState } from '@/shared/types/desktop'
import { inspectVideoRunEntries, resolveProgressRuntimePresentation } from '@/shared/lib/videoRuntimeInspection'

const baseRow: ProgressRowResponse = {
  batch: 'Batch 1',
  run_date: '2026-06-29',
  channel: 'Primary',
  status: 'Queued',
  music: 'Ready',
  image: 'Ready',
  converter: 'Pending',
  merge: 'Pending',
  youtube: 'Pending',
  stage: 'Converter',
  notes: 'Converter and merge progress are still desktop-only and not yet exposed by the API.',
  updated: '2026-06-29 12:00:00',
  meta: {
    batch_id: 'batch-1',
    profile_id: 'profile-1',
    role: 'primary',
    run_dir: 'D:\\Runs\\batch-1\\primary',
    source_mode: 'manual',
    background_16x9_path: 'D:\\Runs\\batch-1\\primary\\background-16x9.png',
    background_9x16_path: 'D:\\Runs\\batch-1\\primary\\background-9x16.png',
    thumbnail_16x9_path: 'D:\\Runs\\batch-1\\primary\\thumbnail-16x9.png',
    thumbnail_9x16_path: 'D:\\Runs\\batch-1\\primary\\thumbnail-9x16.png',
    long_ready: true,
    reel_ready: true,
    expected: 2,
    saved: 2,
    download_ready: 2,
    download_pending: 0,
    bg_ready: 2,
    bg_total: 2,
    th_ready: 2,
    th_total: 2,
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

const baseWorkspace: VideoWorkspaceState = {
  template: {},
  templateId: 'template-1',
  templateName: 'Template 1',
  templates: [],
  outputResolution: '1920x1080',
  previewAspectRatio: { width: 16, height: 9 },
  backgroundPath: '',
  logoPath: '',
  selectedMp3Path: '',
  mp3Directory: 'D:\\Runs\\batch-1\\primary',
  mp3List: [],
  playback: {
    isPlaying: false,
    isReady: false,
    isLoading: false,
    currentTimeSec: 0,
    durationSec: 0,
  },
  export: {
    running: false,
    branch: null,
    workers: 1,
    autoMerge: false,
    mergeRunning: false,
    currentStatus: 'Idle',
    outputDir: 'D:\\Runs\\batch-1\\primary',
    totalJobs: 0,
    completedJobs: 0,
    lastOutputPath: null,
    lastMergedOutputPath: null,
  },
  ui: {
    previewTitle: 'Preview',
    livePreviewOpen: false,
    source: 'python-local',
    notes: [],
  },
}

describe('inspectVideoRunEntries', () => {
  it('splits long, reel, and merged outputs correctly', () => {
    const entries: DirectoryEntry[] = [
      { name: '01 Song.mp4', isDirectory: false },
      { name: '01 Song_REEL.mp4', isDirectory: false },
      { name: 'MERGED_PRIMARY_batch1.mp4', isDirectory: false },
      { name: 'MERGED_REEL_PRIMARY_batch1.mp4', isDirectory: false },
      { name: 'thumb.png', isDirectory: false },
    ]

    const result = inspectVideoRunEntries(baseRow.meta.run_dir ?? '', entries)

    expect(result.longOutputPaths).toHaveLength(1)
    expect(result.reelOutputPaths).toHaveLength(1)
    expect(result.mergedLongPaths).toHaveLength(1)
    expect(result.mergedReelPaths).toHaveLength(1)
  })
})

describe('resolveProgressRuntimePresentation', () => {
  it('promotes the row to Merger while desktop merge is running', () => {
    const runtime = resolveProgressRuntimePresentation(baseRow, null, {
      ...baseWorkspace,
      export: {
        ...baseWorkspace.export,
        running: true,
        branch: 'reel',
        mergeRunning: true,
        currentStatus: 'Merging reel video outputs…',
      },
    })

    expect(runtime.stage).toBe('Merger')
    expect(runtime.status).toBe('Merging')
    expect(runtime.merge).toContain('Merging')
  })

  it('uses merged files on disk as real merger truth', () => {
    const inspection = inspectVideoRunEntries(baseRow.meta.run_dir ?? '', [
      { name: '01 Song.mp4', isDirectory: false },
      { name: '02 Song.mp4', isDirectory: false },
      { name: '01 Song_REEL.mp4', isDirectory: false },
      { name: '02 Song_REEL.mp4', isDirectory: false },
      { name: 'MERGED_PRIMARY_batch1.mp4', isDirectory: false },
      { name: 'MERGED_REEL_PRIMARY_batch1.mp4', isDirectory: false },
    ])

    const runtime = resolveProgressRuntimePresentation(baseRow, inspection, baseWorkspace)

    expect(runtime.stage).toBe('Merger')
    expect(runtime.status).toBe('Completed')
    expect(runtime.converter).toBe('Long 2/2 · Reel 2/2')
    expect(runtime.merge).toBe('Long merged · Reel merged')
  })

  it('labels converter Partial when only one branch exists on disk', () => {
    const inspection = inspectVideoRunEntries(baseRow.meta.run_dir ?? '', [
      { name: '01 Song.mp4', isDirectory: false },
      { name: '02 Song.mp4', isDirectory: false },
    ])

    const runtime = resolveProgressRuntimePresentation(baseRow, inspection, baseWorkspace)

    expect(runtime.stage).toBe('Converter')
    expect(runtime.status).toBe('Partial')
    expect(runtime.converter).toBe('Long 2/2 · Reel 0/2')
  })

  it('labels merger Partial when only long merge exists', () => {
    const inspection = inspectVideoRunEntries(baseRow.meta.run_dir ?? '', [
      { name: '01 Song.mp4', isDirectory: false },
      { name: '02 Song.mp4', isDirectory: false },
      { name: '01 Song_REEL.mp4', isDirectory: false },
      { name: '02 Song_REEL.mp4', isDirectory: false },
      { name: 'MERGED_PRIMARY_batch1.mp4', isDirectory: false },
    ])

    const runtime = resolveProgressRuntimePresentation(baseRow, inspection, baseWorkspace)

    expect(runtime.stage).toBe('Merger')
    expect(runtime.status).toBe('Partial')
    expect(runtime.merge).toBe('Long merged · Reel pending')
  })
})
