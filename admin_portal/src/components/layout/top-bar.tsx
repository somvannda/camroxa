import { useLocation } from 'react-router-dom';
import { LogOut, Search, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { useHealthStatus } from '@/hooks/use-dashboard';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  deploymentEnvironmentBadgeClass,
  resolveDeploymentEnvironmentLabel,
} from '@/lib/deployment-environment';
import { cn } from '@/lib/utils';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/users': 'Users',
  '/licenses': 'Subscriptions',
  '/plans': 'Plans',
  '/redeem-codes': 'Redeem Codes',
  '/mail': 'Mail',
  '/credits': 'Credits',
  '/usage': 'Usage',
  '/user-spent': 'User Spent',
  '/finance': 'Finance',
  '/invitations': 'Invitations',
  '/blog-posts': 'Blog Posts',
  '/batches': 'Batch trace',
  '/songs': 'Song trace',
  '/prompts': 'Music Prompts',
  '/rate-limits': 'Rate Limits',
  '/key-pool': 'Key Pool',
  '/job-queue': 'Job Queue',
  '/pipeline': 'Pipeline Ops',
  '/content-pools': 'Content Pools',
  '/image-sample-packs': 'Image Packs',
  '/marketplace': 'Marketplace',
  '/streaming/upload-jobs': 'Streaming Jobs',
  '/streaming': 'Music Streaming',
  '/audit-log': 'Audit Log',
  '/client-logs': 'Client Logs',
  '/desktop-notifications': 'Desktop Notifications',
  '/software-updates': 'Software Updates',
  '/settings': 'Settings',
};

export function TopBar() {
  const { adminEmail, logout } = useAuth();
  const location = useLocation();
  const healthQuery = useHealthStatus();
  const pageTitle =
    Object.entries(PAGE_TITLES).find(([path]) => location.pathname.startsWith(path))?.[1] ??
    'Admin Portal';
  const environmentLabel = resolveDeploymentEnvironmentLabel({
    apiEnvironment: healthQuery.data?.environment,
    apiEnvironmentLabel: healthQuery.data?.environment_label,
    hostname: typeof window !== 'undefined' ? window.location.hostname : '',
  });

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-slate-950/70 px-5 backdrop-blur-xl lg:px-6">
      <div className="min-w-0">
        <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-violet-300/80">
          Admin control
        </div>
        <div className="truncate text-sm font-medium text-slate-100">{pageTitle}</div>
      </div>

      <div className="flex items-center gap-3">
        <Badge
          variant="outline"
          className={cn(
            'hidden text-[10px] font-semibold uppercase tracking-wide sm:inline-flex',
            deploymentEnvironmentBadgeClass(environmentLabel),
          )}
          title="API environment for this admin portal"
        >
          {environmentLabel}
        </Badge>
        <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-400 md:flex">
          <Search className="h-3.5 w-3.5 text-slate-500" />
          Command and global search coming next
        </div>
        <div className="hidden items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 xl:flex">
          <ShieldCheck className="h-3.5 w-3.5" />
          Admin session
        </div>
        {adminEmail && (
          <div className="hidden min-w-0 rounded-full border border-white/10 bg-slate-900/80 px-3 py-1.5 md:block">
            <div className="truncate text-xs font-medium text-slate-200">{adminEmail}</div>
            <div className="text-[11px] text-slate-500">Authenticated administrator</div>
          </div>
        )}
        <Separator orientation="vertical" className="h-7 bg-white/10" />
        <Button
          variant="ghost"
          size="sm"
          onClick={logout}
          className="gap-2 text-slate-300 hover:bg-slate-800/80 hover:text-white"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </Button>
      </div>
    </header>
  );
}
