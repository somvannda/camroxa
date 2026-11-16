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
