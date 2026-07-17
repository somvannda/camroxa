import { ExternalLink, LogOut, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiGetMe, apiListProfiles } from '@/shared/api/platformEndpoints'
import { logoutCurrentUser } from '@/shared/auth/logout'
import { getDesktopApi } from '@/shared/api/desktop'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { getUserPortalUrl } from '@/shared/lib/webLinks'

export function CompleteSetupPage(): React.JSX.Element {
  const navigate = useNavigate()
  const desktopApi = getDesktopApi()
  const [isOpening, setIsOpening] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const onboardingUrl = getUserPortalUrl('/onboarding')

  async function handleOpenPortal(): Promise<void> {
    setIsOpening(true)
    setMessage(null)
    try {
      const opened = await desktopApi.files.openExternalUrl(onboardingUrl)
      setMessage(
        opened
          ? 'User portal opened in your browser. Finish setup there, then come back and refresh.'
          : `We could not open the browser automatically. Open this URL manually: ${onboardingUrl}`,
      )
    } finally {
      setIsOpening(false)
    }
  }

  async function handleRefresh(): Promise<void> {
    setIsChecking(true)
    setMessage(null)
    try {
      const [me, profiles] = await Promise.all([apiGetMe(), apiListProfiles()])
      if (!me.email_confirmed) {
        setMessage('Your email is not verified yet. Finish verification in the user portal first.')
        return
      }
      if (profiles.length === 0) {
        setMessage('No channel profiles found yet. Complete onboarding in the user portal, then refresh here.')
        return
      }
      navigate('/app/home', { replace: true })
    } catch {
      setMessage('We could not refresh your setup state right now. Try again in a moment.')
    } finally {
      setIsChecking(false)
    }
  }

  async function handleSignOut(): Promise<void> {
    setIsSigningOut(true)
    try {
      await logoutCurrentUser()
      navigate('/auth/login', { replace: true })
    } finally {
      setIsSigningOut(false)
    }
  }

  return (
    <Card className="p-6">
      <div className="space-y-2">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
          <Sparkles className="h-6 w-6" />
        </div>
        <h2 className="text-2xl font-semibold text-white">Complete setup on the web</h2>
        <p className="text-sm text-slate-400">
          CAMXORA onboarding now lives in the user portal so account setup is easier and more polished.
          After that, this desktop app stays focused on studio work.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border border-white/10 bg-[#081028] p-4">
        <p className="text-sm font-medium text-white">Next steps</p>
        <ol className="mt-3 space-y-2 text-sm text-slate-300">
          <li>1. Open the user portal.</li>
          <li>2. Verify your email if needed.</li>
          <li>3. Create your primary and secondary profiles.</li>
          <li>4. Return here and refresh.</li>
        </ol>
      </div>

      {message ? (
        <div className="mt-5 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
          {message}
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-3">
        <Button className="w-full" disabled={isOpening} onClick={() => void handleOpenPortal()} variant="primary">
          <ExternalLink className="h-4 w-4" />
          {isOpening ? 'Opening portal...' : 'Open user portal'}
        </Button>

        <Button className="w-full" disabled={isChecking} onClick={() => void handleRefresh()} variant="secondary">
          <RefreshCw className={`h-4 w-4 ${isChecking ? 'animate-spin' : ''}`} />
          {isChecking ? 'Checking setup...' : 'I finished setup, refresh'}
        </Button>

        <Button className="w-full" disabled={isSigningOut} onClick={() => void handleSignOut()} variant="ghost">
          <LogOut className="h-4 w-4" />
          {isSigningOut ? 'Signing out...' : 'Sign out'}
        </Button>
      </div>

      <div className="mt-4 text-xs text-slate-500">{onboardingUrl}</div>
    </Card>
  )
}

