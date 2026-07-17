import * as React from 'react'
import { DayPicker } from 'react-day-picker'

import { cn } from '@/shared/lib/utils'

export type CalendarProps = React.ComponentProps<typeof DayPicker>

export function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps): React.JSX.Element {
  return (
    <DayPicker
      className={cn('p-3', className)}
      classNames={{
        root: 'rounded-2xl border border-white/10 bg-[#081028] text-slate-100',
        months: 'flex flex-col gap-4 sm:flex-row',
        caption_label: 'text-sm font-semibold text-white',
        month_caption: 'relative flex items-center justify-center pt-1',
        nav: 'flex items-center gap-1',
        button_previous:
          'absolute left-3 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-300 transition hover:border-white/20 hover:bg-white/10 hover:text-white',
        button_next:
          'absolute right-3 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-300 transition hover:border-white/20 hover:bg-white/10 hover:text-white',
        month_grid: 'w-full border-collapse',
        weekday: 'w-9 rounded-md text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500',
        day: 'text-center text-sm',
        day_button:
          'h-9 w-9 rounded-lg p-0 text-sm font-medium text-slate-200 transition hover:bg-white/10 hover:text-white',
        selected:
          'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white hover:from-violet-500 hover:to-fuchsia-500 hover:text-white',
        today: 'border border-fuchsia-400/35 bg-fuchsia-500/10 text-fuchsia-100',
        outside: 'text-slate-600 opacity-60',
        disabled: 'text-slate-700 opacity-40',
        hidden: 'invisible',
        ...classNames,
      }}
      showOutsideDays={showOutsideDays}
      {...props}
    />
  )
}
