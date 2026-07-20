import { resolvePlatformApiBaseUrl } from "@/lib/platform-api-base";

export type PublicDesktopRelease = {
  version: string;
  download_url: string;
  release_notes: string;
  mandatory: boolean;
  published_at: string;
  download_count: number;
  total_downloads: number;
};

export async function getPublicDesktopRelease(): Promise<PublicDesktopRelease | null> {
  const response = await fetch(`${resolvePlatformApiBaseUrl()}/public/desktop-release`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Unable to load desktop release (${response.status})`);
  }

  return (await response.json()) as PublicDesktopRelease;
}
