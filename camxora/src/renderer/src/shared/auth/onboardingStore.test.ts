import { waitFor } from '@testing-library/react'

const ONBOARDING_STORAGE_KEY = 'camxora.onboarding.draft'
const secureStorageMap = new Map<string, string>()
const mockSecureStorage = {
  get: vi.fn(async (key: string) => secureStorageMap.get(key) ?? null),
  set: vi.fn(async (key: string, value: string) => {
    secureStorageMap.set(key, value)
    return true
  }),
  remove: vi.fn(async (key: string) => {
    secureStorageMap.delete(key)
    return true
  }),
  clear: vi.fn(async () => {
    secureStorageMap.clear()
    return true
  }),
}

vi.mock('@/shared/api/desktop', () => ({
  getDesktopApi: () => ({
    secureStorage: mockSecureStorage,
  }),
}))

import { useOnboardingStore } from '@/shared/auth/onboardingStore'

describe('onboardingStore', () => {
  beforeEach(() => {
    secureStorageMap.clear()
    mockSecureStorage.get.mockClear()
    mockSecureStorage.set.mockClear()
    mockSecureStorage.remove.mockClear()
    mockSecureStorage.clear.mockClear()
    useOnboardingStore.getState().reset()
  })

  afterEach(() => {
    secureStorageMap.clear()
    useOnboardingStore.getState().reset()
  })

  it('hydrates the saved onboarding draft for the same signed-in account and persists later edits', async () => {
    secureStorageMap.set(
      ONBOARDING_STORAGE_KEY,
      JSON.stringify({
        email: 'boss@example.com',
        emailVerified: true,
        selectedGenre: { name: 'Pop', matchKey: 'pop' },
        primaryName: 'Primary Boss',
        secondaryName: 'Secondary Boss',
        primaryLogoBase64: 'iVBORw0KGgo-primary-logo',
        secondaryLogoBase64: 'iVBORw0KGgo-secondary-logo',
        primaryCoverBase64: '/9j/primary-cover',
        secondaryCoverBase64: 'UklGRsecondary-cover',
        description: 'Shared channel description',
        keywords: ['keyword one', 'keyword two'],
        tags: ['tag-one', 'tag-two'],
      }),
    )

    await useOnboardingStore.getState().hydrate({
      expectedEmail: 'boss@example.com',
      emailVerified: true,
    })

    expect(useOnboardingStore.getState().selectedGenre).toEqual({
      name: 'Pop',
      matchKey: 'pop',
    })
    expect(useOnboardingStore.getState().primaryName).toBe('Primary Boss')
    expect(useOnboardingStore.getState().secondaryName).toBe('Secondary Boss')
    expect(useOnboardingStore.getState().description).toBe('Shared channel description')
    expect(useOnboardingStore.getState().keywords).toEqual(['keyword one', 'keyword two'])
    expect(useOnboardingStore.getState().tags).toEqual(['tag-one', 'tag-two'])

    useOnboardingStore.getState().setPrimaryName('Primary Boss Reloaded')

    await waitFor(() => {
      const saved = JSON.parse(secureStorageMap.get(ONBOARDING_STORAGE_KEY) ?? '{}') as {
        primaryName?: string
      }
      expect(saved.primaryName).toBe('Primary Boss Reloaded')
    })

    useOnboardingStore.getState().reset()

    await waitFor(() => {
      expect(secureStorageMap.has(ONBOARDING_STORAGE_KEY)).toBe(false)
    })
    expect(useOnboardingStore.getState().selectedGenre).toBeNull()
    expect(useOnboardingStore.getState().primaryName).toBe('')
    expect(useOnboardingStore.getState().description).toBe('')
  })

  it('drops a stale onboarding draft when a different account signs in', async () => {
    secureStorageMap.set(
      ONBOARDING_STORAGE_KEY,
      JSON.stringify({
        email: 'other@example.com',
        selectedGenre: { name: 'EDM', matchKey: 'edm' },
        primaryName: 'Stale Primary',
        description: 'Stale description',
      }),
    )

    await useOnboardingStore.getState().hydrate({
      expectedEmail: 'boss@example.com',
      emailVerified: true,
    })

    expect(useOnboardingStore.getState().email).toBe('boss@example.com')
    expect(useOnboardingStore.getState().emailVerified).toBe(true)
    expect(useOnboardingStore.getState().selectedGenre).toBeNull()
    expect(useOnboardingStore.getState().primaryName).toBe('')
    expect(useOnboardingStore.getState().description).toBe('')
    expect(secureStorageMap.has(ONBOARDING_STORAGE_KEY)).toBe(false)
  })
})
