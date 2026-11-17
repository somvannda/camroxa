export type ThumbnailTextRecord = {
  id: string;
  title: string;
  subtitle: string | null;
  subline: string | null;
  placement: string;
  alignment: string;
  style_hint: string | null;
  is_active: boolean;
  sort_order: number;
  notes: string | null;
};

export type ThumbnailTextListResponse = {
  items: ThumbnailTextRecord[];
};

export type ThumbnailTextCreateRequest = {
  title: string;
  subtitle?: string | null;
  subline?: string | null;
  placement: string;
  alignment: string;
  style_hint?: string | null;
  is_active: boolean;
  sort_order: number;
  notes?: string | null;
};

export type ThumbnailTextUpdateRequest = Partial<ThumbnailTextCreateRequest>;

export type ThumbnailTextImportResponse = {
  inserted: number;
  skipped_existing: number;
  skipped_empty: number;
  errors: string[];
};

export type ThumbnailTextDeleteAllResponse = {
  deleted: number;
};
