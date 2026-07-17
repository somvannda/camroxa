import { useEffect } from 'react'

import { ensureFreshSession } from '@/shared/auth/authRefresh'
import { useAuthStore } from '@/shared/auth/sessionStore'

export function SessionKeepAlive(): null {
  const tokens = useAuthStore((state) => state.tokens)

  useEffect(() => {
    if (!tokens?.refreshToken) {
      return
    }

    const refreshNow = () => {
      void ensureFreshSession()
    }

    refreshNow()
    const intervalId = window.setInterval(refreshNow, 60_000)
    const handleFocus = () => {
      void ensureFreshSession()
    }

    window.addEventListener('focus', handleFocus)
    document.addEventListener('visibilitychange', handleFocus)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('focus', handleFocus)
      document.removeEventListener('visibilitychange', handleFocus)
    }
  }, [tokens?.refreshToken, tokens?.expiresAt])

  return null
}
