"use client";

import {
  createDefaultState,
  createDraftDefaults,
  type OnboardingGenre,
  type PersistedOnboardingState,
  type PublicDescriptionResponse,
} from "@/app/onboarding/types";

const ONBOARDING_STORAGE_KEY = "camxora.onboarding.draft";

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? "").trim()).filter(Boolean) : [];
}

function normalizeGenres(value: unknown): PublicDescriptionResponse[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      const id = String(record.id ?? "").trim();
      const name = String(record.name ?? "").trim();
      const match_key =
        record.match_key === null || record.match_key === undefined
          ? null
          : String(record.match_key).trim();
      if (!id || !name) return null;
      return { id, name, match_key };
    })
    .filter((item): item is PublicDescriptionResponse => Boolean(item));
}

function normalizeSelectedGenre(value: unknown): OnboardingGenre | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const name = String(record.name ?? "").trim();
  const matchKey = String(record.matchKey ?? "").trim();
  if (!name) {
    return null;
  }
  return {
    name,
    matchKey,
  };
}

export function parsePersistedDraft(raw: string | null): PersistedOnboardingState | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<PersistedOnboardingState>;
    const defaults = createDraftDefaults();
    const legacyDescription = String((parsed as { description?: unknown }).description ?? "");
    const legacyKeywords = normalizeStringArray((parsed as { keywords?: unknown }).keywords);
    const legacyTags = normalizeStringArray((parsed as { tags?: unknown }).tags);
    return {
      ...defaults,
      email: typeof parsed.email === "string" && parsed.email.trim() ? parsed.email.trim() : null,
      emailVerified: Boolean(parsed.emailVerified),
      verificationLastSentAt:
        typeof parsed.verificationLastSentAt === "number" ? parsed.verificationLastSentAt : null,
      planSelectionCompleted: Boolean(parsed.planSelectionCompleted),
      selectedPlanId: typeof parsed.selectedPlanId === "string" ? parsed.selectedPlanId : null,
      pendingBillingPaymentId:
        typeof parsed.pendingBillingPaymentId === "string" ? parsed.pendingBillingPaymentId : null,
      pendingBillingCheckoutUrl:
        typeof parsed.pendingBillingCheckoutUrl === "string" ? parsed.pendingBillingCheckoutUrl : null,
      redeemCode: String(parsed.redeemCode ?? ""),
      genres: normalizeGenres(parsed.genres),
      selectedGenre: normalizeSelectedGenre(parsed.selectedGenre),
      primaryName: String(parsed.primaryName ?? ""),
      secondaryName: String(parsed.secondaryName ?? ""),
      primarySuggestions: normalizeStringArray(parsed.primarySuggestions),
      secondarySuggestions: normalizeStringArray(parsed.secondarySuggestions),
      primaryLogoBase64: typeof parsed.primaryLogoBase64 === "string" ? parsed.primaryLogoBase64 : null,
      secondaryLogoBase64:
        typeof parsed.secondaryLogoBase64 === "string" ? parsed.secondaryLogoBase64 : null,
      primaryLogoHistory: normalizeStringArray(parsed.primaryLogoHistory),
      secondaryLogoHistory: normalizeStringArray(parsed.secondaryLogoHistory),
      primaryCoverBase64: typeof parsed.primaryCoverBase64 === "string" ? parsed.primaryCoverBase64 : null,
      secondaryCoverBase64:
        typeof parsed.secondaryCoverBase64 === "string" ? parsed.secondaryCoverBase64 : null,
      primaryCoverHistory: normalizeStringArray(parsed.primaryCoverHistory),
      secondaryCoverHistory: normalizeStringArray(parsed.secondaryCoverHistory),
      primaryDescription: String(parsed.primaryDescription ?? legacyDescription),
      secondaryDescription: String(parsed.secondaryDescription ?? legacyDescription),
      primaryKeywords: normalizeStringArray(parsed.primaryKeywords ?? legacyKeywords),
      secondaryKeywords: normalizeStringArray(parsed.secondaryKeywords ?? legacyKeywords),
      primaryTags: normalizeStringArray(parsed.primaryTags ?? legacyTags),
      secondaryTags: normalizeStringArray(parsed.secondaryTags ?? legacyTags),
    };
  } catch {
    return null;
  }
}

export function toPersistedDraft(
  state: PersistedOnboardingState | ReturnType<typeof createDefaultState>,
): PersistedOnboardingState {
  return {
    email: state.email,
    emailVerified: state.emailVerified,
    verificationLastSentAt: state.verificationLastSentAt,
    planSelectionCompleted: state.planSelectionCompleted,
    selectedPlanId: state.selectedPlanId,
    pendingBillingPaymentId: state.pendingBillingPaymentId,
    pendingBillingCheckoutUrl: state.pendingBillingCheckoutUrl,
    redeemCode: state.redeemCode,
    genres: state.genres,
    selectedGenre: state.selectedGenre,
    primaryName: state.primaryName,
    secondaryName: state.secondaryName,
    primarySuggestions: state.primarySuggestions,
    secondarySuggestions: state.secondarySuggestions,
    // Keep browser storage lightweight. Heavy assets persist in the server draft.
    primaryLogoBase64: null,
    secondaryLogoBase64: null,
    primaryLogoHistory: [],
    secondaryLogoHistory: [],
    primaryCoverBase64: null,
    secondaryCoverBase64: null,
    primaryCoverHistory: [],
    secondaryCoverHistory: [],
    primaryDescription: state.primaryDescription,
    secondaryDescription: state.secondaryDescription,
    primaryKeywords: state.primaryKeywords,
    secondaryKeywords: state.secondaryKeywords,
    primaryTags: state.primaryTags,
    secondaryTags: state.secondaryTags,
  };
}

export function loadOnboardingDraft(): PersistedOnboardingState | null {
  if (typeof window === "undefined") {
    return null;
  }
  return parsePersistedDraft(window.localStorage.getItem(ONBOARDING_STORAGE_KEY));
}

export function saveOnboardingDraft(state: PersistedOnboardingState): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(toPersistedDraft(state)));
  } catch {
    // Ignore quota failures because the authoritative onboarding draft lives in the database.
  }
}

export function clearOnboardingDraft(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(ONBOARDING_STORAGE_KEY);
}
