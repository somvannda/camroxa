import type { TokenResponse } from '@/shared/api/platformEndpoints'
import type { AuthTokens } from '@/shared/auth/sessionStore'

export function tokensFromTokenResponse(response: TokenResponse): AuthTokens {
  const expiresAt = Date.now() + Math.max(0, response.expires_in) * 1000
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    tokenType: response.token_type,
    expiresAt,
  }
}

