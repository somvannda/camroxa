import { type PropsWithChildren, useEffect } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuthStore } from '@/shared/auth/sessionStore'

export function RequireAuth({ children }: PropsWithChildren): React.JSX.Element {
  const tokens = useAuthStore((state) => state.tokens)
  const hydrated = useAuthStore((state) => state.hydrated)
  const hydrate = useAuthStore((state) => state.hydrate)

  useEffect(() => {
    if (!hydrated) {
      void hydrate()
    }
  }, [hydrated, hydrate])

  if (!hydrated) {
    return <div />
  }

  if (!tokens?.accessToken) {
    return <Navigate replace to="/auth/login" />
  }

  return <>{children}</>
}

