import { getDesktopApi } from '@/shared/api/desktop'

export type SavedAccount = {
  userId: string
  email: string
  displayName: string
}

const ACCOUNTS_INDEX_KEY = 'camxora.auth.accounts'
const ACTIVE_ACCOUNT_ID_KEY = 'camxora.auth.activeAccountId'
const TOKENS_STORAGE_KEY = 'camxora.auth.tokens'

function tokenKey(userId: string): string {
  return `camxora.auth.tokens.${userId}`
}

function parseAccounts(raw: string | null): SavedAccount[] {
  if (!raw) {
    return []
  }
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return []
    }
    const accounts: SavedAccount[] = []
    for (const item of parsed) {
      if (!item || typeof item !== 'object') {
        continue
      }
      const record = item as Record<string, unknown>
      const userId = String(record.userId ?? record.user_id ?? '').trim()
      if (!userId) {
        continue
      }
      accounts.push({
        userId,
        email: String(record.email ?? '').trim(),
        displayName: String(record.displayName ?? record.display_name ?? '').trim(),
      })
    }
    return accounts
  } catch {
    return []
  }
}

export async function listSavedAccounts(): Promise<SavedAccount[]> {
  const raw = await getDesktopApi().secureStorage.get(ACCOUNTS_INDEX_KEY)
  return parseAccounts(raw)
}

export async function rememberAccount(params: {
  userId: string
  email: string
  displayName: string
  tokensJson: string
}): Promise<void> {
  const normalizedId = String(params.userId).trim()
  if (!normalizedId) {
    return
  }
  const storage = getDesktopApi().secureStorage
  await storage.set(tokenKey(normalizedId), params.tokensJson)
  await storage.set(ACTIVE_ACCOUNT_ID_KEY, normalizedId)
  const accounts = (await listSavedAccounts()).filter((item) => item.userId !== normalizedId)
  accounts.unshift({
    userId: normalizedId,
    email: String(params.email ?? '').trim(),
    displayName: String(params.displayName ?? '').trim() || String(params.email ?? '').trim(),
  })
  const payload = accounts.slice(0, 8).map((item) => ({
    userId: item.userId,
    email: item.email,
    displayName: item.displayName,
  }))
  await storage.set(ACCOUNTS_INDEX_KEY, JSON.stringify(payload))
}

export async function loadSavedTokens(userId: string): Promise<string | null> {
  return getDesktopApi().secureStorage.get(tokenKey(String(userId).trim()))
}

export async function getActiveAccountId(): Promise<string | null> {
  const value = await getDesktopApi().secureStorage.get(ACTIVE_ACCOUNT_ID_KEY)
  const normalized = String(value ?? '').trim()
  return normalized || null
}

export async function switchSavedAccount(userId: string): Promise<boolean> {
  const tokensJson = await loadSavedTokens(userId)
  if (!tokensJson) {
    return false
  }
  const storage = getDesktopApi().secureStorage
  await storage.set(TOKENS_STORAGE_KEY, tokensJson)
  await storage.set(ACTIVE_ACCOUNT_ID_KEY, String(userId).trim())
  return true
}

export { ACCOUNTS_INDEX_KEY, ACTIVE_ACCOUNT_ID_KEY, TOKENS_STORAGE_KEY }
