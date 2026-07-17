'use client';

import { Disc3, Home, Search, Tag, Users } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/albums', label: 'Albums', icon: Disc3 },
  { href: '/genres', label: 'Genres', icon: Tag },
  { href: '/artists', label: 'Artists', icon: Users },
  { href: '/search', label: 'Search', icon: Search },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-[hsl(var(--border))] bg-[hsl(var(--card))] p-6 md:block">
      <div className="mb-8 flex items-center gap-3">
        <Disc3 className="h-7 w-7 text-[hsl(var(--primary))]" />
        <div>
          <p className="text-lg font-semibold">Camxora Music</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Stream AI-generated tracks</p>
        </div>
      </div>
      <nav className="space-y-1">
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                active
                  ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]'
                  : 'text-[hsl(var(--muted-foreground))] hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
