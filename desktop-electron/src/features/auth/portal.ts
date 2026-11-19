export function portalBase(value?: string): string {
  return (value?.trim() || "https://app.camxora.com").replace(/\/+$/, "");
}

/**
 * Opens a portal link in the system browser through the main process.
 * Returns an error message when the link could not be opened.
 */
export async function openExternal(url: string): Promise<string | null> {
  if (!window.camxora) {
    window.open(url, "_blank", "noopener,noreferrer");
    return null;
  }
  try {
    const result = await window.camxora.app.openExternal(url);
    return result.ok ? null : result.error.message;
  } catch {
    return "Could not open the link in your browser.";
  }
}
