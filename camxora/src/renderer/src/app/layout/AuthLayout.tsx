import { Link, Outlet, useLocation } from 'react-router-dom'
import { Music4, Video, Workflow } from 'lucide-react'

import { DesktopHeader } from '@/app/layout/DesktopHeader'
import { appLogoUrl } from '@/shared/assets'

export function AuthLayout(): React.JSX.Element {
  const location = useLocation()
  const isRegister = location.pathname === '/auth/register'

  return (
    <div className="h-screen w-screen bg-[#081028] text-slate-50">
      <div className="flex h-full w-full flex-col overflow-hidden border border-white/10 bg-[#081028]">
        <DesktopHeader />

        <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[50%_50%]">
          <section className="flex items-center justify-center border-r border-white/10 bg-[linear-gradient(180deg,rgba(124,58,237,0.98)_0%,rgba(91,33,182,0.98)_42%,rgba(76,29,149,0.98)_100%)] p-10">
            <div className="flex w-full max-w-[520px] flex-col items-start justify-center text-left">
              <img alt="CAMXORA brand" className="h-14 w-14" src={appLogoUrl} />
              <h1 className="mt-6 text-3xl font-semibold leading-tight tracking-tight text-white">
                Your desktop studio starts after web onboarding.
              </h1>
              <p className="mt-4 text-sm leading-6 text-fuchsia-50/85">
                CAMXORA now handles account creation and channel setup in the browser, then the desktop
                app becomes your focused production workspace.
              </p>
              <div className="mt-8 w-full space-y-3">
                {[
                  { icon: Music4, text: 'Web onboarding for smoother account setup' },
                  { icon: Video, text: 'Desktop-first music, image, and video workspace' },
                  { icon: Workflow, text: 'Batch pipelines, exports, and publishing tools' },
                ].map(({ icon: Icon, text }) => (
                  <div
                    key={text}
                    className="flex items-center justify-start gap-3 rounded-2xl border border-white/10 bg-white/10 px-4 py-3"
                  >
                    <Icon className="h-5 w-5 text-white" />
                    <p className="text-sm font-medium text-white">{text}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

        <section className="flex flex-col justify-center gap-6 bg-[#081028] p-6 lg:p-8">
          <div className="mx-auto w-full max-w-[430px]">
            <div className="mb-6 flex items-center gap-3 rounded-2xl border border-white/10 bg-[#060b20] p-2">
            <Link
              className={`flex-1 rounded-xl px-4 py-3 text-center text-sm font-medium transition ${
                !isRegister
                  ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white'
                  : 'text-slate-300 hover:bg-white/5 hover:text-white'
              }`}
              to="/auth/login"
            >
              Login
            </Link>
            <Link
              className={`flex-1 rounded-xl px-4 py-3 text-center text-sm font-medium transition ${
                isRegister
                  ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white'
                  : 'text-slate-300 hover:bg-white/5 hover:text-white'
              }`}
              to="/auth/register"
            >
              Register
            </Link>
            </div>
            <Outlet />
          </div>
        </section>
        </div>
      </div>
    </div>
  )
}
