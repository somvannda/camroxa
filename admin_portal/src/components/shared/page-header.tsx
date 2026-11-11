import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow = 'Admin workspace',
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 rounded-3xl border border-white/10 bg-slate-950/55 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.28)] backdrop-blur-xl md:flex-row md:items-end md:justify-between',
        className,
      )}
    >
      <div className="space-y-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-300/85">
          {eyebrow}
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-white">{title}</h1>
          {description ? (
            <p className="max-w-2xl text-sm leading-6 text-slate-400">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-3 md:justify-end">{actions}</div>
      ) : null}
    </div>
  );
}
