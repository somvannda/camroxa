import type { ProfileResponse } from '@/shared/api/platformEndpoints'

const MANUAL_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp']

export type ManualAssetSpec = {
  key: 'background-16x9' | 'background-9x16' | 'thumbnail-16x9' | 'thumbnail-9x16'
  label: string
  fileStem: string
}

export type ManualAssetInspection = {
  directory: string
  ready: boolean
  readyCount: number
  total: number
  missingLabels: string[]
  foundFiles: string[]
}

export const MANUAL_ASSET_SPECS: ManualAssetSpec[] = [
  { key: 'background-16x9', label: 'BG 16:9', fileStem: 'background-16x9' },
  { key: 'background-9x16', label: 'BG 9:16', fileStem: 'background-9x16' },
  { key: 'thumbnail-16x9', label: 'TH 16:9', fileStem: 'thumbnail-16x9' },
  { key: 'thumbnail-9x16', label: 'TH 9:16', fileStem: 'thumbnail-9x16' },
]

function normalizeFsPath(value: string): string {
  return String(value || '').trim().replace(/[\\/]+$/, '')
}

function sanitizeFolderSegment(value: string): string {
  return String(value || '')
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]+/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/\.+$/g, '')
    .trim()
    .slice(0, 80) || 'item'
}

function sanitizeRunLabel(value: string): string {
  return String(value || '')
    .replace(/[^a-zA-Z0-9 _.-]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\s/g, '-')
    .slice(0, 64)
}

export function buildRunFolderLabel(runDate: string, album?: string | null): string {
  const datePart = sanitizeRunLabel(runDate).slice(0, 10) || 'run'
  const albumSlug = sanitizeRunLabel(album || '')
  if (albumSlug && !['run', 'item'].includes(albumSlug.toLowerCase())) {
    return `${datePart}_${albumSlug}`.slice(0, 64)
  }
  return datePart
}

function joinWindowsPath(...segments: string[]): string {
  return segments
    .map((segment, index) => {
      const normalized = String(segment || '').replace(/[\\/]+/g, '\\')
      if (index === 0) {
        return normalized.replace(/[\\/]+$/, '')
      }
      return normalized.replace(/^[\\/]+/, '').replace(/[\\/]+$/, '')
    })
    .filter(Boolean)
    .join('\\')
}

function getProfileFolderSegment(profile: ProfileResponse): string {
  return sanitizeFolderSegment(profile.folder_name || profile.name || profile.id)
}

function getBasename(targetPath: string): string {
  const normalized = String(targetPath || '').replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || normalized
}

export function planManualAssetRunDirectories(options: {
  baseDir: string
  okProfile: ProfileResponse
  altProfile: ProfileResponse
  runLabel: string
  existingOkEntries?: string[]
  existingAltEntries?: string[]
}): { okRunDir: string; altRunDir: string; runFolderName: string } {
  const baseDir = normalizeFsPath(options.baseDir)
  if (!baseDir) {
    return { okRunDir: '', altRunDir: '', runFolderName: '' }
  }

  const okProfileDir = joinWindowsPath(baseDir, getProfileFolderSegment(options.okProfile))
  const altProfileDir = joinWindowsPath(baseDir, getProfileFolderSegment(options.altProfile))
  const baseName = sanitizeRunLabel(options.runLabel) || 'run'
  const pattern = new RegExp(`^${baseName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:_(\\d{2,}))?$`)

  const getMaxIndex = (entries: string[]): number => {
    return entries.reduce((max, entry) => {
      const match = pattern.exec(String(entry || '').trim())
      if (!match) {
        return max
      }
      if (!match[1]) {
        return Math.max(max, 1)
      }
      return Math.max(max, Number(match[1]) || 0)
    }, 0)
  }

  const maxExisting = Math.max(getMaxIndex(options.existingOkEntries ?? []), getMaxIndex(options.existingAltEntries ?? []))
  const runFolderName = maxExisting === 0 ? baseName : `${baseName}_${String(maxExisting + 1).padStart(2, '0')}`

  return {
    okRunDir: joinWindowsPath(okProfileDir, runFolderName),
    altRunDir: joinWindowsPath(altProfileDir, runFolderName),
    runFolderName,
  }
}

export function inspectManualAssetFiles(directory: string, files: string[]): ManualAssetInspection {
  const normalizedNames = new Set(files.map((filePath) => getBasename(filePath).toLowerCase()))
  const missingLabels: string[] = []
  const foundFiles: string[] = []

  MANUAL_ASSET_SPECS.forEach((spec) => {
    const matchedFile = MANUAL_IMAGE_EXTENSIONS
      .map((extension) => `${spec.fileStem}.${extension}`)
      .find((candidate) => normalizedNames.has(candidate))

    if (matchedFile) {
      foundFiles.push(matchedFile)
      return
    }

    missingLabels.push(spec.label)
  })

  return {
    directory,
    ready: missingLabels.length === 0,
    readyCount: MANUAL_ASSET_SPECS.length - missingLabels.length,
    total: MANUAL_ASSET_SPECS.length,
    missingLabels,
    foundFiles,
  }
}
