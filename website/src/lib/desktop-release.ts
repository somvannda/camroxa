export type PublicDesktopRelease = {
  version: string;
  download_url: string;
  release_notes: string;
  mandatory: boolean;
  published_at: string;
};

const DESKTOP_RELEASE_REVALIDATE_SECONDS = 300;

function resolvePlatformApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v1"
      : "https://api.camxora.com/api/v1")
  );
}

export async function getPublicDesktopRelease(): Promise<PublicDesktopRelease | null> {
  const response = await fetch(`${resolvePlatformApiBaseUrl()}/public/desktop-release`, {
    next: { revalidate: DESKTOP_RELEASE_REVALIDATE_SECONDS },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Unable to load desktop release (${response.status})`);
  }

  return (await response.json()) as PublicDesktopRelease;
}
