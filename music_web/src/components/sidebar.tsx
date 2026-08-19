'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ArrowRight,
  Home,
  ListMusic,
  Lock,
  Plus,
  Shield,
  Sparkles,
} from 'lucide-react';

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

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <>
      <aside className="hidden h-full w-72 shrink-0 flex-col border-r border-white/8 bg-[linear-gradient(180deg,rgba(5,10,28,0.96),rgba(3,7,20,0.98))] shadow-[24px_0_64px_rgba(2,6,23,0.42)] backdrop-blur-xl md:flex">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-white/8 bg-white/[0.02] px-5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
          <div className="min-w-0">
            <div className="truncate font-display text-lg font-semibold tracking-[-0.04em] text-white">
              Camxora
            </div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/54">Music</div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 music-scroll">
          <div className="rounded-[7px] border border-white/10 bg-[linear-gradient(180deg,rgba(14,20,50,0.96),rgba(8,12,28,0.98))] p-3 shadow-[0_24px_80px_rgba(15,22,58,0.34)]">
            <nav className="space-y-2">
              {links.map(({ href, label, icon: Icon }) => {
                const active =
                  href === '/'
                    ? pathname === '/'
                    : pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={href}
                    href={href}
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
          </div>
        </div>

        <div className="shrink-0 p-4 pb-5 pt-1">
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
        </div>
      </aside>
    </>
  );
}
