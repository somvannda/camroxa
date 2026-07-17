const CAMXORA_TIMEZONE = 'Asia/Phnom_Penh';

function parseApiDateTime(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  // API timestamps should be UTC with Z; treat legacy naive ISO strings as UTC too.
  const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(trimmed);
  const normalized = hasTimezone ? trimmed : `${trimmed}Z`;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

export function formatAdminDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = parseApiDateTime(value);
  if (!parsed) return value;
  return `${parsed.toLocaleString('en-US', {
    timeZone: CAMXORA_TIMEZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })} ICT`;
}

export function formatAdminDate(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = parseApiDateTime(value);
  if (!parsed) return value;
  return parsed.toLocaleDateString('en-US', {
    timeZone: CAMXORA_TIMEZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatVerificationDurationShort(value: string | null | undefined): {
  label: string;
  expired: boolean;
} {
  if (!value) {
    return { label: '—', expired: false };
  }
  const expires = parseApiDateTime(value);
  if (!expires) {
    return { label: '—', expired: false };
  }
  const msLeft = expires.getTime() - Date.now();
  if (msLeft <= 0) {
    return { label: 'Expired', expired: true };
  }
  const totalSeconds = Math.ceil(msLeft / 1000);
  if (totalSeconds < 60) {
    return { label: `${totalSeconds}s`, expired: false };
  }
  const minutes = Math.ceil(totalSeconds / 60);
  return { label: `${minutes}m`, expired: false };
}
