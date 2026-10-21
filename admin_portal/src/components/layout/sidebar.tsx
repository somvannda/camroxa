import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  KeyRound,
  CreditCard,
  TicketPercent,
  Coins,
  Music,
  Gauge,
  ScrollText,
  FileText,
  BarChart3,
  DollarSign,
  UserPlus,
  Newspaper,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  KeySquare,
  Library,
  Image,
  Sparkles,
  Store,
  Radio,
  UploadCloud,
  Shield,
  Bell,
  Download,
  LogOut,
  ListOrdered,
  Activity,
  Wallet,
} from 'lucide-react';
import { Mail } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useAuth } from '@/hooks/use-auth';

interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'Accounts',
    items: [
      { label: 'Users', path: '/users', icon: Users },
      { label: 'Subscriptions', path: '/licenses', icon: KeyRound },
      { label: 'Plans', path: '/plans', icon: CreditCard },
      { label: 'Redeem Codes', path: '/redeem-codes', icon: TicketPercent },
  { label: 'Mail', path: '/mail', icon: Mail },
      { label: 'Invitations', path: '/invitations', icon: UserPlus },
    ],
  },
  {
    label: 'Billing',
    items: [
      { label: 'Credits', path: '/credits', icon: Coins },
      { label: 'Usage', path: '/usage', icon: BarChart3 },
      { label: 'User Spent', path: '/user-spent', icon: Wallet },
      { label: 'Finance', path: '/finance', icon: DollarSign },
    ],
  },
  {
    label: 'Content',
    items: [
      { label: 'Blog Posts', path: '/blog-posts', icon: Newspaper },
      { label: 'Music Prompts', path: '/prompts', icon: Music },
      { label: 'Content Pools', path: '/content-pools', icon: Library },
      { label: 'Image Packs', path: '/image-sample-packs', icon: Image },
      { label: 'Marketplace', path: '/marketplace', icon: Store },
    ],
  },
  {
    label: 'Operations',
    items: [
      { label: 'Music Streaming', path: '/streaming', icon: Radio },
      { label: 'Streaming Jobs', path: '/streaming/upload-jobs', icon: UploadCloud },
      { label: 'Playback Audit', path: '/streaming/playback-audit', icon: Shield },
      { label: 'Rate Limits', path: '/rate-limits', icon: Gauge },
      { label: 'Key Pool', path: '/key-pool', icon: KeySquare },
      { label: 'Job Queue', path: '/job-queue', icon: ListOrdered },
      { label: 'Pipeline Ops', path: '/pipeline', icon: Activity },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Audit Log', path: '/audit-log', icon: ScrollText },
      { label: 'Client Logs', path: '/client-logs', icon: FileText },
      { label: 'Desktop Notifications', path: '/desktop-notifications', icon: Bell },
      { label: 'Software Updates', path: '/software-updates', icon: Download },
      { label: 'Settings', path: '/settings', icon: Settings },
    ],
  },
];

function isNavItemActive(pathname: string, path: string): boolean {
  if (path === '/streaming') {
    return pathname === '/streaming';
  }
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-white/10 bg-slate-950/80 backdrop-blur-xl transition-all duration-200',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      <div
        className={cn(
          'flex h-16 items-center px-3',
          collapsed ? 'justify-center' : 'justify-between'
        )}
      >
        {!collapsed && (
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-violet-300/20 bg-gradient-to-br from-fuchsia-600/28 via-violet-500/24 to-indigo-500/24 text-violet-100">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-slate-100">Admin Portal</div>
                <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                  Control center
                </div>
              </div>
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed((prev) => !prev)}
          className="h-9 w-9 text-slate-400 hover:bg-slate-800/80 hover:text-white"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </Button>
      </div>

      <Separator className="bg-white/8" />

      <nav className="flex flex-1 flex-col gap-3 p-2 overflow-y-auto">
        {NAV_GROUPS.map((group, groupIndex) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            {collapsed ? (
              groupIndex > 0 && (
                <Separator className="my-1 bg-white/8" />
              )
            ) : (
              <div className="px-2.5 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {group.label}
              </div>
            )}
            {group.items.map((item) => {
              const isActive = isNavItemActive(location.pathname, item.path);
              const Icon = item.icon;

              const linkContent = (
                <Link
                  to={item.path}
                  className={cn(
                    'flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-all duration-150',
                    isActive
                      ? 'bg-gradient-to-r from-fuchsia-600/18 via-violet-500/16 to-indigo-500/16 text-white shadow-[inset_0_0_0_1px_rgba(167,139,250,0.24)]'
                      : 'text-slate-400 hover:bg-slate-900/90 hover:text-slate-100',
                    collapsed && 'justify-center px-0'
                  )}
                >
                  <div
                    className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors',
                      isActive
                        ? 'text-violet-200'
                        : 'text-slate-500'
                    )}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                  </div>
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );

              if (collapsed) {
                return (
                  <Tooltip key={item.path} delayDuration={0}>
                    <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                    <TooltipContent side="right">
                      <p>{item.label}</p>
                    </TooltipContent>
                  </Tooltip>
                );
              }

              return <div key={item.path}>{linkContent}</div>;
            })}
          </div>
        ))}
      </nav>

      <Separator className="bg-white/8" />

      <div className="p-2">
        <LogoutButton collapsed={collapsed} />
      </div>
    </aside>
  );
}

function LogoutButton({ collapsed }: { collapsed: boolean }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const content = (
    <button
      onClick={handleLogout}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-red-400 transition-all duration-150 hover:bg-red-950/40 hover:text-red-300',
        collapsed && 'justify-center px-0'
      )}
    >
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md">
        <LogOut className="h-3.5 w-3.5" />
      </div>
      {!collapsed && <span>Logout</span>}
    </button>
  );

  if (collapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right"><p>Logout</p></TooltipContent>
      </Tooltip>
    );
  }

  return content;
}
