'use client';

import { useState, type ReactNode } from 'react';
import { ChevronDown, Info } from 'lucide-react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/cn';

export const WEB_MUSIC_LYRICS_MAX = 5000;
export const WEB_MUSIC_STYLE_MAX = 1000;

export function MusicSectionError({ message }: { message?: string | null }) {
  if (!message) return null;
  return <p className="text-xs text-rose-300">{message}</p>;
}

export function MusicCharCount({ value, max }: { value: string; max: number }) {
  const count = value.length;
  const nearLimit = count >= max * 0.9;
  const atLimit = count >= max;

  return (
    <p
      className={cn(
        'text-right text-xs tabular-nums',
        atLimit ? 'text-rose-300' : nearLimit ? 'text-amber-200' : 'text-slate-500',
      )}
    >
      {count.toLocaleString()} / {max.toLocaleString()}
    </p>
  );
}

export function MusicSelect({
  value,
  onValueChange,
  options,
  placeholder = 'Select…',
  disabled,
  className,
  triggerClassName,
}: {
  value: string;
  onValueChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
}) {
  if (options.length === 0) {
    return (
      <div
        className={cn(
          'flex h-10 items-center rounded-[7px] border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-500',
          className,
        )}
      >
        {placeholder}
      </div>
    );
  }

  return (
    <Select value={value || undefined} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger className={cn(className, triggerClassName)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
export function MusicCollapsibleSection({
  title,
  defaultOpen = true,
  action,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  action?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-[7px] border border-white/10 bg-[rgba(12,14,28,0.72)]">
      <div className="flex items-center gap-2 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <ChevronDown
            className={cn('h-4 w-4 shrink-0 text-slate-400 transition-transform', open && 'rotate-180')}
          />
          <span className="text-sm font-medium text-white">{title}</span>
        </button>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {open ? <div className="space-y-3 border-t border-white/8 px-4 pb-4 pt-3">{children}</div> : null}
    </div>
  );
}

export function MusicSegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-[7px] border border-white/10 bg-[rgba(8,10,22,0.9)] p-1">
      {options.map((option) => (
        <button
          key={option.value || 'empty'}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium transition',
            value === option.value
              ? 'bg-white/14 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function MusicOptionCard({
  label,
  hint,
  trailing,
  children,
}: {
  label: string;
  hint?: string;
  trailing?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-[7px] border border-white/10 bg-[rgba(10,12,24,0.88)] px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5 text-sm text-slate-200">
          <span>{label}</span>
          {hint ? (
            <span title={hint} className="text-slate-500">
              <Info className="h-3.5 w-3.5" />
            </span>
          ) : null}
        </div>
        {trailing ? <div className="shrink-0">{trailing}</div> : null}
      </div>
      {children ? <div className="mt-3">{children}</div> : null}
    </div>
  );
}

export function MusicPillTabs<T extends string>({
  value,
  options,
  onChange,
  allowDeselect = false,
}: {
  value: T | null;
  options: { value: T; label: string }[];
  onChange: (value: T | null) => void;
  allowDeselect?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(active && allowDeselect ? null : option.value)}
            className={cn(
              'rounded-full border px-3 py-1.5 text-[11px] font-medium transition',
              active
                ? 'border-violet-400/40 bg-violet-500/15 text-white'
                : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-violet-400/25 hover:text-slate-200',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export type MusicModelId = 'V6' | 'V6_MINI' | 'V6_WILD' | 'V5_5' | 'V5';

export function MusicModelSelect({
  value,
  onChange,
}: {
  value: MusicModelId;
  onChange: (value: MusicModelId) => void;
}) {
  return (
    <MusicSelect
      value={value}
      onValueChange={(next) => onChange(next as MusicModelId)}
      options={[
        { value: 'V6', label: 'V6' },
        { value: 'V6_MINI', label: 'V6 Mini' },
        { value: 'V6_WILD', label: 'V6 Wild' },
        { value: 'V5_5', label: 'V5.5' },
        { value: 'V5', label: 'V5' },
      ]}
      className="h-8 w-[6.5rem] border-white/10 text-xs font-medium"
      triggerClassName="rounded-full px-3"
    />
  );
}
export function MusicSettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-sm text-slate-200">
          <span>{label}</span>
          {hint ? (
            <span title={hint} className="text-slate-500">
              <Info className="h-3.5 w-3.5" />
            </span>
          ) : null}
        </div>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function MusicHorizontalTickSlider({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  hint?: string;
}) {
  const pct = Math.round(value * 100);
  const tickCount = 11;

  function tickStyle(index: number) {
    const tickValue = index / (tickCount - 1);
    const thumbIndex = value * (tickCount - 1);
    const distanceSteps = Math.abs(index - thumbIndex);
    const proximity = 1 - distanceSteps / (tickCount - 1);
    const opacity = 0.22 + proximity * 0.68;
    const heightPx = 8 + Math.round(proximity * 8);
    const isLeft = tickValue <= value + 0.001;

    return {
      height: `${heightPx}px`,
      backgroundColor: isLeft
        ? `rgba(167, 139, 250, ${opacity})`
        : `rgba(226, 232, 240, ${0.18 + proximity * 0.5})`,
    };
  }

  return (
    <div className="rounded-[7px] border border-white/10 bg-[rgba(10,12,24,0.88)] px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="flex w-[6.25rem] shrink-0 items-center gap-1.5 text-sm text-slate-200">
          <span>{label}</span>
          {hint ? (
            <span title={hint} className="text-slate-500">
              <Info className="h-3.5 w-3.5" />
            </span>
          ) : null}
        </div>

        <div className="relative flex h-11 min-w-0 flex-1 items-center">
          <div className="relative flex h-8 w-full items-center justify-between">
            {Array.from({ length: tickCount }).map((_, index) => (
              <div
                key={index}
                className="w-px shrink-0 rounded-full transition-all duration-150"
                style={tickStyle(index)}
              />
            ))}
            <div
              className="pointer-events-none absolute top-1/2 z-10 h-8 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-b from-fuchsia-300 via-fuchsia-400 to-pink-500 shadow-[0_0_18px_rgba(236,72,153,0.55)]"
              style={{ left: `${pct}%` }}
            />
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={pct}
            onChange={(event) => onChange(Number(event.target.value) / 100)}
            className="absolute inset-0 z-20 h-full w-full cursor-pointer opacity-0"
            aria-label={label}
          />
        </div>

        <span className="w-9 shrink-0 text-right text-sm text-slate-200">{pct}%</span>
      </div>
    </div>
  );
}

export function MusicTickSlider({
  label,
  value,
  onChange,
  hint,
  compact = false,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  hint?: string;
  compact?: boolean;
}) {
  const pct = Math.round(value * 100);
  const tickCount = 24;

  return (
    <div className="space-y-2 py-1">
      {!compact ? (
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-sm text-slate-200">
            <span>{label}</span>
            {hint ? (
              <span title={hint} className="text-slate-500">
                <Info className="h-3.5 w-3.5" />
              </span>
            ) : null}
          </div>
          <span className="text-sm text-slate-400">{pct}%</span>
        </div>
      ) : null}
      <div className="relative flex h-7 items-center">
        <div className="relative flex h-4 w-full items-center gap-[2px]">
          {Array.from({ length: tickCount }).map((_, index) => {
            const tickValue = index / (tickCount - 1);
            const active = tickValue <= value + 0.001;
            return (
              <div
                key={index}
                className={cn(
                  'h-full flex-1 rounded-[1px] transition-colors',
                  active ? 'bg-violet-500/85' : 'bg-white/10',
                )}
              />
            );
          })}
          <div
            className="pointer-events-none absolute top-1/2 h-1/2 w-0.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-violet-300 to-fuchsia-400 shadow-[0_0_12px_rgba(167,139,250,0.45)]"
            style={{ left: `calc(${pct}% - 1px)` }}
          />
        </div>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={pct}
          onChange={(event) => onChange(Number(event.target.value) / 100)}
          className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
          aria-label={label}
        />
      </div>
    </div>
  );
}

export function MusicInlineChoice({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <MusicPillTabs
      value={value || null}
      options={options.map((option) => ({ value: option.value, label: option.label }))}
      onChange={(next) => onChange(next ?? '')}
      allowDeselect
    />
  );
}

export function MusicFloatingActionBar({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="pointer-events-none fixed bottom-[var(--music-fab-bottom)] left-[4.25rem] right-3 z-[60] md:sticky md:bottom-5 md:left-auto md:right-auto md:z-20 md:mt-auto md:w-full md:px-3 md:pb-2 md:pt-8">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 top-0 hidden bg-gradient-to-t from-[rgba(6,8,18,0.98)] via-[rgba(6,8,18,0.88)] to-transparent md:block" />
      <div className="relative w-full pointer-events-auto">{children}</div>
    </div>
  );
}

export function MusicEqualizerIcon({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-end gap-[2px]', className)} aria-hidden="true">
      {Array.from({ length: 5 }).map((_, index) => (
        <span key={index} className="h-3 w-[2px] rounded-full bg-current" />
      ))}
    </span>
  );
}
