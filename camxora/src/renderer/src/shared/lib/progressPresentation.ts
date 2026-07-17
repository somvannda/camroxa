import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'

export function shortBatchLabel(batch: string): string {
  const text = String(batch || '').trim()
  if (text.length <= 12) {
    return text
  }
  return `…${text.slice(-8)}`
}

export function formatChannelLabel(channel: string, role: string): string {
  const name = String(channel || '').trim() || 'Unknown'
  const roleKey = String(role || '').trim().toUpperCase() || '—'
  return `${name} · ${roleKey}`
}

export function formatMusicCompact(row: ProgressRowResponse): string {
  const base = String(row.music || '').trim() || `${row.meta.saved}/${Math.max(1, row.meta.expected)}`
  if (row.meta.download_pending > 0) {
    return `${base} ↓`
  }
  if (row.meta.saved >= Math.max(1, row.meta.expected)) {
    return `${base} ✓`
  }
  return base
}

function imageBadge(ready: number, total: number, status: string, label: string): string {
  const normalized = String(status || '').trim().toUpperCase()
  const count = `${ready}/${Math.max(1, total)}`
  if (normalized === 'READY' || (total > 0 && ready >= total)) {
    return `${label} ${count} ✓`
  }
  if (normalized === 'FAILED') {
    return `${label} ${count} ✗`
  }
  if (normalized === 'PENDING' || normalized === 'RUNNING' || normalized === 'PROCESSING') {
    return `${label} ${count} …`
  }
  return `${label} ${count}`
}

export function formatImagesCompact(row: ProgressRowResponse): string {
  const meta = row.meta
  return `${imageBadge(meta.bg_ready, meta.bg_total, meta.bg_status, 'BG')} · ${imageBadge(meta.th_ready, meta.th_total, meta.th_status, 'TH')}`
}

export function formatVideoCompact(converter: string, merge: string): string {
  let converterText = String(converter || '').trim()
  let mergeText = String(merge || '').trim()
  if (converterText.toLowerCase().startsWith('pending api parity')) {
    converterText = '—'
  }
  if (mergeText.toLowerCase().startsWith('pending api parity')) {
    mergeText = '—'
  }
  if (!converterText && !mergeText) {
    return '—'
  }
  if (!mergeText || mergeText === '—') {
    return converterText
  }
  if (!converterText || converterText === '—') {
    return mergeText
  }
  return `${converterText} · ${mergeText}`
}

export function formatYoutubeCompact(row: ProgressRowResponse): string {
  const text = String(row.youtube || '').trim()
  if (!text || text === '—') {
    const meta = row.meta
    if (meta.youtube_success > 0) {
      return 'Ready ✓'
    }
    if (meta.youtube_failed > 0) {
      return 'Failed ✗'
    }
    if (meta.youtube_pending > 0) {
      return 'Uploading …'
    }
    if (String(meta.youtube_status || '').toUpperCase() === 'BLOCKED') {
      return 'Blocked'
    }
    return '—'
  }
  if (text.toLowerCase() === 'ready') {
    return 'Ready ✓'
  }
  if (text.toLowerCase() === 'failed') {
    return 'Failed ✗'
  }
  if (text.toLowerCase() === 'uploading' || text.toLowerCase() === 'queued') {
    return `${text} …`
  }
  return text
}

export function stageStatusTone(stage: string, status: string): 'default' | 'success' | 'warning' | 'danger' {
  const stageKey = String(stage || '').trim().toLowerCase()
  const statusKey = String(status || '').trim().toLowerCase()
  if (stageKey === 'error' || statusKey === 'failed') {
    return 'danger'
  }
  if (stageKey === 'done' || statusKey === 'done') {
    return 'success'
  }
  if (
    statusKey === 'running' ||
    statusKey === 'rendering' ||
    statusKey === 'generating' ||
    statusKey === 'downloading' ||
    statusKey === 'converting' ||
    statusKey === 'merging' ||
    statusKey === 'uploading'
  ) {
    return 'warning'
  }
  return 'default'
}
