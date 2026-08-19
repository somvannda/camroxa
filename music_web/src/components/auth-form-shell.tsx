'use client';

import type { ReactNode } from 'react';

type AuthFormShellProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
};

export default function AuthFormShell({ title, subtitle, children, footer }: AuthFormShellProps) {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-8 md:py-10">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-xl backdrop-blur-xl md:p-7">
        <h1 className="text-center font-display text-2xl font-semibold tracking-[-0.03em] text-white">
          {title}
        </h1>
        {subtitle ? <p className="mt-2 text-center text-sm text-slate-400">{subtitle}</p> : null}
        <div className="mt-6">{children}</div>
        {footer ? <div className="mt-5">{footer}</div> : null}
      </div>
    </div>
  );
}
