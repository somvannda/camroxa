import { getDesktopApi } from '@/shared/api/desktop'
import { ensureFreshSession } from '@/shared/auth/authRefresh'
import { useAuthStore } from '@/shared/auth/sessionStore'

export type ApiErrorPayload = {
  message?: string
  detail?: string
  error?:
    | string
    | {
        code?: string
        message?: string
        detail?: string
        details?: unknown
      }
}

export class PlatformApiError extends Error {
  readonly status: number
  readonly payload: unknown

  constructor(status: number, message: string, payload: unknown) {
    super(message)
    this.status = status
    this.payload = payload
  }
}

let invalidatedAccessToken: string | null = null

async function getBaseUrl(): Promise<string> {
  const value = await getDesktopApi().secureStorage.get('camxora.apiBaseUrl')
  return value?.trim() ? value.trim().replace(/\/+$/, '') : 'http://localhost:8000/api/v1'
}

function redirectToLogin(): void {
  window.location.hash = '#/auth/login'
}

async function readJsonSafe(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

function extractErrorMessage(payload: unknown, status: number): string {
  const candidates: unknown[] = []
  if (payload && typeof payload === 'object') {
    const body = payload as ApiErrorPayload & Record<string, unknown>
    if (body.error && typeof body.error === 'object') {
      candidates.push(body.error.message, body.error.detail)
    }
    candidates.push(body.message, body.detail, body.error)
  } else if (typeof payload === 'string') {
    candidates.push(payload)
  }

  for (const value of candidates) {
    const text = normalizeErrorValue(value)
    if (text) {
      return friendlyStatusMessage(status, text)
    }
  }
  return friendlyStatusMessage(status, null)
}

function normalizeErrorValue(value: unknown): string | null {
  if (typeof value === 'string') {
    const text = value.trim()
    return text || null
  }
  if (Array.isArray(value) && value.length > 0) {
    const first = value[0]
    if (first && typeof first === 'object') {
      const row = first as Record<string, unknown>
      for (const key of ['msg', 'message', 'detail'] as const) {
        const nested = row[key]
        if (typeof nested === 'string' && nested.trim()) {
          return nested.trim()
        }
      }
    }
    const text = String(first ?? '').trim()
    return text || null
  }
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>
    for (const key of ['message', 'detail', 'msg'] as const) {
      const nested = row[key]
      if (typeof nested === 'string' && nested.trim()) {
        return nested.trim()
      }
    }
  }
  return null
}

function friendlyStatusMessage(status: number, serverMessage: string | null): string {
  const text = (serverMessage || '').trim()
  if (text.toLowerCase() === 'invalid credentials' || text.toLowerCase() === 'invalid credentials.') {
    return 'Incorrect email or password.'
  }
  if (text) {
    return text
  }
  const defaults: Record<number, string> = {
    400: 'The request could not be completed. Please check your input and try again.',
    401: 'Incorrect email or password.',
    403: 'You do not have permission to do that.',
    404: 'The requested item was not found.',
    409: 'That action conflicts with existing data.',
    422: 'Some fields are invalid. Please review and try again.',
    429: 'Too many requests. Please wait a moment and try again.',
    500: 'Something went wrong on the server. Please try again.',
    502: 'The service is temporarily unavailable. Please try again.',
    503: 'The service is temporarily unavailable. Please try again.',
  }
  return defaults[status] ?? 'Something went wrong. Please try again.'
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  auth?: boolean
}

export async function platformRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = await getBaseUrl()
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`

  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  if (options.auth) {
    await ensureFreshSession()
    const tokens = useAuthStore.getState().tokens
    if (!tokens?.accessToken) {
      await useAuthStore.getState().clear()
      redirectToLogin()
      throw new PlatformApiError(401, 'Unauthenticated', null)
    }
    if (invalidatedAccessToken && tokens.accessToken === invalidatedAccessToken) {
      await useAuthStore.getState().clear()
      redirectToLogin()
      throw new PlatformApiError(401, 'Session expired', null)
    }
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (response.status === 401 && options.auth) {
    const payload = await readJsonSafe(response)
    const activeToken = useAuthStore.getState().tokens?.accessToken ?? null
    invalidatedAccessToken = activeToken
    const refreshed = await ensureFreshSession(true)
    if (refreshed) {
      invalidatedAccessToken = null
      return platformRequest<T>(path, options)
    }
    await useAuthStore.getState().clear()
    redirectToLogin()
    throw new PlatformApiError(401, 'Your session expired. Please sign in again.', payload)
  }

  if (!response.ok) {
    const payload = await readJsonSafe(response)
    const message = extractErrorMessage(payload, response.status)
    throw new PlatformApiError(response.status, message, payload)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const payload = (await readJsonSafe(response)) as T
  return payload
}
