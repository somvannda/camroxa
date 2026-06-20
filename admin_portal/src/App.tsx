import React, { Suspense, Component, type ReactNode, type ErrorInfo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { AuthProvider } from '@/hooks/use-auth';
import { AuthGuard } from '@/components/layout/auth-guard';
import { NavigationShell } from '@/components/layout/navigation-shell';
import { Toaster } from '@/components/ui/toaster';

// Error boundary to catch React render errors
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
          <div className="max-w-lg text-center space-y-4">
            <h1 className="text-xl font-bold text-red-400">Something went wrong</h1>
            <p className="text-sm text-slate-400">{this.state.error?.message}</p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Lazy-loaded page components
const LoginPage = React.lazy(() => import('@/pages/login'));
const DashboardPage = React.lazy(() => import('@/pages/dashboard'));
const UsersPage = React.lazy(() => import('@/pages/users/index'));
const UserDetailPage = React.lazy(() => import('@/pages/users/user-detail'));
const LicensesPage = React.lazy(() => import('@/pages/licenses/index'));
const PlansPage = React.lazy(() => import('@/pages/plans/index'));
const CreditsPage = React.lazy(() => import('@/pages/credits/index'));
const PromptsPage = React.lazy(() => import('@/pages/prompts/index'));
const RateLimitsPage = React.lazy(() => import('@/pages/rate-limits/index'));
const AuditLogPage = React.lazy(() => import('@/pages/audit-log/index'));
const SettingsPage = React.lazy(() => import('@/pages/settings/index'));
const KeyPoolPage = React.lazy(() => import('@/pages/key-pool/index'));

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-700 border-t-blue-500" />
        <p className="text-sm text-slate-400">Loading...</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* Public route */}
                <Route path="/login" element={<LoginPage />} />

                {/* Protected routes */}
                <Route element={<AuthGuard />}>
                  <Route element={<NavigationShell />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/users" element={<UsersPage />} />
                    <Route path="/users/:id" element={<UserDetailPage />} />
                    <Route path="/licenses" element={<LicensesPage />} />
                    <Route path="/plans" element={<PlansPage />} />
                    <Route path="/credits" element={<CreditsPage />} />
                    <Route path="/prompts" element={<PromptsPage />} />
                    <Route path="/rate-limits" element={<RateLimitsPage />} />
                    <Route path="/audit-log" element={<AuditLogPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/key-pool" element={<KeyPoolPage />} />
                  </Route>
                </Route>

                {/* Redirect root to dashboard */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
            <Toaster />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
