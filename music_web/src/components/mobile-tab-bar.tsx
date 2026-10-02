'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ListMusic, Plus, Sparkles, UserRound } from 'lucide-react';

import { cn } from '@/lib/cn';

const tabs = [
  { href: '/create', label: 'Create', icon: Plus, match: (path: string) => path === '/create' || path.startsWith('/create/') },
  { href: '/explore', label: 'Explore', icon: Sparkles, match: (path: string) => path === '/explore' || path.startsWith('/explore/') },
  { href: '/playlists', label: 'Playlists', icon: ListMusic, match: (path: string) => path === '/playlists' || path.startsWith('/playlists/') },
  { href: '/profile', label: 'Profile', icon: UserRound, match: (path: string) => path === '/profile' || path.startsWith('/profile/') },
];

export default function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-[60] border-t border-white/8 bg-[rgba(5,8,18,0.96)] pb-[env(safe-area-inset-bottom,0px)] backdrop-blur-xl md:hidden"
      aria-label="Primary"
    >
      <div className="grid h-[3.75rem] grid-cols-4">
        {tabs.map(({ href, label, icon: Icon, match }) => {
          const active = match(pathname);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition',
                active ? 'text-white' : 'text-slate-400',
              )}
            >
              <span
                className={cn(
                  'inline-flex h-8 w-8 items-center justify-center rounded-full',
                  active
                    ? 'bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_8px_20px_rgba(118,77,255,0.35)]'
                    : 'text-slate-400',
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
