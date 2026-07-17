export type StepId = "setup" | "names" | "logo" | "covers" | "description" | "review";
export type ChannelRole = "primary" | "secondary";

export type PublicDescriptionResponse = {
  id: string;
  name: string;
  match_key: string | null;
};

export type OnboardingGenre = {
  name: string;
  matchKey: string;
};

export type PersistedOnboardingState = {
  email: string | null;
  emailVerified: boolean;
  verificationLastSentAt: number | null;
  planSelectionCompleted: boolean;
  selectedPlanId: string | null;
  pendingBillingPaymentId: string | null;
  pendingBillingCheckoutUrl: string | null;
  redeemCode: string;
  genres: PublicDescriptionResponse[];
  selectedGenre: OnboardingGenre | null;
  primaryName: string;
  secondaryName: string;
  primarySuggestions: string[];
  secondarySuggestions: string[];
  primaryLogoBase64: string | null;
  secondaryLogoBase64: string | null;
  primaryLogoHistory: string[];
  secondaryLogoHistory: string[];
  primaryCoverBase64: string | null;
  secondaryCoverBase64: string | null;
  primaryCoverHistory: string[];
  secondaryCoverHistory: string[];
  primaryDescription: string;
  secondaryDescription: string;
  primaryKeywords: string[];
  secondaryKeywords: string[];
  primaryTags: string[];
  secondaryTags: string[];
};

export type WizardState = PersistedOnboardingState & {
  hydrated: boolean;
  genresLoading: boolean;
};

export function createDraftDefaults(): PersistedOnboardingState {
  return {
    email: null,
    emailVerified: false,
    verificationLastSentAt: null,
    planSelectionCompleted: false,
    selectedPlanId: null,
    pendingBillingPaymentId: null,
    pendingBillingCheckoutUrl: null,
    redeemCode: "",
    genres: [],
    selectedGenre: null,
    primaryName: "",
    secondaryName: "",
    primarySuggestions: [],
    secondarySuggestions: [],
    primaryLogoBase64: null,
    secondaryLogoBase64: null,
    primaryLogoHistory: [],
    secondaryLogoHistory: [],
    primaryCoverBase64: null,
    secondaryCoverBase64: null,
    primaryCoverHistory: [],
    secondaryCoverHistory: [],
    primaryDescription: "",
    secondaryDescription: "",
    primaryKeywords: [],
    secondaryKeywords: [],
    primaryTags: [],
    secondaryTags: [],
  };
}

export function createDefaultState(): WizardState {
  return {
    ...createDraftDefaults(),
    hydrated: false,
    genresLoading: false,
  };
}

export function clampArray<T>(arr: T[], max: number) {
  if (arr.length <= max) return arr;
  return arr.slice(0, max);
}

export function splitLines(text: string) {
  return text
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function joinLines(items: string[]) {
  return items.filter(Boolean).join("\n");
}
