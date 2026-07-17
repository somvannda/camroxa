export type ContentPoolKind = 'titles' | 'albums' | 'openings';

export type ContentPoolStat = {
  total: number;
  unused: number;
  reserved: number;
  stale_reserved: number;
  available: number;
};

export type ContentPoolStatsResponse = {
  titles: ContentPoolStat;
  albums: ContentPoolStat;
  openings: ContentPoolStat;
};

export type ContentPoolRow = {
  id: number;
  text: string;
  secondary_text: string | null;
  used_count: number;
  reservation_state: 'available' | 'reserved' | 'stale';
  reserved_by: string | null;
  reserved_at: string | null;
  created_at: string | null;
};

export type ContentPoolListResponse = {
  kind: ContentPoolKind;
  total: number;
  limit: number;
  offset: number;
  items: ContentPoolRow[];
};

export type ContentPoolPresetConfig = {
  include_defaults: boolean;
  adjectives: string[];
  nouns: string[];
  verbs: string[];
  places: string[];
  feelings: string[];
  whos: string[];
  moods: string[];
  times: string[];
};

export type ContentPoolPresetPack = {
  id: string;
  kind: ContentPoolKind;
  name: string;
  description: string;
  is_active: boolean;
  config: ContentPoolPresetConfig;
  created_at: string | null;
  updated_at: string | null;
};

export type ContentPoolPresetPackListResponse = {
  kind: ContentPoolKind;
  items: ContentPoolPresetPack[];
};

export type GeneratedPresetPackBanks = {
  adjectives: string[];
  nouns: string[];
  verbs: string[];
  places: string[];
  feelings: string[];
  whos: string[];
  moods: string[];
  times: string[];
};

export type GeneratePresetPackBanksResponse = {
  kind: ContentPoolKind;
  target_count: number;
  banks: GeneratedPresetPackBanks;
};

export type GenerateContentPoolResponse = {
  requested: number;
  attempted: number;
  inserted: number;
  duplicates_skipped: number;
};
