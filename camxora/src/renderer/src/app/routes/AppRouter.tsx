import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShellLayout } from '@/app/layout/AppShellLayout'
import { AuthLayout } from '@/app/layout/AuthLayout'
import { CompleteSetupPage } from '@/features/auth/CompleteSetupPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { ImageWorkspacePage } from '@/features/image/ImageWorkspacePage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { MusicWorkspacePage } from '@/features/music/MusicWorkspacePage'
import { SettingsWorkspacePage } from '@/features/settings/SettingsWorkspacePage'
import { HomePage } from '@/features/shell/HomePage'
import { PlaceholderPage } from '@/features/shell/PlaceholderPage'
import { ProfilePage } from '@/features/shell/ProfilePage'
import { ProgressPage } from '@/features/shell/ProgressPage'
import { WorkflowPage } from '@/features/shell/WorkflowPage'
import { StartupPage } from '@/features/startup/StartupPage'
import { VideoExportHostPage } from '@/features/video/VideoExportHostPage'
import { VideoWorkspacePage } from '@/features/video/VideoWorkspacePage'
import { RequireAuth } from '@/shared/auth/RequireAuth'
import { SessionKeepAlive } from '@/shared/auth/SessionKeepAlive'

export function AppRouter(): React.JSX.Element {
  const defaultRoute = '/startup'

  return (
    <HashRouter>
      <SessionKeepAlive />
      <Routes>
        <Route path="/" element={<Navigate replace to={defaultRoute} />} />
        <Route path="/export-host" element={<VideoExportHostPage />} />
        <Route path="/startup" element={<StartupPage />} />
        <Route path="/auth" element={<AuthLayout />}>
          <Route index element={<Navigate replace to="/auth/login" />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route
            path="complete-setup"
            element={
              <RequireAuth>
                <CompleteSetupPage />
              </RequireAuth>
            }
          />
        </Route>
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppShellLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate replace to="/app/home" />} />
          <Route path="home" element={<HomePage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="progress" element={<ProgressPage />} />
          <Route path="music" element={<MusicWorkspacePage />} />
          <Route path="image" element={<ImageWorkspacePage />} />
          <Route path="video" element={<VideoWorkspacePage />} />
          <Route
            path="video-py"
            element={
              <PlaceholderPage
                description="The native Python video workspace entry is not currently bundled in this renderer build."
                eyebrow="Reserved route"
                title="Video (Py)"
              />
            }
          />
          <Route
            path="merger"
            element={
              <PlaceholderPage
                description="This route is reserved for later parity with the Python merger flow."
                eyebrow="Reserved route"
                title="Merger"
              />
            }
          />
          <Route path="settings" element={<SettingsWorkspacePage />} />
          <Route
            path="log"
            element={
              <PlaceholderPage
                description="Runtime logs and diagnostics will be surfaced here for long desktop sessions."
                eyebrow="Reserved route"
                title="Log"
              />
            }
          />
        </Route>
        <Route path="*" element={<Navigate replace to={defaultRoute} />} />
      </Routes>
    </HashRouter>
  )
}
