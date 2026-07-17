import { useState } from 'react'
import { format, isValid, parseISO } from 'date-fns'
import { CalendarDays } from 'lucide-react'

import { cn } from '@/shared/lib/utils'
import { Calendar } from '@/shared/ui/calendar'
import { Input } from '@/shared/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/ui/popover'

export function DatePickerField(props: {
  label: string
  value: string
  onChange: (value: string) => void
  className?: string
  triggerClassName?: string
}): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const selectedDate = props.value ? parseISO(props.value) : undefined
  const displayLabel = selectedDate && isValid(selectedDate) ? format(selectedDate, 'MM/dd/yyyy') : 'Select date'

  return (
    <div className={cn('relative', props.className)}>
      <Input
        aria-label={props.label}
        className="sr-only"
        type="date"
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            aria-label={props.label}
            className={cn(
              'flex h-9 w-full items-center justify-between rounded-xl border border-white/10 bg-slate-950/70 px-2.5 text-[13px] text-slate-100 transition hover:border-white/20 hover:bg-slate-950',
              props.triggerClassName,
            )}
            type="button"
          >
            <span>{displayLabel}</span>
            <CalendarDays className="h-4 w-4 text-slate-400" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto p-0">
          <Calendar
            mode="single"
            selected={selectedDate && isValid(selectedDate) ? selectedDate : undefined}
            onSelect={(date) => {
              props.onChange(date ? format(date, 'yyyy-MM-dd') : '')
              setOpen(false)
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}
