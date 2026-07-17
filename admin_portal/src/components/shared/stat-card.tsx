import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  tone?: 'default' | 'danger' | 'warning' | 'success';
}

const TONE_STYLES = {
  default: 'text-slate-100',
  danger: 'text-red-300',
  warning: 'text-amber-300',
  success: 'text-emerald-300',
};

export function StatCard({ label, value, hint, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-gradient-to-br from-slate-900/90 to-slate-950/90 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {label}
        </div>
        {Icon ? <Icon className="h-4 w-4 text-slate-500" /> : null}
      </div>
      <div className={cn('mt-3 text-3xl font-semibold tracking-tight', TONE_STYLES[tone])}>
        {value}
      </div>
      {hint ? <div className="mt-2 text-xs text-slate-500">{hint}</div> : null}
    </div>
  );
}
