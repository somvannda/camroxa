'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BadgeCheck,
  ChevronUp,
  Home,
  Lock,
  Plus,
  Shield,
  Sparkles,
  UserRound,
} from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { getWebsiteBaseUrl } from '@/lib/site-urls';

const links = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/explore', label: 'Explore', icon: Sparkles },
  { href: '/create', label: 'Create', icon: Plus },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const planLabel = user?.plan_name?.trim() || 'Free';

  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-3 md:flex">
      <div className="rounded-2xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-3 backdrop-blur">
        <nav className="space-y-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active =
              href === '/'
                ? pathname === '/'
                : pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? 'bg-white/10 text-white'
                    : 'text-slate-300/80 hover:bg-white/[0.05] hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto space-y-1 rounded-2xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-3 text-sm backdrop-blur">
        <button
          type="button"
          disabled
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-slate-400"
          title="Coming soon"
        >
          <Lock className="h-4 w-4" />
          Invite friends
        </button>
        <Link
          href={`${getWebsiteBaseUrl()}/privacy`}
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-slate-300/80 hover:bg-white/[0.05] hover:text-white"
        >
          <Shield className="h-4 w-4" />
          Privacy and more
        </Link>
        <Link
          href="/profile"
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-slate-300/80 hover:bg-white/[0.05] hover:text-white"
        >
          <UserRound className="h-4 w-4" />
          {user ? user.display_name : 'Account'}
        </Link>
        <Link
          href={`${getWebsiteBaseUrl()}/pricing`}
          className="mt-2 flex items-center justify-between rounded-xl border border-white/15 px-3 py-2.5 text-white"
        >
          <span className="inline-flex items-center gap-2">
            <BadgeCheck className="h-4 w-4 text-fuchsia-200" />
            Upgrade to Pro
          </span>
          <span className="inline-flex items-center gap-1 text-xs text-slate-400">
            {planLabel}
            <ChevronUp className="h-3 w-3" />
          </span>
        </Link>
      </div>
    </aside>
  );
}
