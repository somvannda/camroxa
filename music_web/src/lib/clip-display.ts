/** Workspace clip subtitle helpers (model tag + generated time). */

export type FormatGeneratedTimeOptions = {
  now?: Date;
  locale?: string;
  timeZone?: string;
};

export function formatModelVersionTag(model: string | null | undefined): string {
  const key = String(model || 'V6')
    .trim()
    .toUpperCase()
    .replace(/[\s.-]+/g, '_');
  if (key === 'V6_MINI') return 'v6 mini';
  if (key === 'V6_WILD') return 'v6 wild';
  if (key === 'V6') return 'v6 pro';
  if (key === 'V5_5') return 'v5.5';
  if (key === 'V5') return 'v5';
  return key.toLowerCase().replace(/_/g, ' ') || 'v6';
}

function calendarDayKey(value: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(value);
}

export function formatGeneratedTime(
  value: string | Date | null | undefined,
  options: FormatGeneratedTimeOptions = {},
): string {
  if (value == null || value === '') return '';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const now = options.now ?? new Date();
  const time = date.toLocaleTimeString(options.locale, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: options.timeZone,
  });

  const generatedDay = calendarDayKey(date, options.timeZone);
  const today = calendarDayKey(now, options.timeZone);
  if (generatedDay === today) {
    return time;
  }

  const sameYear = generatedDay.slice(0, 4) === today.slice(0, 4);
  const day = date.toLocaleDateString(options.locale, {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
    timeZone: options.timeZone,
  });
  return `${day} · ${time}`;
}
