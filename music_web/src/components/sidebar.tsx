'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowRight, Home, Library, ListMusic, Search, Tag, UserRound, Users } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';

const links = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/albums', label: 'Albums', icon: ListMusic },
  { href: '/genres', label: 'Genres', icon: Tag },
  { href: '/artists', label: 'Artists', icon: Users },
  { href: '/library', label: 'Your Library', icon: Library },
  { href: '/profile', label: 'Profile', icon: UserRound },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-4 md:flex">
      <div className="rounded-2xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-4 backdrop-blur">
        <nav className="space-y-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? 'bg-gradient-to-r from-violet-500/90 via-purple-500/90 to-fuchsia-500/90 text-white shadow-[0_12px_28px_rgba(118,77,255,0.28)]'
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

      <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-4 backdrop-blur">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
          <Library className="h-4 w-4 text-fuchsia-200/80" />
          Your Library
        </div>
        {user ? (
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <p className="font-display text-sm font-semibold text-white">Welcome, {user.display_name}</p>
            <p className="mt-2 text-xs leading-5 text-slate-300/65">
              Liked Songs are ready. Custom playlists come next.
            </p>
            <Link
              href="/library"
              className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-3 text-xs font-medium text-white"
            >
              Open library
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-4">
            <p className="font-display text-sm font-semibold text-white">Create your first playlist</p>
            <p className="mt-2 text-xs leading-5 text-slate-300/65">
              Sign in on Music Streaming to save tracks and build playlists — you stay here, not on
              the studio portal.
            </p>
            <Link
              href="/register?next=/library"
              className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-3 text-xs font-medium text-white"
            >
              Get started
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}
