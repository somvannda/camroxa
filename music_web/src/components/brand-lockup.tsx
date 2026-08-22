import Link from 'next/link';

import { cn } from '@/lib/cn';

export default function BrandLockup({
  href = '/',
  compact = false,
  onClick,
}: {
  href?: string;
  compact?: boolean;
  onClick?: () => void;
}) {
  return (
    <Link className="flex min-w-0 items-center gap-2" href={href} onClick={onClick}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        alt="Camxora"
        className={cn('shrink-0', compact ? 'h-8 w-8' : 'h-10 w-10')}
        src="/camxora-logo.svg"
      />
      <div className="min-w-0 leading-tight">
        <div
          className={cn(
            'truncate font-display font-semibold tracking-[-0.04em] text-white',
            compact ? 'text-[15px]' : 'text-lg',
          )}
        >
          Camxora
        </div>
        <div
          className={cn(
            'uppercase text-fuchsia-100/54',
            compact ? 'text-[9px] tracking-[0.18em]' : 'text-[11px] tracking-[0.22em]',
          )}
        >
          Music
        </div>
      </div>
    </Link>
  );
}
