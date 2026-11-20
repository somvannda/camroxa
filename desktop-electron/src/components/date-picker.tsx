import { useEffect, useMemo, useState } from "react";
import { Icon } from "./icon";
import { Input } from "./input";
import { classNames } from "../lib/format";
import type { ControlSize } from "./control-size";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function isValidIso(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(new Date(`${value}T00:00:00Z`).getTime());
}

function toIso(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function todayIso(): string {
  const now = new Date();
  return toIso(now.getFullYear(), now.getMonth(), now.getDate());
}

interface MonthCell {
  iso: string | null;
  day: number;
}

function monthCells(year: number, month: number): MonthCell[] {
  const first = new Date(Date.UTC(year, month, 1));
  const startDay = first.getUTCDay();
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const cells: MonthCell[] = [];
  for (let index = 0; index < startDay; index += 1) cells.push({ iso: null, day: 0 });
  for (let day = 1; day <= days; day += 1) {
    cells.push({ iso: toIso(year, month, day), day });
  }
  while (cells.length % 7 !== 0) cells.push({ iso: null, day: 0 });
  return cells;
}

export interface DatePickerProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  invalid?: boolean;
  disabled?: boolean;
  controlSize?: ControlSize;
  className?: string;
  "data-testid"?: string;
  "aria-label"?: string;
}

/**
 * ISO date field with a custom month calendar.
 *
 * The text input stays fillable for keyboard/exports while the button opens a
 * real calendar instead of the browser's native picker.
 */
export function DatePicker({
  id,
  value,
  onChange,
  min,
  max,
  invalid = false,
  disabled = false,
  controlSize = "md",
  className,
  "data-testid": testId,
  "aria-label": ariaLabel,
}: DatePickerProps) {
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const selected = isValidIso(value) ? new Date(`${value}T00:00:00Z`) : null;
  const [view, setView] = useState(() => {
    const base = selected ?? new Date();
    return { year: base.getUTCFullYear(), month: base.getUTCMonth() };
  });

  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const base = isValidIso(value) ? new Date(`${value}T00:00:00Z`) : new Date();
    setView({ year: base.getUTCFullYear(), month: base.getUTCMonth() });
  }, [open, value]);

  const cells = useMemo(() => monthCells(view.year, view.month), [view]);
  const today = todayIso();

  const commit = (next: string) => {
    if (!isValidIso(next)) return;
    onChange(next);
  };

  const shiftMonth = (amount: number) => {
    setView((current) => {
      const next = new Date(Date.UTC(current.year, current.month + amount, 1));
      return { year: next.getUTCFullYear(), month: next.getUTCMonth() };
    });
  };

  return (
    <div className={classNames("relative", className)}>
      <div className="flex items-center gap-1">
        <Input
          id={id}
          data-testid={testId}
          aria-label={ariaLabel}
          type="text"
          inputMode="numeric"
          placeholder="YYYY-MM-DD"
          maxLength={10}
          controlSize={controlSize}
          invalid={invalid}
          disabled={disabled}
          className="text-tabular"
          value={draft}
          onChange={(event) => {
            const next = event.target.value;
            setDraft(next);
            if (next === "") {
              onChange("");
              return;
            }
            commit(next);
          }}
          onBlur={() => {
            if (!isValidIso(draft)) setDraft(value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              commit(draft);
              (event.target as HTMLInputElement).blur();
            }
          }}
        />
        <button
          type="button"
          aria-label="Open calendar"
          aria-expanded={open}
          disabled={disabled}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-surface-1 text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => setOpen((current) => !current)}
        >
          <Icon name="fa-calendar-days" size={13} />
        </button>
      </div>

      {open ? (
        <>
          <div className="fixed inset-0 z-[85]" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            className="absolute left-0 top-9 z-[86] w-[248px] rounded-card border border-border bg-surface-1 p-2 shadow-[0_18px_48px_rgba(0,0,0,.5)]"
            role="dialog"
            aria-label="Choose a date"
          >
            <div className="flex items-center justify-between gap-1">
              <button
                type="button"
                aria-label="Previous month"
                className="flex h-6 w-6 items-center justify-center rounded-control text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={() => shiftMonth(-1)}
              >
                <Icon name="fa-chevron-left" size={10} />
              </button>
              <p className="text-meta font-medium text-text-primary">
                {MONTHS[view.month]} {view.year}
              </p>
              <button
                type="button"
                aria-label="Next month"
                className="flex h-6 w-6 items-center justify-center rounded-control text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={() => shiftMonth(1)}
              >
                <Icon name="fa-chevron-right" size={10} />
              </button>
            </div>

            <div className="mt-2 grid grid-cols-7 gap-0.5">
              {WEEKDAYS.map((label) => (
                <span
                  key={label}
                  className="py-1 text-center text-[10px] uppercase text-text-muted"
                  aria-hidden="true"
                >
                  {label}
                </span>
              ))}
              {cells.map((cell, index) => {
                if (!cell.iso) return <span key={`blank-${index}`} />;
                const blocked = Boolean(
                  (min && cell.iso < min) || (max && cell.iso > max),
                );
                const isSelected = cell.iso === value;
                const isToday = cell.iso === today;
                return (
                  <button
                    key={cell.iso}
                    type="button"
                    disabled={blocked}
                    aria-current={isToday ? "date" : undefined}
                    className={classNames(
                      "flex h-7 items-center justify-center rounded-[5px] text-caption transition-colors",
                      blocked
                        ? "cursor-not-allowed text-text-disabled"
                        : isSelected
                          ? "bg-accent text-white"
                          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                      isToday && !isSelected ? "border border-accent/40" : "",
                    )}
                    onClick={() => {
                      commit(cell.iso ?? "");
                      setOpen(false);
                    }}
                  >
                    {cell.day}
                  </button>
                );
              })}
            </div>

            <div className="mt-2 flex items-center justify-between border-t border-border pt-2">
              <button
                type="button"
                className="rounded-control px-2 py-1 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={() => {
                  commit(today);
                  setOpen(false);
                }}
              >
                Today
              </button>
              <button
                type="button"
                className="rounded-control px-2 py-1 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
