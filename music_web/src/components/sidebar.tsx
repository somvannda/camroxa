'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  ArrowRight,
  Home,
  ListMusic,
  Lock,
  Menu,
  Plus,
  Shield,
  Sparkles,
  X,
} from 'lucide-react';

import BrandLockup from '@/components/brand-lockup';
import { useAuth } from '@/components/auth-provider';
import CreditHeader from '@/components/credit-header';
import { cn } from '@/lib/cn';
import { getWebsiteBaseUrl } from '@/lib/site-urls';

const links = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/explore', label: 'Explore', icon: Sparkles },
  { href: '/create', label: 'Create', icon: Plus },
  { href: '/playlists', label: 'Playlists', icon: ListMusic },
];

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="space-y-2">
      {links.map(({ href, label, icon: Icon }) => {
        const active =
          href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              'flex items-center justify-between rounded-[7px] border px-4 py-3 text-sm transition',
              active
                ? 'border-violet-400/25 bg-violet-500/[0.12] text-white'
                : 'border-white/8 bg-white/[0.03] text-slate-200/78 hover:border-violet-400/25 hover:bg-violet-500/[0.08] hover:text-white',
            )}
          >
            <span className="flex items-center gap-3">
              <Icon className="h-4 w-4 text-violet-200" />
              {label}
            </span>
            <ArrowRight className="h-4 w-4 text-slate-500" />
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarFooter({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();

  return (
    <div className="rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(14,20,50,0.96),rgba(8,12,28,0.98))] p-3 shadow-[0_24px_80px_rgba(15,22,58,0.34)]">
      <div className="space-y-1 text-sm">
        <button
          type="button"
          disabled
          className="flex w-full items-center gap-3 rounded-[7px] px-3 py-2.5 text-left text-slate-500"
          title="Coming soon"
        >
          <Lock className="h-4 w-4" />
          Invite friends
        </button>
        <Link
          href={`${getWebsiteBaseUrl()}/privacy`}
          onClick={onNavigate}
          className="flex items-center gap-3 rounded-[7px] px-3 py-2.5 text-slate-300/80 transition hover:bg-white/[0.05] hover:text-white"
        >
          <Shield className="h-4 w-4" />
          Privacy and more
        </Link>
      </div>

      {user ? (
        <div className="mt-3 border-t border-white/8 pt-3">
          <CreditHeader variant="sidebar" />
        </div>
      ) : null}
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [mobileOpen]);

  return (
    <>
      <aside className="hidden h-full w-72 shrink-0 flex-col border-r border-white/8 bg-[linear-gradient(180deg,rgba(5,10,28,0.96),rgba(3,7,20,0.98))] shadow-[24px_0_64px_rgba(2,6,23,0.42)] backdrop-blur-xl md:flex">
        <div className="flex h-16 shrink-0 items-center border-b border-white/8 bg-white/[0.02] px-5">
          <BrandLockup />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 music-scroll">
          <div className="rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(14,20,50,0.96),rgba(8,12,28,0.98))] p-3 shadow-[0_24px_80px_rgba(15,22,58,0.34)]">
            <SidebarNav />
          </div>
        </div>
        <div className="shrink-0 p-4 pb-5 pt-1">
          <SidebarFooter />
        </div>
      </aside>

      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="fixed left-3 z-[60] inline-flex h-12 w-12 items-center justify-center rounded-[7px] bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_12px_28px_rgba(118,77,255,0.45)] md:hidden"
        style={{ bottom: 'var(--music-fab-bottom)' }}
        aria-label="Open menu"
        aria-expanded={mobileOpen}
      >
        <Menu className="h-5 w-5" />
      </button>

      {mobileOpen ? (
        <div className="fixed inset-0 z-[80] md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-[min(20rem,88vw)] flex-col border-r border-white/8 bg-[linear-gradient(180deg,rgba(5,10,28,0.98),rgba(3,7,20,1))] shadow-[24px_0_64px_rgba(2,6,23,0.55)]">
            <div className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-white/8 px-4">
              <BrandLockup compact onClick={() => setMobileOpen(false)} />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-200"
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4 music-scroll">
              <div className="rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(14,20,50,0.96),rgba(8,12,28,0.98))] p-3">
                <SidebarNav onNavigate={() => setMobileOpen(false)} />
              </div>
            </div>
            <div className="shrink-0 p-4 pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))]">
              <SidebarFooter onNavigate={() => setMobileOpen(false)} />
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
