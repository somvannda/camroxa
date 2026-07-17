import { apiLogout } from '@/shared/api/platformEndpoints'
import { useAuthStore } from '@/shared/auth/sessionStore'
import { useOnboardingStore } from '@/shared/auth/onboardingStore'

export async function logoutCurrentUser(): Promise<void> {
  try {
    await apiLogout()
  } catch {
    // Best-effort revoke; local clear must still happen.
  }

  useOnboardingStore.getState().reset()
  await useAuthStore.getState().clear()
}

