import * as React from 'react';
import { format } from 'date-fns';
import { CalendarIcon, X } from 'lucide-react';
import { DayPicker, type DateRange } from 'react-day-picker';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

import 'react-day-picker/style.css';

export interface DateRangeValue {
  from?: string;
  to?: string;
}

interface DateRangePickerProps {
  value: DateRangeValue;
  onChange: (value: DateRangeValue) => void;
  className?: string;
}

function parseDate(value?: string): Date | undefined {
  if (!value) return undefined;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function toIsoDate(date?: Date): string | undefined {
  if (!date) return undefined;
  return format(date, 'yyyy-MM-dd');
}

const PRESETS: Array<{ label: string; days?: number; all?: boolean }> = [
  { label: 'Today', days: 0 },
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'All time', all: true },
];

export function DateRangePicker({ value, onChange, className }: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false);
  const selected: DateRange = {
    from: parseDate(value.from),
    to: parseDate(value.to),
  };

  const label =
    value.from && value.to
      ? `${format(parseDate(value.from)!, 'MMM d, yyyy')} – ${format(parseDate(value.to)!, 'MMM d, yyyy')}`
      : value.from
        ? `From ${format(parseDate(value.from)!, 'MMM d, yyyy')}`
        : 'Select date range';

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    if (preset.all) {
      onChange({});
      return;
    }
    const days = preset.days ?? 0;
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - days);
    onChange({ from: toIsoDate(from), to: toIsoDate(to) });
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'h-10 min-w-[240px] justify-start border-white/10 bg-slate-950/70 text-left font-normal text-slate-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] hover:border-violet-400/25 hover:bg-slate-900/90',
            className,
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4 text-slate-400" />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto rounded-2xl border border-white/10 bg-slate-950/95 p-0 text-slate-100 shadow-[0_24px_64px_rgba(2,6,23,0.65)] backdrop-blur-xl"
        align="start"
      >
        <div className="border-b border-white/8 p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Quick ranges
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <Button
                key={preset.label}
                type="button"
                size="sm"
                variant="secondary"
                className="h-8 border border-white/10 bg-slate-900/90 text-slate-200 hover:bg-slate-800/90"
                onClick={() => applyPreset(preset)}
              >
                {preset.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="p-3 [&_.rdp]:text-slate-100 [&_.rdp-button_next]:rounded-xl [&_.rdp-button_next]:border [&_.rdp-button_next]:border-white/10 [&_.rdp-button_next]:bg-slate-900/80 [&_.rdp-button_next]:text-slate-300 [&_.rdp-button_next]:transition-colors [&_.rdp-button_next:hover]:bg-slate-800 [&_.rdp-button_previous]:rounded-xl [&_.rdp-button_previous]:border [&_.rdp-button_previous]:border-white/10 [&_.rdp-button_previous]:bg-slate-900/80 [&_.rdp-button_previous]:text-slate-300 [&_.rdp-button_previous]:transition-colors [&_.rdp-button_previous:hover]:bg-slate-800 [&_.rdp-caption_label]:text-sm [&_.rdp-caption_label]:font-medium [&_.rdp-caption_label]:text-slate-100 [&_.rdp-day]:text-slate-200 [&_.rdp-day_button]:h-10 [&_.rdp-day_button]:w-10 [&_.rdp-day_button]:rounded-xl [&_.rdp-day_button]:transition-colors [&_.rdp-day_button:hover]:bg-slate-800 [&_.rdp-day_range_middle]:bg-violet-500/14 [&_.rdp-day_range_middle]:text-violet-100 [&_.rdp-day_selected]:bg-gradient-to-r [&_.rdp-day_selected]:from-violet-500 [&_.rdp-day_selected]:via-purple-500 [&_.rdp-day_selected]:to-fuchsia-500 [&_.rdp-day_selected]:text-white [&_.rdp-day_selected]:shadow-[0_10px_28px_rgba(118,77,255,0.28)] [&_.rdp-day_today]:text-violet-200 [&_.rdp-head_cell]:text-[11px] [&_.rdp-head_cell]:uppercase [&_.rdp-head_cell]:tracking-[0.18em] [&_.rdp-head_cell]:text-slate-500 [&_.rdp-month]:text-slate-100 [&_.rdp-month_grid]:border-separate [&_.rdp-month_grid]:border-spacing-y-1.5 [&_.rdp-nav]:text-slate-300">
          <DayPicker
            mode="range"
            selected={selected}
            onSelect={(range) => {
              onChange({
                from: toIsoDate(range?.from),
                to: toIsoDate(range?.to),
              });
            }}
            numberOfMonths={2}
            defaultMonth={selected.from ?? new Date()}
          />
        </div>
        <div className="flex items-center justify-between border-t border-white/8 p-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-slate-400 hover:text-slate-200"
            onClick={() => onChange({})}
          >
            <X className="mr-1 h-4 w-4" />
            Clear
          </Button>
          <Button type="button" size="sm" onClick={() => setOpen(false)}>
            Done
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
