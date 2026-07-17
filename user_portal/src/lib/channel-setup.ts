import { platformJson } from "@/lib/auth-fetch";
import type { PersistedOnboardingState, PublicDescriptionResponse } from "@/app/onboarding/types";

export type ChannelRole = "primary" | "secondary";

export type ProfilesStatus = {
  has_profiles: boolean;
  profile_count: number;
};

export type ExistingProfile = {
  id: string;
  user_id: string;
  name: string;
  folder_name?: string | null;
  run_prefix?: string | null;
  logo_path?: string | null;
  video_template_id?: string | null;
  reel_template_id?: string | null;
  output_resolution?: string | null;
  image_config?: Record<string, unknown>;
  youtube_config?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export async function getProfilesStatus(): Promise<ProfilesStatus> {
  return platformJson<ProfilesStatus>({
    path: "/channel-setup/profiles-status",
    method: "GET",
  });
}

export async function listProfiles(): Promise<ExistingProfile[]> {
  return platformJson<ExistingProfile[]>({
    path: "/profiles",
    method: "GET",
  });
}

export async function updateProfile(
  profileId: string,
  input: {
    name?: string;
    folder_name?: string | null;
    run_prefix?: string | null;
    output_resolution?: string | null;
    image_config?: Record<string, unknown> | null;
    youtube_config?: Record<string, unknown> | null;
    logo_base64?: string | null;
    cover_images?: string[] | null;
  },
): Promise<ExistingProfile> {
  return platformJson<ExistingProfile>({
    path: `/profiles/${encodeURIComponent(profileId)}`,
    method: "PUT",
    body: {
      name: input.name,
      folder_name: input.folder_name,
      run_prefix: input.run_prefix,
      output_resolution: input.output_resolution,
      image_config: input.image_config ?? undefined,
      youtube_config: input.youtube_config ?? undefined,
      logo_base64: input.logo_base64 ?? undefined,
      cover_images: input.cover_images ?? undefined,
    },
  });
}

export type CurrentUserResponse = {
  id: string;
  email: string;
  email_confirmed: boolean;
  display_name?: string | null;
  role?: string;
  status?: string;
  suspension_reason?: string | null;
  credit_balance?: number;
  plan_name?: string | null;
  profile_allowance?: number | null;
  profile_addon_slots?: number;
  profile_addon_pending?: number;
  effective_profile_allowance?: number | null;
  effective_quota_channels?: number | null;
  channel_profile_count?: number;
  onboarding_paid?: boolean;
  created_at?: string;
  updated_at?: string | null;
};

export type VerificationResponse = {
  message: string;
  email?: string | null;
  is_verified: boolean;
};

export async function getCurrentUser(): Promise<CurrentUserResponse> {
  return platformJson<CurrentUserResponse>({
    path: "/users/me",
    method: "GET",
  });
}

export async function updateCurrentUser(input: {
  display_name?: string;
  password?: string;
}): Promise<CurrentUserResponse> {
  return platformJson<CurrentUserResponse>({
    path: "/users/me",
    method: "PATCH",
    body: {
      display_name: input.display_name,
      password: input.password,
    },
  });
}

export async function sendVerification(email: string): Promise<VerificationResponse> {
  return platformJson<VerificationResponse>({
    path: "/auth/send-verification",
    method: "POST",
    body: { email },
    auth: false,
  });
}

export async function verifyEmail(input: {
  email: string;
  code: string;
}): Promise<VerificationResponse> {
  return platformJson<VerificationResponse>({
    path: "/auth/verify-email",
    method: "POST",
    body: input,
    auth: false,
  });
}

export async function listPublicGenres(): Promise<PublicDescriptionResponse[]> {
  return platformJson<PublicDescriptionResponse[]>({
    path: "/prompts/descriptions/public",
    method: "GET",
  });
}

export type GenerateNamesResponse = {
  names: string[];
};

export type OnboardingDraftResponse = {
  payload: Partial<PersistedOnboardingState>;
  name_generate_limit: number;
  name_generate_used: number;
  name_generate_remaining: number;
  logo_generate_limit: number;
  logo_generate_used: number;
  logo_generate_remaining: number;
  cover_generate_limit: number;
  cover_generate_used: number;
  cover_generate_remaining: number;
  description_generate_limit: number;
  description_generate_used: number;
  description_generate_remaining: number;
  keywords_generate_limit: number;
  keywords_generate_used: number;
  keywords_generate_remaining: number;
  tags_generate_limit: number;
  tags_generate_used: number;
  tags_generate_remaining: number;
};

export async function getOnboardingDraft(): Promise<OnboardingDraftResponse> {
  return platformJson<OnboardingDraftResponse>({
    path: "/channel-setup/draft",
    method: "GET",
  });
}

export async function saveOnboardingDraftToServer(
  payload: PersistedOnboardingState,
): Promise<OnboardingDraftResponse> {
  return platformJson<OnboardingDraftResponse>({
    path: "/channel-setup/draft",
    method: "PUT",
    body: { payload },
  });
}

export async function generateNames(input: {
  genre: string;
  role: ChannelRole | "both";
  description?: string;
  match_key?: string;
  count?: number;
}): Promise<GenerateNamesResponse> {
  return platformJson<GenerateNamesResponse>({
    path: "/channel-setup/generate-names",
    method: "POST",
    body: {
      genre: input.genre,
      role: input.role,
      description: input.description ?? "",
      match_key: input.match_key ?? "",
      count: input.count ?? 10,
    },
  });
}

export type GenerateImageResponse = {
  image_base64: string;
  width: number;
  height: number;
};

export async function generateLogo(input: {
  channel_name: string;
  genre: string;
  role: ChannelRole;
  match_key?: string;
}): Promise<GenerateImageResponse> {
  return platformJson<GenerateImageResponse>({
    path: "/channel-setup/generate-logo",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      role: input.role,
      match_key: input.match_key ?? "",
    },
  });
}

export type GenerateCoversResponse = {
  images: string[];
};

export async function generateCovers(input: {
  channel_name: string;
  genre: string;
  role: ChannelRole;
  match_key?: string;
  count?: number;
}): Promise<GenerateCoversResponse> {
  return platformJson<GenerateCoversResponse>({
    path: "/channel-setup/generate-covers",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      role: input.role,
      match_key: input.match_key ?? "",
      count: input.count ?? 1,
    },
  });
}

export type GenerateDescriptionResponse = {
  description: string;
  keywords: string[];
  tags: string[];
};

export type GenerateDescriptionTextResponse = {
  description: string;
};

export type GenerateKeywordsResponse = {
  keywords: string[];
};

export type GenerateTagsResponse = {
  tags: string[];
};

export async function generateDescription(input: {
  channel_name: string;
  genre: string;
  match_key?: string;
  description?: string;
}): Promise<GenerateDescriptionResponse> {
  return platformJson<GenerateDescriptionResponse>({
    path: "/channel-setup/generate-description",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      match_key: input.match_key ?? "",
      description: input.description ?? "",
    },
  });
}

export async function generateDescriptionText(input: {
  channel_name: string;
  genre: string;
  match_key?: string;
  description?: string;
}): Promise<GenerateDescriptionTextResponse> {
  return platformJson<GenerateDescriptionTextResponse>({
    path: "/channel-setup/generate-description-text",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      match_key: input.match_key ?? "",
      description: input.description ?? "",
    },
  });
}

export async function generateKeywords(input: {
  channel_name: string;
  genre: string;
  match_key?: string;
  description?: string;
}): Promise<GenerateKeywordsResponse> {
  return platformJson<GenerateKeywordsResponse>({
    path: "/channel-setup/generate-keywords",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      match_key: input.match_key ?? "",
      description: input.description ?? "",
    },
  });
}

export async function generateTags(input: {
  channel_name: string;
  genre: string;
  match_key?: string;
  description?: string;
}): Promise<GenerateTagsResponse> {
  return platformJson<GenerateTagsResponse>({
    path: "/channel-setup/generate-tags",
    method: "POST",
    body: {
      channel_name: input.channel_name,
      genre: input.genre,
      match_key: input.match_key ?? "",
      description: input.description ?? "",
    },
  });
}

export type CreateProfileResponse = {
  profile_id: string;
  name: string;
  message: string;
};

export async function createProfile(input: {
  name: string;
  genre: string;
  role: ChannelRole;
  logo_base64?: string | null;
  cover_images?: string[];
  description?: string;
  keywords?: string[];
  tags?: string[];
  match_key?: string;
}): Promise<CreateProfileResponse> {
  return platformJson<CreateProfileResponse>({
    path: "/channel-setup/create-profile",
    method: "POST",
    body: {
      name: input.name,
      genre: input.genre,
      role: input.role,
      logo_base64: input.logo_base64 ?? null,
      cover_images: input.cover_images ?? [],
      description: input.description ?? "",
      keywords: input.keywords ?? [],
      tags: input.tags ?? [],
      match_key: input.match_key ?? "",
    },
  });
}
