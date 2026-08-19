const OPERATION_LABELS: Record<string, string> = {
  song_draft: 'Song draft',
  llm_draft: 'Song draft',
  title: 'Title',
  album: 'Album',
  lyric: 'Lyrics (Desktop / Batch)',
  lyrics: 'Lyrics (Desktop / Batch)',
  web_music_lyrics: 'Music Lyric',
  web_music_style: 'Music Style Tags',
  suno: 'Music (Suno)',
  suno_generation: 'Music (Suno)',
  image: 'Image',
  image_generation: 'Image',
  background_image: 'Background image',
  thumbnail_image: 'Thumbnail image',
  music: 'Music',
  music_generation: 'Music',
  video: 'Studio export',
  video_manual: 'Manual export',
  video_merge: 'Video merge',
  channel_setup: 'Channel setup',
  draft_generation_failed: 'Draft refund',
  credit_pack_purchase: 'Credit pack',
};

export function formatOperationLabel(operation?: string | null): string {
  if (!operation) return 'All operations';
  return OPERATION_LABELS[operation] ?? operation.replace(/_/g, ' ');
}

const PROVIDER_LABELS: Record<string, string> = {
  slai: 'SLAI',
  fal: 'Fal',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  suno: 'Suno',
  cala: 'Cala',
  local: 'Local',
};

export function formatProviderLabel(provider?: string | null): string {
  if (!provider) return 'All providers';
  const key = provider.trim().toLowerCase();
  return PROVIDER_LABELS[key] ?? provider;
}

export function formatCredits(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1) return abs.toFixed(4).replace(/\.?0+$/, '');
  return abs.toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
}

/** Convert micro-credit units to display credits when present. */
export function formatCreditUnits(units?: number | null): string | null {
  if (units == null || Number.isNaN(Number(units))) return null;
  return formatCredits(Number(units) / 10_000);
}

export type UsageBillingFields = {
  amount: number;
  direction: string;
  billing?: string | null;
  list_credit_units?: number | null;
  charged_credit_units?: number | null;
  coverage?: string | null;
  metadata?: Record<string, unknown> | null;
};

function metaBilling(row: UsageBillingFields): string | null {
  const fromField = row.billing?.trim();
  if (fromField) return fromField;
  const meta = row.metadata;
  if (meta && typeof meta.billing === 'string' && meta.billing.trim()) {
    return meta.billing.trim();
  }
  return null;
}

function metaListUnits(row: UsageBillingFields): number | null {
  if (typeof row.list_credit_units === 'number') return row.list_credit_units;
  const raw = row.metadata?.list_credit_units;
  return typeof raw === 'number' ? raw : null;
}

/**
 * Smart cost label for usage rows.
 * Plan-included ops (amount 0 / billing=plan_allowance) show list credit value.
 */
export function formatUsageCostLabel(row: UsageBillingFields): string {
  const billing = metaBilling(row);
  const listUnits = metaListUnits(row);
  const listLabel = formatCreditUnits(listUnits);
  const isPlan =
    billing === 'plan_allowance' ||
    (row.direction === 'debit' && Math.abs(row.amount) < 1e-12);

  if (isPlan) {
    if (listLabel) return `Plan allowance (list ${listLabel})`;
    return 'Plan allowance';
  }

  if (billing === 'platform_absorb') {
    if (listLabel) return `Platform absorbed (list ${listLabel})`;
    return 'Platform absorbed';
  }

  if (billing === 'wallet') {
    return `Credits charged −${formatCredits(Math.abs(row.amount))}`;
  }

  const prefix = row.direction === 'debit' ? '−' : row.direction === 'refund' ? '+' : '+';
  return `${prefix}${formatCredits(Math.abs(row.amount))}`;
}

export function truncateId(id?: string | null, length = 10): string {
  if (!id) return '—';
  if (id.length <= length) return id;
  return `${id.slice(0, length)}…`;
}
