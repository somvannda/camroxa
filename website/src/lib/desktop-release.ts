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

/** Previous desktop line that stays downloadable beside the current release. */
export const PREVIOUS_DESKTOP_RELEASE = {
  version: "1.7.1",
  label: "Camxora Desktop 1.7.1 (previous)",
  description:
    "The earlier Python desktop. It is kept available for anyone who needs it; installing 2.0.0 replaces it.",
} as const;

/** Public installer URL for any uploaded version (the API serves the storage file). */
export function getDesktopInstallerUrl(version: string): string {
  return `${resolvePlatformApiBaseUrl()}/public/desktop-release/files/Camxora-${encodeURIComponent(
    version,
  )}.exe`;
}

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
