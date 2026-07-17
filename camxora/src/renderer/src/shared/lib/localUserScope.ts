const LAST_USER_ID_KEY = 'camxora.auth.lastUserId'

export function scopedStorageKey(prefix: string, userId: string | null | undefined): string {
  const normalized = String(userId ?? '').trim()
  if (!normalized) {
    return prefix
  }
  return `${prefix}.${normalized}`
}

export { LAST_USER_ID_KEY }
