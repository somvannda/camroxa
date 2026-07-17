import { apiRefresh } from '@/shared/api/platformEndpoints'
import { useAuthStore } from '@/shared/auth/sessionStore'
import { tokensFromTokenResponse } from '@/shared/auth/tokens'

let refreshPromise: Promise<boolean> | null = null

export async function ensureFreshSession(force = false): Promise<boolean> {
  const tokens = useAuthStore.getState().tokens
  if (!tokens?.refreshToken) {
    return false
  }

  const shouldRefresh = force || Date.now() > tokens.expiresAt - 120_000
  if (!shouldRefresh) {
    return true
  }

  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    try {
      const refreshed = await apiRefresh({ refresh_token: tokens.refreshToken })
      await useAuthStore.getState().setTokens(tokensFromTokenResponse(refreshed))
      return true
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}
