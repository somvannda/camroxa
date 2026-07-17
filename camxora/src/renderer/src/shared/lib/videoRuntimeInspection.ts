import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { DirectoryEntry, VideoWorkspaceState } from '@/shared/types/desktop'

export type VideoRunInspection = {
  directory: string
  longOutputPaths: string[]
  reelOutputPaths: string[]
  mergedLongPaths: string[]
  mergedReelPaths: string[]
}

export type ProgressRuntimePresentation = {
  converter: string
  merge: string
  stage: string
  status: string
  notes: string
  converterPercent: number
  mergePercent: number
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function normalizePath(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/[\\/]+$/, '')
    .toLowerCase()
}

function joinWindowsPath(directory: string, name: string): string {
  const base = String(directory || '').trim().replace(/[\\/]+$/, '')
  return base ? `${base}\\${name}` : name
}

function buildRuntimeKey(row: ProgressRowResponse): string {
  return `${row.meta.batch_id}:${row.meta.profile_id}:${row.meta.role}`
}

function isTerminalStage(stage: string): boolean {
  const normalized = String(stage || '').trim().toLowerCase()
  return normalized === 'youtube' || normalized === 'done' || normalized === 'error'
}

function stageRank(stage: string): number {
  switch (String(stage || '').trim().toLowerCase()) {
    case 'music':
      return 1
    case 'image':
      return 2
    case 'converter':
      return 3
    case 'merger':
      return 4
    case 'youtube':
      return 5
    case 'done':
      return 6
    case 'error':
      return 7
    default:
      return 0
  }
}

function shouldOverrideStage(apiStage: string, runtimeStage: string): boolean {
  if (!runtimeStage) {
    return false
  }
  if (isTerminalStage(apiStage)) {
    return false
  }
  return stageRank(runtimeStage) >= stageRank(apiStage)
}

export function getProgressRuntimeKey(batchId: string, profileId: string, role: string): string {
  return `${batchId}:${profileId}:${role}`
}

export function inspectVideoRunEntries(directory: string, entries: DirectoryEntry[]): VideoRunInspection {
  const inspection: VideoRunInspection = {
    directory: String(directory || '').trim(),
    longOutputPaths: [],
    reelOutputPaths: [],
    mergedLongPaths: [],
    mergedReelPaths: [],
  }

  entries
    .filter((entry) => !entry.isDirectory)
    .forEach((entry) => {
      const name = String(entry.name || '').trim()
      const lower = name.toLowerCase()
      const fullPath = joinWindowsPath(inspection.directory, name)
      if (!lower.endsWith('.mp4')) {
        return
      }
      if (lower.startsWith('merged_reel_')) {
        inspection.mergedReelPaths.push(fullPath)
        return
      }
      if (lower.startsWith('merged_')) {
        inspection.mergedLongPaths.push(fullPath)
        return
      }
      if (lower.endsWith('_reel.mp4')) {
        inspection.reelOutputPaths.push(fullPath)
        return
      }
      inspection.longOutputPaths.push(fullPath)
    })

  inspection.longOutputPaths.sort((left, right) => left.localeCompare(right))
  inspection.reelOutputPaths.sort((left, right) => left.localeCompare(right))
  inspection.mergedLongPaths.sort((left, right) => left.localeCompare(right))
  inspection.mergedReelPaths.sort((left, right) => left.localeCompare(right))
  return inspection
}

export function resolveProgressRuntimePresentation(
  row: ProgressRowResponse,
  inspection: VideoRunInspection | null | undefined,
  workspace: VideoWorkspaceState | null | undefined,
): ProgressRuntimePresentation {
  const expected = Math.max(1, Number(row.meta.expected || 0))
  const longCount = inspection?.longOutputPaths.length ?? 0
  const reelCount = inspection?.reelOutputPaths.length ?? 0
  const mergedLongCount = inspection?.mergedLongPaths.length ?? 0
  const mergedReelCount = inspection?.mergedReelPaths.length ?? 0
  const normalizedRunDir = normalizePath(row.meta.run_dir)
  const activeRunDir = normalizePath(workspace?.export.outputDir ?? workspace?.mp3Directory ?? '')
  const isActiveRun = Boolean(workspace?.export.running) && normalizedRunDir && normalizedRunDir === activeRunDir
  const activeBranch = workspace?.export.branch === 'reel' ? 'reel' : 'long'
  const mergeRunning = Boolean(isActiveRun && workspace?.export.mergeRunning)
  const exportRunning = Boolean(isActiveRun && workspace?.export.running && !workspace?.export.mergeRunning)

  let longRatio = expected > 0 ? Math.min(longCount / expected, 1) : 0
  let reelRatio = expected > 0 ? Math.min(reelCount / expected, 1) : 0

  if (exportRunning && (workspace?.export.totalJobs ?? 0) > 0) {
    const runningRatio = Math.min((workspace?.export.completedJobs ?? 0) / Math.max(workspace?.export.totalJobs ?? 1, 1), 1)
    if (activeBranch === 'reel') {
      reelRatio = Math.max(reelRatio, runningRatio)
    } else {
      longRatio = Math.max(longRatio, runningRatio)
    }
  }

  let longMergeRatio = mergedLongCount > 0 ? 1 : 0
  let reelMergeRatio = mergedReelCount > 0 ? 1 : 0
  if (expected < 2 && (longCount > 0 || reelCount > 0 || exportRunning || mergeRunning)) {
    longMergeRatio = 1
    reelMergeRatio = 1
  } else if (mergeRunning) {
    if (activeBranch === 'reel') {
      reelMergeRatio = 0.5
    } else {
      longMergeRatio = 0.5
    }
  }

  const converterPercent = clampPercent(((longRatio + reelRatio) / 2) * 100)
  const mergePercent = clampPercent(((longMergeRatio + reelMergeRatio) / 2) * 100)

  let converter = row.converter
  if (exportRunning) {
    converter = workspace?.export.currentStatus?.trim() || `Converting ${activeBranch === 'reel' ? 'reel' : 'long'} videos…`
  } else if (longCount > 0 || reelCount > 0) {
    converter = `Long ${Math.min(longCount, expected)}/${expected} · Reel ${Math.min(reelCount, expected)}/${expected}`
  }

  let merge = row.merge
  if (mergeRunning) {
    merge = workspace?.export.currentStatus?.trim() || `Merging ${activeBranch === 'reel' ? 'reel' : 'long'} outputs…`
  } else if (mergedLongCount > 0 || mergedReelCount > 0) {
    const longLabel = mergedLongCount > 0 ? 'Long merged' : expected < 2 ? 'Long single' : 'Long pending'
    const reelLabel = mergedReelCount > 0 ? 'Reel merged' : expected < 2 ? 'Reel single' : 'Reel pending'
    merge = `${longLabel} · ${reelLabel}`
  } else if (expected < 2 && (longCount > 0 || reelCount > 0)) {
    merge = 'Not required for a single-track run'
  } else if (longCount > 0 || reelCount > 0) {
    merge = 'Ready for merge once enough branch outputs exist'
  }

  let runtimeStage = row.stage
  let runtimeStatus = row.status
  let runtimeNotes = row.notes

  if (mergeRunning) {
    runtimeStage = 'Merger'
    runtimeStatus = 'Merging'
    runtimeNotes = workspace?.export.currentStatus?.trim() || 'Desktop merge is running for this batch/channel run.'
  } else if (exportRunning) {
    runtimeStage = 'Converter'
    runtimeStatus = 'Converting'
    runtimeNotes = workspace?.export.currentStatus?.trim() || 'Desktop video export is running for this batch/channel run.'
  } else if (mergedLongCount > 0 || mergedReelCount > 0) {
    runtimeStage = 'Merger'
    const mergeComplete =
      expected < 2
        ? mergedLongCount > 0 || longCount > 0
        : mergedLongCount > 0 && mergedReelCount > 0
    runtimeStatus = mergeComplete ? 'Completed' : 'Partial'
    runtimeNotes =
      mergedLongCount > 0 || mergedReelCount > 0
        ? mergeComplete
          ? 'Merged outputs were detected locally in the run directory.'
          : 'Only part of the merge branches are ready locally; the other branch is still pending.'
        : row.notes
  } else if (longCount > 0 || reelCount > 0) {
    runtimeStage = 'Converter'
    const convertComplete = longCount >= expected && reelCount >= expected
    runtimeStatus = convertComplete ? 'Completed' : 'Partial'
    runtimeNotes = convertComplete
      ? 'Exported MP4 outputs were detected locally in the run directory.'
      : 'Long and reel exports are only partially present in the run directory.'
  }

  if (!shouldOverrideStage(row.stage, runtimeStage)) {
    runtimeStage = row.stage
    runtimeStatus = row.status
    runtimeNotes = row.notes
  }

  return {
    converter,
    merge,
    stage: runtimeStage,
    status: runtimeStatus,
    notes: runtimeNotes,
    converterPercent,
    mergePercent,
  }
}

export function buildRuntimePresentationMap(
  rows: ProgressRowResponse[],
  inspections: Record<string, VideoRunInspection>,
  workspace: VideoWorkspaceState | null | undefined,
): Record<string, ProgressRuntimePresentation> {
  return Object.fromEntries(
    rows.map((row) => {
      const key = buildRuntimeKey(row)
      return [key, resolveProgressRuntimePresentation(row, inspections[key], workspace)]
    }),
  )
}
