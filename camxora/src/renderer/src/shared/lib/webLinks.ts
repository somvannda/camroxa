function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

function getConfiguredUrl(envValue: string | undefined, fallback: string): string {
  const normalized = String(envValue ?? '').trim()
  if (normalized.length > 0) {
    return trimTrailingSlash(normalized)
  }
  return trimTrailingSlash(fallback)
}

export function getWebsiteBaseUrl(): string {
  return getConfiguredUrl(import.meta.env.VITE_CAMXORA_WEBSITE_URL, 'https://camxora.com')
}

export function getUserPortalBaseUrl(): string {
  return getConfiguredUrl(
    import.meta.env.VITE_CAMXORA_USER_PORTAL_URL,
    import.meta.env.DEV ? 'http://127.0.0.1:3001' : 'https://user.camxora.com',
  )
}

export function getUserPortalUrl(path = '/'): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${getUserPortalBaseUrl()}${normalizedPath}`
}

