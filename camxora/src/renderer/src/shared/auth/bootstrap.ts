import { apiGetMe, apiListProfiles, apiRefresh } from '@/shared/api/platformEndpoints'
import { useOnboardingStore } from '@/shared/auth/onboardingStore'
import { useAuthStore } from '@/shared/auth/sessionStore'
import { tokensFromTokenResponse } from '@/shared/auth/tokens'

export type BootstrapResult = {
  redirectTo: '/auth/login' | '/auth/complete-setup' | '/app/home'
}

export async function runBootstrap(params: {
  report: (payload: { label: string; detail: string; progress: number }) => void
}): Promise<BootstrapResult> {
  params.report({ label: 'Loading session', detail: 'Reading saved session tokens.', progress: 15 })
  await useAuthStore.getState().hydrate()

  let tokens = useAuthStore.getState().tokens
  if (!tokens?.accessToken || !tokens?.refreshToken) {
    await useAuthStore.getState().clear()
    params.report({ label: 'Opening sign in', detail: 'No session found.', progress: 100 })
    return { redirectTo: '/auth/login' }
  }

  if (Date.now() > tokens.expiresAt - 30_000) {
    params.report({ label: 'Refreshing session', detail: 'Renewing your login session.', progress: 35 })
    try {
      const refreshed = await apiRefresh({ refresh_token: tokens.refreshToken })
      await useAuthStore.getState().setTokens(tokensFromTokenResponse(refreshed))
      tokens = useAuthStore.getState().tokens
    } catch {
      await useAuthStore.getState().clear()
      params.report({ label: 'Opening sign in', detail: 'Session expired.', progress: 100 })
      return { redirectTo: '/auth/login' }
    }
  }

  params.report({ label: 'Validating session', detail: 'Checking account session.', progress: 55 })
  let me
  try {
    me = await apiGetMe()
    await useAuthStore.getState().rememberCurrentAccount({
      id: me.id,
      email: me.email,
      display_name: me.display_name,
    })
    await useOnboardingStore.getState().hydrate({
      expectedEmail: me.email,
      emailVerified: Boolean(me.email_confirmed),
    })
  } catch {
    await useAuthStore.getState().clear()
    params.report({ label: 'Opening sign in', detail: 'Session expired.', progress: 100 })
    return { redirectTo: '/auth/login' }
  }

  params.report({ label: 'Loading profiles', detail: 'Preparing your workspace.', progress: 80 })
  try {
    const profiles = await apiListProfiles()
    if (profiles.length === 0) {
      params.report({
        label: 'Opening setup handoff',
        detail: 'Finish account setup in the web portal before using the desktop studio.',
        progress: 100,
      })
      return { redirectTo: '/auth/complete-setup' }
    }
  } catch {
    params.report({ label: 'Opening studio', detail: 'Continuing with existing session.', progress: 100 })
    return { redirectTo: '/app/home' }
  }

  params.report({ label: 'Opening studio', detail: 'Welcome back.', progress: 100 })
  return { redirectTo: '/app/home' }
}
