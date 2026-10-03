"use client";

import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Date-range picker mirroring sunoapi.org's `/usage` control: a trigger showing
 * `MMM d - MMM d` that opens a quick-select + custom-range popover, capped at 31
 * days. Presets are week/month-to-date and rolling 7/14/30-day windows.
 */

export type UsageRange = { start: string; end: string };

export const MAX_RANGE_DAYS = 31;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function toISO(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseISO(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function addDays(s: string, n: number): string {
  const d = parseISO(s);
  d.setDate(d.getDate() + n);
  return toISO(d);
}

export function todayISO(): string {
  return toISO(new Date());
}

export function rangeDays(range: Pick<UsageRange, "start" | "end">): number {
  if (!range.start || !range.end) return 0;
  return Math.round((parseISO(range.end).getTime() - parseISO(range.start).getTime()) / 86_400_000) + 1;
}

export function formatShortDate(s: string): string {
  if (!s) return "--";
  return parseISO(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatFullDate(s: string): string {
  if (!s) return "";
  return parseISO(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function lastNDays(n: number): UsageRange {
  const end = todayISO();
  return { start: addDays(end, -(n - 1)), end };
}

function weekToDate(): UsageRange {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay()); // date-fns default: week starts Sunday
  return { start: toISO(d), end: todayISO() };
}

function monthToDate(): UsageRange {
  const d = new Date();
  const start = new Date(d.getFullYear(), d.getMonth(), 1);
  return { start: toISO(start), end: todayISO() };
}

export function defaultUsageRange(): UsageRange {
  return lastNDays(14);
}

const PRESETS: Array<{ key: string; label: string; range: () => UsageRange }> = [
  { key: "week", label: "Week to date", range: weekToDate },
  { key: "month", label: "Month to date", range: monthToDate },
  { key: "7d", label: "Last 7 days", range: () => lastNDays(7) },
  { key: "14d", label: "Last 14 days", range: () => lastNDays(14) },
  { key: "30d", label: "Last 30 days", range: () => lastNDays(30) },
];

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect width="18" height="18" x="3" y="4" rx="2" />
      <path d="M3 10h18M8 2v4M16 2v4" />
    </svg>
  );
}

function ChevronDown({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function Chevron({ dir, className }: { dir: "left" | "right"; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      {dir === "left" ? <path d="m15 18-6-6 6-6" /> : <path d="m9 18 6-6-6-6" />}
    </svg>
  );
}

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

/** A compact month calendar used by the custom-range panel. */
function MiniCalendar({
  value,
  rangeStart,
  rangeEnd,
  min,
  max,
  onSelect,
}: {
  value: string | null;
  rangeStart: string | null;
  rangeEnd: string | null;
  min?: string;
  max?: string;
  onSelect: (iso: string) => void;
}) {
  const [view, setView] = useState(() => {
    const d = parseISO(value || todayISO());
    return { year: d.getFullYear(), month: d.getMonth() };
  });

  const cells = useMemo(() => {
    const firstWeekday = new Date(view.year, view.month, 1).getDay();
    const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();
    const out: Array<string | null> = [];
    for (let i = 0; i < firstWeekday; i++) out.push(null);
    for (let d = 1; d <= daysInMonth; d++) out.push(toISO(new Date(view.year, view.month, d)));
    while (out.length % 7 !== 0) out.push(null);
    return out;
  }, [view]);

  const monthLabel = new Date(view.year, view.month, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  function shift(delta: number) {
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });
  }

  return (
    <div className="w-[264px] rounded-xl border border-white/10 bg-[#1a1a1d] p-3 shadow-2xl">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => shift(-1)}
          className="rounded-md p-1 text-white/60 transition hover:bg-white/10 hover:text-white"
          aria-label="Previous month"
        >
          <Chevron dir="left" className="h-4 w-4" />
        </button>
        <div className="text-sm font-semibold text-white">{monthLabel}</div>
        <button
          type="button"
          onClick={() => shift(1)}
          className="rounded-md p-1 text-white/60 transition hover:bg-white/10 hover:text-white"
          aria-label="Next month"
        >
          <Chevron dir="right" className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {WEEKDAYS.map((w) => (
          <div key={w} className="flex h-7 items-center justify-center text-[11px] text-white/40">
            {w}
          </div>
        ))}
        {cells.map((iso, i) => {
          if (!iso) return <div key={`empty-${i}`} className="h-8" />;
          const disabled = (!!min && iso < min) || (!!max && iso > max);
          const isStart = iso === rangeStart;
          const isEnd = iso === rangeEnd;
          const inRange = !!rangeStart && !!rangeEnd && iso > rangeStart && iso < rangeEnd;
          const isToday = iso === todayISO();
          return (
            <button
              key={iso}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(iso)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm transition-colors ${
                isStart || isEnd
                  ? "bg-[#8b5cf6] font-semibold text-white"
                  : inRange
                    ? "bg-white/[0.08] text-white"
                    : disabled
                      ? "text-white/20"
                      : "text-white/75 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span className={isToday && !isStart && !isEnd ? "underline decoration-dotted underline-offset-2" : undefined}>
                {Number(iso.slice(8, 10))}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function DateRangePicker({ value, onChange }: { value: UsageRange; onChange: (r: UsageRange) => void }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(false);
  const [draft, setDraft] = useState<UsageRange>(value);
  const [calendarFor, setCalendarFor] = useState<"start" | "end" | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const activeKey = useMemo(() => {
    for (const preset of PRESETS) {
      const r = preset.range();
      if (r.start === value.start && r.end === value.end) return preset.key;
    }
    return "custom";
  }, [value]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const draftDays = rangeDays(draft);
  const invalidOrder = !!draft.start && !!draft.end && draft.end < draft.start;
  const exceeds = !!draft.start && !!draft.end && !invalidOrder && draftDays > MAX_RANGE_DAYS;

  function choosePreset(key: string, range: UsageRange) {
    setCustom(false);
    setOpen(false);
    setCalendarFor(null);
    if (key !== activeKey) onChange(range);
  }

  function applyCustom() {
    if (!draft.start || !draft.end) return;
    if (invalidOrder || exceeds) return;
    const next = draft.start <= draft.end ? draft : { start: draft.end, end: draft.start };
    setOpen(false);
    onChange(next);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setDraft(value);
          setCalendarFor(null);
        }}
        className="inline-flex min-w-[180px] items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white/80 transition hover:bg-white/[0.07]"
      >
        <span className="inline-flex items-center gap-2">
          <CalendarIcon className="h-4 w-4 text-white/50" />
          {formatShortDate(value.start)} - {formatShortDate(value.end)}
        </span>
        <ChevronDown className="h-4 w-4 text-white/40" />
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[calc(100vw-2rem)] rounded-xl border border-white/10 bg-[#141416] shadow-2xl sm:w-[520px]">
          <div className="flex max-h-[420px] w-full flex-col md:flex-row">
            {/* Quick select */}
            <div className="w-full rounded-t-xl border-b border-white/10 bg-white/[0.02] p-4 md:w-[30%] md:rounded-l-xl md:rounded-tr-none md:border-b-0 md:border-r">
              <div className="mb-3 text-sm font-medium text-white">Quick Select</div>
              <div className="flex w-full flex-wrap gap-2 md:flex-col md:gap-1">
                {PRESETS.map((preset) => {
                  const active = !custom && activeKey === preset.key;
                  return (
                    <button
                      key={preset.key}
                      type="button"
                      onClick={() => choosePreset(preset.key, preset.range())}
                      className={`flex w-auto items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors md:w-full ${
                        active ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/[0.05] hover:text-white"
                      }`}
                    >
                      {preset.label}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => {
                    setCustom(true);
                    setDraft(value);
                    setCalendarFor(null);
                  }}
                  className={`flex w-auto items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors md:w-full ${
                    custom ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/[0.05] hover:text-white"
                  }`}
                >
                  <CalendarIcon className="h-4 w-4" />
                  Custom Range
                </button>
              </div>
              <div className="my-3 border-t border-white/10" />
              <div className="text-xs text-white/45">
                <div>Max Range: {MAX_RANGE_DAYS} days</div>
                {custom && draft.start && draft.end && !invalidOrder && (
                  <div className="mt-1">Selected: {draftDays} days</div>
                )}
              </div>
            </div>

            {/* Custom range / prompt */}
            <div className="w-full flex-1 p-4">
              {custom ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium text-white">Custom Range</div>
                    <button
                      type="button"
                      onClick={() => {
                        setCustom(false);
                        setCalendarFor(null);
                      }}
                      className="rounded-md px-2 py-1 text-xs text-white/60 transition hover:bg-white/[0.05] hover:text-white"
                    >
                      Cancel
                    </button>
                  </div>

                  <div className="text-xs text-white/60">
                    {draft.start ? (
                      draft.end ? (
                        <div className="flex items-center justify-between gap-3">
                          <span>Selected: {draftDays} days</span>
                          {exceeds && <span className="text-red-400">Exceeds limit ({MAX_RANGE_DAYS} days)</span>}
                        </div>
                      ) : (
                        <span>Select the end date for your range</span>
                      )
                    ) : (
                      <span>Select your date range using the calendar below</span>
                    )}
                  </div>

                  <div className="space-y-3 rounded-md border border-white/10 p-3">
                    <div className="relative">
                      <label className="mb-1 block text-xs text-white/50">Start time</label>
                      <button
                        type="button"
                        onClick={() => setCalendarFor((f) => (f === "start" ? null : "start"))}
                        className="flex w-full items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-2 py-2 text-left text-sm text-white transition hover:bg-white/[0.06]"
                      >
                        <CalendarIcon className="h-4 w-4 text-white/40" />
                        {draft.start ? formatFullDate(draft.start) : <span className="text-white/35">Select date</span>}
                      </button>
                      {calendarFor === "start" && (
                        <div className="absolute left-0 top-full z-50 mt-1">
                          <MiniCalendar
                            value={draft.start}
                            rangeStart={draft.start}
                            rangeEnd={draft.end}
                            max={todayISO()}
                            onSelect={(iso) => {
                              setDraft((d) => ({ ...d, start: iso }));
                              setCalendarFor(null);
                            }}
                          />
                        </div>
                      )}
                    </div>

                    <div className="relative">
                      <label className="mb-1 block text-xs text-white/50">End time</label>
                      <button
                        type="button"
                        onClick={() => setCalendarFor((f) => (f === "end" ? null : "end"))}
                        className="flex w-full items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-2 py-2 text-left text-sm text-white transition hover:bg-white/[0.06]"
                      >
                        <CalendarIcon className="h-4 w-4 text-white/40" />
                        {draft.end ? formatFullDate(draft.end) : <span className="text-white/35">Select date</span>}
                      </button>
                      {calendarFor === "end" && (
                        <div className="absolute left-0 top-full z-50 mt-1">
                          <MiniCalendar
                            value={draft.end}
                            rangeStart={draft.start}
                            rangeEnd={draft.end}
                            min={draft.start || undefined}
                            max={todayISO()}
                            onSelect={(iso) => {
                              setDraft((d) => ({ ...d, end: iso }));
                              setCalendarFor(null);
                            }}
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setDraft(monthToDate());
                        setCalendarFor(null);
                      }}
                      className="rounded-md px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/[0.05] hover:text-white"
                    >
                      Month to date
                    </button>
                    <button
                      type="button"
                      onClick={applyCustom}
                      disabled={!draft.start || !draft.end || invalidOrder || exceeds}
                      className="grad-bg rounded-md px-3 py-1.5 text-xs font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Apply Range
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center py-8 text-center text-white/45">
                  <CalendarIcon className="mb-4 h-12 w-12 opacity-50" />
                  <p className="text-sm">Select your date range using the calendar below</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
