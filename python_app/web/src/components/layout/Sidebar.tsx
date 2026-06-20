import React from 'react';
import { cn } from '../../lib/utils';
import {
  LayoutDashboard,
  GitBranch,
  BarChart3,
  Music,
  Image as ImageIcon,
  Film,
  Layers,
  ScrollText,
  Settings,
  Zap,
} from 'lucide-react';
import type { PageKey } from '../../types';

interface SidebarProps {
  currentPage: PageKey;
  onNavigate: (page: PageKey) => void;
}

interface NavItem {
  key: PageKey;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { key: 'home', label: 'Dashboard', icon: <LayoutDashboard className="h-[18px] w-[18px]" /> },
  { key: 'workflow', label: 'Workflow', icon: <GitBranch className="h-[18px] w-[18px]" /> },
  { key: 'progress', label: 'Progress', icon: <BarChart3 className="h-[18px] w-[18px]" /> },
  { key: 'music', label: 'Music', icon: <Music className="h-[18px] w-[18px]" /> },
  { key: 'image', label: 'Image', icon: <ImageIcon className="h-[18px] w-[18px]" /> },
  { key: 'video', label: 'Video', icon: <Film className="h-[18px] w-[18px]" /> },
  { key: 'merger', label: 'Merger', icon: <Layers className="h-[18px] w-[18px]" /> },
  { key: 'log', label: 'Log', icon: <ScrollText className="h-[18px] w-[18px]" /> },
  { key: 'settings', label: 'Settings', icon: <Settings className="h-[18px] w-[18px]" /> },
];

export function Sidebar({ currentPage, onNavigate }: SidebarProps) {
  return (
    <aside className="flex h-full w-[220px] shrink-0 flex-col border-r border-white/5 bg-[#0a0e27]">
      {/* Logo at top */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#6d28d9] to-[#a855f7] shadow-lg shadow-purple-500/20">
          <span className="text-sm font-bold text-white">N</span>
        </div>
        <span className="text-[13px] font-semibold tracking-wide text-white">
          CAMXORA
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive = currentPage === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
              className={cn(
                'group flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-[13px] font-medium transition-all duration-200',
                isActive
                  ? 'bg-gradient-to-r from-[#7c3aed] to-[#a855f7] text-white shadow-lg shadow-purple-500/25'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              )}
            >
              <span className={cn(
                'flex h-5 w-5 items-center justify-center',
                isActive ? 'text-white' : 'text-gray-500 group-hover:text-gray-300'
              )}>
                {item.icon}
              </span>
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Upgrade card */}
      <div className="mx-3 mb-3 rounded-2xl bg-gradient-to-br from-[#1a1f3a] to-[#12162e] p-4 border border-white/5">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#7c3aed] to-[#a855f7] shadow-lg shadow-purple-500/30">
            <Zap className="h-5 w-5 text-white" />
          </div>
        </div>
        <h3 className="text-[13px] font-semibold text-white">Unlock Full Power</h3>
        <p className="mt-1 text-[11px] leading-relaxed text-gray-400">
          Upgrade to Pro and scale your automations.
        </p>
        <button className="mt-3 w-full rounded-xl bg-gradient-to-r from-[#7c3aed] to-[#a855f7] px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-purple-500/25 hover:opacity-90 transition-opacity">
          Upgrade Now
        </button>
      </div>

      {/* User profile + Logout */}
      <div className="border-t border-white/5 p-3">
        <div className="flex items-center gap-3 mb-3">
          <div className="relative">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[#7c3aed] to-[#a855f7] text-[11px] font-bold text-white">
              AM
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[#0a0e27] bg-green-500" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="truncate text-[13px] font-medium text-white">Alex Morgan</div>
            <div className="truncate text-[11px] text-[#a855f7]">Pro Plan</div>
          </div>
        </div>
        <button
          onClick={() => {
            // Logout - navigate back to login
            window.location.reload();
          }}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-[12px] text-gray-400 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20 transition-all"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Logout
        </button>
      </div>
    </aside>
  );
}
