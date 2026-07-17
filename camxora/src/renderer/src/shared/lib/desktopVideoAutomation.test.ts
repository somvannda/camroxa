import { describe, expect, it } from 'vitest'

import type { ProfileResponse, ProgressRowResponse, UserSettingsResponse } from '@/shared/api/platformEndpoints'
import { selectNextAutoVideoCandidate, selectNextAutoYouTubeCandidate } from '@/shared/lib/desktopVideoAutomation'
import type { ProgressRuntimePresentation, VideoRunInspection } from '@/shared/lib/videoRuntimeInspection'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

const row: ProgressRowResponse = {
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
  notes: '',
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
    youtube_status: '',
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

const settings: UserSettingsResponse = {
  autoVideoAfterSuno: true,
  autoReelAfterVideo: true,
}

const workspace: VideoWorkspaceState = {
  template: {},
  templateId: 'video-template-1',
  templateName: 'Template',
  templates: [
    { id: 'video-template-1', name: 'Long Template', kind: 'local', updatedAt: null },
    { id: 'reel-template-1', name: 'Reel Template', kind: 'local', updatedAt: null },
  ],
  outputResolution: '1920x1080',
  previewAspectRatio: { width: 16, height: 9 },
  backgroundPath: '',
  logoPath: '',
  selectedMp3Path: '',
  mp3Directory: '',
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
    outputDir: null,
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

const runtime: ProgressRuntimePresentation = {
  converter: 'Pending',
  merge: 'Pending',
  stage: 'Converter',
  status: 'Queued',
  notes: '',
  converterPercent: 0,
  mergePercent: 0,
}

describe('selectNextAutoVideoCandidate', () => {
  it('prefers long export before reel export', () => {
    const inspections: Record<string, VideoRunInspection> = {
      'batch-1:profile-1:primary': {
        directory: row.meta.run_dir ?? '',
        longOutputPaths: [],
        reelOutputPaths: [],
        mergedLongPaths: [],
        mergedReelPaths: [],
      },
    }

    const candidate = selectNextAutoVideoCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections,
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace,
    })

    expect(candidate?.branch).toBe('long')
    expect(candidate?.templateId).toBe('video-template-1')
  })

  it('starts reel export only after long outputs exist', () => {
    const inspections: Record<string, VideoRunInspection> = {
      'batch-1:profile-1:primary': {
        directory: row.meta.run_dir ?? '',
        longOutputPaths: ['a.mp4', 'b.mp4'],
        reelOutputPaths: [],
        mergedLongPaths: ['MERGED_PRIMARY.mp4'],
        mergedReelPaths: [],
      },
    }

    const candidate = selectNextAutoVideoCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections,
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace,
    })

    expect(candidate?.branch).toBe('reel')
    expect(candidate?.templateId).toBe('reel-template-1')
  })

  it('does not schedule anything while export is already running', () => {
    const candidate = selectNextAutoVideoCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections: {},
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace: {
        ...workspace,
        export: {
          ...workspace.export,
          running: true,
          branch: 'long',
        },
      },
    })

    expect(candidate).toBeNull()
  })

  it('does not schedule anything while merge is still running', () => {
    const candidate = selectNextAutoVideoCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections: {},
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace: {
        ...workspace,
        export: {
          ...workspace.export,
          mergeRunning: true,
        },
      },
    })

    expect(candidate).toBeNull()
  })

  it('waits until desktop mp3 downloads are fully complete', () => {
    const candidate = selectNextAutoVideoCandidate({
      rows: [
        {
          ...row,
          meta: {
            ...row.meta,
            saved: 1,
            download_ready: 2,
            download_pending: 1,
          },
        },
      ],
      profiles: [profile],
      settings,
      inspections: {},
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace,
    })

    expect(candidate).toBeNull()
  })

  it('does not schedule when the required local template is missing', () => {
    const candidate = selectNextAutoVideoCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections: {},
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
      workspace: {
        ...workspace,
        templates: [],
      },
    })

    expect(candidate).toBeNull()
  })
})

describe('selectNextAutoYouTubeCandidate', () => {
  it('selects the first long merged lane when auto upload is enabled', () => {
    const candidate = selectNextAutoYouTubeCandidate({
      rows: [row],
      profiles: [profile],
      settings: {
        ...settings,
        autoUploadYouTube: true,
      },
      inspections: {
        'batch-1:profile-1:primary': {
          directory: row.meta.run_dir ?? '',
          longOutputPaths: ['a.mp4', 'b.mp4'],
          reelOutputPaths: ['a_reel.mp4', 'b_reel.mp4'],
          mergedLongPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4'],
          mergedReelPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_REEL_PRIMARY.mp4'],
        },
      },
      runtimeByKey: { 'batch-1:profile-1:primary': { ...runtime, stage: 'Merger', status: 'Completed' } },
    })

    expect(candidate).toEqual({
      key: 'batch-1:profile-1:primary',
      batchId: 'batch-1',
      profileId: 'profile-1',
      role: 'primary',
      mergedMp4Path: 'D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4',
    })
  })

  it('does not select lanes without auto upload enabled', () => {
    const candidate = selectNextAutoYouTubeCandidate({
      rows: [row],
      profiles: [profile],
      settings,
      inspections: {
        'batch-1:profile-1:primary': {
          directory: row.meta.run_dir ?? '',
          longOutputPaths: ['a.mp4', 'b.mp4'],
          reelOutputPaths: [],
          mergedLongPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4'],
          mergedReelPaths: [],
        },
      },
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
    })

    expect(candidate).toBeNull()
  })

  it('does not auto enqueue when a YouTube job already exists or finished', () => {
    const candidate = selectNextAutoYouTubeCandidate({
      rows: [
        {
          ...row,
          meta: {
            ...row.meta,
            youtube_status: 'running',
            youtube_pending: 1,
          },
        },
      ],
      profiles: [profile],
      settings: {
        ...settings,
        autoUploadYouTube: true,
      },
      inspections: {
        'batch-1:profile-1:primary': {
          directory: row.meta.run_dir ?? '',
          longOutputPaths: ['a.mp4', 'b.mp4'],
          reelOutputPaths: [],
          mergedLongPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4'],
          mergedReelPaths: [],
        },
      },
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
    })

    expect(candidate).toBeNull()
  })

  it('does not auto retry blocked or failed YouTube rows', () => {
    const blockedCandidate = selectNextAutoYouTubeCandidate({
      rows: [
        {
          ...row,
          meta: {
            ...row.meta,
            youtube_status: 'blocked',
          },
        },
      ],
      profiles: [profile],
      settings: {
        ...settings,
        autoUploadYouTube: true,
      },
      inspections: {
        'batch-1:profile-1:primary': {
          directory: row.meta.run_dir ?? '',
          longOutputPaths: ['a.mp4', 'b.mp4'],
          reelOutputPaths: [],
          mergedLongPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4'],
          mergedReelPaths: [],
        },
      },
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
    })
    const failedCandidate = selectNextAutoYouTubeCandidate({
      rows: [
        {
          ...row,
          meta: {
            ...row.meta,
            youtube_status: 'failed',
            youtube_failed: 1,
          },
        },
      ],
      profiles: [profile],
      settings: {
        ...settings,
        autoUploadYouTube: true,
      },
      inspections: {
        'batch-1:profile-1:primary': {
          directory: row.meta.run_dir ?? '',
          longOutputPaths: ['a.mp4', 'b.mp4'],
          reelOutputPaths: [],
          mergedLongPaths: ['D:\\Runs\\batch-1\\primary\\MERGED_PRIMARY.mp4'],
          mergedReelPaths: [],
        },
      },
      runtimeByKey: { 'batch-1:profile-1:primary': runtime },
    })

    expect(blockedCandidate).toBeNull()
    expect(failedCandidate).toBeNull()
  })
})
