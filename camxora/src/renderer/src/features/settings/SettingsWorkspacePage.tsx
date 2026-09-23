import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUpRight,
  CalendarDays,
  Download,
  FileText,
  Folder,
  FolderOpen,
  Hash,
  Image,
  Info,
  Layers3,
  Link2,
  List,
  Minus,
  Music4,
  Plus,
  Radio,
  RefreshCw,
  RefreshCcw,
  Save,
  Settings2,
  Sparkles,
  Tag,
  Trash2,
  Type,
  UserRound,
  Video,
  type LucideIcon,
} from 'lucide-react'

import { useSettingsWorkspaceQuery } from '@/features/settings/useSettingsWorkspaceQuery'
import { UserOwnedPromptPanel } from '@/features/settings/UserOwnedPromptPanel'
import { getDesktopApi } from '@/shared/api/desktop'
import { PlatformApiError } from '@/shared/api/platformClient'
import {
  apiGetContentPoolStats,
  apiListContentPoolItems,
  apiListImageSamplePacks,
  apiDisconnectYouTubeConnection,
  apiCreateUserProfile,
  apiDeleteUserProfile,
  apiListYouTubePlaylists,
  apiPatchSettings,
  apiResyncYouTubeConnection,
  apiSelectYouTubeChannel,
  apiStartYouTubeConnection,
  apiUpdateUserProfile,
  type ContentPoolKind,
  type ContentPoolRow,
  type CreateProfileRequest,
  type ImageSamplePackItem,
  type PromptNameOption,
  type ProfileResponse,
  type YouTubeConnectionResponse,
  type YouTubePlaylistOption,
} from '@/shared/api/platformEndpoints'
import { getUserPortalUrl } from '@/shared/lib/webLinks'
import { cn } from '@/shared/lib/utils'
import { OUTPUT_RESOLUTION_OPTIONS } from '@/shared/lib/outputResolutions'
import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Input } from '@/shared/ui/input'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import { Textarea } from '@/shared/ui/textarea'

type NoticeTone = 'error' | 'success'
type SettingsTabId =
  | 'youtube'
  | 'profiles'
  | 'publication'
  | 'settings'
  | 'descriptions'
  | 'structures'
  | 'pools'
  | 'suno'
type SelectedProfileKey = string | 'new' | null
type PoolTabId = ContentPoolKind
type PendingConfirmation =
  | { type: 'delete-profile'; profileId: string; profileName: string }
  | { type: 'disconnect-youtube'; profileId: string; profileName: string }
type SampleLibraryKind = 'bg' | 'th'

type SelectOption = {
  value: string
  label: string
}

type ProfileDraft = {
  name: string
  folder_name: string
  run_prefix: string
  logo_path: string
  logo_base64: string | null
  cover_path: string
  cover_base64: string | null
  video_template_id: string
  reel_template_id: string
  output_resolution: string
  image_mode: string
}

type PublicationDraft = {
  description: string
  keywords: string
  visibility: string
  publishDate: string
  publishHour: string
  publishMinute: string
  madeForKids: boolean
  aiUse: boolean
  category: string
  playlist: string
  tags: string
  titleTemplate: string
  descriptionTemplate: string
}

type SystemSettingsDraft = {
  ffmpegPath: string
  downloadsDir: string
  sunoOutputDir: string
  mergedDir: string
  perfMusicWorkers: number
  perfImageWorkers: number
  perfExportWorkers: number
  perfMergeWorkers: number
  perfYouTubeWorkers: number
  youtubeUploadChunkSizeMb: number
  imageBackgroundSamplesDir: string
  imageThumbnailSamplesDir: string
  imageBgRandom: boolean
  imageThumbRandom: boolean
  imageBgSamples: string[]
  imageThumbSamples: string[]
  imageOutputDir: string
  outputResolution: string
  styleStrength: number
  imageSourceMode: string
  backgroundSourceMode: string
  thumbnailOverlayMode: string
}

type SystemPathField =
  | 'ffmpegPath'
  | 'downloadsDir'
  | 'sunoOutputDir'
  | 'mergedDir'
  | 'imageBackgroundSamplesDir'
  | 'imageThumbnailSamplesDir'
  | 'imageOutputDir'

type SunoSettingsDraft = {
  sunoCallbackUrl: string
  sunoTimeoutMs: number
  sunoRetryCount: number
  sunoDefaultVersion: string
  sunoMergeEnabled: boolean
  sunoMergeGroupSize: number
  sunoCreditsReserve: number
  sunoCreditsCostMusic: number
  sunoCreditsCostLyrics: number
}

const PROFILE_IMAGE_MODE_OPTIONS = [
  { value: 'bg_thumb', label: 'BG + TH' },
  { value: 'bg_only', label: 'BG Only' },
  { value: 'thumb_only', label: 'TH Only' },
]
const IMAGE_SOURCE_MODE_OPTIONS = [
  { value: 'ai', label: 'AI Generated' },
  { value: 'manual', label: 'User Provided' },
]
const BACKGROUND_SOURCE_OPTIONS = [{ value: 'samples', label: 'Samples' }]
const THUMBNAIL_OVERLAY_OPTIONS = [{ value: 'ai', label: 'AI' }]
const SUNO_VERSION_OPTIONS = ['v6', 'v6 mini', 'v6 wild', 'v5.5', 'v5']
const SUNO_MERGE_OPTIONS = [
  { value: 'off', label: 'Off' },
  { value: 'on', label: 'On' },
]
const VISIBILITY_OPTIONS = [
  { value: 'unlisted', label: 'Unlisted' },
  { value: 'public', label: 'Public' },
  { value: 'private', label: 'Private' },
  { value: 'scheduled', label: 'Scheduled' },
]
const YES_NO_OPTIONS = [
  { value: 'false', label: 'No' },
  { value: 'true', label: 'Yes' },
]
const PUBLISH_HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => ({
  value: String(hour).padStart(2, '0'),
  label: String(hour).padStart(2, '0'),
}))
const PUBLISH_MINUTE_OPTIONS = Array.from({ length: 12 }, (_, index) => {
  const minute = index * 5
  return {
    value: String(minute).padStart(2, '0'),
    label: String(minute).padStart(2, '0'),
  }
})
const YOUTUBE_CHUNK_SIZE_OPTIONS = [128, 256, 512].map((value) => ({
  value: String(value),
  label: `${value} MB`,
}))
const CONTENT_POOL_PAGE_SIZE = 50
const CATEGORY_OPTIONS = [
  { value: '10', label: 'Music' },
  { value: '24', label: 'Entertainment' },
  { value: '22', label: 'People & Blogs' },
  { value: '20', label: 'Gaming' },
  { value: '1', label: 'Film & Animation' },
  { value: '2', label: 'Autos & Vehicles' },
  { value: '15', label: 'Pets & Animals' },
  { value: '17', label: 'Sports' },
  { value: '19', label: 'Travel & Events' },
  { value: '26', label: 'Howto & Style' },
  { value: '27', label: 'Education' },
  { value: '28', label: 'Science & Technology' },
  { value: '25', label: 'News & Politics' },
  { value: '23', label: 'Comedy' },
]
const TAB_META: Array<{
  id: SettingsTabId
  label: string
  icon: typeof Video
}> = [
  { id: 'profiles', label: 'Profiles', icon: UserRound },
  { id: 'youtube', label: 'YouTube', icon: Video },
  { id: 'publication', label: 'Publication', icon: Radio },
  { id: 'settings', label: 'Preferences', icon: Settings2 },
  { id: 'descriptions', label: 'Descriptions', icon: FileText },
  { id: 'structures', label: 'Structures', icon: Layers3 },
  { id: 'pools', label: 'Pools', icon: Sparkles },
  { id: 'suno', label: 'Suno', icon: Music4 },
]

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getStringSetting(settings: Record<string, unknown>, key: string, fallback = ''): string {
  const value = settings[key]
  return typeof value === 'string' ? value : fallback
}

function getNumberSetting(settings: Record<string, unknown>, key: string, fallback: number): number {
  const value = Number(settings[key])
  return Number.isFinite(value) ? value : fallback
}

function getBoolSetting(settings: Record<string, unknown>, key: string, fallback = false): boolean {
  const value = settings[key]
  return typeof value === 'boolean' ? value : fallback
}

function getStringArraySetting(settings: Record<string, unknown>, key: string): string[] {
  const value = settings[key]
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string').map((item) => item.trim()).filter(Boolean)
}

function normalizePath(value: string): string {
  return value.trim()
}

function toggleSampleSelection(current: string[], next: string): string[] {
  const normalized = next.trim()
  if (!normalized) {
    return current
  }
  if (current.includes(normalized)) {
    return current.filter((item) => item !== normalized)
  }
  if (current.length >= 5) {
    return current
  }
  return [...current, normalized]
}

function formatShortDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return '—'
  }
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function getProfileInitials(name: string): string {
  return (
    name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('') || 'P'
  )
}

function getProfileSearchHaystack(profile: ProfileResponse): string {
  return [profile.name, profile.folder_name ?? '', profile.run_prefix ?? ''].join(' ').trim().toLowerCase()
}

function normalizeProfileImageMode(value: unknown): string {
  const mode = String(value ?? '').trim().toLowerCase()
  if (mode === 'bg_only' || mode === 'thumb_only') {
    return mode
  }
  return 'bg_thumb'
}

function normalizeImageSourceMode(value: unknown): string {
  return String(value ?? '').trim().toLowerCase() === 'manual' ? 'manual' : 'ai'
}

function buildProfileDraft(profile: ProfileResponse | null): ProfileDraft {
  const imageConfig = isRecord(profile?.image_config) ? profile.image_config : {}
  const coverPaths = Array.isArray(imageConfig.cover_paths)
    ? imageConfig.cover_paths.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    : []
  if (!profile) {
    return {
      name: '',
      folder_name: '',
      run_prefix: '',
      logo_path: '',
      logo_base64: null,
      cover_path: '',
      cover_base64: null,
      video_template_id: '',
      reel_template_id: '',
      output_resolution: '1920x1080',
      image_mode: 'bg_thumb',
    }
  }

  return {
    name: profile.name ?? '',
    folder_name: profile.folder_name ?? '',
    run_prefix: profile.run_prefix ?? '',
    logo_path: profile.logo_path ?? '',
    logo_base64: null,
    cover_path: coverPaths[0] ?? '',
    cover_base64: null,
    video_template_id: profile.video_template_id ?? '',
    reel_template_id: profile.reel_template_id ?? '',
    output_resolution: profile.output_resolution || '1920x1080',
    image_mode: normalizeProfileImageMode(imageConfig.mode),
  }
}

function splitPublishAt(value: unknown): { publishDate: string; publishHour: string; publishMinute: string } {
  const text = String(value ?? '').trim()
  const match = text.match(/^(?:(\d{4}-\d{2}-\d{2})[T ])?(\d{1,2}):(\d{2})/)
  if (!match) {
    return { publishDate: '', publishHour: '00', publishMinute: '00' }
  }

  const hour = String(clamp(Number(match[2]), 0, 23)).padStart(2, '0')
  const flooredMinute = Math.floor(clamp(Number(match[3]), 0, 59) / 5) * 5
  const minute = String(flooredMinute).padStart(2, '0')

  return {
    publishDate: match[1] ?? '',
    publishHour: hour,
    publishMinute: minute,
  }
}

function buildPublicationDraft(profile: ProfileResponse | null): PublicationDraft {
  const youtubeConfig = isRecord(profile?.youtube_config) ? profile.youtube_config : {}
  const keywords = Array.isArray(youtubeConfig.keywords)
    ? youtubeConfig.keywords.filter((value): value is string => typeof value === 'string').join(', ')
    : String(youtubeConfig.keywords ?? '')
  const tags = Array.isArray(youtubeConfig.tags)
    ? youtubeConfig.tags.filter((value): value is string => typeof value === 'string').join(', ')
    : String(youtubeConfig.tags ?? '')
  const publishBits = splitPublishAt(youtubeConfig.publish_at)

  return {
    description: String(youtubeConfig.description ?? ''),
    keywords,
    visibility: String(youtubeConfig.visibility ?? 'unlisted'),
    publishDate: publishBits.publishDate,
    publishHour: publishBits.publishHour,
    publishMinute: publishBits.publishMinute,
    madeForKids: Boolean(youtubeConfig.made_for_kids ?? false),
    aiUse: Boolean(youtubeConfig.ai_use ?? false),
    category: String(youtubeConfig.category ?? '10'),
    playlist: String(youtubeConfig.playlist ?? ''),
    tags,
    titleTemplate: String(youtubeConfig.title_template ?? ''),
    descriptionTemplate: String(youtubeConfig.description_template ?? ''),
  }
}

function buildSystemSettingsDraft(settings: Record<string, unknown>): SystemSettingsDraft {
  return {
    ffmpegPath: getStringSetting(settings, 'ffmpegPath'),
    downloadsDir: getStringSetting(settings, 'downloadsDir'),
    sunoOutputDir: getStringSetting(settings, 'sunoOutputDir'),
    mergedDir: getStringSetting(settings, 'mergedDir'),
    perfMusicWorkers: clamp(getNumberSetting(settings, 'perfMusicWorkers', 1), 1, 5),
    perfImageWorkers: clamp(getNumberSetting(settings, 'perfImageWorkers', 4), 1, 8),
    perfExportWorkers: clamp(getNumberSetting(settings, 'videoExportWorkers', getNumberSetting(settings, 'perfExportWorkers', 1)), 1, 10),
    perfMergeWorkers: clamp(getNumberSetting(settings, 'perfMergeWorkers', 1), 1, 2),
    perfYouTubeWorkers: clamp(getNumberSetting(settings, 'perfYouTubeWorkers', 1), 1, 5),
    youtubeUploadChunkSizeMb: clamp(getNumberSetting(settings, 'youtubeUploadChunkSizeMb', 256), 8, 512),
    imageBackgroundSamplesDir: getStringSetting(settings, 'imageBackgroundSamplesDir'),
    imageThumbnailSamplesDir: getStringSetting(settings, 'imageThumbnailSamplesDir'),
    imageBgRandom: getBoolSetting(settings, 'imageBgRandom', false),
    imageThumbRandom: getBoolSetting(settings, 'imageThumbRandom', false),
    imageBgSamples: getStringArraySetting(settings, 'imageBgSamples').slice(0, 5),
    imageThumbSamples: getStringArraySetting(settings, 'imageThumbSamples').slice(0, 5),
    imageOutputDir: getStringSetting(settings, 'imageOutputDir'),
    outputResolution:
      getStringSetting(settings, 'outputResolution') || getStringSetting(settings, 'imageResolution') || '1920x1080',
    styleStrength: clamp(getNumberSetting(settings, 'styleStrength', 60), 0, 100),
    imageSourceMode: normalizeImageSourceMode(settings.imageSourceMode),
    backgroundSourceMode: getStringSetting(settings, 'backgroundSourceMode', 'samples') || 'samples',
    thumbnailOverlayMode: getStringSetting(settings, 'thumbnailOverlayMode', 'ai') || 'ai',
  }
}

function buildSunoSettingsDraft(settings: Record<string, unknown>): SunoSettingsDraft {
  return {
    sunoCallbackUrl: getStringSetting(settings, 'sunoCallbackUrl'),
    sunoTimeoutMs: Math.max(1000, getNumberSetting(settings, 'sunoTimeoutMs', 90000)),
    sunoRetryCount: Math.max(0, getNumberSetting(settings, 'sunoRetryCount', 3)),
    sunoDefaultVersion: getStringSetting(settings, 'sunoDefaultVersion', 'v6') || 'v6',
    sunoMergeEnabled: getBoolSetting(settings, 'sunoMergeEnabled', false),
    sunoMergeGroupSize: Math.max(0, getNumberSetting(settings, 'sunoMergeGroupSize', 0)),
    sunoCreditsReserve: Math.max(0, getNumberSetting(settings, 'sunoCreditsReserve', 10)),
    sunoCreditsCostMusic: Math.max(0, getNumberSetting(settings, 'sunoCreditsCostMusic', 5)),
    sunoCreditsCostLyrics: Math.max(0, getNumberSetting(settings, 'sunoCreditsCostLyrics', 1)),
  }
}

function buildProfilePayload(draft: ProfileDraft, profile: ProfileResponse | null): CreateProfileRequest {
  const baseImageConfig = isRecord(profile?.image_config) ? profile.image_config : {}
  return {
    name: draft.name.trim(),
    folder_name: draft.folder_name.trim() || null,
    run_prefix: draft.run_prefix.trim() || null,
    logo_path: draft.logo_path.trim() || null,
    logo_base64: draft.logo_base64,
    cover_images: draft.cover_base64 ? [draft.cover_base64] : [],
    video_template_id: draft.video_template_id.trim() || null,
    reel_template_id: draft.reel_template_id.trim() || null,
    output_resolution: draft.output_resolution || '1920x1080',
    image_config: { ...baseImageConfig, mode: normalizeProfileImageMode(draft.image_mode) },
  }
}

function buildPublicationPayload(draft: PublicationDraft, baseConfig: Record<string, unknown>): Record<string, unknown> {
  const publishAt =
    draft.visibility === 'scheduled'
      ? `${draft.publishHour}:${draft.publishMinute}`
      : null

  return {
    ...baseConfig,
    description: draft.description.trim(),
    keywords: draft.keywords
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    visibility: draft.visibility,
    publish_at: publishAt,
    made_for_kids: draft.madeForKids,
    ai_use: draft.aiUse,
    category: draft.category.trim(),
    playlist: draft.playlist.trim(),
    tags: draft.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean),
    title_template: draft.titleTemplate.trim(),
    description_template: draft.descriptionTemplate.trim(),
  }
}

function buildSystemSettingsPatch(
  draft: SystemSettingsDraft,
  currentSettings: Record<string, unknown>,
): Record<string, unknown> {
  const current = buildSystemSettingsDraft(currentSettings)
  const patch: Record<string, unknown> = {}

  const assignString = (key: keyof SystemSettingsDraft, patchKey = key) => {
    const nextValue = normalizePath(draft[key] as string)
    const currentValue = normalizePath(current[key] as string)
    if (nextValue !== currentValue) {
      patch[patchKey] = nextValue
    }
  }
  const assignNumber = (key: keyof SystemSettingsDraft, patchKey = key) => {
    if (draft[key] !== current[key]) {
      patch[patchKey] = draft[key]
    }
  }

  assignString('ffmpegPath')
  assignString('downloadsDir')
  assignString('sunoOutputDir')
  assignString('mergedDir')
  assignNumber('perfMusicWorkers')
  assignNumber('perfImageWorkers')
  assignNumber('perfMergeWorkers')
  assignNumber('perfYouTubeWorkers')
  assignNumber('youtubeUploadChunkSizeMb')
  assignString('imageBackgroundSamplesDir')
  assignString('imageThumbnailSamplesDir')
  if (draft.imageBgRandom !== current.imageBgRandom) {
    patch.imageBgRandom = draft.imageBgRandom
  }
  if (draft.imageThumbRandom !== current.imageThumbRandom) {
    patch.imageThumbRandom = draft.imageThumbRandom
  }
  if (JSON.stringify(draft.imageBgSamples) !== JSON.stringify(current.imageBgSamples)) {
    patch.imageBgSamples = draft.imageBgSamples
  }
  if (JSON.stringify(draft.imageThumbSamples) !== JSON.stringify(current.imageThumbSamples)) {
    patch.imageThumbSamples = draft.imageThumbSamples
  }
  assignString('imageOutputDir')
  assignNumber('styleStrength')
  assignString('imageSourceMode')
  assignString('backgroundSourceMode')
  assignString('thumbnailOverlayMode')

  if (draft.outputResolution !== current.outputResolution) {
    patch.outputResolution = draft.outputResolution
    patch.imageResolution = draft.outputResolution
  }
  if (draft.perfExportWorkers !== current.perfExportWorkers) {
    patch.perfExportWorkers = draft.perfExportWorkers
    patch.videoExportWorkers = draft.perfExportWorkers
  }

  return patch
}

function buildSunoSettingsPatch(
  draft: SunoSettingsDraft,
  currentSettings: Record<string, unknown>,
): Record<string, unknown> {
  const current = buildSunoSettingsDraft(currentSettings)
  const patch: Record<string, unknown> = {}

  if (draft.sunoCallbackUrl.trim() !== current.sunoCallbackUrl.trim()) {
    patch.sunoCallbackUrl = draft.sunoCallbackUrl.trim()
  }
  if (draft.sunoTimeoutMs !== current.sunoTimeoutMs) {
    patch.sunoTimeoutMs = draft.sunoTimeoutMs
  }
  if (draft.sunoRetryCount !== current.sunoRetryCount) {
    patch.sunoRetryCount = draft.sunoRetryCount
  }
  if (draft.sunoDefaultVersion !== current.sunoDefaultVersion) {
    patch.sunoDefaultVersion = draft.sunoDefaultVersion
  }
  if (draft.sunoMergeEnabled !== current.sunoMergeEnabled) {
    patch.sunoMergeEnabled = draft.sunoMergeEnabled
  }
  if (draft.sunoMergeGroupSize !== current.sunoMergeGroupSize) {
    patch.sunoMergeGroupSize = draft.sunoMergeGroupSize
  }
  if (draft.sunoCreditsReserve !== current.sunoCreditsReserve) {
    patch.sunoCreditsReserve = draft.sunoCreditsReserve
  }
  if (draft.sunoCreditsCostMusic !== current.sunoCreditsCostMusic) {
    patch.sunoCreditsCostMusic = draft.sunoCreditsCostMusic
  }
  if (draft.sunoCreditsCostLyrics !== current.sunoCreditsCostLyrics) {
    patch.sunoCreditsCostLyrics = draft.sunoCreditsCostLyrics
  }

  return patch
}

function getYouTubeStatusLabel(status: YouTubeConnectionResponse['status'] | 'not_connected'): string {
  switch (status) {
    case 'connected':
      return 'Connected'
    case 'pending_browser':
      return 'Waiting for browser sign-in'
    case 'awaiting_channel_selection':
      return 'Choose a channel'
    case 'error':
      return 'Connection issue'
    case 'not_connected':
    default:
      return 'Not connected'
  }
}

function getYouTubeStatusTone(status: YouTubeConnectionResponse['status'] | 'not_connected'): string {
  switch (status) {
    case 'connected':
      return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-100'
    case 'pending_browser':
      return 'border-sky-400/25 bg-sky-500/10 text-sky-100'
    case 'awaiting_channel_selection':
      return 'border-amber-400/25 bg-amber-500/10 text-amber-100'
    case 'error':
      return 'border-rose-400/25 bg-rose-500/10 text-rose-100'
    case 'not_connected':
    default:
      return 'border-white/10 bg-slate-950/60 text-slate-300'
  }
}

function Panel(props: {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}): React.JSX.Element {
  return (
    <Card className={cn('flex h-full flex-col border-white/10 bg-[#081028] p-4', props.className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{props.title}</p>
          {props.subtitle ? <p className="mt-1 text-xs leading-5 text-slate-400">{props.subtitle}</p> : null}
        </div>
        {props.actions}
      </div>
      <div className="mt-4 grid flex-1 gap-3">{props.children}</div>
    </Card>
  )
}

function FormRow(props: {
  label: string
  icon?: LucideIcon
  children: React.ReactNode
}): React.JSX.Element {
  const Icon = props.icon
  return (
    <div className="grid gap-2 xl:grid-cols-[170px_1fr] xl:items-center">
      <div className="flex items-center gap-2 text-sm text-slate-300">
        {Icon ? <Icon className="h-4 w-4 shrink-0 text-slate-400" /> : null}
        <label>{props.label}</label>
      </div>
      {props.children}
    </div>
  )
}

function SettingsSelect(props: {
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  placeholder: string
  disabled?: boolean
}): React.JSX.Element {
  return (
    <AppSelect
      disabled={props.disabled}
      options={props.options}
      placeholder={props.placeholder}
      value={props.value}
      onChange={props.onChange}
    />
  )
}

function TabButton(props: {
  active: boolean
  icon: typeof Video
  label: string
  onClick: () => void
}): React.JSX.Element {
  const Icon = props.icon
  return (
    <button
      className={cn(
        'flex min-w-0 items-center justify-center gap-2 rounded-xl border px-2 py-2 text-xs font-medium transition',
        props.active
          ? 'border-fuchsia-500/60 bg-fuchsia-500/15 text-white'
          : 'border-white/10 bg-slate-950/60 text-slate-300 hover:border-white/20 hover:bg-white/5',
      )}
      type="button"
      onClick={props.onClick}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{props.label}</span>
    </button>
  )
}

function MiniStat(props: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{props.label}</p>
      <p className="mt-1 text-sm font-medium text-white">{props.value}</p>
    </div>
  )
}

function PlaceholderTable(props: {
  headers: string[]
  rows: Array<Array<string>>
  emptyMessage: string
  bodyClassName?: string
}): React.JSX.Element {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <div className={`grid gap-3 bg-slate-950/70 px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-slate-500`} style={{ gridTemplateColumns: `repeat(${props.headers.length}, minmax(0, 1fr))` }}>
        {props.headers.map((header) => (
          <span key={header}>{header}</span>
        ))}
      </div>
      {props.rows.length ? (
        <div className={cn('divide-y divide-white/10', props.bodyClassName)}>
          {props.rows.map((row, rowIndex) => (
            <div className="grid gap-3 bg-[#081028] px-3 py-2 text-sm text-slate-300" key={`row-${rowIndex + 1}`} style={{ gridTemplateColumns: `repeat(${props.headers.length}, minmax(0, 1fr))` }}>
              {row.map((cell, cellIndex) => (
                <span className="truncate" key={`cell-${rowIndex + 1}-${cellIndex + 1}`}>
                  {cell}
                </span>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-[#081028] px-4 py-10 text-center text-sm text-slate-400">{props.emptyMessage}</div>
      )}
    </div>
  )
}

function PromptNameList(props: {
  items: PromptNameOption[]
  selectedId: string
  emptyMessage: string
  onSelect: (id: string) => void
}): React.JSX.Element {
  if (!props.items.length) {
    return (
      <div className="rounded-xl border border-dashed border-white/10 bg-slate-950/60 px-4 py-10 text-center text-sm text-slate-400">
        {props.emptyMessage}
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-950/60">
      {props.items.map((item, index) => {
        const isActive = item.id === props.selectedId
        return (
          <button
            className={cn(
              'flex w-full items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-left transition last:border-b-0',
              isActive
                ? 'bg-fuchsia-500/10 text-white'
                : 'text-slate-300 hover:bg-white/5',
            )}
            key={item.id}
            type="button"
            onClick={() => props.onSelect(item.id)}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{item.name}</p>
            </div>
            <span className="text-xs text-slate-500">{String(index + 1).padStart(2, '0')}</span>
          </button>
        )
      })}
    </div>
  )
}

function PathSettingRow(props: {
  icon: LucideIcon
  label: string
  value: string
  onChange: (value: string) => void
  browseLabel?: string
  canBrowse?: boolean
  canOpen?: boolean
  onBrowse?: () => void | Promise<void>
  onOpen?: () => void | Promise<void>
}): React.JSX.Element {
  const Icon = props.icon

  return (
    <FormRow icon={Icon} label={props.label}>
      <div className="grid gap-2 xl:grid-cols-[minmax(0,1fr)_88px_72px]">
        <Input className="h-9" value={props.value} onChange={(event) => props.onChange(event.target.value)} />
        <Button
          className="h-9 px-3 text-xs"
          disabled={!props.canBrowse}
          size="sm"
          type="button"
          variant="secondary"
          onClick={() => void props.onBrowse?.()}
        >
          <FolderOpen className="h-4 w-4" />
          {props.browseLabel ?? 'Browse'}
        </Button>
        <Button
          className="h-9 px-3 text-xs"
          disabled={!props.canOpen}
          size="sm"
          type="button"
          variant="secondary"
          onClick={() => void props.onOpen?.()}
        >
          <ArrowUpRight className="h-4 w-4" />
          Open
        </Button>
      </div>
    </FormRow>
  )
}

function WorkerStepperCard(props: {
  icon: LucideIcon
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (value: number) => void
}): React.JSX.Element {
  const Icon = props.icon
  const step = props.step ?? 1

  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-slate-300" />
          <p className="truncate text-sm font-medium leading-5 text-slate-100">{props.label}</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#081028] px-2 py-1">
          <Button
            className="h-7 w-7 rounded-md border border-white/10 px-0"
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => props.onChange(clamp(props.value - step, props.min, props.max))}
          >
            <Minus className="h-3.5 w-3.5" />
          </Button>
          <span className="min-w-[28px] text-center text-sm font-semibold text-white">{props.value}</span>
          <Button
            className="h-7 w-7 rounded-md border border-white/10 px-0"
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => props.onChange(clamp(props.value + step, props.min, props.max))}
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export function SettingsWorkspacePage(): React.JSX.Element {
  const queryClient = useQueryClient()
  const desktopApi = getDesktopApi()
  const profileNameInputRef = useRef<HTMLInputElement | null>(null)
  const [activeTab, setActiveTab] = useState<SettingsTabId>('profiles')
  const [selectedProfileKey, setSelectedProfileKey] = useState<SelectedProfileKey>(null)
  const [selectedDescriptionId, setSelectedDescriptionId] = useState<string>('')
  const [selectedStructureId, setSelectedStructureId] = useState<string>('')
  const [search, setSearch] = useState('')
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(() => buildProfileDraft(null))
  const [publicationDraft, setPublicationDraft] = useState<PublicationDraft>(() => buildPublicationDraft(null))
  const [systemDraft, setSystemDraft] = useState<SystemSettingsDraft>(() => buildSystemSettingsDraft({}))
  const [sunoDraft, setSunoDraft] = useState<SunoSettingsDraft>(() => buildSunoSettingsDraft({}))
  const [poolTab, setPoolTab] = useState<PoolTabId>('openings')
  const [poolOffset, setPoolOffset] = useState(0)
  const [notice, setNotice] = useState<{ tone: NoticeTone; message: string } | null>(null)
  const [lastPersistedProfileKey, setLastPersistedProfileKey] = useState<string | null>(null)
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null)
  const [backgroundSampleFiles, setBackgroundSampleFiles] = useState<string[]>([])
  const [thumbnailSampleFiles, setThumbnailSampleFiles] = useState<string[]>([])
  const [samplePreviewPath, setSamplePreviewPath] = useState<string | null>(null)
  const [samplePreviewDataUrl, setSamplePreviewDataUrl] = useState<string | null>(null)
  const [selectedBackgroundPackId, setSelectedBackgroundPackId] = useState('')
  const [selectedThumbnailPackId, setSelectedThumbnailPackId] = useState('')

  const { data, isLoading, isError, isFetching } = useSettingsWorkspaceQuery()
  const settings = useMemo(() => (isRecord(data?.settings) ? data.settings : {}), [data?.settings])
  const profiles = data?.profiles ?? []
  const descriptionOptions = data?.descriptionOptions ?? []
  const structureOptions = data?.structureOptions ?? []
  const youtubeConnections = data?.youtubeConnections ?? []
  const videoTemplateOptions = data?.videoWorkspace?.templates ?? []
  const selectedProfile =
    selectedProfileKey && selectedProfileKey !== 'new'
      ? profiles.find((profile) => profile.id === selectedProfileKey) ?? null
      : null
  const selectedDescription =
    descriptionOptions.find((item) => item.id === selectedDescriptionId) ?? descriptionOptions[0] ?? null
  const selectedStructure =
    structureOptions.find((item) => item.id === selectedStructureId) ?? structureOptions[0] ?? null
  const selectedYouTubeConnection = useMemo<YouTubeConnectionResponse | null>(() => {
    if (!selectedProfile) {
      return null
    }
    return (
      youtubeConnections.find((connection) => connection.profile_id === selectedProfile.id) ?? {
        profile_id: selectedProfile.id,
        profile_name: selectedProfile.name,
        status: 'not_connected',
        channel_id: null,
        channel_title: null,
        session_id: null,
        channels: [],
        message: 'No YouTube channel is connected yet.',
      }
    )
  }, [selectedProfile, youtubeConnections])
  const publicationPlaylistsQuery = useQuery({
    queryKey: ['youtube-playlists', selectedProfile?.id ?? null],
    queryFn: async () => {
      if (!selectedProfile?.id) {
        return [] as YouTubePlaylistOption[]
      }
      const response = await apiListYouTubePlaylists(selectedProfile.id)
      return response.playlists
    },
    enabled: Boolean(selectedProfile?.id && selectedYouTubeConnection?.status === 'connected'),
    staleTime: 30_000,
  })
  const contentPoolStatsQuery = useQuery({
    queryKey: ['content-pool-stats'],
    queryFn: apiGetContentPoolStats,
    enabled: activeTab === 'pools',
    staleTime: 30_000,
  })
  const contentPoolListQuery = useQuery({
    queryKey: ['content-pool-items', poolTab, poolOffset],
    queryFn: async () => apiListContentPoolItems(poolTab, { limit: CONTENT_POOL_PAGE_SIZE, offset: poolOffset }),
    enabled: activeTab === 'pools',
    staleTime: 30_000,
  })
  const imageSamplePacksQuery = useQuery({
    queryKey: ['image-sample-packs'],
    queryFn: apiListImageSamplePacks,
    enabled: activeTab === 'settings',
    staleTime: 30_000,
  })
  const publicationPlaylistOptions = useMemo<SelectOption[]>(() => {
    const rows = publicationPlaylistsQuery.data ?? []
    const options = rows.map((playlist) => ({
      value: playlist.id,
      label: `${playlist.title} (${playlist.id})`,
    }))
    const currentPlaylist = publicationDraft.playlist.trim()
    if (currentPlaylist && !options.some((option) => option.value === currentPlaylist)) {
      options.push({
        value: currentPlaylist,
        label: `Missing (${currentPlaylist})`,
      })
    }
    return options
  }, [publicationDraft.playlist, publicationPlaylistsQuery.data])
  const selectedPoolStat = useMemo(() => {
    const stats = contentPoolStatsQuery.data
    if (!stats) {
      return null
    }
    return stats[poolTab]
  }, [contentPoolStatsQuery.data, poolTab])
  const contentPoolRows = useMemo<Array<Array<string>>>(() => {
    const items = contentPoolListQuery.data?.items ?? []
    return items.map((item: ContentPoolRow) => [
      String(item.id),
      item.secondary_text ? `${item.text} / ${item.secondary_text}` : item.text,
      String(item.used_count),
      formatShortDate(item.created_at),
    ])
  }, [contentPoolListQuery.data?.items])
  const [selectedYouTubeChannelId, setSelectedYouTubeChannelId] = useState('')

  const filteredProfiles = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) {
      return profiles
    }
    return profiles.filter((profile) => getProfileSearchHaystack(profile).includes(term))
  }, [profiles, search])
  const profileUsage = data?.me.channel_profile_count ?? profiles.length
  const profileAllowance = data?.me.profile_allowance
  const canCreateProfile = profileAllowance == null || profileUsage < profileAllowance
  const isCreatingNewProfile = selectedProfileKey === 'new'
  const profileEditorEnabled = Boolean(selectedProfile || isCreatingNewProfile)
  const publicationEditorEnabled = Boolean(selectedProfile) && !isCreatingNewProfile
  const globalResolutionValue =
    getStringSetting(settings, 'outputResolution') || getStringSetting(settings, 'imageResolution') || '1920x1080'
  const profileResolutionOptions = useMemo(() => {
    const values = [globalResolutionValue, ...OUTPUT_RESOLUTION_OPTIONS.map((item) => item.value)].filter(Boolean)
    const uniqueValues = Array.from(new Set(values))
    const labelByValue = new Map(OUTPUT_RESOLUTION_OPTIONS.map((option) => [option.value, option.label]))
    return uniqueValues.map((value, index) => ({
      value,
      label: index === 0 ? `Use current global (${labelByValue.get(value) ?? value})` : labelByValue.get(value) ?? value,
    }))
  }, [globalResolutionValue])
  const baselineProfileDraft = useMemo(
    () => buildProfileDraft(selectedProfileKey === 'new' ? null : selectedProfile),
    [selectedProfile, selectedProfileKey],
  )
  const baselinePublicationDraft = useMemo(() => buildPublicationDraft(selectedProfile), [selectedProfile])
  const profileDirty =
    selectedProfileKey !== null &&
    JSON.stringify(buildProfilePayload(profileDraft, selectedProfileKey === 'new' ? null : selectedProfile)) !==
      JSON.stringify(buildProfilePayload(baselineProfileDraft, selectedProfileKey === 'new' ? null : selectedProfile))
  const publicationDirty =
    selectedProfileKey !== null &&
    selectedProfileKey !== 'new' &&
    JSON.stringify(publicationDraft) !== JSON.stringify(baselinePublicationDraft)
  const systemDirty = Object.keys(buildSystemSettingsPatch(systemDraft, settings)).length > 0
  const sunoDirty = Object.keys(buildSunoSettingsPatch(sunoDraft, settings)).length > 0
  const isYouTubePolling = youtubeConnections.some((connection) => connection.status === 'pending_browser')
  const dirtyTabs = [
    ...(profileDirty ? ['Profiles'] : []),
    ...(publicationDirty ? ['Publication'] : []),
    ...(systemDirty ? ['Preferences'] : []),
    ...(sunoDirty ? ['Suno'] : []),
  ]

  const imageSamplePacks = imageSamplePacksQuery.data?.items ?? []
  const backgroundSamplePacks = useMemo(
    () => imageSamplePacks.filter((pack) => pack.category.toLowerCase() === 'background'),
    [imageSamplePacks],
  )
  const thumbnailSamplePacks = useMemo(
    () => imageSamplePacks.filter((pack) => pack.category.toLowerCase() === 'thumbnail'),
    [imageSamplePacks],
  )
  const backgroundPackOptions = useMemo<SelectOption[]>(() => {
    return backgroundSamplePacks.map((pack) => ({
      value: pack.id,
      label: pack.version_label ? `${pack.name} (${pack.version_label})` : pack.name,
    }))
  }, [backgroundSamplePacks])
  const thumbnailPackOptions = useMemo<SelectOption[]>(() => {
    return thumbnailSamplePacks.map((pack) => ({
      value: pack.id,
      label: pack.version_label ? `${pack.name} (${pack.version_label})` : pack.name,
    }))
  }, [thumbnailSamplePacks])
  const selectedBackgroundPack = useMemo(
    () => backgroundSamplePacks.find((pack) => pack.id === selectedBackgroundPackId) ?? null,
    [backgroundSamplePacks, selectedBackgroundPackId],
  )
  const selectedThumbnailPack = useMemo(
    () => thumbnailSamplePacks.find((pack) => pack.id === selectedThumbnailPackId) ?? null,
    [selectedThumbnailPackId, thumbnailSamplePacks],
  )

  const refreshSampleLibrary = async () => {
    const [backgroundFiles, thumbnailFiles] = await Promise.all([
      systemDraft.imageBackgroundSamplesDir.trim()
        ? desktopApi.files.listDirectoryImages({
            directoryPath: systemDraft.imageBackgroundSamplesDir.trim(),
            maxResults: 500,
          })
        : Promise.resolve([]),
      systemDraft.imageThumbnailSamplesDir.trim()
        ? desktopApi.files.listDirectoryImages({
            directoryPath: systemDraft.imageThumbnailSamplesDir.trim(),
            maxResults: 500,
          })
        : Promise.resolve([]),
    ])
    setBackgroundSampleFiles(backgroundFiles)
    setThumbnailSampleFiles(thumbnailFiles)
  }

  useEffect(() => {
    if (activeTab !== 'settings') {
      return
    }
    if (!selectedBackgroundPackId && backgroundSamplePacks.length) {
      setSelectedBackgroundPackId(backgroundSamplePacks[0]?.id ?? '')
    }
    if (!selectedThumbnailPackId && thumbnailSamplePacks.length) {
      setSelectedThumbnailPackId(thumbnailSamplePacks[0]?.id ?? '')
    }
  }, [
    activeTab,
    backgroundSamplePacks,
    selectedBackgroundPackId,
    selectedThumbnailPackId,
    thumbnailSamplePacks,
  ])

  const installSamplePackMutation = useMutation({
    mutationFn: async (payload: { pack: ImageSamplePackItem; destinationDir: string }) => {
      const result = await desktopApi.files.downloadAndExtractZip({
        url: payload.pack.source_value,
        destinationDir: payload.destinationDir,
      })
      if (!result.ok) {
        throw new Error(result.error || 'Unable to install sample pack.')
      }
      return { installedCount: result.installedCount, pack: payload.pack, destinationDir: payload.destinationDir }
    },
    onSuccess: async (result) => {
      setNotice({
        tone: 'success',
        message: `Installed ${result.installedCount} files from "${result.pack.name}" into ${result.destinationDir}.`,
      })
      await refreshSampleLibrary()
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Unable to install sample pack.'
      setNotice({ tone: 'error', message })
    },
  })

  const updateSamplePreview = async (path: string | null) => {
    const target = String(path || '').trim()
    setSamplePreviewPath(target || null)
    if (!target) {
      setSamplePreviewDataUrl(null)
      return
    }
    const base64 = await desktopApi.files.readFileAsBase64(target)
    setSamplePreviewDataUrl(base64 ? `data:image/png;base64,${base64}` : null)
  }

  const toggleLibrarySample = (kind: SampleLibraryKind, path: string) => {
    setSystemDraft((current) => {
      if (kind === 'bg') {
        const nextSamples = toggleSampleSelection(current.imageBgSamples, path)
        return { ...current, imageBgSamples: nextSamples }
      }
      const nextSamples = toggleSampleSelection(current.imageThumbSamples, path)
      return { ...current, imageThumbSamples: nextSamples }
    })
    void updateSamplePreview(path)
  }

  useEffect(() => {
    if (profiles.length === 0) {
      if (selectedProfileKey === 'new') {
        return
      }
      if (selectedProfileKey !== null) {
        setSelectedProfileKey(null)
      }
      return
    }
    if (selectedProfileKey === 'new') {
      return
    }
    if (!selectedProfileKey || !profiles.some((profile) => profile.id === selectedProfileKey)) {
      setSelectedProfileKey(profiles[0]?.id ?? null)
    }
  }, [profiles, selectedProfileKey])

  useEffect(() => {
    if (!filteredProfiles.length || !selectedProfileKey || selectedProfileKey === 'new') {
      return
    }
    if (!filteredProfiles.some((profile) => profile.id === selectedProfileKey)) {
      setSelectedProfileKey(filteredProfiles[0]?.id ?? null)
    }
  }, [filteredProfiles, selectedProfileKey])

  useEffect(() => {
    if (selectedProfileKey && selectedProfileKey !== 'new') {
      setLastPersistedProfileKey(selectedProfileKey)
    }
  }, [selectedProfileKey])

  useEffect(() => {
    if (selectedProfileKey === 'new') {
      return
    }
    setProfileDraft(buildProfileDraft(selectedProfile))
    setPublicationDraft(buildPublicationDraft(selectedProfile))
  }, [selectedProfile, selectedProfileKey])

  useEffect(() => {
    if (!isCreatingNewProfile) {
      return
    }
    const frameId = window.requestAnimationFrame(() => {
      profileNameInputRef.current?.focus()
      profileNameInputRef.current?.select()
    })
    return () => {
      window.cancelAnimationFrame(frameId)
    }
  }, [isCreatingNewProfile])

  useEffect(() => {
    if (selectedYouTubeConnection?.status === 'awaiting_channel_selection' && selectedYouTubeConnection.channels.length) {
      if (!selectedYouTubeConnection.channels.some((channel) => channel.id === selectedYouTubeChannelId)) {
        setSelectedYouTubeChannelId(selectedYouTubeConnection.channels[0]?.id ?? '')
      }
      return
    }
    if (selectedYouTubeChannelId) {
      setSelectedYouTubeChannelId('')
    }
  }, [selectedYouTubeChannelId, selectedYouTubeConnection])

  useEffect(() => {
    setSystemDraft(buildSystemSettingsDraft(settings))
    setSunoDraft(buildSunoSettingsDraft(settings))
  }, [settings])

  useEffect(() => {
    if (activeTab !== 'settings') {
      return
    }
    void refreshSampleLibrary()
  }, [
    activeTab,
    desktopApi,
    systemDraft.imageBackgroundSamplesDir,
    systemDraft.imageThumbnailSamplesDir,
  ])

  useEffect(() => {
    const current = samplePreviewPath ? samplePreviewPath.toLowerCase() : null
    const available = new Set(
      [...backgroundSampleFiles, ...thumbnailSampleFiles].map((path) => path.toLowerCase()),
    )
    if (current && !available.has(current)) {
      setSamplePreviewPath(null)
      setSamplePreviewDataUrl(null)
    }
  }, [backgroundSampleFiles, samplePreviewPath, thumbnailSampleFiles])

  useEffect(() => {
    setPoolOffset(0)
  }, [poolTab])

  useEffect(() => {
    if (!descriptionOptions.length) {
      setSelectedDescriptionId('')
      return
    }
    if (!descriptionOptions.some((item) => item.id === selectedDescriptionId)) {
      setSelectedDescriptionId(descriptionOptions[0]?.id ?? '')
    }
  }, [descriptionOptions, selectedDescriptionId])

  useEffect(() => {
    if (!structureOptions.length) {
      setSelectedStructureId('')
      return
    }
    if (!structureOptions.some((item) => item.id === selectedStructureId)) {
      setSelectedStructureId(structureOptions[0]?.id ?? '')
    }
  }, [selectedStructureId, structureOptions])

  useEffect(() => {
    if (!isYouTubePolling) {
      return
    }
    const intervalId = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['settings-workspace'] })
    }, 3000)
    return () => {
      window.clearInterval(intervalId)
    }
  }, [isYouTubePolling, queryClient])

  const invalidateWorkspace = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings-workspace'] }),
      queryClient.invalidateQueries({ queryKey: ['content-pool-stats'] }),
      queryClient.invalidateQueries({ queryKey: ['content-pool-items'] }),
      queryClient.invalidateQueries({ queryKey: ['youtube-playlists'] }),
      queryClient.invalidateQueries({ queryKey: ['music-workspace'] }),
      queryClient.invalidateQueries({ queryKey: ['shell-summary'] }),
    ])
  }

  const saveProfileMutation = useMutation({
    mutationFn: async () => {
      const payload = buildProfilePayload(profileDraft, selectedProfileKey === 'new' ? null : selectedProfile)
      if (!payload.name) {
        throw new Error('Profile name is required.')
      }
      if (selectedProfileKey === 'new') {
        return apiCreateUserProfile(payload)
      }
      if (!selectedProfile) {
        throw new Error('Select a profile first.')
      }
      return apiUpdateUserProfile(selectedProfile.id, payload)
    },
    onSuccess: async (profile) => {
      setNotice({
        tone: 'success',
        message: selectedProfileKey === 'new' ? `Created profile "${profile.name}".` : `Saved profile "${profile.name}".`,
      })
      setSelectedProfileKey(profile.id)
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message: error instanceof PlatformApiError || error instanceof Error ? error.message : 'Unable to save profile right now.',
      })
    },
  })

  const deleteProfileMutation = useMutation({
    mutationFn: async (profile: { profileId: string }) => {
      return apiDeleteUserProfile(profile.profileId)
    },
    onSuccess: async () => {
      setNotice({ tone: 'success', message: 'Deleted the selected profile.' })
      setPendingConfirmation(null)
      setSelectedProfileKey(null)
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message: error instanceof PlatformApiError || error instanceof Error ? error.message : 'Unable to delete profile right now.',
      })
    },
  })

  const savePublicationMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProfile) {
        throw new Error('Select a profile to edit publication defaults.')
      }

      return apiUpdateUserProfile(selectedProfile.id, {
        youtube_config: buildPublicationPayload(
          publicationDraft,
          isRecord(selectedProfile.youtube_config) ? selectedProfile.youtube_config : {},
        ),
      })
    },
    onSuccess: async () => {
      setNotice({ tone: 'success', message: 'Saved publication defaults for the selected profile.' })
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to save publication defaults right now.',
      })
    },
  })

  const saveSystemSettingsMutation = useMutation({
    mutationFn: async () => {
      const patch = buildSystemSettingsPatch(systemDraft, settings)
      if (!Object.keys(patch).length) {
        return settings
      }
      return apiPatchSettings(patch)
    },
    onSuccess: async () => {
      setNotice({ tone: 'success', message: 'Saved Preferences tab values.' })
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to save settings right now.',
      })
    },
  })

  const saveSunoSettingsMutation = useMutation({
    mutationFn: async () => {
      const patch = buildSunoSettingsPatch(sunoDraft, settings)
      if (!Object.keys(patch).length) {
        return settings
      }
      return apiPatchSettings(patch)
    },
    onSuccess: async () => {
      setNotice({ tone: 'success', message: 'Saved Suno settings.' })
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to save Suno settings right now.',
      })
    },
  })
  const connectYouTubeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProfile) {
        throw new Error('Select a profile to connect.')
      }
      const result = await apiStartYouTubeConnection(selectedProfile.id)
      const opened = await desktopApi.files.openExternalUrl(result.auth_url)
      return { ...result, opened }
    },
    onSuccess: async (result) => {
      setNotice({
        tone: 'success',
        message: result.opened
          ? 'Google sign-in opened in your browser. Finish the connection there, then return to CAMXORA.'
          : 'Connection started, but CAMXORA could not open the browser automatically. Start the connection again and check your default browser settings.',
      })
      await queryClient.invalidateQueries({ queryKey: ['settings-workspace'] })
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to start the YouTube connection right now.',
      })
    },
  })
  const selectYouTubeChannelMutation = useMutation({
    mutationFn: async () => {
      if (!selectedYouTubeConnection?.session_id) {
        throw new Error('No active channel selection session was found.')
      }
      if (!selectedYouTubeChannelId.trim()) {
        throw new Error('Choose a channel to connect.')
      }
      return apiSelectYouTubeChannel(selectedYouTubeConnection.session_id, selectedYouTubeChannelId)
    },
    onSuccess: async (connection) => {
      setNotice({
        tone: 'success',
        message: connection.channel_title
          ? `Connected "${connection.channel_title}" to ${connection.profile_name}.`
          : 'Connected the selected YouTube channel.',
      })
      await queryClient.invalidateQueries({ queryKey: ['settings-workspace'] })
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to attach the selected YouTube channel right now.',
      })
    },
  })
  const disconnectYouTubeMutation = useMutation({
    mutationFn: async (profile: { profileId: string }) => {
      return apiDisconnectYouTubeConnection(profile.profileId)
    },
    onSuccess: async () => {
      setNotice({ tone: 'success', message: 'Disconnected the YouTube channel for the selected profile.' })
      setPendingConfirmation(null)
      await queryClient.invalidateQueries({ queryKey: ['settings-workspace'] })
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to disconnect the YouTube channel right now.',
      })
    },
  })
  const resyncYouTubeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProfile) {
        throw new Error('Select a connected profile to resync.')
      }
      return apiResyncYouTubeConnection(selectedProfile.id)
    },
    onSuccess: async (connection) => {
      setNotice({
        tone: 'success',
        message: connection.channel_title
          ? `Resynced "${connection.channel_title}" into ${connection.profile_name}.`
          : 'Resynced the connected YouTube channel data.',
      })
      await invalidateWorkspace()
    },
    onError: (error) => {
      setNotice({
        tone: 'error',
        message:
          error instanceof PlatformApiError || error instanceof Error
            ? error.message
            : 'Unable to resync the connected YouTube channel right now.',
      })
    },
  })
  const isSavePending =
    saveProfileMutation.isPending ||
    savePublicationMutation.isPending ||
    saveSystemSettingsMutation.isPending ||
    saveSunoSettingsMutation.isPending ||
    deleteProfileMutation.isPending
  const isYouTubePending =
    connectYouTubeMutation.isPending ||
    selectYouTubeChannelMutation.isPending ||
    disconnectYouTubeMutation.isPending ||
    resyncYouTubeMutation.isPending
  const isPublicationPending = savePublicationMutation.isPending || publicationPlaylistsQuery.isFetching

  const startInlineProfileCreate = () => {
    if (!canCreateProfile) {
      setNotice({
        tone: 'error',
        message:
          profileAllowance != null
            ? `Your current plan allows ${profileAllowance} profiles. Remove one first or upgrade before creating another one.`
            : 'Profile creation is unavailable right now.',
      })
      return
    }
    setNotice(null)
    setProfileDraft(buildProfileDraft(null))
    setPublicationDraft(buildPublicationDraft(null))
    setSelectedProfileKey('new')
  }

  const cancelInlineProfileCreate = () => {
    setNotice(null)
    setProfileDraft(buildProfileDraft(null))
    setPublicationDraft(buildPublicationDraft(null))
    setSelectedProfileKey(lastPersistedProfileKey ?? profiles[0]?.id ?? null)
  }

  const handleBrowseProfileLogo = async () => {
    if (!profileEditorEnabled) {
      return
    }
    const selectedPath = await desktopApi.files.selectFile({
      title: 'Select profile logo',
      filters: [
        { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })
    if (!selectedPath) {
      return
    }
    try {
      const imageBase64 = await desktopApi.files.readFileAsBase64(selectedPath)
      setProfileDraft((current) => ({
        ...current,
        logo_path: selectedPath,
        logo_base64: imageBase64,
      }))
    } catch {
      setNotice({ tone: 'error', message: 'Unable to read the selected logo file.' })
      return
    }
    setNotice(null)
  }

  const handleBrowseProfileCover = async () => {
    if (!profileEditorEnabled) {
      return
    }
    const selectedPath = await desktopApi.files.selectFile({
      title: 'Select channel cover',
      filters: [
        { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })
    if (!selectedPath) {
      return
    }
    try {
      const imageBase64 = await desktopApi.files.readFileAsBase64(selectedPath)
      setProfileDraft((current) => ({
        ...current,
        cover_path: selectedPath,
        cover_base64: imageBase64,
      }))
    } catch {
      setNotice({ tone: 'error', message: 'Unable to read the selected cover file.' })
      return
    }
    setNotice(null)
  }

  const handleOpenProfileCover = async () => {
    const targetPath = profileDraft.cover_path.trim()
    if (!profileEditorEnabled || !targetPath) {
      return
    }
    const opened = await desktopApi.files.openPath(targetPath)
    if (!opened) {
      setNotice({ tone: 'error', message: 'Unable to open the selected cover path right now.' })
    }
  }

  const handleOpenProfileLogo = async () => {
    const targetPath = profileDraft.logo_path.trim()
    if (!profileEditorEnabled || !targetPath) {
      return
    }
    const opened = await desktopApi.files.openPath(targetPath)
    if (!opened) {
      setNotice({ tone: 'error', message: 'Unable to open the selected logo path right now.' })
    }
  }

  const handleBrowseSystemPath = async (field: SystemPathField, options: {
    title: string
    kind: 'file' | 'directory'
    filters?: Array<{ name: string; extensions: string[] }>
  }) => {
    const selectedPath =
      options.kind === 'directory'
        ? await desktopApi.files.selectPath({
            title: options.title,
            kind: 'directory',
          })
        : await desktopApi.files.selectPath({
            title: options.title,
            kind: 'file',
            filters: options.filters,
          })

    if (!selectedPath) {
      return
    }

    setSystemDraft((current) => ({
      ...current,
      [field]: selectedPath,
    }))
    setNotice(null)
  }

  const handleOpenSystemPath = async (field: SystemPathField, label: string) => {
    const targetPath = systemDraft[field].trim()
    if (!targetPath) {
      return
    }
    const opened = await desktopApi.files.openPath(targetPath)
    if (!opened) {
      setNotice({ tone: 'error', message: `Unable to open the selected ${label.toLowerCase()} path right now.` })
    }
  }

  const handleSaveAll = async () => {
    try {
      if (profileDirty && selectedProfileKey !== null) {
        await saveProfileMutation.mutateAsync()
      }

      if (publicationDirty && selectedProfile) {
        await savePublicationMutation.mutateAsync()
      }

      if (systemDirty) {
        await saveSystemSettingsMutation.mutateAsync()
      }

      if (sunoDirty) {
        await saveSunoSettingsMutation.mutateAsync()
      }

      if (!dirtyTabs.length) {
        setNotice({ tone: 'success', message: 'No changes to save.' })
      } else if (selectedProfileKey === 'new' && publicationDraft.titleTemplate.trim()) {
        setNotice({
          tone: 'success',
          message: 'Profile saved. Save publication defaults after the new profile is created.',
        })
      } else {
        setNotice({ tone: 'success', message: `Saved ${dirtyTabs.join(', ')}.` })
      }
    } catch {
      // Mutation callbacks already surface the user-facing error state.
    }
  }

  const renderYouTubeTab = () => {
    const status = selectedYouTubeConnection?.status ?? 'not_connected'
    const statusLabel = getYouTubeStatusLabel(status)
    const canDisconnect = Boolean(selectedProfile && status !== 'not_connected')
    const canStartConnection = Boolean(selectedProfile) && !isYouTubePending
    const canResync = Boolean(selectedProfile && status === 'connected') && !isYouTubePending
    const canChooseChannel = Boolean(
      selectedYouTubeConnection?.status === 'awaiting_channel_selection' &&
        selectedYouTubeConnection.session_id &&
        selectedYouTubeChannelId,
    )

    return (
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel
          title="Channel Connection"
          subtitle="Attach a YouTube channel to the selected profile and use it for publication settings."
        >
          <MiniStat label="Connection status" value={statusLabel} />
          <FormRow icon={UserRound} label="Profile">
            <SettingsSelect
              placeholder="Select a profile"
              options={profiles.map((profile) => ({ value: profile.id, label: profile.name }))}
              value={selectedProfileKey === 'new' ? '' : selectedProfile?.id ?? ''}
              onChange={(value) => {
                setNotice(null)
                setSelectedProfileKey(value || null)
              }}
            />
          </FormRow>
          <FormRow icon={Video} label="Channel">
            <div
              className={cn(
                'rounded-xl border px-3 py-2 text-sm',
                getYouTubeStatusTone(status),
              )}
            >
              {selectedYouTubeConnection?.channel_title
                ? `${selectedYouTubeConnection.channel_title}${selectedYouTubeConnection.channel_id ? ` (${selectedYouTubeConnection.channel_id})` : ''}`
                : selectedProfile
                  ? selectedYouTubeConnection?.message ?? 'No YouTube channel is connected yet.'
                  : 'Select a profile to continue.'}
            </div>
          </FormRow>
          {selectedYouTubeConnection?.status === 'awaiting_channel_selection' ? (
            <FormRow icon={List} label="Choose channel">
              <div className="flex gap-2">
                <SettingsSelect
                  placeholder="Select a returned channel"
                  options={selectedYouTubeConnection.channels.map((channel) => ({
                    value: channel.id,
                    label: channel.title,
                  }))}
                  value={selectedYouTubeChannelId}
                  onChange={setSelectedYouTubeChannelId}
                />
                <Button
                  disabled={!canChooseChannel || isYouTubePending}
                  type="button"
                  onClick={() => void selectYouTubeChannelMutation.mutateAsync()}
                >
                  <Link2 className="h-4 w-4" />
                  {selectYouTubeChannelMutation.isPending ? 'Attaching...' : 'Attach Channel'}
                </Button>
              </div>
            </FormRow>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={!canStartConnection}
              size="sm"
              type="button"
              onClick={() => void connectYouTubeMutation.mutateAsync()}
            >
              <Link2 className="h-4 w-4" />
              {connectYouTubeMutation.isPending
                ? 'Opening Browser...'
                : status === 'pending_browser'
                  ? 'Restart Sign-In'
                : status === 'connected'
                  ? 'Reconnect Channel'
                  : status === 'error'
                    ? 'Try Again'
                  : status === 'awaiting_channel_selection'
                    ? 'Start Again'
                    : 'Connect Channel'}
            </Button>
            <Button
              disabled={!canResync}
              size="sm"
              type="button"
              variant="secondary"
              onClick={() => void resyncYouTubeMutation.mutateAsync()}
            >
              <RefreshCcw className="h-4 w-4" />
              {resyncYouTubeMutation.isPending ? 'Resyncing...' : 'Resync Channel Data'}
            </Button>
            <Button
              disabled={!canDisconnect || isYouTubePending}
              size="sm"
              type="button"
              variant="secondary"
              onClick={async () => {
                if (!selectedProfile) {
                  return
                }
                setPendingConfirmation({
                  type: 'disconnect-youtube',
                  profileId: selectedProfile.id,
                  profileName: selectedProfile.name,
                })
              }}
            >
              <Trash2 className="h-4 w-4" />
              {disconnectYouTubeMutation.isPending ? 'Disconnecting...' : 'Disconnect'}
            </Button>
          </div>
          <p className="text-xs leading-5 text-slate-400">
            {selectedYouTubeConnection?.status === 'pending_browser'
              ? 'Finish Google sign-in in your browser. If the browser flow was closed or cancelled, use Restart Sign-In to begin a fresh connection.'
              : selectedYouTubeConnection?.status === 'awaiting_channel_selection'
                ? 'Google returned more than one channel. Choose which one should be connected to this profile.'
                : selectedYouTubeConnection?.status === 'error'
                  ? 'The previous YouTube connection attempt failed. Use Try Again to start a fresh sign-in flow.'
                : 'Connect once here, then keep publication defaults per profile in the Publication tab.'}
          </p>
        </Panel>

        <Panel
          title="Channel Access"
          subtitle="Review the current YouTube connection state for the selected profile."
        >
          <div className="grid gap-3 md:grid-cols-3">
            <MiniStat label="Selected profile" value={selectedProfile?.name ?? 'No profile'} />
            <MiniStat
              label="Returned channels"
              value={String(selectedYouTubeConnection?.channels.length ?? (selectedYouTubeConnection?.channel_id ? 1 : 0))}
            />
            <MiniStat
              label="Session"
              value={
                selectedYouTubeConnection?.status === 'pending_browser'
                  ? 'In progress'
                  : selectedYouTubeConnection?.status === 'awaiting_channel_selection'
                    ? 'Needs selection'
                    : selectedYouTubeConnection?.status === 'connected'
                      ? 'Ready'
                      : 'Idle'
              }
            />
          </div>
          <div className="space-y-3 rounded-xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-300">
            <p className="font-medium text-white">Current state</p>
            <p className="leading-6 text-slate-300">
              {selectedProfile
                ? selectedYouTubeConnection?.message ?? 'No YouTube channel is connected yet.'
                : 'Select a profile first to review its YouTube connection state.'}
            </p>
          </div>
          <div className="space-y-3 rounded-xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-300">
            <p className="font-medium text-white">Connected channel</p>
            <p className="leading-6 text-slate-300">
              {selectedYouTubeConnection?.channel_title
                ? `${selectedYouTubeConnection.channel_title}${selectedYouTubeConnection.channel_id ? ` (${selectedYouTubeConnection.channel_id})` : ''}`
                : 'No YouTube channel is connected yet.'}
            </p>
            <p className="text-xs leading-5 text-slate-400">
              Use this tab to connect or disconnect the account. Publication metadata remains editable in the Publication tab.
            </p>
          </div>
        </Panel>
      </div>
    )
  }

  const renderProfilesTab = () => (
    <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
      <Panel title="Your Profiles" subtitle="Select a profile to edit. Search matches name, folder name, and run prefix.">
        <div className="flex h-full min-h-[520px] flex-col gap-3">
          <Input
            placeholder="Search by name, folder, or prefix..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="grid flex-1 content-start gap-2">
            {isCreatingNewProfile ? (
              <button
                className="flex items-center gap-3 rounded-xl border border-violet-400/40 bg-violet-500/10 px-3 py-3 text-left transition"
                type="button"
                onClick={() => {
                  setNotice(null)
                  setSelectedProfileKey('new')
                }}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-500/20 text-sm font-semibold text-violet-100">
                  <Plus className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">{profileDraft.name.trim() || 'New profile draft'}</p>
                  <p className="truncate text-xs text-slate-300">Save this draft to create a new profile.</p>
                </div>
              </button>
            ) : null}
            {filteredProfiles.length ? (
              filteredProfiles.map((profile) => {
                const isActive = selectedProfileKey === profile.id
                return (
                  <button
                    className={cn(
                      'flex items-center gap-3 rounded-xl border px-3 py-3 text-left transition',
                      isActive
                        ? 'border-violet-400/40 bg-violet-500/10'
                        : 'border-white/10 bg-slate-950/60 hover:border-white/20 hover:bg-white/5',
                    )}
                    key={profile.id}
                    type="button"
                    onClick={() => {
                      setNotice(null)
                      setSelectedProfileKey(profile.id)
                    }}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-sm font-semibold text-white">
                      {getProfileInitials(profile.name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{profile.name}</p>
                      <p className="truncate text-xs text-slate-400">
                        {profile.folder_name || profile.run_prefix || profile.output_resolution}
                      </p>
                    </div>
                  </button>
                )
              })
            ) : (
              <div className="rounded-xl border border-dashed border-white/10 bg-slate-950/60 px-4 py-8 text-center text-sm text-slate-400">
                {profiles.length
                  ? 'No profiles match your search.'
                  : canCreateProfile
                    ? 'No profiles yet. Click Add New Profile to create your first profile.'
                    : 'No profiles yet, but profile creation is currently unavailable for this account.'}
              </div>
            )}
          </div>
          {isCreatingNewProfile ? (
            <div className="rounded-xl border border-violet-400/20 bg-violet-500/10 px-3 py-3 text-xs leading-5 text-violet-100">
              Creating a new inline profile draft. Complete the profile form on the right, then save to create it.
            </div>
          ) : null}
          <Button
            className="mt-auto"
            type="button"
            variant={!canCreateProfile || isCreatingNewProfile ? 'secondary' : 'primary'}
            onClick={startInlineProfileCreate}
          >
            <Plus className="h-4 w-4" />
            {isCreatingNewProfile ? 'Creating New Profile' : canCreateProfile ? 'Add New Profile' : 'Profile Limit Reached'}
          </Button>
        </div>
      </Panel>

      <Panel
        title={profileDraft.name || (isCreatingNewProfile ? 'New profile' : 'No profile selected')}
        subtitle={
          isCreatingNewProfile
            ? 'Create a new profile directly here, then continue with publication defaults after it has been saved.'
            : 'Manage the selected profile here, or use the footer to save changes across tabs.'
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={!profileEditorEnabled || !profileDirty || saveProfileMutation.isPending}
              size="sm"
              type="button"
              onClick={async () => {
                await saveProfileMutation.mutateAsync()
              }}
            >
              <Save className="h-4 w-4" />
              {saveProfileMutation.isPending ? (isCreatingNewProfile ? 'Creating...' : 'Saving...') : isCreatingNewProfile ? 'Create Profile' : 'Save Changes'}
            </Button>
            {isCreatingNewProfile ? (
              <Button
                disabled={saveProfileMutation.isPending}
                size="sm"
                type="button"
                variant="secondary"
                onClick={cancelInlineProfileCreate}
              >
                Cancel Draft
              </Button>
            ) : null}
            {!isCreatingNewProfile ? (
              <Button
                disabled={!profileEditorEnabled || deleteProfileMutation.isPending}
                size="sm"
                type="button"
                variant="secondary"
                onClick={async () => {
                  if (!selectedProfile) {
                    return
                  }
                  setPendingConfirmation({
                    type: 'delete-profile',
                    profileId: selectedProfile.id,
                    profileName: selectedProfile.name,
                  })
                }}
              >
                <Trash2 className="h-4 w-4" />
                {deleteProfileMutation.isPending ? 'Deleting...' : 'Delete'}
              </Button>
            ) : null}
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-sm font-semibold text-white">
            {getProfileInitials(profileDraft.name || selectedProfile?.name || 'Profile')}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-white">{isCreatingNewProfile ? 'Source: New inline profile' : 'Source: Account profile'}</p>
            <p className="text-xs text-slate-400">
              {isCreatingNewProfile
                ? 'YouTube: Save this profile first before connecting a channel.'
                : `YouTube: ${getYouTubeStatusLabel(selectedYouTubeConnection?.status ?? 'not_connected')}`}
            </p>
          </div>
        </div>

        <FormRow icon={UserRound} label="Name">
          <Input
            disabled={!profileEditorEnabled}
            ref={profileNameInputRef}
            value={profileDraft.name}
            onChange={(event) => setProfileDraft((current) => ({ ...current, name: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Folder} label="Folder name">
          <Input
            disabled={!profileEditorEnabled}
            value={profileDraft.folder_name}
            onChange={(event) => setProfileDraft((current) => ({ ...current, folder_name: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Hash} label="Run prefix (optional)">
          <Input
            disabled={!profileEditorEnabled}
            value={profileDraft.run_prefix}
            onChange={(event) => setProfileDraft((current) => ({ ...current, run_prefix: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Image} label="Channel logo (center)">
          <div className="flex gap-2">
            <Input
              disabled={!profileEditorEnabled}
              value={profileDraft.logo_path}
              onChange={(event) => setProfileDraft((current) => ({ ...current, logo_path: event.target.value }))}
            />
            <Button disabled={!profileEditorEnabled} type="button" variant="secondary" onClick={() => void handleBrowseProfileLogo()}>
              <FolderOpen className="h-4 w-4" />
              Browse
            </Button>
            <Button
              disabled={!profileEditorEnabled || !profileDraft.logo_path.trim()}
              type="button"
              variant="secondary"
              onClick={() => void handleOpenProfileLogo()}
            >
              <ArrowUpRight className="h-4 w-4" />
              Open
            </Button>
          </div>
        </FormRow>
        <FormRow icon={Image} label="Channel cover">
          <div className="flex gap-2">
            <Input
              disabled={!profileEditorEnabled}
              value={profileDraft.cover_path}
              onChange={(event) => setProfileDraft((current) => ({ ...current, cover_path: event.target.value }))}
            />
            <Button disabled={!profileEditorEnabled} type="button" variant="secondary" onClick={() => void handleBrowseProfileCover()}>
              <FolderOpen className="h-4 w-4" />
              Browse
            </Button>
            <Button
              disabled={!profileEditorEnabled || !profileDraft.cover_path.trim()}
              type="button"
              variant="secondary"
              onClick={() => void handleOpenProfileCover()}
            >
              <ArrowUpRight className="h-4 w-4" />
              Open
            </Button>
          </div>
        </FormRow>
        <FormRow icon={Video} label="Video template">
          <SettingsSelect
            disabled={!profileEditorEnabled}
            placeholder="No template selected"
            options={videoTemplateOptions.map((template) => ({ value: template.id, label: template.name }))}
            value={profileDraft.video_template_id}
            onChange={(value) => setProfileDraft((current) => ({ ...current, video_template_id: value }))}
          />
        </FormRow>
        <FormRow icon={Video} label="Reel template">
          <SettingsSelect
            disabled={!profileEditorEnabled}
            placeholder="No template selected"
            options={videoTemplateOptions.map((template) => ({ value: template.id, label: template.name }))}
            value={profileDraft.reel_template_id}
            onChange={(value) => setProfileDraft((current) => ({ ...current, reel_template_id: value }))}
          />
        </FormRow>
        <FormRow icon={Settings2} label="Output resolution">
          <div id="settings-profile-resolution">
            <SettingsSelect
            disabled={!profileEditorEnabled}
            placeholder="Select an output resolution"
            options={profileResolutionOptions}
            value={profileDraft.output_resolution}
            onChange={(value) => setProfileDraft((current) => ({ ...current, output_resolution: value }))}
            />
          </div>
        </FormRow>
        <FormRow icon={Image} label="Image mode">
          <SettingsSelect
            disabled={!profileEditorEnabled}
            placeholder="Select an image mode"
            options={PROFILE_IMAGE_MODE_OPTIONS}
            value={profileDraft.image_mode}
            onChange={(value) => setProfileDraft((current) => ({ ...current, image_mode: value }))}
          />
        </FormRow>
        <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3 text-xs leading-5 text-slate-300">
          `BG + TH` creates both background and thumbnail jobs. `BG Only` or `TH Only` only affect future batches.
        </div>
      </Panel>
    </div>
  )

  const renderPublicationTab = () => {
    const isScheduledVisibility = publicationDraft.visibility === 'scheduled'
    const publicationYouTubeTone = getYouTubeStatusTone(selectedYouTubeConnection?.status ?? 'not_connected')
    const publishSummary =
      isScheduledVisibility
        ? `Scheduled uploads use the batch date and the saved time ${publicationDraft.publishHour}:${publicationDraft.publishMinute}.`
        : 'This field only applies when visibility is set to Scheduled.'

    return (
      <div className="grid gap-4">
        <Panel
          title="Publication"
          subtitle="Manage profile-specific publishing metadata and YouTube publishing defaults."
          actions={
            <Button
              disabled={!publicationEditorEnabled || !publicationDirty || savePublicationMutation.isPending}
              size="sm"
              type="button"
              onClick={async () => {
                await savePublicationMutation.mutateAsync()
              }}
            >
              <Save className="h-4 w-4" />
              {savePublicationMutation.isPending ? 'Saving...' : 'Save Publication'}
            </Button>
          }
        >
        <FormRow icon={UserRound} label="Selected profile">
          <SettingsSelect
            placeholder="Select a profile"
            options={profiles.map((profile) => ({ value: profile.id, label: profile.name }))}
            value={selectedProfileKey === 'new' ? '' : selectedProfile?.id ?? ''}
            onChange={(value) => {
              setNotice(null)
              setSelectedProfileKey(value || null)
            }}
          />
        </FormRow>
        <FormRow icon={Video} label="YouTube">
          <div className={cn('rounded-xl border px-3 py-2 text-sm', publicationYouTubeTone)}>
            {!publicationEditorEnabled
              ? 'Save the new profile first before editing publication defaults.'
              : selectedYouTubeConnection?.channel_title
              ? `${getYouTubeStatusLabel(selectedYouTubeConnection.status)}: ${selectedYouTubeConnection.channel_title}`
              : getYouTubeStatusLabel(selectedYouTubeConnection?.status ?? 'not_connected')}
          </div>
        </FormRow>
        <FormRow icon={Link2} label="Channel access">
          <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">
            {publicationEditorEnabled
              ? 'Connect or change the YouTube channel from the YouTube tab. Publication defaults here apply to the currently connected channel.'
              : 'Finish creating this profile first. Once it is saved, you can return here to edit publication defaults and connect YouTube access.'}
          </div>
        </FormRow>
        <FormRow icon={Info} label="Publication status">
          <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">
            {!publicationEditorEnabled
              ? 'Publication settings are locked until the profile is saved.'
              : isPublicationPending
                ? 'Loading publication dependencies...'
                : publicationDirty
                  ? 'You have unsaved publication changes.'
                  : 'Publication defaults are up to date.'}
          </div>
        </FormRow>

        {!publicationEditorEnabled ? (
          <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 px-3 py-3 text-xs leading-5 text-amber-100">
            Publication settings are disabled while this profile is still an unsaved draft.
          </div>
        ) : null}

        <div className="h-px bg-white/10" />

        <FormRow icon={Radio} label="Visibility">
          <SettingsSelect
            disabled={!publicationEditorEnabled}
            placeholder="Select visibility"
            options={VISIBILITY_OPTIONS}
            value={publicationDraft.visibility}
            onChange={(value) =>
              setPublicationDraft((current) => ({
                ...current,
                visibility: value,
                publishDate: value === 'scheduled' ? '' : '',
              }))
            }
          />
        </FormRow>
        {isScheduledVisibility ? (
        <FormRow icon={CalendarDays} label="Publish at">
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-[140px] flex-1">
                <SettingsSelect
                  disabled={!publicationEditorEnabled}
                  placeholder="Select hour"
                  options={PUBLISH_HOUR_OPTIONS}
                  value={publicationDraft.publishHour}
                  onChange={(value) => setPublicationDraft((current) => ({ ...current, publishHour: value || '00' }))}
                />
              </div>
              <div className="min-w-[140px] flex-1">
                <SettingsSelect
                  disabled={!publicationEditorEnabled}
                  placeholder="Select minute"
                  options={PUBLISH_MINUTE_OPTIONS}
                  value={publicationDraft.publishMinute}
                  onChange={(value) => setPublicationDraft((current) => ({ ...current, publishMinute: value || '00' }))}
                />
              </div>
              <Button
                disabled={!publicationEditorEnabled}
                size="sm"
                type="button"
                variant="secondary"
                onClick={() =>
                  setPublicationDraft((current) => ({
                    ...current,
                    publishDate: '',
                    publishHour: '00',
                    publishMinute: '00',
                  }))
                }
              >
                Clear
              </Button>
            </div>
            <p className="text-xs leading-5 text-slate-400">{publishSummary}</p>
          </div>
        </FormRow>
        ) : null}
        <FormRow icon={UserRound} label="Audience">
          <InlineToggle
            className="h-10 px-3 text-sm"
            disabled={!publicationEditorEnabled}
            label="Made for kids"
            pressed={publicationDraft.madeForKids}
            onPressedChange={(pressed) => setPublicationDraft((current) => ({ ...current, madeForKids: pressed }))}
          />
        </FormRow>
        <FormRow icon={Sparkles} label="AI use">
          <SettingsSelect
            disabled={!publicationEditorEnabled}
            placeholder="Select AI use"
            options={YES_NO_OPTIONS}
            value={String(publicationDraft.aiUse)}
            onChange={(value) => setPublicationDraft((current) => ({ ...current, aiUse: value === 'true' }))}
          />
        </FormRow>
        <FormRow icon={List} label="Category">
          <SettingsSelect
            disabled={!publicationEditorEnabled}
            placeholder="Select a category"
            options={CATEGORY_OPTIONS}
            value={publicationDraft.category}
            onChange={(value) => setPublicationDraft((current) => ({ ...current, category: value }))}
          />
        </FormRow>
        <FormRow icon={List} label="Playlist">
          <SettingsSelect
            disabled={!publicationEditorEnabled || selectedYouTubeConnection?.status !== 'connected'}
            placeholder={
              selectedYouTubeConnection?.status === 'connected'
                ? publicationPlaylistsQuery.isFetching
                  ? 'Loading playlists...'
                  : 'No playlist'
                : 'Connect YouTube first'
            }
            options={publicationPlaylistOptions}
            value={publicationDraft.playlist}
            onChange={(value) => setPublicationDraft((current) => ({ ...current, playlist: value }))}
          />
        </FormRow>
        <FormRow icon={FileText} label="Channel description">
          <Textarea
            className="min-h-[120px]"
            disabled={!publicationEditorEnabled}
            value={publicationDraft.description}
            onChange={(event) => setPublicationDraft((current) => ({ ...current, description: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Hash} label="Keywords">
          <Input
            disabled={!publicationEditorEnabled}
            value={publicationDraft.keywords}
            onChange={(event) => setPublicationDraft((current) => ({ ...current, keywords: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Tag} label="Tags">
          <Input
            disabled={!publicationEditorEnabled}
            value={publicationDraft.tags}
            onChange={(event) => setPublicationDraft((current) => ({ ...current, tags: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={Type} label="Title template">
          <Input
            disabled={!publicationEditorEnabled}
            value={publicationDraft.titleTemplate}
            onChange={(event) => setPublicationDraft((current) => ({ ...current, titleTemplate: event.target.value }))}
          />
        </FormRow>
        <FormRow icon={FileText} label="Description template">
          <Textarea
            className="min-h-[120px]"
            disabled={!publicationEditorEnabled}
            value={publicationDraft.descriptionTemplate}
            onChange={(event) => setPublicationDraft((current) => ({ ...current, descriptionTemplate: event.target.value }))}
          />
        </FormRow>
        </Panel>
      </div>
    )
  }

  const renderSettingsTab = () => {
    const youtubeChunkOptions =
      YOUTUBE_CHUNK_SIZE_OPTIONS.some((option) => Number(option.value) === systemDraft.youtubeUploadChunkSizeMb)
        ? YOUTUBE_CHUNK_SIZE_OPTIONS
        : [
            ...YOUTUBE_CHUNK_SIZE_OPTIONS,
            {
              value: String(systemDraft.youtubeUploadChunkSizeMb),
              label: `Current (${systemDraft.youtubeUploadChunkSizeMb} MB)`,
            },
          ]

    return (
      <div className="grid gap-4">
        <Panel
          className="overflow-hidden"
          title="Web Portal"
          subtitle="Onboarding, account, and billing flows are handled on the web."
        >
          <div className="grid gap-3 md:grid-cols-3">
            <Button
              type="button"
              variant="primary"
              onClick={() => void desktopApi.files.openExternalUrl(getUserPortalUrl('/onboarding'))}
              title={getUserPortalUrl('/onboarding')}
            >
              Open Onboarding
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void desktopApi.files.openExternalUrl(getUserPortalUrl('/account'))}
              title={getUserPortalUrl('/account')}
            >
              Open Account
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void desktopApi.files.openExternalUrl(getUserPortalUrl('/billing'))}
              title={getUserPortalUrl('/billing')}
            >
              Open Billing
            </Button>
          </div>
        </Panel>

        <div className="grid items-stretch gap-4 xl:grid-cols-2">
        <Panel
          className="overflow-hidden"
          title="Video Paths"
          subtitle="Core local paths used by rendering, downloads, Suno output, and merges."
        >
          <PathSettingRow
            icon={Video}
            label="FFmpeg path"
            value={systemDraft.ffmpegPath}
            canBrowse
            canOpen={Boolean(systemDraft.ffmpegPath.trim())}
            onBrowse={() =>
              handleBrowseSystemPath('ffmpegPath', {
                title: 'Select FFmpeg executable',
                kind: 'file',
                filters: [
                  { name: 'Executable', extensions: ['exe', 'cmd', 'bat'] },
                  { name: 'All files', extensions: ['*'] },
                ],
              })
            }
            onOpen={() => handleOpenSystemPath('ffmpegPath', 'FFmpeg')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, ffmpegPath: value }))}
          />
          <PathSettingRow
            icon={Download}
            label="Downloads dir"
            value={systemDraft.downloadsDir}
            canBrowse
            canOpen={Boolean(systemDraft.downloadsDir.trim())}
            onBrowse={() => handleBrowseSystemPath('downloadsDir', { title: 'Select downloads folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('downloadsDir', 'Downloads')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, downloadsDir: value }))}
          />
          <PathSettingRow
            icon={Music4}
            label="Suno output dir"
            value={systemDraft.sunoOutputDir}
            canBrowse
            canOpen={Boolean(systemDraft.sunoOutputDir.trim())}
            onBrowse={() => handleBrowseSystemPath('sunoOutputDir', { title: 'Select Suno output folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('sunoOutputDir', 'Suno output')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, sunoOutputDir: value }))}
          />
          <PathSettingRow
            icon={Layers3}
            label="Merged dir"
            value={systemDraft.mergedDir}
            canBrowse
            canOpen={Boolean(systemDraft.mergedDir.trim())}
            onBrowse={() => handleBrowseSystemPath('mergedDir', { title: 'Select merged output folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('mergedDir', 'Merged')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, mergedDir: value }))}
          />
          <div className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2.5 text-sm text-slate-300">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-indigo-200" />
              <span>Keep these paths accessible to the app.</span>
            </div>
          </div>
        </Panel>

        <Panel
          className="overflow-hidden"
          title="Workers"
          subtitle="Worker and chunk settings used by generation, rendering, and uploads."
        >
          <div className="grid gap-2 md:grid-cols-2">
            <WorkerStepperCard
              icon={Music4}
              label="Music Workers"
              max={5}
              min={1}
              value={systemDraft.perfMusicWorkers}
              onChange={(value) => setSystemDraft((current) => ({ ...current, perfMusicWorkers: value }))}
            />
            <WorkerStepperCard
              icon={Image}
              label="Image Workers"
              max={8}
              min={1}
              value={systemDraft.perfImageWorkers}
              onChange={(value) => setSystemDraft((current) => ({ ...current, perfImageWorkers: value }))}
            />
            <WorkerStepperCard
              icon={Video}
              label="Export Workers"
              max={10}
              min={1}
              value={systemDraft.perfExportWorkers}
              onChange={(value) => setSystemDraft((current) => ({ ...current, perfExportWorkers: value }))}
            />
            <WorkerStepperCard
              icon={Layers3}
              label="Merge Workers"
              max={2}
              min={1}
              value={systemDraft.perfMergeWorkers}
              onChange={(value) => setSystemDraft((current) => ({ ...current, perfMergeWorkers: value }))}
            />
            <WorkerStepperCard
              icon={Video}
              label="YouTube Upload Workers"
              max={5}
              min={1}
              value={systemDraft.perfYouTubeWorkers}
              onChange={(value) => setSystemDraft((current) => ({ ...current, perfYouTubeWorkers: value }))}
            />
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]">
              <div className="flex min-w-0 items-center gap-2">
                <Link2 className="h-4 w-4 shrink-0 text-slate-300" />
                <p className="truncate text-sm font-medium leading-5 text-slate-100">YouTube chunk size (MB)</p>
              </div>
              <div className="mt-2">
                <SettingsSelect
                  placeholder="Select chunk size"
                  options={youtubeChunkOptions}
                  value={String(systemDraft.youtubeUploadChunkSizeMb)}
                  onChange={(value) =>
                    setSystemDraft((current) => ({
                      ...current,
                      youtubeUploadChunkSizeMb: clamp(Number(value || 256), 128, 512),
                    }))
                  }
                />
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2.5 text-sm text-slate-300">
            <div className="flex items-start gap-2">
              <Sparkles className="mt-0.5 h-4 w-4 text-violet-200" />
              <span>Keep worker counts aligned with your CPU, RAM, and expected workload.</span>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Image" subtitle="System-wide image folders and rendering defaults.">
          <PathSettingRow
            icon={Image}
            label="BG samples dir"
            value={systemDraft.imageBackgroundSamplesDir}
            canBrowse
            canOpen={Boolean(systemDraft.imageBackgroundSamplesDir.trim())}
            onBrowse={() => handleBrowseSystemPath('imageBackgroundSamplesDir', { title: 'Select background samples folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('imageBackgroundSamplesDir', 'Background samples')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, imageBackgroundSamplesDir: value }))}
          />
          <PathSettingRow
            icon={Image}
            label="Thumb samples dir"
            value={systemDraft.imageThumbnailSamplesDir}
            canBrowse
            canOpen={Boolean(systemDraft.imageThumbnailSamplesDir.trim())}
            onBrowse={() => handleBrowseSystemPath('imageThumbnailSamplesDir', { title: 'Select thumbnail samples folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('imageThumbnailSamplesDir', 'Thumbnail samples')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, imageThumbnailSamplesDir: value }))}
          />
          <PathSettingRow
            icon={Folder}
            label="Output dir (optional)"
            value={systemDraft.imageOutputDir}
            canBrowse
            canOpen={Boolean(systemDraft.imageOutputDir.trim())}
            onBrowse={() => handleBrowseSystemPath('imageOutputDir', { title: 'Select image output folder', kind: 'directory' })}
            onOpen={() => handleOpenSystemPath('imageOutputDir', 'Image output')}
            onChange={(value) => setSystemDraft((current) => ({ ...current, imageOutputDir: value }))}
          />
          <div className="flex justify-end">
            <Button size="sm" type="button" variant="secondary" onClick={() => { window.location.hash = '#/app/image' }}>
              Open Image workspace
            </Button>
          </div>
        </Panel>

        <Panel title="Rendering" subtitle="Image output resolution and style blending used by the desktop renderer.">
          <FormRow icon={Settings2} label="Output resolution">
            <SettingsSelect
              placeholder="Select an output resolution"
              options={[...OUTPUT_RESOLUTION_OPTIONS]}
              value={systemDraft.outputResolution}
              onChange={(value) => setSystemDraft((current) => ({ ...current, outputResolution: value }))}
            />
          </FormRow>
          <FormRow icon={Sparkles} label="Style strength">
            <div className="grid gap-2">
              <input
                className="h-2 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-fuchsia-500"
                max={100}
                min={0}
                step={10}
                type="range"
                value={systemDraft.styleStrength}
                onChange={(event) =>
                  setSystemDraft((current) => ({ ...current, styleStrength: clamp(Number(event.target.value), 0, 100) }))
                }
              />
              <p className="text-right text-xs text-slate-400">{systemDraft.styleStrength} / 100</p>
            </div>
          </FormRow>
          <FormRow icon={Image} label="Image source mode">
            <SettingsSelect
              placeholder="Select an image source mode"
              options={IMAGE_SOURCE_MODE_OPTIONS}
              value={systemDraft.imageSourceMode}
              onChange={(value) => setSystemDraft((current) => ({ ...current, imageSourceMode: value }))}
            />
          </FormRow>
          <FormRow icon={Image} label="Background source">
            <SettingsSelect
              placeholder="Select a background source"
              options={BACKGROUND_SOURCE_OPTIONS}
              value={systemDraft.backgroundSourceMode}
              onChange={(value) => setSystemDraft((current) => ({ ...current, backgroundSourceMode: value }))}
            />
          </FormRow>
          <FormRow icon={Layers3} label="Thumbnail overlay">
            <SettingsSelect
              placeholder="Select a thumbnail overlay mode"
              options={THUMBNAIL_OVERLAY_OPTIONS}
              value={systemDraft.thumbnailOverlayMode}
              onChange={(value) => setSystemDraft((current) => ({ ...current, thumbnailOverlayMode: value }))}
            />
          </FormRow>
          <div className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2.5 text-sm text-slate-300">
            {systemDraft.imageSourceMode === 'manual'
              ? 'Manual mode will later wait for user-provided BG/TH files in the batch folders instead of calling AI image generation.'
              : 'AI mode keeps the current background + thumbnail generation pipeline enabled.'}
          </div>
        </Panel>
      </div>

      <Panel
        title="Sample Pack Downloads"
        subtitle="Download background + thumbnail sample packs from Admin-managed links and extract them into your local sample library folders."
        actions={
          <Button
            disabled={imageSamplePacksQuery.isFetching}
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => void imageSamplePacksQuery.refetch()}
          >
            <RefreshCw className={cn('h-4 w-4', imageSamplePacksQuery.isFetching && 'animate-spin')} />
            Reload Packs
          </Button>
        }
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Background Packs</p>
                <p className="mt-1 text-xs text-slate-400">Installs into: {systemDraft.imageBackgroundSamplesDir.trim() || '—'}</p>
              </div>
              <span className="rounded-lg border border-white/10 bg-[#081028] px-2 py-1 text-[11px] text-slate-400">
                {backgroundSamplePacks.length} available
              </span>
            </div>
            <div className="mt-4">
              <SettingsSelect
                placeholder={imageSamplePacksQuery.isLoading ? 'Loading packs…' : 'Select a background pack'}
                options={backgroundPackOptions}
                value={selectedBackgroundPackId}
                disabled={imageSamplePacksQuery.isLoading || backgroundPackOptions.length === 0}
                onChange={(value) => setSelectedBackgroundPackId(value)}
              />
              {selectedBackgroundPack?.notes ? (
                <p className="mt-2 text-xs text-slate-400">{selectedBackgroundPack.notes}</p>
              ) : null}
              {imageSamplePacksQuery.isError ? (
                <p className="mt-2 text-xs text-rose-200">Unable to load sample pack list.</p>
              ) : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                disabled={
                  installSamplePackMutation.isPending ||
                  !selectedBackgroundPack ||
                  !systemDraft.imageBackgroundSamplesDir.trim()
                }
                size="sm"
                type="button"
                variant="secondary"
                onClick={() => {
                  if (!selectedBackgroundPack) return
                  void installSamplePackMutation.mutateAsync({
                    pack: selectedBackgroundPack,
                    destinationDir: systemDraft.imageBackgroundSamplesDir.trim(),
                  })
                }}
              >
                <Download className="h-4 w-4" />
                Install
              </Button>
              <Button
                disabled={!selectedBackgroundPack}
                size="sm"
                type="button"
                variant="secondary"
                onClick={() => {
                  if (selectedBackgroundPack) {
                    void desktopApi.files.openExternalUrl(selectedBackgroundPack.source_value)
                  }
                }}
              >
                <ArrowUpRight className="h-4 w-4" />
                Open Link
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Thumbnail Packs</p>
                <p className="mt-1 text-xs text-slate-400">Installs into: {systemDraft.imageThumbnailSamplesDir.trim() || '—'}</p>
              </div>
              <span className="rounded-lg border border-white/10 bg-[#081028] px-2 py-1 text-[11px] text-slate-400">
                {thumbnailSamplePacks.length} available
              </span>
            </div>
            <div className="mt-4">
              <SettingsSelect
                placeholder={imageSamplePacksQuery.isLoading ? 'Loading packs…' : 'Select a thumbnail pack'}
                options={thumbnailPackOptions}
                value={selectedThumbnailPackId}
                disabled={imageSamplePacksQuery.isLoading || thumbnailPackOptions.length === 0}
                onChange={(value) => setSelectedThumbnailPackId(value)}
              />
              {selectedThumbnailPack?.notes ? (
                <p className="mt-2 text-xs text-slate-400">{selectedThumbnailPack.notes}</p>
              ) : null}
              {imageSamplePacksQuery.isError ? (
                <p className="mt-2 text-xs text-rose-200">Unable to load sample pack list.</p>
              ) : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                disabled={
                  installSamplePackMutation.isPending ||
                  !selectedThumbnailPack ||
                  !systemDraft.imageThumbnailSamplesDir.trim()
                }
                size="sm"
                type="button"
                variant="secondary"
                onClick={() => {
                  if (!selectedThumbnailPack) return
                  void installSamplePackMutation.mutateAsync({
                    pack: selectedThumbnailPack,
                    destinationDir: systemDraft.imageThumbnailSamplesDir.trim(),
                  })
                }}
              >
                <Download className="h-4 w-4" />
                Install
              </Button>
              <Button
                disabled={!selectedThumbnailPack}
                size="sm"
                type="button"
                variant="secondary"
                onClick={() => {
                  if (selectedThumbnailPack) {
                    void desktopApi.files.openExternalUrl(selectedThumbnailPack.source_value)
                  }
                }}
              >
                <ArrowUpRight className="h-4 w-4" />
                Open Link
              </Button>
            </div>
          </div>
        </div>
      </Panel>

      <Panel
        title="Sample Library Manager"
        subtitle="Curate which background and thumbnail samples stay available for manual or random image generation."
        actions={
          <Button size="sm" type="button" variant="secondary" onClick={() => void refreshSampleLibrary()}>
            <RefreshCw className="h-4 w-4" />
            Refresh Samples
          </Button>
        }
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Background Samples</p>
                <p className="mt-1 text-xs text-slate-400">
                  Click to curate up to 5 allowed images. Hover previews, click pins and selects.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={cn(
                    'h-8 rounded-lg border px-3 text-xs font-medium transition',
                    systemDraft.imageBgRandom
                      ? 'border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100'
                      : 'border-white/10 bg-white/5 text-slate-200 hover:border-white/20',
                  )}
                  onClick={() => setSystemDraft((current) => ({ ...current, imageBgRandom: !current.imageBgRandom }))}
                >
                  Random {systemDraft.imageBgRandom ? 'On' : 'Off'}
                </button>
                <span className="rounded-lg border border-white/10 bg-[#081028] px-2 py-1 text-[11px] text-slate-400">
                  Selected {systemDraft.imageBgSamples.length}/5
                </span>
              </div>
            </div>
            <div className="mt-4 max-h-72 space-y-1 overflow-auto pr-2">
              {backgroundSampleFiles.length ? (
                backgroundSampleFiles.map((path) => {
                  const isSelected = systemDraft.imageBgSamples.includes(path)
                  return (
                    <button
                      key={path}
                      type="button"
                      className={cn(
                        'flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-xs transition',
                        isSelected
                          ? 'border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100'
                          : 'border-white/10 bg-slate-950/50 text-slate-200 hover:border-white/20 hover:bg-white/5',
                      )}
                      onMouseEnter={() => void updateSamplePreview(path)}
                      onClick={() => toggleLibrarySample('bg', path)}
                    >
                      <span className="truncate">{path.split(/[\\/]/).pop()}</span>
                      <span className="text-[10px] text-slate-400">{isSelected ? 'Selected' : 'Available'}</span>
                    </button>
                  )
                })
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 bg-slate-950/40 px-4 py-8 text-center text-xs text-slate-500">
                  No background sample images found.
                </div>
              )}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Random on uses the selected subset first, then falls back to the full folder when nothing is selected.
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Thumbnail Samples</p>
                <p className="mt-1 text-xs text-slate-400">
                  Curate thumbnail styles separately so unselected images stay available only for random fallback.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={cn(
                    'h-8 rounded-lg border px-3 text-xs font-medium transition',
                    systemDraft.imageThumbRandom
                      ? 'border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100'
                      : 'border-white/10 bg-white/5 text-slate-200 hover:border-white/20',
                  )}
                  onClick={() => setSystemDraft((current) => ({ ...current, imageThumbRandom: !current.imageThumbRandom }))}
                >
                  Random {systemDraft.imageThumbRandom ? 'On' : 'Off'}
                </button>
                <span className="rounded-lg border border-white/10 bg-[#081028] px-2 py-1 text-[11px] text-slate-400">
                  Selected {systemDraft.imageThumbSamples.length}/5
                </span>
              </div>
            </div>
            <div className="mt-4 max-h-72 space-y-1 overflow-auto pr-2">
              {thumbnailSampleFiles.length ? (
                thumbnailSampleFiles.map((path) => {
                  const isSelected = systemDraft.imageThumbSamples.includes(path)
                  return (
                    <button
                      key={path}
                      type="button"
                      className={cn(
                        'flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-xs transition',
                        isSelected
                          ? 'border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100'
                          : 'border-white/10 bg-slate-950/50 text-slate-200 hover:border-white/20 hover:bg-white/5',
                      )}
                      onMouseEnter={() => void updateSamplePreview(path)}
                      onClick={() => toggleLibrarySample('th', path)}
                    >
                      <span className="truncate">{path.split(/[\\/]/).pop()}</span>
                      <span className="text-[10px] text-slate-400">{isSelected ? 'Selected' : 'Available'}</span>
                    </button>
                  )
                })
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 bg-slate-950/40 px-4 py-8 text-center text-xs text-slate-500">
                  No thumbnail sample images found.
                </div>
              )}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Clicked images stay pinned in the preview below so you can compare curation choices more easily.
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Sample Preview</p>
              <p className="mt-1 text-xs text-slate-400">
                Hover any sample for a quick look. Click a sample to keep it selected and pinned.
              </p>
            </div>
            {samplePreviewPath ? (
              <Button size="sm" type="button" variant="secondary" onClick={() => void desktopApi.files.openPath(samplePreviewPath)}>
                <ArrowUpRight className="h-4 w-4" />
                Open File
              </Button>
            ) : null}
          </div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-[#081028]">
            {samplePreviewDataUrl ? (
              <img alt="Sample preview" className="aspect-[16/7] w-full object-cover" src={samplePreviewDataUrl} />
            ) : (
              <div className="flex aspect-[16/7] items-center justify-center text-sm text-slate-500">
                Hover or click a sample to preview it here.
              </div>
            )}
          </div>
          {samplePreviewPath ? <p className="mt-3 truncate text-xs text-slate-500">{samplePreviewPath}</p> : null}
        </div>
      </Panel>
      </div>
    )
  }

  const renderTextLibraryTab = (kind: 'descriptions' | 'structures') => {
    const isDescriptions = kind === 'descriptions'
    const items = isDescriptions ? descriptionOptions : structureOptions
    const selectedItem = isDescriptions ? selectedDescription : selectedStructure

    return (
      <div className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <Panel
            title={isDescriptions ? 'Music Description Names' : 'Music Structure Names'}
            subtitle={
              isDescriptions
                ? 'Camxora-owned names are visible here; full prompt content stays on the server.'
                : 'Camxora-owned names are visible here; full structure content stays on the server.'
            }
          >
            <MiniStat label="Available names" value={String(items.length)} />
            <PromptNameList
              emptyMessage={isDescriptions ? 'No music description names are available yet.' : 'No music structure names are available yet.'}
              items={items}
              selectedId={isDescriptions ? selectedDescriptionId : selectedStructureId}
              onSelect={(id) => {
                if (isDescriptions) {
                  setSelectedDescriptionId(id)
                } else {
                  setSelectedStructureId(id)
                }
              }}
            />
          </Panel>

          <Panel
            title={isDescriptions ? 'Selected Music Description' : 'Selected Music Structure'}
            subtitle={
              selectedItem?.is_owned
                ? 'This is one of your own prompts. Edit it in the My Library section below.'
                : isDescriptions
                  ? 'Choose which description name should be used. Camxora content stays hidden.'
                  : 'Choose which structure name should be used. Camxora content stays hidden.'
            }
          >
            <FormRow icon={isDescriptions ? FileText : Layers3} label="Available names">
              <SettingsSelect
                placeholder="Select a name"
                options={items.map((item) => ({
                  value: item.id,
                  label: item.is_owned ? `${item.name} (mine)` : item.name,
                }))}
                value={selectedItem?.id ?? ''}
                onChange={(value) => {
                  if (isDescriptions) {
                    setSelectedDescriptionId(value)
                  } else {
                    setSelectedStructureId(value)
                  }
                }}
              />
            </FormRow>
            {isDescriptions ? (
              <FormRow icon={Layers3} label="Available structures">
                <SettingsSelect
                  placeholder="Select a structure"
                  options={structureOptions.map((item) => ({
                    value: item.id,
                    label: item.is_owned ? `${item.name} (mine)` : item.name,
                  }))}
                  value={selectedStructure?.id ?? ''}
                  onChange={setSelectedStructureId}
                />
              </FormRow>
            ) : null}
            <FormRow icon={Type} label="Selected name">
              <Input disabled value={selectedItem?.name ?? ''} />
            </FormRow>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-4 text-sm text-slate-400">
              {selectedItem
                ? selectedItem.is_owned
                  ? `Using your custom prompt "${selectedItem.name}".`
                  : `Using Camxora prompt "${selectedItem.name}". Content is resolved on the server during generation.`
                : `Select a ${isDescriptions ? 'music description' : 'music structure'} name to continue.`}
            </div>
          </Panel>
        </div>
        <UserOwnedPromptPanel kind={kind} />
      </div>
    )
  }

  const renderPoolsTab = () => (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MiniStat
          label="Openings"
          value={
            contentPoolStatsQuery.isLoading
              ? 'Loading...'
              : contentPoolStatsQuery.data
                ? `${Math.max(0, contentPoolStatsQuery.data.openings.total - contentPoolStatsQuery.data.openings.unused)} used / ${contentPoolStatsQuery.data.openings.total}`
                : 'Unavailable'
          }
        />
        <MiniStat
          label="Titles"
          value={
            contentPoolStatsQuery.isLoading
              ? 'Loading...'
              : contentPoolStatsQuery.data
                ? `${Math.max(0, contentPoolStatsQuery.data.titles.total - contentPoolStatsQuery.data.titles.unused)} used / ${contentPoolStatsQuery.data.titles.total}`
                : 'Unavailable'
          }
        />
        <MiniStat
          label="Albums"
          value={
            contentPoolStatsQuery.isLoading
              ? 'Loading...'
              : contentPoolStatsQuery.data
                ? `${Math.max(0, contentPoolStatsQuery.data.albums.total - contentPoolStatsQuery.data.albums.unused)} used / ${contentPoolStatsQuery.data.albums.total}`
                : 'Unavailable'
          }
        />
        <MiniStat label="Ownership" value="Admin Portal" />
      </div>

      <Panel
        title="Content Pools"
        subtitle="Read-only pool visibility for users. Editing, generating, importing, and clearing stay in the Admin Portal."
      >
        <div className="grid items-start gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="grid gap-3">
            <div className="grid grid-cols-3 gap-2">
              {(['openings', 'titles', 'albums'] as const).map((kind) => (
                <button
                  className={cn(
                    'rounded-xl border px-3 py-2 text-sm transition',
                    poolTab === kind
                      ? 'border-fuchsia-500/60 bg-fuchsia-500/15 text-white'
                      : 'border-white/10 bg-slate-950/60 text-slate-300 hover:border-white/20',
                  )}
                  key={kind}
                  type="button"
                  onClick={() => setPoolTab(kind)}
                >
                  {kind[0].toUpperCase()}
                  {kind.slice(1)}
                </button>
              ))}
            </div>
            <PlaceholderTable
              bodyClassName="max-h-[22.5rem] overflow-y-auto"
              emptyMessage={
                contentPoolListQuery.isLoading
                  ? `Loading ${poolTab}...`
                  : `No ${poolTab} data is available right now.`
              }
              headers={['ID', poolTab === 'openings' ? 'Opening' : 'Name', 'Used', 'Created']}
              rows={contentPoolRows}
            />
            <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2">
              <div className="text-sm text-slate-300">
                Page {Math.floor(poolOffset / CONTENT_POOL_PAGE_SIZE) + 1}
                {contentPoolListQuery.data
                  ? ` / ${Math.max(1, Math.ceil(contentPoolListQuery.data.total / CONTENT_POOL_PAGE_SIZE))}`
                  : ''}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  disabled={poolOffset === 0 || contentPoolListQuery.isFetching}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() => setPoolOffset((current) => Math.max(0, current - CONTENT_POOL_PAGE_SIZE))}
                >
                  Prev
                </Button>
                <Button
                  disabled={
                    contentPoolListQuery.isFetching ||
                    !contentPoolListQuery.data ||
                    poolOffset + CONTENT_POOL_PAGE_SIZE >= contentPoolListQuery.data.total
                  }
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() => setPoolOffset((current) => current + CONTENT_POOL_PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
          <div className="grid content-start gap-3 self-start">
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
              <p className="text-sm font-medium text-white">Current pool</p>
              <p className="mt-1 text-sm text-slate-300">
                {selectedPoolStat
                  ? `${selectedPoolStat.total} total entries, ${Math.max(0, selectedPoolStat.total - selectedPoolStat.unused)} used, ${selectedPoolStat.unused} unused.`
                  : 'Pool counts are unavailable right now.'}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
              <p className="text-sm font-medium text-white">AI preset mixing</p>
              <p className="mt-1 text-sm leading-6 text-slate-300">
                Admin-generated preset packs can be mixed to create candidates, but uniqueness still has to be enforced centrally in the backend.
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
              <p className="text-sm font-medium text-white">Editing scope</p>
              <p className="mt-1 text-sm leading-6 text-slate-300">
                Users can review pool contents and see how many times entries have been used. All editing stays in the Admin Portal.
              </p>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  )

  const renderSunoTab = () => (
    <div className="grid gap-4">
      <Panel
        title="Suno"
        subtitle="Manage Suno runtime defaults for timeout, retries, version, and merge behavior."
        actions={
          <Button
            disabled={!sunoDirty || saveSunoSettingsMutation.isPending}
            size="sm"
            type="button"
            onClick={async () => {
              await saveSunoSettingsMutation.mutateAsync()
            }}
          >
            <Save className="h-4 w-4" />
            {saveSunoSettingsMutation.isPending ? 'Saving...' : 'Save Suno'}
          </Button>
        }
      >
        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="grid gap-3">
            <FormRow icon={Music4} label="Default Suno version">
              <SettingsSelect
                placeholder="Select a Suno version"
                options={SUNO_VERSION_OPTIONS.map((option) => ({ value: option, label: option }))}
                value={sunoDraft.sunoDefaultVersion}
                onChange={(value) => setSunoDraft((current) => ({ ...current, sunoDefaultVersion: value }))}
              />
            </FormRow>
            <FormRow icon={Layers3} label="Auto merge downloads">
              <SettingsSelect
                placeholder="Select merge behavior"
                options={SUNO_MERGE_OPTIONS}
                value={sunoDraft.sunoMergeEnabled ? 'on' : 'off'}
                onChange={(value) => setSunoDraft((current) => ({ ...current, sunoMergeEnabled: value === 'on' }))}
              />
            </FormRow>
            <FormRow icon={Layers3} label="Merge group size">
              <Input
                min={0}
                type="number"
                value={sunoDraft.sunoMergeGroupSize}
                onChange={(event) =>
                  setSunoDraft((current) => ({ ...current, sunoMergeGroupSize: Math.max(0, Number(event.target.value) || 0) }))
                }
              />
            </FormRow>
          </div>

          <div className="grid gap-3">
            <FormRow icon={Sparkles} label="Timeout (ms)">
              <Input
                min={1000}
                step={1000}
                type="number"
                value={sunoDraft.sunoTimeoutMs}
                onChange={(event) =>
                  setSunoDraft((current) => ({ ...current, sunoTimeoutMs: Math.max(1000, Number(event.target.value) || 1000) }))
                }
              />
            </FormRow>
            <FormRow icon={RefreshCcw} label="Retry count">
              <Input
                min={0}
                type="number"
                value={sunoDraft.sunoRetryCount}
                onChange={(event) =>
                  setSunoDraft((current) => ({ ...current, sunoRetryCount: Math.max(0, Number(event.target.value) || 0) }))
                }
              />
            </FormRow>
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
          Only the supported Suno defaults are shown here.
        </div>
      </Panel>
    </div>
  )

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'profiles':
        return renderProfilesTab()
      case 'publication':
        return renderPublicationTab()
      case 'settings':
        return renderSettingsTab()
      case 'descriptions':
        return renderTextLibraryTab('descriptions')
      case 'structures':
        return renderTextLibraryTab('structures')
      case 'pools':
        return renderPoolsTab()
      case 'suno':
        return renderSunoTab()
      case 'youtube':
      default:
        return renderYouTubeTab()
    }
  }

  return (
    <>
      <div className="grid gap-4">
        <Card className="border-white/10 bg-[#081028] p-3">
          <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${TAB_META.length}, minmax(0, 1fr))` }}>
            {TAB_META.map((tab) => (
              <TabButton active={tab.id === activeTab} icon={tab.icon} key={tab.id} label={tab.label} onClick={() => setActiveTab(tab.id)} />
            ))}
          </div>
        </Card>

        {isError ? (
          <Card className="border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-200">
            Unable to load the settings workspace right now.
          </Card>
        ) : null}

        {!isError ? (
          <>
            {isLoading ? (
              <Card className="border-white/10 bg-[#081028] p-6 text-sm text-slate-400">Loading settings workspace...</Card>
            ) : (
              renderActiveTab()
            )}
          </>
        ) : null}

        {!isLoading && !isError ? (
          <Card className="sticky bottom-4 border-white/10 bg-slate-950/95 p-3 backdrop-blur">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Status</p>
                <p
                  className={cn(
                    'mt-1 text-sm',
                    notice?.tone === 'error'
                      ? 'text-rose-200'
                      : dirtyTabs.length
                        ? 'text-amber-200'
                        : 'text-slate-300',
                  )}
                >
                  {isYouTubePending
                    ? 'Updating YouTube connection...'
                    : isSavePending
                    ? 'Saving supported Settings changes...'
                    : notice?.message ??
                      (dirtyTabs.length
                        ? `Unsaved changes in ${dirtyTabs.join(', ')}.`
                        : isFetching
                          ? 'Syncing latest Settings data...'
                          : 'All supported Settings changes are saved.')}
                </p>
                {selectedProfileKey === 'new' && publicationDraft.titleTemplate.trim() ? (
                  <p className="mt-1 text-xs text-slate-400">
                    Publication defaults are saved after the new profile has been created.
                  </p>
                ) : null}
              </div>
              <Button disabled={!dirtyTabs.length || isSavePending || isYouTubePending} type="button" onClick={() => void handleSaveAll()}>
                <Save className="h-4 w-4" />
                {isSavePending ? 'Saving...' : 'Save All Changes'}
              </Button>
            </div>
          </Card>
        ) : null}
      </div>

      <ConfirmDialog
        cancelLabel="Keep It"
        confirmLabel={
          pendingConfirmation?.type === 'delete-profile'
            ? deleteProfileMutation.isPending
              ? 'Deleting...'
              : 'Delete Profile'
            : disconnectYouTubeMutation.isPending
              ? 'Disconnecting...'
              : 'Disconnect Channel'
        }
        description={
          pendingConfirmation?.type === 'delete-profile'
            ? `This removes "${pendingConfirmation.profileName}" from your account. Existing generated outputs stay on disk, but this profile record will be deleted.`
            : pendingConfirmation?.type === 'disconnect-youtube'
              ? `Disconnect the YouTube channel flow for "${pendingConfirmation?.profileName}"? You can reconnect again anytime.`
              : undefined
        }
        onCancel={() => setPendingConfirmation(null)}
        onConfirm={async () => {
          if (!pendingConfirmation) {
            return
          }
          if (pendingConfirmation.type === 'delete-profile') {
            await deleteProfileMutation.mutateAsync({ profileId: pendingConfirmation.profileId })
            return
          }
          await disconnectYouTubeMutation.mutateAsync({ profileId: pendingConfirmation.profileId })
        }}
        open={Boolean(pendingConfirmation)}
        pending={deleteProfileMutation.isPending || disconnectYouTubeMutation.isPending}
        title={
          pendingConfirmation?.type === 'delete-profile'
            ? `Delete "${pendingConfirmation.profileName}"?`
            : pendingConfirmation?.type === 'disconnect-youtube'
              ? `Disconnect YouTube for "${pendingConfirmation.profileName}"?`
              : 'Confirm action'
        }
        tone="danger"
      />
    </>
  )
}
