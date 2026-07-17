import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { ExternalLink, HelpCircle, LogIn } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { getDesktopApi } from '@/shared/api/desktop'
import { PlatformApiError } from '@/shared/api/platformClient'
import { apiLogin } from '@/shared/api/platformEndpoints'
import { runBootstrap } from '@/shared/auth/bootstrap'
import { switchSavedAccount } from '@/shared/auth/accountTokenStore'
import { useOnboardingStore } from '@/shared/auth/onboardingStore'
import { useAuthStore } from '@/shared/auth/sessionStore'
import { tokensFromTokenResponse } from '@/shared/auth/tokens'
import { getUserPortalUrl } from '@/shared/lib/webLinks'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  password: z.string().min(8, 'Password must be at least 8 characters.'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginPage(): React.JSX.Element {
  const navigate = useNavigate()
  const desktopApi = getDesktopApi()
  const savedAccounts = useAuthStore((state) => state.savedAccounts)
  const hydrate = useAuthStore((state) => state.hydrate)
  const [switchingAccountId, setSwitchingAccountId] = useState<string | null>(null)
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  useEffect(() => {
    void hydrate()
  }, [hydrate])

  return (
    <Card className="p-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-white">Welcome back</h2>
        <p className="text-sm text-slate-400">Sign in to continue to your studio</p>
      </div>

      {form.formState.errors.root?.message ? (
        <div className="mt-5 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {form.formState.errors.root.message}
        </div>
      ) : null}

      {savedAccounts.length > 0 ? (
        <div className="mt-5 space-y-2">
          <p className="text-sm text-slate-400">Continue as</p>
          <div className="space-y-2">
            {savedAccounts.map((account) => (
              <Button
                key={account.userId}
                className="w-full justify-start"
                disabled={Boolean(switchingAccountId) || form.formState.isSubmitting}
                type="button"
                variant="secondary"
                onClick={() => {
                  void (async () => {
                    setSwitchingAccountId(account.userId)
                    form.clearErrors('root')
                    try {
                      const switched = await switchSavedAccount(account.userId)
                      if (!switched) {
                        form.setError('root', { message: 'Saved session not found for this account.' })
                        return
                      }
                      await hydrate()
                      const result = await runBootstrap({ report: () => undefined })
                      navigate(result.redirectTo, { replace: true })
                    } catch (error) {
                      const message =
                        error instanceof PlatformApiError
                          ? error.message
                          : 'Unable to switch accounts right now.'
                      form.setError('root', { message })
                    } finally {
                      setSwitchingAccountId(null)
                    }
                  })()
                }}
              >
                {account.displayName || account.email || account.userId}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      <form
        className="mt-6 space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          form.clearErrors('root')
          try {
            useOnboardingStore.getState().reset()
            const tokens = await apiLogin(values)
            await useAuthStore.getState().setTokens(tokensFromTokenResponse(tokens))
            const result = await runBootstrap({ report: () => undefined })
            navigate(result.redirectTo, { replace: true })
          } catch (error) {
            const message =
              error instanceof PlatformApiError ? error.message : 'Unable to sign in right now.'
            form.setError('root', { message })
          }
        })}
      >
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-200" htmlFor="login-email">
            Email
          </label>
          <Input id="login-email" placeholder="Enter your email" {...form.register('email')} />
          <p className="text-xs text-rose-300">{form.formState.errors.email?.message}</p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-200" htmlFor="login-password">
            Password
          </label>
          <Input
            id="login-password"
            type="password"
            placeholder="Enter your password"
            {...form.register('password')}
          />
          <p className="text-xs text-rose-300">{form.formState.errors.password?.message}</p>
        </div>

        <div className="flex justify-end">
          <button
            className="inline-flex items-center gap-2 text-sm font-medium text-fuchsia-300 transition hover:text-fuchsia-200"
            type="button"
          >
            <HelpCircle className="h-4 w-4" />
            Forgot password?
          </button>
        </div>

        <Button className="w-full" disabled={form.formState.isSubmitting} type="submit" variant="primary">
          <LogIn className="h-4 w-4" />
          Sign In
        </Button>

        <Button
          className="w-full"
          type="button"
          variant="secondary"
          onClick={() => void desktopApi.files.openExternalUrl(getUserPortalUrl('/register'))}
        >
          <ExternalLink className="h-4 w-4" />
          Create account on the web
        </Button>
      </form>
    </Card>
  )
}
