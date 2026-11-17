export type ImagePromptKind = 'background' | 'thumbnail';

export type ImagePromptStyleRecord = {
  id: string;
  kind: ImagePromptKind;
  name: string;
  prompt_text: string;
  text_template: string | null;
  is_active: boolean;
  sort_order: number;
  notes: string | null;
};

export type ImagePromptStyleListResponse = {
  items: ImagePromptStyleRecord[];
};

export type ImagePromptStyleCreateRequest = {
  kind: ImagePromptKind;
  name: string;
  prompt_text: string;
  text_template?: string | null;
  is_active: boolean;
  sort_order: number;
  notes?: string | null;
};

export type ImagePromptStyleUpdateRequest = Partial<ImagePromptStyleCreateRequest>;

export type ImagePromptImportResponse = {
  inserted_background: number;
  inserted_thumbnail: number;
  skipped_existing: number;
  skipped_empty: number;
  errors: string[];
};

export type ImagePromptDeleteAllResponse = {
  deleted: number;
  kind: ImagePromptKind;
};
