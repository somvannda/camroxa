export interface MarketplaceItem {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  kind: string;
  tags: string[];
  status: string;
  price: number;
  preview_url: string;
  created_at: string;
  /** Optional schema hints; the catalog does not always send them. */
  schema?: unknown;
  template_schema?: unknown;
  licence?: unknown;
  license?: unknown;
}

export interface MarketplaceCatalogResponse {
  items: MarketplaceItem[];
  total: number;
  page: number;
  page_size: number;
}

export type MarketplaceKind = "all" | "video" | "reel";
export type MarketplaceSchema = "vizzy" | "legacy";
