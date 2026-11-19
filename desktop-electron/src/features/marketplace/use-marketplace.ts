import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type { InstalledTemplate } from "../../../electron/shared/types";
import { CATALOG_PAGE_SIZE, kindParam } from "./marketplace-model";
import type { MarketplaceCatalogResponse, MarketplaceKind } from "./marketplace-types";

export async function fetchCatalog(
  page: number,
  kind: MarketplaceKind,
  search: string,
): Promise<MarketplaceCatalogResponse> {
  const query: Record<string, string | number | undefined> = {
    page,
    page_size: CATALOG_PAGE_SIZE,
  };
  const kindValue = kindParam(kind);
  if (kindValue) query.kind = kindValue;
  if (search) query.search = search;

  const response = await apiRequest<Partial<MarketplaceCatalogResponse>>({
    method: "GET",
    path: "/marketplace/catalog",
    query,
  });

  const items = Array.isArray(response?.items)
    ? response.items.filter((item) => item && typeof item.id === "string" && item.id && item.name)
    : [];
  return {
    items,
    total: Number(response?.total ?? items.length) || 0,
    page: Number(response?.page ?? page) || page,
    page_size: Number(response?.page_size ?? CATALOG_PAGE_SIZE) || CATALOG_PAGE_SIZE,
  };
}

export function useMarketplaceCatalog(page: number, kind: MarketplaceKind, search: string) {
  return useQuery<MarketplaceCatalogResponse>({
    queryKey: ["marketplace-catalog", page, kind, search],
    queryFn: () => fetchCatalog(page, kind, search),
    retry: 0,
    staleTime: 0,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}

async function fetchInstalled(): Promise<InstalledTemplate[]> {
  const result = await window.camxora.templates.list();
  if (!result.ok) throw new Error(result.error.message);
  return result.data;
}

/** Installed templates come from the local store, so they survive navigation. */
export function useInstalledTemplates() {
  return useQuery<InstalledTemplate[]>({
    queryKey: ["templates"],
    queryFn: fetchInstalled,
    retry: 0,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });
}
