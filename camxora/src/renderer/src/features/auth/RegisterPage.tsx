import { ExternalLink, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

import { getDesktopApi } from '@/shared/api/desktop'
import { getUserPortalUrl } from '@/shared/lib/webLinks'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'

export function RegisterPage(): React.JSX.Element {
  const desktopApi = getDesktopApi()

  return (
    <Card className="p-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-white">Create your account on the web</h2>
        <p className="text-sm text-slate-400">
          Registration, email verification, and onboarding now live in the user portal. Once that is
          done, come back here and sign in to the desktop studio.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border border-white/10 bg-[#081028] p-4">
        <p className="text-sm font-medium text-white">What changed</p>
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <p>1. Create your account in the browser.</p>
          <p>2. Finish the onboarding wizard there.</p>
          <p>3. Return to CAMXORA and sign in.</p>
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-3">
        <Button
          className="w-full"
          type="button"
          onClick={() => void desktopApi.files.openExternalUrl(getUserPortalUrl('/register'))}
        >
          <ExternalLink className="h-4 w-4" />
          Open user portal registration
        </Button>
        <Button asChild className="w-full" type="button" variant="ghost">
          <Link to="/auth/login">
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </Button>
      </div>
    </Card>
  )
}
