import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Check, Copy, FolderOpen, History, Loader2, Music4, Sparkles, Wand2 } from 'lucide-react'

import { GeneratingTitleLabel } from '@/features/music/GeneratingTitleLabel'
import { isSongTitleGenerating } from '@/features/music/musicHistoryLabels'
import { useMusicWorkspaceQuery } from '@/features/music/useMusicWorkspaceQuery'
import { getDesktopApi } from '@/shared/api/desktop'
import { PlatformApiError } from '@/shared/api/platformClient'
import { formatCredits } from '@/shared/lib/formatCredits'
import {
  apiClaimContentPoolItem,
  apiCreateBatch,
  apiFinalizeContentPoolItem,
  apiGenerateDraft,
  apiPatchSettings,
  apiPolishLyrics,
  apiReleaseContentPoolItem,
  type BatchCreateRequest,
  type ClaimedContentPoolItem,
  type DraftGenerationRequest,
  type MusicHistoryBatchResponse,
  type MusicHistorySongResponse,
  type OperationCostResponse,
  type PromptNameOption,
  type ProfileResponse,
} from '@/shared/api/platformEndpoints'
import { cn } from '@/shared/lib/utils'
import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { DatePickerField } from '@/shared/ui/date-picker-field'
import { Input } from '@/shared/ui/input'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import { Textarea } from '@/shared/ui/textarea'

type MusicSettingsState = {
  language: string
  creativity: number
  uniqueOpening: boolean
  strictLevel: number
  historyWindow: number
  songCount: number
  autoGenImage: boolean
  autoGSuno: boolean
  autoVideoAfterSuno: boolean
  autoMergeAfterVideo: boolean
  autoReelAfterVideo: boolean
  autoUploadYouTube: boolean
  polishStrength: number
}

type ComposerState = {
  fromDate: string
  toDate: string
  primaryProfileIds: string[]
  secondaryProfileIds: string[]
  description: string
  structure: string
  title: string
  album: string
  lyrics: string
}

type DraftPoolSeedState = {
  titleSeed: string
  albumSeed: string
  openingSeed: string | null
}

type HistoryFiltersState = {
  fromDate: string
  toDate: string
  lastBatchOnly: boolean
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

type HistoryRow = {
  rowNumber: number
  batch: MusicHistoryBatchResponse
  song: MusicHistorySongResponse
}

const LANGUAGE_OPTIONS = [
  { label: 'English', value: 'en' },
  { label: 'Khmer', value: 'km' },
  { label: 'German', value: 'de' },
  { label: 'Spanish', value: 'es' },
  { label: 'French', value: 'fr' },
] as const

const EMPTY_PROFILES: ProfileResponse[] = []
const EMPTY_PROMPTS: PromptNameOption[] = []
const EMPTY_HISTORY_BATCHES: NonNullable<ReturnType<typeof useMusicWorkspaceQuery>['data']>['history']['batches'] = []

function getTodayInputValue(): string {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function blankComposerState(): ComposerState {
  const today = getTodayInputValue()

  return {
    fromDate: today,
    toDate: today,
    primaryProfileIds: [],
    secondaryProfileIds: [],
    description: '',
    structure: '',
    title: '',
    album: '',
    lyrics: '',
  }
}

function blankMusicSettingsState(): MusicSettingsState {
  return {
    language: 'en',
    creativity: 55,
    uniqueOpening: false,
    strictLevel: 3,
    historyWindow: 100,
    songCount: 4,
    autoGenImage: false,
    autoGSuno: false,
    autoVideoAfterSuno: false,
    autoMergeAfterVideo: false,
    autoReelAfterVideo: false,
    autoUploadYouTube: false,
    polishStrength: 60,
  }
}

function getInclusiveDaySpan(fromDate: string, toDate: string): number | null {
  if (!fromDate || !toDate) {
    return null
  }

  const start = new Date(`${fromDate}T00:00:00`)
  const end = new Date(`${toDate}T00:00:00`)

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return null
  }

  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1
}

function getInclusiveDateList(fromDate: string, toDate: string): string[] {
  const daySpan = getInclusiveDaySpan(fromDate, toDate)
  if (daySpan === null) {
    return []
  }

  const start = new Date(`${fromDate}T00:00:00`)
  const results: string[] = []

  for (let index = 0; index < daySpan; index += 1) {
    const current = new Date(start.getTime() + index * 86_400_000)
    const year = current.getFullYear()
    const month = String(current.getMonth() + 1).padStart(2, '0')
    const day = String(current.getDate()).padStart(2, '0')
    results.push(`${year}-${month}-${day}`)
  }

  return results
}

function formatDateTimeLabel(value: string | null | undefined): string {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function getStatusChipClass(status: string): string {
  const normalized = status.toLowerCase()

  if (normalized.includes('success') || normalized.includes('done') || normalized.includes('completed')) {
    return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200'
  }
  if (normalized.includes('fail') || normalized.includes('error')) {
    return 'border-rose-400/25 bg-rose-500/10 text-rose-200'
  }
  if (normalized.includes('process') || normalized.includes('pending') || normalized.includes('upload')) {
    return 'border-amber-400/25 bg-amber-500/10 text-amber-200'
  }

  return 'border-white/10 bg-white/5 text-slate-200'
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function effectPreviewFromCreativity(creativity: number): { valence: number; danceability: number; instrumentalness: number } {
  const value = clamp(creativity, 0, 100)

  return {
    valence: clamp(Math.round(20 + value * 0.7), 5, 95),
    danceability: clamp(Math.round(15 + value * 0.75), 5, 95),
    instrumentalness: clamp(Math.round(10 + value * 0.55), 5, 95),
  }
}

function readBooleanSetting(settings: Record<string, unknown> | undefined, key: string, fallback: boolean): boolean {
  const value = settings?.[key]

  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'true') {
      return true
    }
    if (normalized === 'false') {
      return false
    }
  }

  return fallback
}

function readNumberSetting(settings: Record<string, unknown> | undefined, key: string, fallback: number): number {
  const value = settings?.[key]

  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  return fallback
}

function readStringSetting(settings: Record<string, unknown> | undefined, key: string, fallback = ''): string {
  const value = settings?.[key]
  return typeof value === 'string' ? value.trim() || fallback : fallback
}

function normalizeLanguageSetting(value: unknown): string {
  if (typeof value !== 'string') {
    return 'en'
  }

  const normalized = value.trim().toLowerCase()
  const matchedOption = LANGUAGE_OPTIONS.find((option) => option.value === normalized || option.label.toLowerCase() === normalized)
  return matchedOption?.value ?? 'en'
}

function buildMusicSettingsState(settings: Record<string, unknown> | undefined): MusicSettingsState {
  const defaults = blankMusicSettingsState()

  return {
    language: normalizeLanguageSetting(settings?.language),
    creativity: clamp(readNumberSetting(settings, 'creativity', defaults.creativity), 0, 100),
    uniqueOpening: readBooleanSetting(settings, 'uniqueOpening', defaults.uniqueOpening),
    strictLevel: clamp(readNumberSetting(settings, 'strictLevel', defaults.strictLevel), 1, 5),
    historyWindow: clamp(readNumberSetting(settings, 'uniquenessHistoryWindow', defaults.historyWindow), 50, 1500),
    songCount: clamp(readNumberSetting(settings, 'defaultSongCount', defaults.songCount), 1, 50),
    autoGenImage: readBooleanSetting(settings, 'autoGenImage', defaults.autoGenImage),
    autoGSuno: readBooleanSetting(settings, 'autoGSuno', defaults.autoGSuno),
    autoVideoAfterSuno: readBooleanSetting(settings, 'autoVideoAfterSuno', defaults.autoVideoAfterSuno),
    autoMergeAfterVideo: readBooleanSetting(settings, 'autoMergeAfterVideo', defaults.autoMergeAfterVideo),
    autoReelAfterVideo: readBooleanSetting(settings, 'autoReelAfterVideo', defaults.autoReelAfterVideo),
    autoUploadYouTube: readBooleanSetting(settings, 'autoUploadYouTube', defaults.autoUploadYouTube),
    polishStrength: clamp(readNumberSetting(settings, 'lyricsPolishStrength', defaults.polishStrength), 0, 100),
  }
}

function buildMusicSettingsPatch(settings: MusicSettingsState): Record<string, unknown> {
  return {
    language: settings.language,
    creativity: settings.creativity,
    uniqueOpening: settings.uniqueOpening,
    strictLevel: settings.strictLevel,
    uniquenessHistoryWindow: settings.historyWindow,
    defaultSongCount: settings.songCount,
    autoGenImage: settings.autoGenImage,
    autoGSuno: settings.autoGSuno,
    autoVideoAfterSuno: settings.autoVideoAfterSuno,
    autoMergeAfterVideo: settings.autoMergeAfterVideo,
    autoReelAfterVideo: settings.autoReelAfterVideo,
    autoUploadYouTube: settings.autoUploadYouTube,
    lyricsPolishStrength: settings.polishStrength,
  }
}

function normalizeHistoryBoundary(batch: MusicHistoryBatchResponse, side: 'from' | 'to'): string {
  if (side === 'from') {
    return batch.from_date ?? batch.created_at.slice(0, 10)
  }

  return batch.to_date ?? batch.updated_at.slice(0, 10)
}

function matchesHistoryFilters(batch: MusicHistoryBatchResponse, filters: HistoryFiltersState, batchIndex: number): boolean {
  if (filters.lastBatchOnly && batchIndex > 0) {
    return false
  }

  const batchFrom = normalizeHistoryBoundary(batch, 'from')
  const batchTo = normalizeHistoryBoundary(batch, 'to')

  if (filters.fromDate && batchTo < filters.fromDate) {
    return false
  }
  if (filters.toDate && batchFrom > filters.toDate) {
    return false
  }

  return true
}

function saveStatusMessage(status: SaveStatus): string {
  if (status === 'saving') {
    return 'Saving music defaults...'
  }
  if (status === 'saved') {
    return 'Music defaults saved.'
  }
  if (status === 'error') {
    return 'Unable to save music defaults.'
  }

  return 'Music defaults are ready.'
}

function toggleSelectedProfileIds(currentIds: string[], profileId: string): string[] {
  if (!profileId) {
    return currentIds
  }

  return currentIds.includes(profileId) ? currentIds.filter((item) => item !== profileId) : [...currentIds, profileId]
}

function sanitizeSelectedProfileIds(
  selectedIds: string[],
  profiles: ProfileResponse[],
  fallbackIds: string[],
): string[] {
  const validIds = new Set(profiles.map((profile) => profile.id))
  const deduped = selectedIds.filter((id, index) => validIds.has(id) && selectedIds.indexOf(id) === index)

  if (deduped.length) {
    return deduped
  }

  return fallbackIds.filter((id, index) => id && validIds.has(id) && fallbackIds.indexOf(id) === index)
}

function extractLyricsOpening(lyrics: string | null | undefined): string | null {
  if (!lyrics) {
    return null
  }

  const line = lyrics
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find((item) => item && !item.startsWith('['))

  return line || null
}

function buildHistoryAvoidLists(
  historyBatches: MusicHistoryBatchResponse[],
  historyWindow: number,
): { titles: string[]; albums: string[]; openings: string[] } {
  const titles = new Set<string>()
  const albums = new Set<string>()
  const openings = new Set<string>()
  const batchLimit = Math.max(1, Math.ceil(historyWindow / 10))

  historyBatches.slice(0, batchLimit).forEach((batch) => {
    batch.songs.forEach((song) => {
      const title = song.title?.trim()
      const album = song.album?.trim()
      const opening = extractLyricsOpening(song.lyrics)

      if (title) {
        titles.add(title)
      }
      if (album) {
        albums.add(album)
      }
      if (opening) {
        openings.add(opening)
      }
    })
  })

  return {
    titles: Array.from(titles).slice(0, 200),
    albums: Array.from(albums).slice(0, 200),
    openings: Array.from(openings).slice(0, 200),
  }
}

function buildDraftDescription(baseDescription: string, poolSeeds: DraftPoolSeedState): string {
  const inspiration = [poolSeeds.titleSeed, poolSeeds.albumSeed].filter(Boolean).join(' / ')

  if (!inspiration) {
    return baseDescription
  }

  return `${baseDescription}\n\nInspiration (do not copy words): ${inspiration}`.trim()
}

function buildReservationToken(): string {
  return globalThis.crypto?.randomUUID?.() ?? `pool-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function mapOperationCosts(items: OperationCostResponse[] | undefined): Record<string, OperationCostResponse> {
  return Object.fromEntries((items ?? []).map((item) => [item.operation_type, item]))
}

function formatOperationCostLabel(item: OperationCostResponse | undefined, fallback: string): string {
  if (!item?.available || item.credits_per_operation == null) {
    return `${fallback}: unavailable`
  }

  return `${fallback}: ${formatCredits(item.credits_per_operation)} credits`
}

function formatButtonCreditLabel(label: string, credits: number | null, unavailableLabel = 'Unavailable'): string {
  if (credits == null) {
    return `${label} (${unavailableLabel})`
  }
  return `${label} (${formatCredits(credits)} Credits)`
}

type MusicPlanCostBreakdown = {
  plannedDayCount: number
  pairCount: number
  plannedBatchCount: number
  songsPerBatch: number
  plannedSongCount: number
  draftUnitCost: number | null
  draftTotalCost: number | null
  sunoUnitCost: number | null
  sunoTotalCost: number | null
  imageUnitCost: number | null
  imageJobsPerSong: number
  imageTotalCost: number | null
  totalCost: number | null
}

function getOperationUnitCost(item: OperationCostResponse | undefined): number | null {
  if (!item?.available || item.credits_per_operation == null) {
    return null
  }
  return item.credits_per_operation
}

function getBatchGenerateTotalCost(
  lyricCost: OperationCostResponse | undefined,
  musicCost: OperationCostResponse | undefined,
  imageCost: OperationCostResponse | undefined,
  primaryProfiles: ProfileResponse[],
  secondaryProfiles: ProfileResponse[],
  songCount: number,
  autoGenImage: boolean,
  autoGSuno: boolean,
  plannedDayCount: number | null,
  imageSourceMode: string,
): number | null {
  if (
    songCount <= 0 ||
    primaryProfiles.length <= 0 ||
    primaryProfiles.length !== secondaryProfiles.length ||
    plannedDayCount == null ||
    plannedDayCount <= 0
  ) {
    return null
  }

  if (!lyricCost?.available || lyricCost.credits_per_operation == null) {
    return null
  }

  const pairCount = primaryProfiles.length
  let totalCost = lyricCost.credits_per_operation * pairCount * songCount * plannedDayCount

  if (autoGSuno) {
    if (!musicCost?.available || musicCost.credits_per_operation == null) {
      return null
    }
    totalCost += musicCost.credits_per_operation * pairCount * songCount * plannedDayCount
  }

  if (!autoGenImage || imageSourceMode === 'manual') {
    return totalCost
  }

  if (!imageCost?.available || imageCost.credits_per_operation == null) {
    return null
  }

  const imageJobsPerSong = [...primaryProfiles, ...secondaryProfiles].reduce((total, profile) => total + getProfileImageJobCount(profile), 0)
  totalCost += imageJobsPerSong * imageCost.credits_per_operation * songCount * plannedDayCount
  return totalCost
}

function getProfileImageJobCount(profile: ProfileResponse | null | undefined): number {
  const imageConfig = profile?.image_config
  const rawMode = typeof imageConfig?.mode === 'string' ? imageConfig.mode : 'bg_thumb'
  const mode = rawMode.trim().toLowerCase()

  if (mode === 'bg_only' || mode === 'thumb_only') {
    return 1
  }

  return 2
}

function getMusicPlanCostBreakdown(
  lyricCost: OperationCostResponse | undefined,
  musicCost: OperationCostResponse | undefined,
  imageCost: OperationCostResponse | undefined,
  primaryProfiles: ProfileResponse[],
  secondaryProfiles: ProfileResponse[],
  songCount: number,
  autoGenImage: boolean,
  autoGSuno: boolean,
  plannedDayCount: number | null,
  imageSourceMode: string,
): MusicPlanCostBreakdown | null {
  if (
    songCount <= 0 ||
    primaryProfiles.length <= 0 ||
    primaryProfiles.length !== secondaryProfiles.length ||
    plannedDayCount == null ||
    plannedDayCount <= 0
  ) {
    return null
  }

  const pairCount = primaryProfiles.length
  const plannedBatchCount = pairCount * plannedDayCount
  const plannedSongCount = plannedBatchCount * songCount
  const draftUnitCost = getOperationUnitCost(lyricCost)
  const sunoUnitCost = getOperationUnitCost(musicCost)
  const imageUnitCost = getOperationUnitCost(imageCost)
  const imageJobsPerSong = autoGenImage && imageSourceMode !== 'manual'
    ? [...primaryProfiles, ...secondaryProfiles].reduce((total, profile) => total + getProfileImageJobCount(profile), 0)
    : 0

  const draftTotalCost = draftUnitCost == null ? null : draftUnitCost * plannedSongCount
  const sunoTotalCost = !autoGSuno ? 0 : sunoUnitCost == null ? null : sunoUnitCost * plannedSongCount
  const imageTotalCost = !autoGenImage || imageSourceMode === 'manual'
    ? 0
    : imageUnitCost == null
      ? null
      : imageUnitCost * imageJobsPerSong * plannedSongCount

  let totalCost: number | null = null
  if (draftTotalCost != null && sunoTotalCost != null && imageTotalCost != null) {
    totalCost = draftTotalCost + sunoTotalCost + imageTotalCost
  }

  return {
    plannedDayCount,
    pairCount,
    plannedBatchCount,
    songsPerBatch: songCount,
    plannedSongCount,
    draftUnitCost,
    draftTotalCost,
    sunoUnitCost,
    sunoTotalCost,
    imageUnitCost,
    imageJobsPerSong,
    imageTotalCost,
    totalCost,
  }
}

async function copyToClipboard(value: string): Promise<void> {
  if (!value.trim()) {
    return
  }

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
  }
}

function SectionCard(props: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element {
  return <Card {...props} className={cn('border-white/10 bg-[#081028]', props.className)} />
}

function StatusChip(props: { status: string | null | undefined }): React.JSX.Element {
  const label = props.status?.trim() || 'pending'

  return (
    <span className={cn('inline-flex w-fit rounded-full border px-2 py-0.5 text-[11px] font-medium', getStatusChipClass(label))}>
      {label}
    </span>
  )
}

function EffectMetric(props: { label: string; value: number }): React.JSX.Element {
  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{props.label}</span>
        <span className="text-[11px] font-medium text-slate-300">{props.value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-fuchsia-400/85" style={{ width: `${props.value}%` }} />
      </div>
    </div>
  )
}

function ChannelSelectionColumn(props: {
  title: string
  selectedIds: string[]
  profiles: ProfileResponse[]
  onToggle: (profileId: string) => void
}): React.JSX.Element {
  return (
    <div className="flex min-h-0 flex-col">
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">{props.title}</h2>
        <span className="text-xs text-slate-400">{props.selectedIds.length}</span>
      </div>
      <div className="grid min-h-0 flex-1 content-start gap-1.5 overflow-y-auto pr-1">
        {props.profiles.length ? (
          props.profiles.map((profile) => {
            const selectedIndex = props.selectedIds.indexOf(profile.id)
            const selected = selectedIndex >= 0

            return (
              <button
                key={profile.id}
                className={cn(
                  'flex min-h-[30px] items-center justify-between gap-2 rounded-lg border px-2 py-1 text-left transition',
                  selected
                    ? 'border-fuchsia-400/35 bg-fuchsia-500/10'
                    : 'border-white/10 bg-slate-950/45 hover:border-white/20 hover:bg-white/5',
                )}
                type="button"
                onClick={() => props.onToggle(profile.id)}
              >
                <div className="min-w-0">
                  <p className="truncate text-[12px] font-medium leading-4 text-white">{profile.name}</p>
                  <p className="truncate text-[10px] leading-3.5 text-slate-500">{profile.folder_name?.trim() || 'No folder name'}</p>
                </div>
                <span
                  className={cn(
                    'flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                    selected ? 'border-fuchsia-300 bg-fuchsia-400/20 text-fuchsia-100' : 'border-white/15 text-transparent',
                  )}
                >
                  {selected ? <span className="text-[9px] font-semibold">{selectedIndex + 1}</span> : <Check className="h-2.5 w-2.5" />}
                </span>
              </button>
            )
          })
        ) : (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-white/10 bg-slate-950/35 px-4 text-center text-sm text-slate-400">
            No profiles available yet.
          </div>
        )}
      </div>
    </div>
  )
}

export function MusicWorkspacePage(): React.JSX.Element {
  const desktopApi = getDesktopApi()
  const queryClient = useQueryClient()
  const [composer, setComposer] = useState<ComposerState>(blankComposerState)
  const [musicSettings, setMusicSettings] = useState<MusicSettingsState>(blankMusicSettingsState)
  const [draftPoolSeeds, setDraftPoolSeeds] = useState<DraftPoolSeedState | null>(null)
  const [historyFilters, setHistoryFilters] = useState<HistoryFiltersState>({
    fromDate: '',
    toDate: '',
    lastBatchOnly: false,
  })
  const [selectedDescriptionId, setSelectedDescriptionId] = useState('')
  const [selectedStructureId, setSelectedStructureId] = useState('')
  const [selectedHistorySongId, setSelectedHistorySongId] = useState<string | null>(null)
  const [latestBatchId, setLatestBatchId] = useState<string | null>(null)
  const [latestBatchSummary, setLatestBatchSummary] = useState<string | null>(null)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const initializedSettingsRef = useRef(false)
  const lastPersistedSettingsSnapshotRef = useRef('')
  const { data, isLoading, isError } = useMusicWorkspaceQuery()
  const batchStatusQuery = useBatchStatusQuery(latestBatchId)
  const lastBatchProgressKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (!latestBatchId || !batchStatusQuery.data) {
      return
    }

    const progressKey = [
      batchStatusQuery.data.status,
      batchStatusQuery.data.drafts_completed,
      batchStatusQuery.data.drafts_failed,
      batchStatusQuery.data.suno_completed,
      batchStatusQuery.data.suno_failed,
    ].join(':')

    if (progressKey === lastBatchProgressKeyRef.current) {
      return
    }

    lastBatchProgressKeyRef.current = progressKey
    void queryClient.invalidateQueries({ queryKey: ['music-workspace'] })

    if (['completed', 'partial', 'failed'].includes(batchStatusQuery.data.status)) {
      setLatestBatchId(null)
      lastBatchProgressKeyRef.current = null
    }
  }, [batchStatusQuery.data, latestBatchId, queryClient])

  const profiles = data?.profiles ?? EMPTY_PROFILES
  const descriptionOptions = data?.descriptionOptions ?? EMPTY_PROMPTS
  const structureOptions = data?.structureOptions ?? EMPTY_PROMPTS
  const historyBatches = data?.history.batches ?? EMPTY_HISTORY_BATCHES
  const operationCostByType = useMemo(() => mapOperationCosts(data?.operationCosts.items), [data?.operationCosts.items])
  const plannedDaySpan = useMemo(() => getInclusiveDaySpan(composer.fromDate, composer.toDate), [composer.fromDate, composer.toDate])
  const plannedRunDates = useMemo(() => getInclusiveDateList(composer.fromDate, composer.toDate), [composer.fromDate, composer.toDate])
  const isInvalidBatchRange = Boolean(composer.fromDate && composer.toDate && plannedDaySpan === null)
  const creativityEffects = useMemo(() => effectPreviewFromCreativity(musicSettings.creativity), [musicSettings.creativity])

  const flattenedHistoryRows = useMemo<HistoryRow[]>(() => {
    const rows: HistoryRow[] = []
    let rowNumber = 1

    historyBatches.forEach((batch, batchIndex) => {
      if (!matchesHistoryFilters(batch, historyFilters, batchIndex)) {
        return
      }

      batch.songs.forEach((song) => {
        rows.push({ rowNumber, batch, song })
        rowNumber += 1
      })
    })

    return rows
  }, [historyBatches, historyFilters])

  const primarySelectedProfiles = useMemo(
    () => profiles.filter((profile) => composer.primaryProfileIds.includes(profile.id)),
    [composer.primaryProfileIds, profiles],
  )
  const secondarySelectedProfiles = useMemo(
    () => profiles.filter((profile) => composer.secondaryProfileIds.includes(profile.id)),
    [composer.secondaryProfileIds, profiles],
  )
  const selectedPairCount = primarySelectedProfiles.length === secondarySelectedProfiles.length ? primarySelectedProfiles.length : 0
  const plannedBatchCount = plannedDaySpan != null ? plannedDaySpan * selectedPairCount : 0
  const overlappingProfileIds = useMemo(
    () => composer.primaryProfileIds.filter((profileId) => composer.secondaryProfileIds.includes(profileId)),
    [composer.primaryProfileIds, composer.secondaryProfileIds],
  )
  const imageSourceMode = readStringSetting(data?.settings as Record<string, unknown> | undefined, 'imageSourceMode', 'ai')
  const manualRunBaseDir =
    readStringSetting(data?.settings as Record<string, unknown> | undefined, 'sunoOutputDir')
    || readStringSetting(data?.settings as Record<string, unknown> | undefined, 'downloadsDir')
  const generateBatchTotalCost = useMemo(
    () =>
      getBatchGenerateTotalCost(
        operationCostByType.lyric,
        operationCostByType.music,
        operationCostByType.background_image,
        primarySelectedProfiles,
        secondarySelectedProfiles,
        musicSettings.songCount,
        musicSettings.autoGenImage,
        musicSettings.autoGSuno,
        plannedDaySpan,
        imageSourceMode,
      ),
    [
      imageSourceMode,
      musicSettings.autoGenImage,
      musicSettings.autoGSuno,
      musicSettings.songCount,
      operationCostByType.background_image,
      operationCostByType.lyric,
      operationCostByType.music,
      plannedDaySpan,
      primarySelectedProfiles,
      secondarySelectedProfiles,
    ],
  )
  const musicPlanCostBreakdown = useMemo(
    () =>
      getMusicPlanCostBreakdown(
        operationCostByType.lyric,
        operationCostByType.music,
        operationCostByType.background_image,
        primarySelectedProfiles,
        secondarySelectedProfiles,
        musicSettings.songCount,
        musicSettings.autoGenImage,
        musicSettings.autoGSuno,
        plannedDaySpan,
        imageSourceMode,
      ),
    [
      imageSourceMode,
      musicSettings.autoGenImage,
      musicSettings.autoGSuno,
      musicSettings.songCount,
      operationCostByType.background_image,
      operationCostByType.lyric,
      operationCostByType.music,
      plannedDaySpan,
      primarySelectedProfiles,
      secondarySelectedProfiles,
    ],
  )
  const lyricUnitCost = getOperationUnitCost(operationCostByType.lyric)

  useEffect(() => {
    if (!profiles.length) {
      setComposer((current) => {
        if (!current.primaryProfileIds.length && !current.secondaryProfileIds.length) {
          return current
        }

        return { ...current, primaryProfileIds: [], secondaryProfileIds: [] }
      })
      return
    }

    setComposer((current) => {
      const primaryProfileIds = sanitizeSelectedProfileIds(current.primaryProfileIds, profiles, [profiles[0]?.id ?? ''])
      const secondaryFallbackId = profiles[Math.min(1, profiles.length - 1)]?.id ?? profiles[0]?.id ?? ''
      const secondaryProfileIds = sanitizeSelectedProfileIds(current.secondaryProfileIds, profiles, [secondaryFallbackId])

      if (
        primaryProfileIds.join('|') === current.primaryProfileIds.join('|')
        && secondaryProfileIds.join('|') === current.secondaryProfileIds.join('|')
      ) {
        return current
      }

      return { ...current, primaryProfileIds, secondaryProfileIds }
    })
  }, [profiles])

  useEffect(() => {
    if (!data || initializedSettingsRef.current) {
      return
    }

    const nextSettings = buildMusicSettingsState(data.settings as Record<string, unknown> | undefined)
    const nextSnapshot = JSON.stringify(nextSettings)

    setMusicSettings(nextSettings)
    lastPersistedSettingsSnapshotRef.current = nextSnapshot
    initializedSettingsRef.current = true
  }, [data])

  useEffect(() => {
    if (!selectedDescriptionId && descriptionOptions.length) {
      setSelectedDescriptionId(descriptionOptions[0].id)
    }
  }, [descriptionOptions, selectedDescriptionId])

  useEffect(() => {
    if (!selectedStructureId && structureOptions.length) {
      setSelectedStructureId(structureOptions[0].id)
    }
  }, [selectedStructureId, structureOptions])

  useEffect(() => {
    const selectedDescription = descriptionOptions.find((item) => item.id === selectedDescriptionId)
    if (!selectedDescription) {
      return
    }

    setComposer((current) => (current.description === selectedDescription.name ? current : { ...current, description: selectedDescription.name }))
  }, [descriptionOptions, selectedDescriptionId])

  useEffect(() => {
    const selectedStructure = structureOptions.find((item) => item.id === selectedStructureId)
    if (!selectedStructure) {
      return
    }

    setComposer((current) => (current.structure === selectedStructure.name ? current : { ...current, structure: selectedStructure.name }))
  }, [selectedStructureId, structureOptions])

  useEffect(() => {
    if (selectedHistorySongId && !flattenedHistoryRows.some((row) => row.song.song_id === selectedHistorySongId)) {
      setSelectedHistorySongId(null)
    }
  }, [flattenedHistoryRows, selectedHistorySongId])

  useEffect(() => {
    if (saveStatus !== 'saved') {
      return
    }

    const timeoutId = window.setTimeout(() => setSaveStatus('idle'), 1800)
    return () => window.clearTimeout(timeoutId)
  }, [saveStatus])

  const invalidateWorkspace = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['music-workspace'] }),
      queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
    ])
  }

  const persistSettingsMutation = useMutation({
    mutationFn: async (input: { patch: Record<string, unknown>; snapshot: string }) => {
      await apiPatchSettings(input.patch)
      return input.snapshot
    },
    onSuccess: (snapshot) => {
      lastPersistedSettingsSnapshotRef.current = snapshot
      setSaveStatus('saved')
    },
    onError: () => {
      setSaveStatus('error')
    },
  })

  useEffect(() => {
    if (!initializedSettingsRef.current) {
      return
    }

    const snapshot = JSON.stringify(musicSettings)
    if (snapshot === lastPersistedSettingsSnapshotRef.current) {
      return
    }

    setSaveStatus('saving')
    const timeoutId = window.setTimeout(() => {
      persistSettingsMutation.mutate({
        patch: buildMusicSettingsPatch(musicSettings),
        snapshot,
      })
    }, 400)

    return () => window.clearTimeout(timeoutId)
  }, [musicSettings, persistSettingsMutation])

  const generateDraftMutation = useMutation({
    mutationFn: async () => {
      if (!composer.description.trim()) {
        throw new Error('Song description is required before generating a draft.')
      }

      const payload: DraftGenerationRequest = {
        language: musicSettings.language,
        creativity_level: musicSettings.creativity,
        description: composer.description.trim(),
        structure: composer.structure.trim(),
        description_id: selectedDescriptionId || null,
        structure_id: selectedStructureId || null,
        channel_profile_id: primarySelectedProfiles[0]?.id ?? null,
      }

      const avoidLists = buildHistoryAvoidLists(historyBatches, musicSettings.historyWindow)
      const reservationToken = buildReservationToken()
      const claimedSeeds: Array<{ kind: 'titles' | 'albums' | 'openings'; item: ClaimedContentPoolItem }> = []

      const claimSeed = async (kind: 'titles' | 'albums' | 'openings') => {
        const response = await apiClaimContentPoolItem(kind, {
          reservation_token: reservationToken,
          consumer: 'music-draft',
        })
        claimedSeeds.push({ kind, item: response.item })
        return response.item
      }

      try {
        const [titleSeed, albumSeed, openingSeed] = await Promise.all([
          claimSeed('titles'),
          claimSeed('albums'),
          musicSettings.uniqueOpening ? claimSeed('openings') : Promise.resolve(null),
        ])

        const poolSeeds: DraftPoolSeedState = {
          titleSeed: titleSeed.text,
          albumSeed: albumSeed.text,
          openingSeed: openingSeed
            ? [openingSeed.text, openingSeed.secondary_text].filter(Boolean).join('\n')
            : null,
        }

        const draft = await apiGenerateDraft({
          ...payload,
          description: composer.description.trim(),
          avoid_titles: avoidLists.titles,
          avoid_albums: avoidLists.albums,
          avoid_openings: avoidLists.openings,
          title_seed: poolSeeds.titleSeed,
          album_seed: poolSeeds.albumSeed,
          forced_opening: poolSeeds.openingSeed,
        })

        await Promise.all(
          claimedSeeds.map((claim) =>
            apiFinalizeContentPoolItem(claim.kind, {
              item_id: claim.item.id,
              reservation_token: claim.item.reservation_token,
            }),
          ),
        )

        return { draft, poolSeeds }
      } catch (error) {
        await Promise.allSettled(
          claimedSeeds.map((claim) =>
            apiReleaseContentPoolItem(claim.kind, {
              item_id: claim.item.id,
              reservation_token: claim.item.reservation_token,
            }),
          ),
        )
        throw error
      }
    },
    onSuccess: ({ draft, poolSeeds }) => {
      setWorkspaceError(null)
      setDraftPoolSeeds(poolSeeds)
      setComposer((current) => ({
        ...current,
        title: draft.title,
        album: draft.album,
        lyrics: draft.lyrics,
      }))
    },
    onError: (error) => {
      setWorkspaceError(
        error instanceof PlatformApiError || error instanceof Error ? error.message : 'Unable to generate a draft right now.',
      )
    },
  })

  const polishLyricsMutation = useMutation({
    mutationFn: async () => {
      if (!composer.lyrics.trim()) {
        throw new Error('Generate or enter lyrics before polishing.')
      }

      return apiPolishLyrics({
        lyrics: composer.lyrics,
        strength: musicSettings.polishStrength,
        channel_profile_id: primarySelectedProfiles[0]?.id ?? null,
      })
    },
    onSuccess: (result) => {
      setWorkspaceError(null)
      setComposer((current) => ({ ...current, lyrics: result.lyrics }))
    },
    onError: (error) => {
      setWorkspaceError(
        error instanceof PlatformApiError || error instanceof Error ? error.message : 'Unable to polish lyrics right now.',
      )
    },
  })

  const createBatchMutation = useMutation({
    mutationFn: async () => {
      if (!primarySelectedProfiles.length || !secondarySelectedProfiles.length) {
        throw new Error('Select at least one Primary and one Secondary channel before creating a batch.')
      }
      if (primarySelectedProfiles.length !== secondarySelectedProfiles.length) {
        throw new Error('Primary and Secondary channel counts must match before generating.')
      }
      if (overlappingProfileIds.length) {
        throw new Error('Primary and Secondary channel lists must not contain the same profile.')
      }
      if (!composer.fromDate || !composer.toDate || plannedDaySpan === null) {
        throw new Error('Choose a valid batch date range before creating a batch.')
      }

      const results = []
      for (const runDate of plannedRunDates) {
        for (let index = 0; index < primarySelectedProfiles.length; index += 1) {
          const payload: BatchCreateRequest = {
            ok_profile_id: primarySelectedProfiles[index]!.id,
            alt_profile_id: secondarySelectedProfiles[index]!.id,
            description_id: selectedDescriptionId || null,
            structure_id: selectedStructureId || null,
            auto_gen_image: musicSettings.autoGenImage,
            auto_gsuno: musicSettings.autoGSuno,
            song_count: musicSettings.songCount,
            language: musicSettings.language,
            creativity_level: musicSettings.creativity,
            pairing_mode: 'match_key',
            from_date: runDate,
            to_date: runDate,
          }

          const response = await apiCreateBatch(payload)
          results.push(response)
        }
      }

      return results
    },
    onSuccess: async (results) => {
      setWorkspaceError(null)
      setLatestBatchId(results[results.length - 1]?.batch_id ?? null)
      setLatestBatchSummary(
        `Created ${results.length} batch run${results.length === 1 ? '' : 's'} across ${plannedRunDates.length} planned day${plannedRunDates.length === 1 ? '' : 's'} and ${selectedPairCount} channel pair${selectedPairCount === 1 ? '' : 's'}.`,
      )
      await invalidateWorkspace()
    },
    onError: (error) => {
      setWorkspaceError(
        error instanceof PlatformApiError || error instanceof Error ? error.message : 'Unable to create a batch right now.',
      )
    },
  })

  const handleMusicSettingChange = (patch: Partial<MusicSettingsState>) => {
    setMusicSettings((current) => ({ ...current, ...patch }))
  }

  const handleSelectHistoryRow = (row: HistoryRow) => {
    setSelectedHistorySongId(row.song.song_id)
    setDraftPoolSeeds(null)
    if (row.song.description_id) {
      setSelectedDescriptionId(row.song.description_id)
    }
    if (row.song.structure_id) {
      setSelectedStructureId(row.song.structure_id)
    }
    setComposer((current) => ({
      ...current,
      title: row.song.title ?? current.title,
      album: row.song.album ?? current.album,
      lyrics: row.song.lyrics ?? current.lyrics,
    }))
  }

  const handleOpenHistoryFolder = async (
    targetPath: string | null | undefined,
    label: 'Primary' | 'Secondary',
  ) => {
    const normalizedPath = targetPath?.trim()
    if (!normalizedPath) {
      setWorkspaceError(`${label} channel output folder is not available yet for this song.`)
      return
    }

    const opened = await desktopApi.files.openPath(normalizedPath)
    if (!opened) {
      setWorkspaceError(`Unable to open the ${label} channel output folder.`)
    }
  }

  const batchStatusLabel = latestBatchId
    ? [latestBatchSummary, batchStatusQuery.data?.status ?? 'Polling latest batch...'].filter(Boolean).join(' · ')
    : latestBatchSummary ?? 'Ready for the next batch.'

  return (
    <div className="grid gap-3">
      {workspaceError ? (
        <SectionCard className="border-rose-500/25 bg-rose-500/10 p-3 text-sm text-rose-200">{workspaceError}</SectionCard>
      ) : null}

      {isLoading ? <SectionCard className="p-5 text-sm text-slate-400">Loading music workspace...</SectionCard> : null}

      {isError ? (
        <SectionCard className="border-rose-500/25 bg-rose-500/10 p-5 text-sm text-rose-200">
          Unable to load the music workspace from the current backend contracts.
        </SectionCard>
      ) : null}

      {!isLoading && !isError ? (
        <div className="grid gap-3">
          <SectionCard className="p-2.5">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">From</span>
              <DatePickerField
                className="w-[124px]"
                label="From"
                value={composer.fromDate}
                onChange={(value) => setComposer((current) => ({ ...current, fromDate: value }))}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">To</span>
              <DatePickerField
                className="w-[124px]"
                label="To"
                value={composer.toDate}
                onChange={(value) => setComposer((current) => ({ ...current, toDate: value }))}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Language</span>
              <AppSelect
                options={LANGUAGE_OPTIONS.map((option) => ({ label: option.label, value: option.value }))}
                placeholder="Language"
                triggerClassName="h-9 w-[118px] bg-slate-950/70 px-2.5 text-[13px]"
                value={musicSettings.language}
                onChange={(value) => handleMusicSettingChange({ language: value || 'en' })}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Creativity</span>
              <div className="flex w-[178px] items-center gap-2 rounded-xl border border-white/10 bg-slate-950/40 px-2.5 py-2">
                <input
                  aria-label="Creativity"
                  className="w-full accent-fuchsia-500"
                  max={100}
                  min={0}
                  type="range"
                  value={musicSettings.creativity}
                  onChange={(event) => handleMusicSettingChange({ creativity: Number(event.target.value) })}
                />
                <span className="min-w-[24px] text-right text-[11px] font-medium text-slate-200">{musicSettings.creativity}</span>
              </div>
              <InlineToggle
                label="Unique opening"
                pressed={musicSettings.uniqueOpening}
                onPressedChange={(pressed) => handleMusicSettingChange({ uniqueOpening: pressed })}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Strict</span>
              <AppSelect
                options={[1, 2, 3, 4, 5].map((value) => ({ label: String(value), value: String(value) }))}
                placeholder="Strict"
                triggerClassName="h-9 w-[68px] bg-slate-950/70 px-2.5 text-[13px]"
                value={String(musicSettings.strictLevel)}
                onChange={(value) => handleMusicSettingChange({ strictLevel: Number(value || 1) })}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">History</span>
              <AppSelect
                options={[50, 100, 200, 500, 1500].map((value) => ({ label: String(value), value: String(value) }))}
                placeholder="History"
                triggerClassName="h-9 w-[88px] bg-slate-950/70 px-2.5 text-[13px]"
                value={String(musicSettings.historyWindow)}
                onChange={(value) => handleMusicSettingChange({ historyWindow: Number(value || 50) })}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Count</span>
              <Input
                aria-label="Count"
                className="h-9 w-[68px]"
                max={50}
                min={1}
                type="number"
                value={musicSettings.songCount}
                onChange={(event) => handleMusicSettingChange({ songCount: clamp(Number(event.target.value) || 1, 1, 50) })}
              />
              <div className="inline-flex h-8 items-center gap-2 rounded-xl border border-white/10 bg-slate-950/35 px-2.5 text-[11px] text-slate-400 xl:ml-auto">
                <CalendarDays className="h-4 w-4 text-slate-500" />
                <span className={cn(isInvalidBatchRange ? 'text-rose-300' : undefined)}>
                  {plannedDaySpan === null ? 'Choose a valid inclusive date range.' : `${plannedDaySpan} planned day${plannedDaySpan === 1 ? '' : 's'}`}
                </span>
              </div>
            </div>
          </SectionCard>

          <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1.5fr)_minmax(240px,0.75fr)_minmax(240px,0.75fr)_minmax(260px,0.95fr)]">
            <SectionCard className="flex min-h-0 flex-col p-2.5">
              <div className="flex min-h-0 flex-1 flex-col gap-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-white">Song</h2>
                    <p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">Effects and polish</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      className="h-8 px-3 text-[12px]"
                      disabled={generateDraftMutation.isPending || !composer.description.trim()}
                      size="sm"
                      type="button"
                      variant="secondary"
                      onClick={() => void generateDraftMutation.mutateAsync()}
                    >
                      {generateDraftMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      {formatButtonCreditLabel('Draft', lyricUnitCost)}
                    </Button>
                    <Button
                      className="h-8 px-3 text-[12px]"
                      disabled={polishLyricsMutation.isPending || !composer.lyrics.trim()}
                      size="sm"
                      type="button"
                      variant="secondary"
                      onClick={() => void polishLyricsMutation.mutateAsync()}
                    >
                      {polishLyricsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                      {formatButtonCreditLabel('Polish', lyricUnitCost)}
                    </Button>
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-4">
                  <EffectMetric label="Valence" value={creativityEffects.valence} />
                  <EffectMetric label="Danceability" value={creativityEffects.danceability} />
                  <EffectMetric label="Instrumental" value={creativityEffects.instrumentalness} />
                  <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">Polish</span>
                      <span className="text-[11px] font-medium text-slate-300">{musicSettings.polishStrength}</span>
                    </div>
                    <input
                      aria-label="Polish"
                      className="w-full accent-fuchsia-500"
                      max={100}
                      min={0}
                      type="range"
                      value={musicSettings.polishStrength}
                      onChange={(event) => handleMusicSettingChange({ polishStrength: Number(event.target.value) })}
                    />
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-[1.2fr_1fr]">
                  <Input
                    aria-label="Song title"
                    className="h-9"
                    placeholder="Song title"
                    value={composer.title}
                    onChange={(event) => setComposer((current) => ({ ...current, title: event.target.value }))}
                  />
                  <Input
                    aria-label="Album"
                    className="h-9"
                    placeholder="Album"
                    value={composer.album}
                    onChange={(event) => setComposer((current) => ({ ...current, album: event.target.value }))}
                  />
                </div>

                {draftPoolSeeds ? (
                  <div className="rounded-xl border border-sky-500/25 bg-sky-500/10 px-3 py-2 text-[11px] text-sky-100">
                    Draft seeded from pools and rephrased into a new result:
                    {` title "${draftPoolSeeds.titleSeed}"`}
                    {`, album "${draftPoolSeeds.albumSeed}"`}
                    {draftPoolSeeds.openingSeed ? `, opening "${draftPoolSeeds.openingSeed.split('\n')[0]}"` : ''}
                    . Pool seeds stay on-theme; the LLM changes the wording.
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <Button
                    className="h-8 min-w-[124px] flex-1 justify-center px-2 text-[11px]"
                    size="sm"
                    type="button"
                    onClick={() => void copyToClipboard(composer.title)}
                  >
                    <Copy className="h-4 w-4" />
                    Copy title
                  </Button>
                  <Button
                    className="h-8 min-w-[124px] flex-1 justify-center px-2 text-[11px]"
                    size="sm"
                    type="button"
                    onClick={() => void copyToClipboard(composer.lyrics)}
                  >
                    <Copy className="h-4 w-4" />
                    Copy lyrics
                  </Button>
                  <Button
                    className="h-8 min-w-[124px] flex-1 justify-center px-2 text-[11px]"
                    size="sm"
                    type="button"
                    onClick={() => void copyToClipboard([composer.title, composer.lyrics].filter(Boolean).join('\n\n'))}
                  >
                    <Copy className="h-4 w-4" />
                    Copy both
                  </Button>
                  <Button
                    className="h-8 min-w-[124px] flex-1 justify-center bg-amber-600 px-2 text-[11px] text-white hover:bg-amber-500"
                    disabled={polishLyricsMutation.isPending || !composer.lyrics.trim()}
                    size="sm"
                    type="button"
                    onClick={() => void polishLyricsMutation.mutateAsync()}
                  >
                    {polishLyricsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                    {formatButtonCreditLabel('Polish', lyricUnitCost)}
                  </Button>
                  <Button
                    className="h-8 min-w-[124px] flex-1 justify-center px-2 text-[11px]"
                    disabled
                    size="sm"
                    type="button"
                    variant="secondary"
                  >
                    {formatButtonCreditLabel('Revisions', 0)}
                  </Button>
                </div>

                <Textarea
                  className="min-h-[178px] flex-1 resize-none"
                  placeholder="Lyrics"
                  value={composer.lyrics}
                  onChange={(event) => setComposer((current) => ({ ...current, lyrics: event.target.value }))}
                />
              </div>
            </SectionCard>

            <SectionCard className="flex min-h-0 flex-col p-2.5">
              <div className="mb-1.5">
                <h2 className="text-sm font-semibold text-white">Primary channels</h2>
                <p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">Ordered pairs</p>
              </div>
              <div className="min-h-0 flex-1">
                <ChannelSelectionColumn
                  profiles={profiles}
                  selectedIds={composer.primaryProfileIds}
                  title="Primary"
                  onToggle={(profileId) =>
                    setComposer((current) => ({ ...current, primaryProfileIds: toggleSelectedProfileIds(current.primaryProfileIds, profileId) }))
                  }
                />
              </div>
            </SectionCard>

            <SectionCard className="flex min-h-0 flex-col p-2.5">
              <div className="mb-1.5">
                <h2 className="text-sm font-semibold text-white">Secondary channels</h2>
                <p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">Ordered pairs</p>
              </div>
              <div className="min-h-0 flex-1">
                <ChannelSelectionColumn
                  profiles={profiles}
                  selectedIds={composer.secondaryProfileIds}
                  title="Secondary"
                  onToggle={(profileId) =>
                    setComposer((current) => ({ ...current, secondaryProfileIds: toggleSelectedProfileIds(current.secondaryProfileIds, profileId) }))
                  }
                />
              </div>
            </SectionCard>

            <SectionCard className="flex min-h-0 flex-col p-2.5">
              <div className="mb-2">
                <h2 className="text-sm font-semibold text-white">Automation</h2>
                <p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">Top to bottom</p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="grid gap-1">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Description</span>
                  <AppSelect
                    options={
                      descriptionOptions.length
                        ? descriptionOptions.map((option) => ({ label: option.name, value: option.id }))
                        : []
                    }
                    placeholder="No descriptions"
                    triggerClassName="h-8 text-[12px]"
                    value={selectedDescriptionId}
                    onChange={setSelectedDescriptionId}
                  />
                </div>

                <div className="grid gap-1">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Structure</span>
                  <AppSelect
                    options={
                      structureOptions.length
                        ? structureOptions.map((option) => ({ label: option.name, value: option.id }))
                        : []
                    }
                    placeholder="No structures"
                    triggerClassName="h-8 text-[12px]"
                    value={selectedStructureId}
                    onChange={setSelectedStructureId}
                  />
                </div>

                <div className="grid gap-1.5 sm:col-span-2 sm:grid-cols-2">
                  <InlineToggle
                    label="Auto-Gen Image"
                    pressed={musicSettings.autoGenImage}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoGenImage: pressed })}
                  />
                  <InlineToggle
                    label="Auto-GSuno"
                    pressed={musicSettings.autoGSuno}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoGSuno: pressed })}
                  />
                  <InlineToggle
                    label="Auto-Video"
                    pressed={musicSettings.autoVideoAfterSuno}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoVideoAfterSuno: pressed })}
                  />
                  <InlineToggle
                    label="Auto Merge"
                    pressed={musicSettings.autoMergeAfterVideo}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoMergeAfterVideo: pressed })}
                  />
                  <InlineToggle
                    label="Auto Reel"
                    pressed={musicSettings.autoReelAfterVideo}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoReelAfterVideo: pressed })}
                  />
                  <InlineToggle
                    label="Auto-Upload"
                    pressed={musicSettings.autoUploadYouTube}
                    onPressedChange={(pressed) => handleMusicSettingChange({ autoUploadYouTube: pressed })}
                    disabled
                  />
                </div>

                <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 px-2.5 py-2 text-[10px] text-amber-100 sm:col-span-2">
                  Active pipeline automation currently includes `Draft`, `Auto-GSuno`, optional `Auto-Gen Image`, and
                  desktop MP3 downloading from the `platform_api` Suno links. `Auto-Video`, `Auto Merge`, and
                  `Auto Reel` now use the real desktop export/merge runtime from the app shell. `Auto-Upload` remains
                  disabled until the long-merged YouTube path is validated end to end in signed-in desktop QA.
                </div>

                <div className="rounded-xl border border-white/10 bg-slate-950/35 px-2.5 py-2 text-[11px] text-slate-400 sm:col-span-2">
                  <div className="truncate">{saveStatusMessage(saveStatus)}</div>
                  <div className="mt-1 truncate text-slate-200">{batchStatusLabel}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
                    <span>{formatOperationCostLabel(operationCostByType.lyric, 'Draft')}</span>
                    <span>{formatOperationCostLabel(operationCostByType.lyric, 'Polish')}</span>
                    <span>Revisions: 0 credits</span>
                    <span>{formatOperationCostLabel(operationCostByType.music, 'Suno')}</span>
                    <span>{formatOperationCostLabel(operationCostByType.background_image, 'Image')}</span>
                  </div>
                  <div className="mt-2 grid gap-1 text-[10px] text-slate-300">
                    <div>
                      Plan: {musicPlanCostBreakdown
                        ? `${musicPlanCostBreakdown.plannedDayCount} day${musicPlanCostBreakdown.plannedDayCount === 1 ? '' : 's'} x ${musicPlanCostBreakdown.pairCount} pair${musicPlanCostBreakdown.pairCount === 1 ? '' : 's'} x ${musicPlanCostBreakdown.songsPerBatch} song${musicPlanCostBreakdown.songsPerBatch === 1 ? '' : 's'} = ${musicPlanCostBreakdown.plannedSongCount} song job${musicPlanCostBreakdown.plannedSongCount === 1 ? '' : 's'}`
                        : 'Select a valid date range and matching channel pairs to see plan totals.'}
                    </div>
                    <div>
                      {musicPlanCostBreakdown?.draftTotalCost != null
                        ? `Draft total: ${musicPlanCostBreakdown.draftTotalCost} credits`
                        : 'Draft total: unavailable'}
                      {'  '}
                      {musicPlanCostBreakdown?.sunoTotalCost != null
                        ? `Suno total: ${musicPlanCostBreakdown.sunoTotalCost} credits`
                        : 'Suno total: unavailable'}
                      {'  '}
                      {musicPlanCostBreakdown
                        ? musicPlanCostBreakdown.imageTotalCost == null
                          ? 'Image total: unavailable'
                          : musicSettings.autoGenImage && imageSourceMode !== 'manual'
                            ? `Image total: ${musicPlanCostBreakdown.imageTotalCost} credits`
                            : 'Image total: 0 credits'
                        : 'Image total: 0 credits'}
                    </div>
                    <div>
                      {musicPlanCostBreakdown?.totalCost != null
                        ? `Batch total: ${musicPlanCostBreakdown.totalCost} credits`
                        : 'Batch total: unavailable'}
                    </div>
                  </div>
                  <div className="mt-1 text-[10px] text-slate-500">
                    Draft and Polish use the routed lyric model. Revisions is a non-AI history action and does not spend credits.
                  </div>
                </div>

                <Button
                  className="h-8 w-full px-3 text-[12px] sm:col-span-2"
                  disabled={
                    createBatchMutation.isPending ||
                    !composer.primaryProfileIds.length ||
                    !composer.secondaryProfileIds.length ||
                    composer.primaryProfileIds.length !== composer.secondaryProfileIds.length ||
                    Boolean(overlappingProfileIds.length) ||
                    isInvalidBatchRange
                  }
                  type="button"
                  onClick={() => void createBatchMutation.mutateAsync()}
                >
                  {createBatchMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Music4 className="h-4 w-4" />}
                  {generateBatchTotalCost != null ? `Generate (${generateBatchTotalCost} Credits)` : 'Generate'}
                </Button>
                <div className="text-[10px] text-slate-500 sm:col-span-2">
                  {plannedBatchCount > 0
                    ? `${plannedBatchCount} planned batch run${plannedBatchCount === 1 ? '' : 's'} from ${plannedDaySpan} day${plannedDaySpan === 1 ? '' : 's'} x ${selectedPairCount} pair${selectedPairCount === 1 ? '' : 's'}${musicSettings.autoGenImage && imageSourceMode !== 'manual' ? ' · Includes image credits' : ''}`
                    : musicSettings.autoGenImage && imageSourceMode !== 'manual'
                      ? 'Includes image credits when batch generation is available.'
                      : 'Generate creates one batch per planned day and channel pair.'}
                </div>
              </div>
              {composer.primaryProfileIds.length !== composer.secondaryProfileIds.length ? (
                <p className="mt-2 text-xs text-amber-300">Primary and Secondary channel counts must match.</p>
              ) : null}
              {overlappingProfileIds.length ? (
                <p className="mt-2 text-xs text-amber-300">Choose different channels for each side.</p>
              ) : null}
            </SectionCard>
          </div>

          <SectionCard className="flex min-h-[360px] flex-col p-3">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="mr-auto flex items-center gap-2">
                <History className="h-4 w-4 text-slate-300" />
                <h2 className="text-sm font-semibold text-white">History</h2>
              </div>
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">From</span>
              <DatePickerField
                className="w-[132px]"
                label="History from"
                value={historyFilters.fromDate}
                onChange={(value) => setHistoryFilters((current) => ({ ...current, fromDate: value }))}
              />
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">To</span>
              <DatePickerField
                className="w-[132px]"
                label="History to"
                value={historyFilters.toDate}
                onChange={(value) => setHistoryFilters((current) => ({ ...current, toDate: value }))}
              />
              <InlineToggle
                label="Last batch"
                pressed={historyFilters.lastBatchOnly}
                onPressedChange={(pressed) => setHistoryFilters((current) => ({ ...current, lastBatchOnly: pressed }))}
              />
              <Button
                size="sm"
                type="button"
                variant="secondary"
                onClick={() =>
                  setHistoryFilters({
                    fromDate: '',
                    toDate: '',
                    lastBatchOnly: false,
                  })
                }
              >
                Show all
              </Button>
            </div>

            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
              <span>{data?.history.summary ?? 'No history yet.'}</span>
              <span>Updated {formatDateTimeLabel(data?.history.updated_at)}</span>
            </div>

            {flattenedHistoryRows.length ? (
              <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-white/10">
                <table className="min-w-full table-fixed border-collapse">
                  <thead className="sticky top-0 z-10 bg-slate-950/90">
                    <tr className="text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      <th className="w-[60px] px-3 py-3 font-medium">No</th>
                      <th className="w-[180px] px-3 py-3 font-medium">Album</th>
                      <th className="w-[220px] px-3 py-3 font-medium">Title</th>
                      <th className="w-[170px] px-3 py-3 font-medium">Description</th>
                      <th className="w-[170px] px-3 py-3 font-medium">Structure</th>
                      <th className="w-[170px] px-3 py-3 font-medium">Primary Channel</th>
                      <th className="w-[170px] px-3 py-3 font-medium">Secondary Channel</th>
                      <th className="w-[110px] px-3 py-3 font-medium">Suno</th>
                      <th className="w-[150px] px-3 py-3 font-medium">Generated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 bg-[#081028]">
                    {flattenedHistoryRows.map((row) => {
                      const selected = row.song.song_id === selectedHistorySongId

                      return (
                        <tr
                          key={row.song.song_id}
                          className={cn(
                            'cursor-pointer text-sm text-slate-300 transition hover:bg-white/5',
                            selected && 'bg-fuchsia-500/10',
                          )}
                          onClick={() => handleSelectHistoryRow(row)}
                        >
                          <td className="px-3 py-3 align-top">{row.rowNumber}</td>
                          <td className="truncate px-3 py-3 align-top text-slate-300">{row.song.album || '—'}</td>
                          <td className="px-3 py-3 align-top">
                            <div className="truncate font-medium text-white">
                              {isSongTitleGenerating(row.song) ? (
                                <GeneratingTitleLabel />
                              ) : (
                                row.song.title || '—'
                              )}
                            </div>
                            <div className="truncate text-xs text-slate-500">#{row.song.batch_index + 1} · {row.batch.batch_id.slice(0, 8)}</div>
                          </td>
                          <td className="truncate px-3 py-3 align-top">{row.song.description_name || '—'}</td>
                          <td className="truncate px-3 py-3 align-top">{row.song.structure_name || '—'}</td>
                          <td className="px-3 py-3 align-top">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate">{row.batch.ok_profile_name || '—'}</span>
                              <Button
                                className="h-7 w-7 shrink-0 p-0"
                                disabled={!row.song.output_dir_ok}
                                size="sm"
                                type="button"
                                variant="secondary"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  void handleOpenHistoryFolder(row.song.output_dir_ok, 'Primary')
                                }}
                              >
                                <FolderOpen className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </td>
                          <td className="px-3 py-3 align-top">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate">{row.batch.alt_profile_name || '—'}</span>
                              <Button
                                className="h-7 w-7 shrink-0 p-0"
                                disabled={!row.song.output_dir_alt}
                                size="sm"
                                type="button"
                                variant="secondary"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  void handleOpenHistoryFolder(row.song.output_dir_alt, 'Secondary')
                                }}
                              >
                                <FolderOpen className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </td>
                          <td className="px-3 py-3 align-top">
                            <StatusChip status={row.song.suno_status ?? row.song.status} />
                          </td>
                          <td className="px-3 py-3 align-top text-xs text-slate-400">{formatDateTimeLabel(row.song.updated_at)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-white/10 bg-slate-950/30 px-6 text-center text-sm text-slate-400">
                No history rows match the current filters.
              </div>
            )}
          </SectionCard>
        </div>
      ) : null}
    </div>
  )
}
