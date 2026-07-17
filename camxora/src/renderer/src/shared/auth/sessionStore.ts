import { create } from 'zustand'

import { getDesktopApi } from '@/shared/api/desktop'
import {
  ACTIVE_ACCOUNT_ID_KEY,
  getActiveAccountId,
  listSavedAccounts,
  rememberAccount,
  type SavedAccount,
  TOKENS_STORAGE_KEY,
} from '@/shared/auth/accountTokenStore'

export type AuthTokens = {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresAt: number
}

type AuthState = {
  hydrated: boolean
  tokens: AuthTokens | null
  activeUserId: string | null
  savedAccounts: SavedAccount[]
  hydrate: () => Promise<void>
  setTokens: (tokens: AuthTokens) => Promise<void>
  rememberCurrentAccount: (profile: { id: string; email: string; display_name?: string | null }) => Promise<void>
  clear: () => Promise<void>
}

function parseTokens(raw: string | null): AuthTokens | null {
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as AuthTokens
    if (!parsed?.accessToken || !parsed?.refreshToken) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  hydrated: false,
  tokens: null,
  activeUserId: null,
  savedAccounts: [],
  hydrate: async () => {
    const raw = await getDesktopApi().secureStorage.get(TOKENS_STORAGE_KEY)
    const tokens = parseTokens(raw)
    const [activeUserId, savedAccounts] = await Promise.all([getActiveAccountId(), listSavedAccounts()])
    set({ hydrated: true, tokens, activeUserId, savedAccounts })
  },
  setTokens: async (tokens) => {
    await getDesktopApi().secureStorage.set(TOKENS_STORAGE_KEY, JSON.stringify(tokens))
    set({ tokens })
  },
  rememberCurrentAccount: async (profile) => {
    const tokens = get().tokens
    if (!tokens) {
      return
    }
    await rememberAccount({
      userId: profile.id,
      email: profile.email,
      displayName: profile.display_name ?? profile.email,
      tokensJson: JSON.stringify(tokens),
    })
    const [activeUserId, savedAccounts] = await Promise.all([getActiveAccountId(), listSavedAccounts()])
    set({ activeUserId, savedAccounts })
  },
  clear: async () => {
    await getDesktopApi().secureStorage.remove(TOKENS_STORAGE_KEY)
    if (get().tokens) {
      set({ tokens: null, activeUserId: null })
    }
  },
}))

export { ACTIVE_ACCOUNT_ID_KEY }

