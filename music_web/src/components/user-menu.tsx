'use client';

import Link from 'next/link';
import { ChevronDown, LogOut, UserRound } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { getUserAvatarUrl } from '@/lib/auth-api';
import { cn } from '@/lib/cn';

export default function UserMenu() {
  const { user, logout } = useAuth();

  if (!user) return null;

  const avatarSrc = user.avatar_url ? getUserAvatarUrl(user.id, user.avatar_url) : null;
  const initial = (user.display_name || user.email || 'U').slice(0, 1).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'group inline-flex h-10 max-w-[12rem] items-center gap-2 rounded-[7px] border border-white/10 bg-white/[0.03] px-3 text-sm font-medium text-slate-100 transition hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/30 data-[state=open]:border-violet-400/30 data-[state=open]:bg-violet-500/[0.08]',
          )}
        >
          {avatarSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarSrc}
              alt=""
              className="h-7 w-7 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-200">
              {initial}
            </span>
          )}
          <span className="hidden truncate min-[420px]:inline">{user.display_name}</span>
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition group-data-[state=open]:rotate-180 group-data-[state=open]:text-violet-200" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem asChild>
          <Link href="/profile" className="cursor-pointer text-slate-200">
            <UserRound className="text-violet-200" />
            Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer text-slate-200"
          onSelect={() => {
            void logout();
          }}
        >
          <LogOut className="text-slate-400" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
