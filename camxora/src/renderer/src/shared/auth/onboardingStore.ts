import { create } from 'zustand'

import { getDesktopApi } from '@/shared/api/desktop'
import type { PublicDescriptionResponse } from '@/shared/api/platformEndpoints'

export type OnboardingGenre = {
  name: string
  matchKey: string
}

type OnboardingState = {
  hydrated: boolean
  hydrate: (options?: { expectedEmail?: string | null; emailVerified?: boolean }) => Promise<void>
  email: string | null
  emailVerified: boolean
  setEmail: (email: string) => void
  setEmailVerified: (verified: boolean) => void
  verificationLastSentAt: number | null
  setVerificationLastSentAt: (timestamp: number | null) => void

  genres: PublicDescriptionResponse[]
  genresLoading: boolean
  setGenresLoading: (loading: boolean) => void
  setGenres: (genres: PublicDescriptionResponse[]) => void

  selectedGenre: OnboardingGenre | null
  setSelectedGenre: (genre: OnboardingGenre | null) => void

  primaryName: string
  secondaryName: string
  setPrimaryName: (name: string) => void
  setSecondaryName: (name: string) => void

  primarySuggestions: string[]
  secondarySuggestions: string[]
  setNameSuggestions: (input: { primary: string[]; secondary: string[] }) => void

  primaryLogoBase64: string | null
  secondaryLogoBase64: string | null
  setLogoBase64: (input: { role: 'primary' | 'secondary'; base64: string | null }) => void

  primaryCoverBase64: string | null
  secondaryCoverBase64: string | null
  setCoverBase64: (input: { role: 'primary' | 'secondary'; base64: string | null }) => void

  description: string
  keywords: string[]
  tags: string[]
  setDescription: (description: string) => void
  setKeywords: (keywords: string[]) => void
  setTags: (tags: string[]) => void
  reset: () => void
}

const ONBOARDING_STORAGE_KEY = 'camxora.onboarding.draft'

type PersistedOnboardingState = {
  email: string | null
  emailVerified: boolean
  verificationLastSentAt: number | null
  genres: PublicDescriptionResponse[]
  selectedGenre: OnboardingGenre | null
  primaryName: string
  secondaryName: string
  primarySuggestions: string[]
  secondarySuggestions: string[]
  primaryLogoBase64: string | null
  secondaryLogoBase64: string | null
  primaryCoverBase64: string | null
  secondaryCoverBase64: string | null
  description: string
  keywords: string[]
  tags: string[]
}

function createDraftDefaults(): PersistedOnboardingState {
  return {
    email: null,
    emailVerified: false,
    verificationLastSentAt: null,
    genres: [],
    selectedGenre: null,
    primaryName: '',
    secondaryName: '',
    primarySuggestions: [],
    secondarySuggestions: [],
    primaryLogoBase64: null,
    secondaryLogoBase64: null,
    primaryCoverBase64: null,
    secondaryCoverBase64: null,
    description: '',
    keywords: [],
    tags: [],
  }
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? '').trim()).filter(Boolean) : []
}

function normalizeSelectedGenre(value: unknown): OnboardingGenre | null {
  if (!value || typeof value !== 'object') {
    return null
  }
  const record = value as Record<string, unknown>
  const name = String(record.name ?? '').trim()
  const matchKey = String(record.matchKey ?? '').trim()
  if (!name) {
    return null
  }
  return {
    name,
    matchKey,
  }
}

function parsePersistedDraft(raw: string | null): PersistedOnboardingState | null {
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<PersistedOnboardingState>
    const defaults = createDraftDefaults()
    return {
      ...defaults,
      email: typeof parsed.email === 'string' && parsed.email.trim() ? parsed.email.trim() : null,
      emailVerified: Boolean(parsed.emailVerified),
      verificationLastSentAt:
        typeof parsed.verificationLastSentAt === 'number' ? parsed.verificationLastSentAt : null,
      genres: Array.isArray(parsed.genres) ? parsed.genres : defaults.genres,
      selectedGenre: normalizeSelectedGenre(parsed.selectedGenre),
      primaryName: String(parsed.primaryName ?? ''),
      secondaryName: String(parsed.secondaryName ?? ''),
      primarySuggestions: normalizeStringArray(parsed.primarySuggestions),
      secondarySuggestions: normalizeStringArray(parsed.secondarySuggestions),
      primaryLogoBase64: typeof parsed.primaryLogoBase64 === 'string' ? parsed.primaryLogoBase64 : null,
      secondaryLogoBase64: typeof parsed.secondaryLogoBase64 === 'string' ? parsed.secondaryLogoBase64 : null,
      primaryCoverBase64: typeof parsed.primaryCoverBase64 === 'string' ? parsed.primaryCoverBase64 : null,
      secondaryCoverBase64: typeof parsed.secondaryCoverBase64 === 'string' ? parsed.secondaryCoverBase64 : null,
      description: String(parsed.description ?? ''),
      keywords: normalizeStringArray(parsed.keywords),
      tags: normalizeStringArray(parsed.tags),
    }
  } catch {
    return null
  }
}

function toPersistedDraft(state: OnboardingState | PersistedOnboardingState): PersistedOnboardingState {
  return {
    email: state.email,
    emailVerified: state.emailVerified,
    verificationLastSentAt: state.verificationLastSentAt,
    genres: state.genres,
    selectedGenre: state.selectedGenre,
    primaryName: state.primaryName,
    secondaryName: state.secondaryName,
    primarySuggestions: state.primarySuggestions,
    secondarySuggestions: state.secondarySuggestions,
    primaryLogoBase64: state.primaryLogoBase64,
    secondaryLogoBase64: state.secondaryLogoBase64,
    primaryCoverBase64: state.primaryCoverBase64,
    secondaryCoverBase64: state.secondaryCoverBase64,
    description: state.description,
    keywords: state.keywords,
    tags: state.tags,
  }
}

async function persistDraft(state: OnboardingState | PersistedOnboardingState): Promise<void> {
  const storage = getDesktopApi().secureStorage
  if (!storage?.set) {
    return
  }
  await storage.set(ONBOARDING_STORAGE_KEY, JSON.stringify(toPersistedDraft(state)))
}

async function clearPersistedDraft(): Promise<void> {
  const storage = getDesktopApi().secureStorage
  if (!storage?.remove) {
    return
  }
  await storage.remove(ONBOARDING_STORAGE_KEY)
}

export const useOnboardingStore = create<OnboardingState>((set, get) => {
  const updateAndPersist = (patch: Partial<PersistedOnboardingState>): void => {
    set(patch)
    void persistDraft(get())
  }

  return {
    hydrated: false,
    hydrate: async (options) => {
      const storage = getDesktopApi().secureStorage
      const raw = storage?.get ? await storage.get(ONBOARDING_STORAGE_KEY) : null
      const persisted = parsePersistedDraft(raw)
      const expectedEmail = String(options?.expectedEmail ?? '')
        .trim()
        .toLowerCase()
      const persistedEmail = String(persisted?.email ?? '')
        .trim()
        .toLowerCase()

      if (expectedEmail && persistedEmail && expectedEmail !== persistedEmail) {
        await clearPersistedDraft()
        set({
          ...createDraftDefaults(),
          email: options?.expectedEmail?.trim() || null,
          emailVerified: Boolean(options?.emailVerified),
          genresLoading: false,
          hydrated: true,
        })
        return
      }

      const nextDraft = persisted ?? createDraftDefaults()
      set({
        ...nextDraft,
        email: options?.expectedEmail?.trim() || nextDraft.email,
        emailVerified: typeof options?.emailVerified === 'boolean' ? options.emailVerified : nextDraft.emailVerified,
        genresLoading: false,
        hydrated: true,
      })

      if (options?.expectedEmail || typeof options?.emailVerified === 'boolean') {
        void persistDraft(get())
      }
    },
    ...createDraftDefaults(),
    setEmail: (email) => updateAndPersist({ email }),
    setEmailVerified: (emailVerified) => updateAndPersist({ emailVerified }),
    verificationLastSentAt: null,
    setVerificationLastSentAt: (verificationLastSentAt) => updateAndPersist({ verificationLastSentAt }),

    genresLoading: false,
    setGenresLoading: (genresLoading) => set({ genresLoading }),
    setGenres: (genres) => updateAndPersist({ genres }),

    selectedGenre: null,
    setSelectedGenre: (selectedGenre) => updateAndPersist({ selectedGenre }),

    primaryName: '',
    secondaryName: '',
    setPrimaryName: (primaryName) => updateAndPersist({ primaryName }),
    setSecondaryName: (secondaryName) => updateAndPersist({ secondaryName }),

    primarySuggestions: [],
    secondarySuggestions: [],
    setNameSuggestions: ({ primary, secondary }) =>
      updateAndPersist({ primarySuggestions: primary, secondarySuggestions: secondary }),

    primaryLogoBase64: null,
    secondaryLogoBase64: null,
    setLogoBase64: ({ role, base64 }) =>
      updateAndPersist(role === 'primary' ? { primaryLogoBase64: base64 } : { secondaryLogoBase64: base64 }),

    primaryCoverBase64: null,
    secondaryCoverBase64: null,
    setCoverBase64: ({ role, base64 }) =>
      updateAndPersist(role === 'primary' ? { primaryCoverBase64: base64 } : { secondaryCoverBase64: base64 }),

    description: '',
    keywords: [],
    tags: [],
    setDescription: (description) => updateAndPersist({ description }),
    setKeywords: (keywords) => updateAndPersist({ keywords }),
    setTags: (tags) => updateAndPersist({ tags }),
    reset: () => {
      set({
        ...createDraftDefaults(),
        genresLoading: false,
        hydrated: true,
      })
      void clearPersistedDraft()
    },
  }
})
