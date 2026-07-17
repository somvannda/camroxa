"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Copy,
  ExternalLink,
  Image as ImageIcon,
  LoaderCircle,
  Mail,
  ShieldCheck,
} from "lucide-react";

import { clearOnboardingDraft, loadOnboardingDraft, saveOnboardingDraft } from "@/app/onboarding/draft";
import {
  createDefaultState,
  type ChannelRole,
  type OnboardingGenre,
  type WizardState,
} from "@/app/onboarding/types";
import { PortalMarketingShell } from "@/components/auth/portal-marketing-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/hooks/use-toast";
import {
  formatYoutubeKeywords,
  formatYoutubeTags,
  parseYoutubeCommaInput,
} from "@/lib/youtube-seo";
import {
  createProfile,
  generateCovers,
  generateDescriptionText,
  generateKeywords,
  generateLogo,
  generateNames,
  generateTags,
  getOnboardingDraft,
  type CurrentUserResponse,
  getCurrentUser,
  getProfilesStatus,
  listProfiles,
  listPublicGenres,
  saveOnboardingDraftToServer,
  sendVerification,
  verifyEmail,
} from "@/lib/channel-setup";
import {
  createBillingPayment,
  completeAddonOnboarding,
  getBillingPayment,
  getPublicPlanTermDiscounts,
  listBillingProviders,
  listPublicPlans,
  resolveBillingPaymentByExternalId,
  type BillingPayment,
  type BillingProviderConfig,
  type PublicPlan,
} from "@/lib/billing";
import { OnboardingPlanPicker } from "@/components/onboarding/onboarding-plan-picker";
import { DEFAULT_TERM_DISCOUNTS, type PlanTermDiscounts } from "@/lib/plan-pricing";
import { getWebsiteBaseUrl } from "@/lib/site-urls";
import { refreshWithToken } from "@/lib/platform-api";
import { clearSession, saveSession } from "@/lib/auth";
import {
  clearPendingRedeemCode,
  loadPendingRedeemCode,
  previewRedeemCode,
  savePendingRedeemCode,
} from "@/lib/redeem-codes";
import { cn } from "@/lib/utils";

const ROLE_ORDER: ChannelRole[] = ["primary", "secondary"];
const ROLE_LABELS: Record<ChannelRole, string> = {
  primary: "Primary",
  secondary: "Secondary",
};
const ROLE_ACCENTS: Record<ChannelRole, string> = {
  primary: "#8B5CF6",
  secondary: "#3B82F6",
};
const MAX_SHARED_NAME_GENERATES = 3;
const STEP_DEFS = [
  { emoji: "🎵", title: "Pick Your Genre", subtitle: "Choose your music genre" },
  { emoji: "✏️", title: "Choose Names", subtitle: "Pick unique channel names" },
  { emoji: "🎨", title: "Design Logos", subtitle: "Create visual identity" },
  { emoji: "🖼️", title: "Cover Art", subtitle: "YouTube banners" },
  { emoji: "📝", title: "Description", subtitle: "SEO content & tags" },
] as const;

type ExistingRoleState = Record<ChannelRole, boolean>;
type BusyState = {
  loading: boolean;
  loadingPlans: boolean;
  sendingCode: boolean;
  verifyingCode: boolean;
  creatingPayment: boolean;
  checkingPayment: boolean;
  previewingRedeem: boolean;
  generatingNames: boolean;
  generatingLogos: Record<ChannelRole, boolean>;
  generatingCovers: Record<ChannelRole, boolean>;
  generatingDescriptions: Record<ChannelRole, boolean>;
  generatingKeywords: Record<ChannelRole, boolean>;
  generatingTags: Record<ChannelRole, boolean>;
  creatingProfiles: boolean;
};

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

function dataUrlFromBase64(base64: string | null) {
  return base64 ? `data:image/png;base64,${base64}` : null;
}

function parseCsv(text: string) {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinCsv(items: string[]) {
  return items.filter(Boolean).join(", ");
}

function uniquePush(items: string[], value: string) {
  if (!value) return items;
  if (items.includes(value)) return items;
  return [value, ...items].slice(0, 6);
}

function splitCombinedSuggestions(items: string[]) {
  const midpoint = Math.ceil(items.length / 2);
  return {
    primary: items.slice(0, midpoint),
    secondary: items.slice(midpoint),
  };
}

function buildNamePromptContext(genre: string, prompt?: string) {
  const trimmed = prompt?.trim();
  if (!trimmed) return undefined;
  return `Selected genre: ${genre}\nAdditional direction: ${trimmed}`;
}

function getRoleValue<T>(role: ChannelRole, primary: T, secondary: T): T {
  return role === "primary" ? primary : secondary;
}

function hexToRgba(hex: string, alpha: number) {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) return `rgba(255, 255, 255, ${alpha})`;
  const value = Number.parseInt(normalized, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function fileToBase64(file: File) {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return window.btoa(binary);
}

function downloadBase64(base64: string, filename: string) {
  const link = document.createElement("a");
  link.href = `data:image/png;base64,${base64}`;
  link.download = filename;
  link.click();
}

function VerificationCodeBoxes(props: {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const inputRefs = React.useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length: 6 }, (_, index) => props.value[index] ?? "");

  function commit(nextDigits: string[]) {
    props.onChange(nextDigits.join("").slice(0, 6));
  }

  function focusIndex(index: number) {
    const target = inputRefs.current[index];
    if (target) {
      target.focus();
      target.select();
    }
  }

  function setDigit(index: number, rawValue: string) {
    const cleaned = rawValue.replace(/\D/g, "");
    if (!cleaned) {
      const next = [...digits];
      next[index] = "";
      commit(next);
      return;
    }

    const next = [...digits];
    for (let offset = 0; offset < cleaned.length && index + offset < 6; offset += 1) {
      next[index + offset] = cleaned[offset] ?? "";
    }
    commit(next);
    focusIndex(Math.min(index + cleaned.length, 5));
  }

  return (
    <div className="grid grid-cols-6 gap-2 sm:gap-3">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(node) => {
            inputRefs.current[index] = node;
          }}
          value={digit}
          disabled={props.disabled}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          maxLength={1}
          aria-label={`Verification digit ${index + 1}`}
          onChange={(event) => setDigit(index, event.target.value)}
          onFocus={(event) => event.currentTarget.select()}
          onKeyDown={(event) => {
            if (event.key === "Backspace") {
              if (digits[index]) {
                const next = [...digits];
                next[index] = "";
                commit(next);
              } else if (index > 0) {
                const next = [...digits];
                next[index - 1] = "";
                commit(next);
                focusIndex(index - 1);
              }
              return;
            }

            if (event.key === "ArrowLeft" && index > 0) {
              event.preventDefault();
              focusIndex(index - 1);
            }

            if (event.key === "ArrowRight" && index < 5) {
              event.preventDefault();
              focusIndex(index + 1);
            }
          }}
          onPaste={(event) => {
            event.preventDefault();
            setDigit(index, event.clipboardData.getData("text"));
          }}
          className="h-14 rounded-xl border border-white/10 bg-white/[0.04] text-center text-xl font-semibold tracking-[0.08em] text-white outline-none transition focus:border-fuchsia-300/60 focus:bg-white/[0.07] focus:ring-2 focus:ring-fuchsia-400/20 disabled:cursor-not-allowed disabled:opacity-60"
        />
      ))}
    </div>
  );
}

function ChannelNameColumn(props: {
  role: ChannelRole;
  accent: string;
  suggestions: string[];
  value: string;
  status: string;
  disabled: boolean;
  onPick: (value: string) => void;
  onChange: (value: string) => void;
  onGenerate: () => void;
  generateLabel: string;
}) {
  const accentBorder = hexToRgba(props.accent, 0.34);
  const accentSoft = hexToRgba(props.accent, 0.14);
  const accentStrong = hexToRgba(props.accent, 0.28);

  return (
    <div
      className="flex min-h-[460px] flex-col rounded-xl border p-4"
      style={{
        borderColor: accentBorder,
        background:
          "linear-gradient(180deg, rgba(22, 16, 40, 0.96) 0%, rgba(12, 18, 48, 0.98) 100%)",
        boxShadow: `inset 0 1px 0 rgba(255,255,255,0.03), 0 18px 44px ${hexToRgba(props.accent, 0.08)}`,
      }}
    >
      <div className="text-lg font-semibold" style={{ color: props.accent }}>
        {ROLE_LABELS[props.role]} Channel
      </div>
      <div className="mt-2 text-sm text-[#a8afc7]">{props.status}</div>

      <Input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        placeholder="Type your own name..."
        className="mt-4 h-11 border px-4 text-sm text-white placeholder:text-[#7d84a0] focus-visible:ring-0 focus-visible:ring-offset-0"
        style={{
          borderColor: accentBorder,
          backgroundColor: "rgba(17, 23, 56, 0.82)",
          boxShadow: `inset 0 1px 0 rgba(255,255,255,0.02), 0 0 0 1px ${accentSoft}`,
        }}
        disabled={props.disabled}
      />

      <div className="mt-4 flex-1 overflow-hidden rounded-lg">
        <div className="camxora-scrollbar grid max-h-[180px] grid-cols-1 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
          {props.suggestions.map((suggestion) => {
            const selected = suggestion === props.value;
            return (
              <button
                key={`${props.role}-${suggestion}`}
                type="button"
                onClick={() => props.onPick(suggestion)}
                disabled={props.disabled}
                className={cn(
                  "h-9 truncate rounded-md border px-3 text-left text-[13px] font-semibold transition-colors",
                  selected
                    ? "border-transparent text-white"
                    : "text-[#eef4ff] hover:bg-white/[0.08]",
                )}
                style={
                  selected
                    ? {
                        borderColor: props.accent,
                        backgroundImage: `linear-gradient(135deg, ${hexToRgba(props.accent, 0.96)} 0%, ${hexToRgba(props.accent, 0.76)} 100%)`,
                        boxShadow: `0 12px 24px ${accentStrong}`,
                      }
                    : {
                        borderColor: accentBorder,
                        backgroundColor: "rgba(17, 23, 56, 0.72)",
                      }
                }
              >
                {suggestion}
              </button>
            );
          })}
        </div>
      </div>

      <Button
        type="button"
        variant="ghost"
        onClick={props.onGenerate}
        disabled={props.disabled}
        className="mt-4 h-10 justify-start rounded-lg border px-4 text-sm text-white transition-colors hover:bg-white/10"
        style={{
          borderColor: accentBorder,
          backgroundColor: accentSoft,
          boxShadow: `inset 0 1px 0 rgba(255,255,255,0.02)`,
        }}
      >
        {props.generateLabel}
      </Button>
    </div>
  );
}

function ThumbnailButton(props: {
  src: string;
  selected: boolean;
  circle?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={cn(
        "overflow-hidden border transition-colors",
        props.circle ? "h-12 w-12 rounded-full" : "h-12 w-20 rounded-md",
        props.selected ? "border-primary" : "border-white/10 hover:border-primary/50",
      )}
    >
      <img
        src={dataUrlFromBase64(props.src) ?? ""}
        alt=""
        className={cn("h-full w-full object-cover", props.circle ? "rounded-full" : "rounded-md")}
      />
    </button>
  );
}

function AssetColumn(props: {
  role: ChannelRole;
  accent: string;
  preview: string | null;
  history: string[];
  loading: boolean;
  circle?: boolean;
  previewLabel: string;
  countLabel?: string;
  primaryAction: string;
  generateDisabled?: boolean;
  onGenerate: () => void;
  onSave: () => void;
  onUpload: () => void;
  onPickHistory: (value: string) => void;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-white/10 bg-[#0c1230] p-5">
      <div className="text-lg font-semibold" style={{ color: props.accent }}>
        {props.previewLabel}
      </div>

      <div className="mt-4 flex justify-center">
        <div
          className={cn(
            "relative flex items-center justify-center overflow-hidden border border-primary/20 bg-[#111738] text-xs text-white/30",
            props.circle ? "h-[210px] w-[210px] rounded-full" : "h-[214px] w-full max-w-[380px] rounded-lg",
          )}
        >
          {props.preview ? (
            <img
              src={dataUrlFromBase64(props.preview) ?? ""}
              alt=""
              className={cn("h-full w-full object-cover", props.circle ? "rounded-full" : "rounded-lg")}
            />
          ) : (
            <div>{props.loading ? "Generating..." : "Click Generate"}</div>
          )}
          {props.loading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-[#0c1230]/60">
              <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : null}
        </div>
      </div>

      {props.countLabel ? <div className="mt-3 text-center text-xs text-[#8a8fa8]">{props.countLabel}</div> : null}

      <div className="mt-3 flex min-h-12 flex-wrap items-center justify-center gap-2">
        {props.history.map((item, index) => (
          <ThumbnailButton
            key={`${props.role}-${index}-${item.slice(0, 20)}`}
            src={item}
            selected={item === props.preview}
            circle={props.circle}
            onClick={() => props.onPickHistory(item)}
          />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <Button
          type="button"
          variant="ghost"
          onClick={props.onGenerate}
          disabled={props.loading || props.generateDisabled}
          className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
        >
          {props.primaryAction}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={props.onSave}
          disabled={!props.preview}
          className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
        >
          💾 Save
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={props.onUpload}
          className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
        >
          {props.circle ? "📁 Upload" : "Upload"}
        </Button>
      </div>
    </div>
  );
}

export function OnboardingWizard({
  returnedPaymentId,
  returnedPaymentStatus,
  returnedReferenceId,
  addonMode = false,
}: {
  returnedPaymentId?: string | null;
  returnedPaymentStatus?: string | null;
  returnedReferenceId?: string | null;
  addonMode?: boolean;
}) {
  const router = useRouter();
  const [stepIndex, setStepIndex] = React.useState(0);
  const [state, setState] = React.useState<WizardState>(createDefaultState);
  const [profileCount, setProfileCount] = React.useState<number | null>(null);
  const [publicPlans, setPublicPlans] = React.useState<PublicPlan[]>([]);
  const [termDiscounts, setTermDiscounts] = React.useState<PlanTermDiscounts>(DEFAULT_TERM_DISCOUNTS);
  const [billingConfig, setBillingConfig] = React.useState<BillingProviderConfig | null>(null);
  const [currentPayment, setCurrentPayment] = React.useState<BillingPayment | null>(null);
  const [currentUser, setCurrentUser] = React.useState<CurrentUserResponse | null>(null);
  const [existingRoles, setExistingRoles] = React.useState<ExistingRoleState>({
    primary: false,
    secondary: false,
  });
  const [verificationCode, setVerificationCode] = React.useState("");
  const [verificationError, setVerificationError] = React.useState("");
  const [nameGenerateLimit, setNameGenerateLimit] = React.useState(MAX_SHARED_NAME_GENERATES);
  const [sharedGenerateCount, setSharedGenerateCount] = React.useState(0);
  const [logoGenerateLimit, setLogoGenerateLimit] = React.useState(0);
  const [logoGenerateUsed, setLogoGenerateUsed] = React.useState(0);
  const [coverGenerateLimit, setCoverGenerateLimit] = React.useState(0);
  const [coverGenerateUsed, setCoverGenerateUsed] = React.useState(0);
  const [descriptionGenerateLimit, setDescriptionGenerateLimit] = React.useState(0);
  const [descriptionGenerateUsed, setDescriptionGenerateUsed] = React.useState(0);
  const [keywordsGenerateLimit, setKeywordsGenerateLimit] = React.useState(0);
  const [keywordsGenerateUsed, setKeywordsGenerateUsed] = React.useState(0);
  const [tagsGenerateLimit, setTagsGenerateLimit] = React.useState(0);
  const [tagsGenerateUsed, setTagsGenerateUsed] = React.useState(0);
  const [customPrompt, setCustomPrompt] = React.useState("");
  const [busy, setBusy] = React.useState<BusyState>({
    loading: true,
    loadingPlans: true,
    sendingCode: false,
    verifyingCode: false,
    creatingPayment: false,
    checkingPayment: false,
    previewingRedeem: false,
    generatingNames: false,
    generatingLogos: { primary: false, secondary: false },
    generatingCovers: { primary: false, secondary: false },
    generatingDescriptions: { primary: false, secondary: false },
    generatingKeywords: { primary: false, secondary: false },
    generatingTags: { primary: false, secondary: false },
    creatingProfiles: false,
  });

  const primaryLogoUploadRef = React.useRef<HTMLInputElement | null>(null);
  const secondaryLogoUploadRef = React.useRef<HTMLInputElement | null>(null);
  const primaryCoverUploadRef = React.useRef<HTMLInputElement | null>(null);
  const secondaryCoverUploadRef = React.useRef<HTMLInputElement | null>(null);
  const autoVerificationSentRef = React.useRef(false);
  const handledCheckoutReturnRef = React.useRef<string | null>(null);

  const selectedGenre = state.selectedGenre;
  const hasBothNames =
    (existingRoles.primary || state.primaryName.trim().length > 0) &&
    (existingRoles.secondary || state.secondaryName.trim().length > 0);
  const logosReady =
    (existingRoles.primary || Boolean(state.primaryLogoBase64)) &&
    (existingRoles.secondary || Boolean(state.secondaryLogoBase64));
  const coversReady =
    (existingRoles.primary || Boolean(state.primaryCoverBase64)) &&
    (existingRoles.secondary || Boolean(state.secondaryCoverBase64));
  const seoReady =
    (existingRoles.primary ||
      (Boolean(state.primaryDescription.trim()) &&
        state.primaryKeywords.length > 0 &&
        state.primaryTags.length > 0)) &&
    (existingRoles.secondary ||
      (Boolean(state.secondaryDescription.trim()) &&
        state.secondaryKeywords.length > 0 &&
        state.secondaryTags.length > 0));

  const persistableState = React.useMemo(
    () => ({
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
      primaryLogoBase64: state.primaryLogoBase64,
      secondaryLogoBase64: state.secondaryLogoBase64,
      primaryLogoHistory: state.primaryLogoHistory,
      secondaryLogoHistory: state.secondaryLogoHistory,
      primaryCoverBase64: state.primaryCoverBase64,
      secondaryCoverBase64: state.secondaryCoverBase64,
      primaryCoverHistory: state.primaryCoverHistory,
      secondaryCoverHistory: state.secondaryCoverHistory,
      primaryDescription: state.primaryDescription,
      secondaryDescription: state.secondaryDescription,
      primaryKeywords: state.primaryKeywords,
      secondaryKeywords: state.secondaryKeywords,
      primaryTags: state.primaryTags,
      secondaryTags: state.secondaryTags,
    }),
    [state],
  );

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const refreshed = await refreshWithToken().catch(() => null);
        if (refreshed) {
          saveSession(refreshed);
        }
        const [meResult, genresResult, statusResult, plansResult, billingConfigResult, termDiscountsResult, draftResult] = await Promise.all([
          getCurrentUser(),
          listPublicGenres().catch(() => []),
          getProfilesStatus(),
          listPublicPlans().catch(() => []),
          listBillingProviders().catch(() => null),
          getPublicPlanTermDiscounts().catch(() => DEFAULT_TERM_DISCOUNTS),
          getOnboardingDraft().catch(() => null),
        ]);
        if (cancelled) return;

        const addonPending = meResult.profile_addon_pending ?? 0;
        if (!addonMode && statusResult.profile_count >= 2) {
          router.replace("/dashboard");
          return;
        }
        if (addonMode && addonPending < 2) {
          router.replace("/dashboard/profiles");
          return;
        }

        const persisted = loadOnboardingDraft();
        const expectedEmail = meResult.email.trim().toLowerCase();
        const persistedEmail = String(persisted?.email ?? "")
          .trim()
          .toLowerCase();
        const validPersisted = persisted && persistedEmail === expectedEmail ? persisted : null;
        const serverDraft = draftResult?.payload ?? null;
        const pendingRedeemCode = loadPendingRedeemCode();

        if (persisted && persistedEmail && persistedEmail !== expectedEmail) {
          clearOnboardingDraft();
        }

        const nextState: WizardState = {
          ...createDefaultState(),
          ...(validPersisted ?? {}),
          ...(serverDraft ?? {}),
          email: meResult.email,
          emailVerified: Boolean(meResult.email_confirmed),
          planSelectionCompleted: Boolean(
            addonMode ||
              serverDraft?.planSelectionCompleted ||
              validPersisted?.planSelectionCompleted ||
              meResult.onboarding_paid,
          ),
          redeemCode: String(serverDraft?.redeemCode ?? validPersisted?.redeemCode ?? pendingRedeemCode ?? ""),
          genres: genresResult,
          hydrated: true,
          genresLoading: false,
        };

        setCurrentUser(meResult);
        setState(nextState);
        setProfileCount(statusResult.profile_count);
        if (addonMode) {
          setExistingRoles({ primary: false, secondary: false });
        }
        setPublicPlans(plansResult);
        setTermDiscounts(termDiscountsResult);
        setBillingConfig(billingConfigResult);
        setSharedGenerateCount(draftResult?.name_generate_used ?? 0);
        setNameGenerateLimit(draftResult?.name_generate_limit ?? MAX_SHARED_NAME_GENERATES);
        setLogoGenerateUsed(draftResult?.logo_generate_used ?? 0);
        setLogoGenerateLimit(draftResult?.logo_generate_limit ?? 0);
        setCoverGenerateUsed(draftResult?.cover_generate_used ?? 0);
        setCoverGenerateLimit(draftResult?.cover_generate_limit ?? 0);
        setDescriptionGenerateUsed(draftResult?.description_generate_used ?? 0);
        setDescriptionGenerateLimit(draftResult?.description_generate_limit ?? 0);
        setKeywordsGenerateUsed(draftResult?.keywords_generate_used ?? 0);
        setKeywordsGenerateLimit(draftResult?.keywords_generate_limit ?? 0);
        setTagsGenerateUsed(draftResult?.tags_generate_used ?? 0);
        setTagsGenerateLimit(draftResult?.tags_generate_limit ?? 0);

        if (nextState.primaryLogoBase64 && nextState.primaryLogoHistory.length === 0) {
          nextState.primaryLogoHistory = [nextState.primaryLogoBase64];
        }
        if (nextState.secondaryLogoBase64 && nextState.secondaryLogoHistory.length === 0) {
          nextState.secondaryLogoHistory = [nextState.secondaryLogoBase64];
        }
        if (nextState.primaryCoverBase64 && nextState.primaryCoverHistory.length === 0) {
          nextState.primaryCoverHistory = [nextState.primaryCoverBase64];
        }
        if (nextState.secondaryCoverBase64 && nextState.secondaryCoverHistory.length === 0) {
          nextState.secondaryCoverHistory = [nextState.secondaryCoverBase64];
        }

        if (statusResult.profile_count === 1) {
          const profiles = await listProfiles().catch(() => []);
          if (cancelled) return;
          const existing = profiles[0];
          setExistingRoles({ primary: true, secondary: false });
          setState((current) => ({
            ...current,
            primaryName: existing?.name ?? current.primaryName,
          }));
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "";
          if (message.includes("(401)") || message.includes("(403)")) {
            router.replace("/register");
            return;
          }
          setState((current) => ({
            ...current,
            hydrated: true,
            genresLoading: false,
          }));
        }
      } finally {
        if (!cancelled) {
          setBusy((current) => ({ ...current, loading: false, loadingPlans: false }));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  React.useEffect(() => {
    if (!state.hydrated || !state.email) return;
    saveOnboardingDraft(persistableState);

    const timeoutId = window.setTimeout(() => {
      void saveOnboardingDraftToServer(persistableState)
        .then((draft) => {
          setSharedGenerateCount(draft.name_generate_used);
          setNameGenerateLimit(draft.name_generate_limit);
          setLogoGenerateUsed(draft.logo_generate_used);
          setLogoGenerateLimit(draft.logo_generate_limit);
          setCoverGenerateUsed(draft.cover_generate_used);
          setCoverGenerateLimit(draft.cover_generate_limit);
          setDescriptionGenerateUsed(draft.description_generate_used);
          setDescriptionGenerateLimit(draft.description_generate_limit);
          setKeywordsGenerateUsed(draft.keywords_generate_used);
          setKeywordsGenerateLimit(draft.keywords_generate_limit);
          setTagsGenerateUsed(draft.tags_generate_used);
          setTagsGenerateLimit(draft.tags_generate_limit);
        })
        .catch(() => undefined);
    }, 400);

    return () => window.clearTimeout(timeoutId);
  }, [persistableState, state.email, state.hydrated]);

  React.useEffect(() => {
    if (!state.hydrated || state.emailVerified || !state.email) {
      return;
    }

    const lastSentAt = state.verificationLastSentAt ?? 0;
    const shouldAutoSend = !autoVerificationSentRef.current && Date.now() - lastSentAt > 60_000;
    if (!shouldAutoSend) {
      return;
    }

    autoVerificationSentRef.current = true;
    setBusy((current) => ({ ...current, sendingCode: true }));
    sendVerification(state.email)
      .then(() => {
        setState((current) => ({ ...current, verificationLastSentAt: Date.now() }));
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Failed to send verification code.";
        toast({ variant: "destructive", title: "Verification email failed", description: message });
      })
      .finally(() => {
        setBusy((current) => ({ ...current, sendingCode: false }));
      });
  }, [state.email, state.emailVerified, state.hydrated, state.verificationLastSentAt]);

  const resendSecondsLeft = React.useMemo(() => {
    if (!state.verificationLastSentAt) return 0;
    return Math.max(0, 60 - Math.floor((Date.now() - state.verificationLastSentAt) / 1000));
  }, [state.verificationLastSentAt]);

  React.useEffect(() => {
    if (!state.verificationLastSentAt || state.emailVerified) return;
    const timer = window.setInterval(() => {
      setState((current) => ({ ...current }));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [state.emailVerified, state.verificationLastSentAt]);

  const refreshPendingPayment = React.useCallback(
    async (showSuccessToast: boolean, paymentIdOverride?: string) => {
      const targetPaymentId = paymentIdOverride ?? state.pendingBillingPaymentId;
      if (!targetPaymentId) return;

      setBusy((current) => ({ ...current, checkingPayment: true }));
      try {
        const payment = await getBillingPayment(targetPaymentId);
        setCurrentPayment(payment);
        setState((current) => ({
          ...current,
          selectedPlanId: payment.plan_id,
          pendingBillingPaymentId: payment.id,
          pendingBillingCheckoutUrl: payment.checkout_url,
        }));

        if (payment.status === "paid" && payment.fulfilled_at) {
          setState((current) => ({
            ...current,
            planSelectionCompleted: true,
            selectedPlanId: payment.plan_id,
            pendingBillingPaymentId: addonMode ? null : null,
            pendingBillingCheckoutUrl: null,
          }));
          setCurrentPayment(null);
          if (showSuccessToast) {
            toast({
              title: addonMode || payment.product_type === "profile_addon" ? "Add-on purchased" : "Plan activated",
              description:
                addonMode || payment.product_type === "profile_addon"
                  ? "Complete the channel setup below to activate your new quota."
                  : `${payment.plan_name} is now active on your CAMXORA account.`,
            });
          }
          return;
        }

        if (payment.status === "expired" || payment.status === "failed") {
          setState((current) => ({
            ...current,
            pendingBillingPaymentId: null,
            pendingBillingCheckoutUrl: null,
          }));
          setCurrentPayment(null);
          toast({
            variant: "destructive",
            title: payment.status === "expired" ? "Payment expired" : "Payment failed",
            description: "Start a new checkout when you are ready.",
          });
          return;
        }

        if (showSuccessToast) {
          toast({
            title: "Payment still pending",
            description: "We are still waiting for provider confirmation. You can reopen checkout if needed.",
          });
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to refresh payment status.";
        toast({ variant: "destructive", title: "Payment check failed", description: message });
      } finally {
        setBusy((current) => ({ ...current, checkingPayment: false }));
      }
    },
    [state.pendingBillingPaymentId, addonMode],
  );

  React.useEffect(() => {
    if (!state.emailVerified || !state.pendingBillingPaymentId || state.planSelectionCompleted) {
      return;
    }

    const initialRefresh = window.setTimeout(() => {
      void refreshPendingPayment(false);
    }, 0);
    const timer = window.setInterval(() => {
      void refreshPendingPayment(false);
    }, 5000);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(timer);
    };
  }, [
    refreshPendingPayment,
    state.emailVerified,
    state.pendingBillingPaymentId,
    state.planSelectionCompleted,
  ]);

  React.useEffect(() => {
    if (!state.emailVerified || state.planSelectionCompleted || !returnedPaymentId) {
      return;
    }
    if (handledCheckoutReturnRef.current === returnedPaymentId) {
      return;
    }

    handledCheckoutReturnRef.current = returnedPaymentId;

    (async () => {
      let localPaymentId = returnedPaymentId;
      try {
        if (!isUuid(returnedPaymentId)) {
          const resolved = await resolveBillingPaymentByExternalId(returnedPaymentId);
          localPaymentId = resolved.id;
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to resolve checkout return.";
        toast({ variant: "destructive", title: "Payment return failed", description: message });
        return;
      }

      setState((current) => ({
        ...current,
        pendingBillingPaymentId: localPaymentId,
      }));
      router.replace(addonMode ? "/onboarding?mode=addon" : "/onboarding");

      if (returnedPaymentStatus === "failed") {
        toast({
          variant: "destructive",
          title: "Payment failed",
          description: "Your KHQR payment did not complete. Choose a plan to try again.",
        });
      }

      void refreshPendingPayment(true, localPaymentId);
    })();
  }, [
    refreshPendingPayment,
    returnedPaymentId,
    returnedPaymentStatus,
    returnedReferenceId,
    router,
    state.emailVerified,
    state.planSelectionCompleted,
    addonMode,
  ]);

  function setSelectedGenre(genre: OnboardingGenre | null) {
    setState((current) => ({ ...current, selectedGenre: genre }));
  }

  async function handleSelectPaidPlan(planId: string) {
    setBusy((current) => ({ ...current, creatingPayment: true }));
    try {
      const payment = await createBillingPayment(planId, state.redeemCode);
      setCurrentPayment(payment);
      setState((current) => ({
        ...current,
        selectedPlanId: planId,
        pendingBillingPaymentId: payment.id,
        pendingBillingCheckoutUrl: payment.checkout_url,
      }));
      if (state.redeemCode.trim()) {
        clearPendingRedeemCode();
      }
      window.location.href = payment.checkout_url;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to start checkout.";
      toast({ variant: "destructive", title: "Checkout failed", description: message });
    } finally {
      setBusy((current) => ({ ...current, creatingPayment: false }));
    }
  }

  async function handleCheckRedeemCode() {
    const code = state.redeemCode.trim();
    if (!code) {
      toast({
        variant: "destructive",
        title: "Redeem code required",
        description: "Enter a redeem code before checking it.",
      });
      return;
    }

    setBusy((current) => ({ ...current, previewingRedeem: true }));
    try {
      const preview = await previewRedeemCode({
        code,
        planId: state.selectedPlanId || null,
      });
      savePendingRedeemCode(code);
      toast({
        title: "Redeem code ready",
        description:
          preview.message ??
          (preview.reward_type === "credit_grant"
            ? "This code grants credits in the signed-in user panel."
            : "This code is available for onboarding checkout."),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to validate redeem code.";
      toast({ variant: "destructive", title: "Redeem code invalid", description: message });
    } finally {
      setBusy((current) => ({ ...current, previewingRedeem: false }));
    }
  }

  function setRoleName(role: ChannelRole, value: string) {
    setState((current) =>
      role === "primary" ? { ...current, primaryName: value } : { ...current, secondaryName: value },
    );
  }

  function setRoleLogo(role: ChannelRole, value: string | null) {
    setState((current) =>
      role === "primary"
        ? {
            ...current,
            primaryLogoBase64: value,
            primaryLogoHistory: value ? uniquePush(current.primaryLogoHistory, value) : current.primaryLogoHistory,
          }
        : {
            ...current,
            secondaryLogoBase64: value,
            secondaryLogoHistory: value
              ? uniquePush(current.secondaryLogoHistory, value)
              : current.secondaryLogoHistory,
          },
    );
  }

  function setRoleCover(role: ChannelRole, value: string | null) {
    setState((current) =>
      role === "primary"
        ? {
            ...current,
            primaryCoverBase64: value,
            primaryCoverHistory: value ? uniquePush(current.primaryCoverHistory, value) : current.primaryCoverHistory,
          }
        : {
            ...current,
            secondaryCoverBase64: value,
            secondaryCoverHistory: value
              ? uniquePush(current.secondaryCoverHistory, value)
              : current.secondaryCoverHistory,
          },
    );
  }

  function setRoleSeo(
    role: ChannelRole,
    patch: Partial<{
      description: string;
      keywords: string[];
      tags: string[];
    }>,
  ) {
    setState((current) =>
      role === "primary"
        ? {
            ...current,
            primaryDescription: patch.description ?? current.primaryDescription,
            primaryKeywords: patch.keywords ?? current.primaryKeywords,
            primaryTags: patch.tags ?? current.primaryTags,
          }
        : {
            ...current,
            secondaryDescription: patch.description ?? current.secondaryDescription,
            secondaryKeywords: patch.keywords ?? current.secondaryKeywords,
            secondaryTags: patch.tags ?? current.secondaryTags,
          },
    );
  }

  async function handleSendVerification() {
    if (!state.email || resendSecondsLeft > 0) return;

    setBusy((current) => ({ ...current, sendingCode: true }));
    try {
      await sendVerification(state.email);
      setState((current) => ({ ...current, verificationLastSentAt: Date.now() }));
      toast({ title: "Verification code sent", description: `We sent a code to ${state.email}.` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send verification code.";
      toast({ variant: "destructive", title: "Verification email failed", description: message });
    } finally {
      setBusy((current) => ({ ...current, sendingCode: false }));
    }
  }

  async function handleVerifyEmail() {
    if (!state.email || verificationCode.trim().length !== 6) return;

    setBusy((current) => ({ ...current, verifyingCode: true }));
    setVerificationError("");
    try {
      await verifyEmail({ email: state.email, code: verificationCode.trim() });
      setState((current) => ({ ...current, emailVerified: true }));
      toast({
        title: "Email verified",
        description: "Choose a plan and complete payment to start channel setup.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid or expired verification code.";
      setVerificationError(message);
    } finally {
      setBusy((current) => ({ ...current, verifyingCode: false }));
    }
  }

  async function handleGenerateNames(target: ChannelRole | "both", prompt?: string) {
    if (!selectedGenre?.name) {
      toast({ variant: "destructive", title: "Missing genre", description: "Select a music genre first." });
      return;
    }
    const effectiveTarget =
      target === "both"
        ? existingRoles.primary && !existingRoles.secondary
          ? "secondary"
          : existingRoles.secondary && !existingRoles.primary
            ? "primary"
            : "both"
        : target;

    if (sharedGenerateCount >= nameGenerateLimit) {
      toast({ variant: "destructive", title: "Max generates reached", description: "You have used all 3 generates." });
      return;
    }

    setBusy((current) => ({ ...current, generatingNames: true }));
    try {
      const description = buildNamePromptContext(selectedGenre.name, prompt);
      const response = await generateNames({
        genre: selectedGenre.name,
        role: effectiveTarget,
        match_key: selectedGenre.matchKey,
        description,
        count: effectiveTarget === "both" ? 8 : 6,
      });
      const names = response.names ?? [];

      setState((current) => {
        if (effectiveTarget === "both") {
          const split = splitCombinedSuggestions(names);
          return {
            ...current,
            primarySuggestions: existingRoles.primary ? current.primarySuggestions : split.primary,
            secondarySuggestions: existingRoles.secondary ? current.secondarySuggestions : split.secondary,
            primaryName: existingRoles.primary ? current.primaryName : current.primaryName || split.primary[0] || "",
            secondaryName: existingRoles.secondary ? current.secondaryName : current.secondaryName || split.secondary[0] || "",
          };
        }

        if (effectiveTarget === "primary") {
          return {
            ...current,
            primarySuggestions: names,
            primaryName: current.primaryName || names[0] || "",
          };
        }

        return {
          ...current,
          secondarySuggestions: names,
          secondaryName: current.secondaryName || names[0] || "",
        };
      });
      setSharedGenerateCount((current) => Math.min(nameGenerateLimit, current + 1));
      setCustomPrompt("");
      toast({ title: "Channel names generated", description: "Pick a name or type your own." });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate names.";
      toast({ variant: "destructive", title: "Generate names failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setSharedGenerateCount(draft?.name_generate_used ?? nameGenerateLimit);
        setNameGenerateLimit(draft?.name_generate_limit ?? nameGenerateLimit);
      }
    } finally {
      setBusy((current) => ({ ...current, generatingNames: false }));
    }
  }

  async function handleGenerateLogo(role: ChannelRole) {
    const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
    if (!selectedGenre?.name || !name) return;
    if (logoGenerateLimit > 0 && logoGenerateUsed >= logoGenerateLimit) {
      toast({
        variant: "destructive",
        title: "Max logo generates reached",
        description: "You have used all logo generation attempts for onboarding.",
      });
      return;
    }

    setBusy((current) => ({
      ...current,
      generatingLogos: { ...current.generatingLogos, [role]: true },
    }));
    try {
      const response = await generateLogo({
        channel_name: name,
        genre: selectedGenre.name,
        role,
        match_key: selectedGenre.matchKey,
      });
      setRoleLogo(role, response.image_base64);
      const draft = await getOnboardingDraft().catch(() => null);
      if (draft) {
        setLogoGenerateUsed(draft.logo_generate_used);
        setLogoGenerateLimit(draft.logo_generate_limit);
      } else {
        setLogoGenerateUsed((current) => current + 1);
      }
      toast({ title: `${ROLE_LABELS[role]} logo ready` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate logo.";
      toast({ variant: "destructive", title: "Generate logo failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setLogoGenerateUsed(draft?.logo_generate_used ?? logoGenerateUsed);
        setLogoGenerateLimit(draft?.logo_generate_limit ?? logoGenerateLimit);
      }
    } finally {
      setBusy((current) => ({
        ...current,
        generatingLogos: { ...current.generatingLogos, [role]: false },
      }));
    }
  }

  async function handleGenerateCover(role: ChannelRole) {
    const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
    if (!selectedGenre?.name || !name) return;
    if (coverGenerateLimit > 0 && coverGenerateUsed >= coverGenerateLimit) {
      toast({
        variant: "destructive",
        title: "Max cover generates reached",
        description: "You have used all cover generation attempts for onboarding.",
      });
      return;
    }

    setBusy((current) => ({
      ...current,
      generatingCovers: { ...current.generatingCovers, [role]: true },
    }));
    try {
      const response = await generateCovers({
        channel_name: name,
        genre: selectedGenre.name,
        role,
        match_key: selectedGenre.matchKey,
        count: 1,
      });
      const images = response.images ?? [];
      const selected = images[0] ?? null;
      setState((current) =>
        role === "primary"
          ? {
              ...current,
              primaryCoverBase64: selected ?? current.primaryCoverBase64,
              primaryCoverHistory: images.reduce((history, item) => uniquePush(history, item), current.primaryCoverHistory),
            }
          : {
              ...current,
              secondaryCoverBase64: selected ?? current.secondaryCoverBase64,
              secondaryCoverHistory: images.reduce(
                (history, item) => uniquePush(history, item),
                current.secondaryCoverHistory,
              ),
            },
      );
      const draft = await getOnboardingDraft().catch(() => null);
      if (draft) {
        setCoverGenerateUsed(draft.cover_generate_used);
        setCoverGenerateLimit(draft.cover_generate_limit);
      } else {
        setCoverGenerateUsed((current) => current + 1);
      }
      toast({ title: `${ROLE_LABELS[role]} cover generated` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate cover.";
      toast({ variant: "destructive", title: "Generate cover failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setCoverGenerateUsed(draft?.cover_generate_used ?? coverGenerateUsed);
        setCoverGenerateLimit(draft?.cover_generate_limit ?? coverGenerateLimit);
      }
    } finally {
      setBusy((current) => ({
        ...current,
        generatingCovers: { ...current.generatingCovers, [role]: false },
      }));
    }
  }

  async function handleGenerateDescriptionText(role: ChannelRole) {
    const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
    const description = getRoleValue(role, state.primaryDescription, state.secondaryDescription);
    if (!selectedGenre?.name || !name) return;
    if (descriptionGenerateLimit > 0 && descriptionGenerateUsed >= descriptionGenerateLimit) {
      toast({
        variant: "destructive",
        title: "Max description generates reached",
        description: "You have used all description generation attempts for onboarding.",
      });
      return;
    }
    setBusy((current) => ({
      ...current,
      generatingDescriptions: { ...current.generatingDescriptions, [role]: true },
    }));
    try {
      const response = await generateDescriptionText({
        channel_name: name,
        genre: selectedGenre.name,
        match_key: selectedGenre.matchKey,
        description,
      });
      setRoleSeo(role, { description: response.description ?? description });
      const draft = await getOnboardingDraft().catch(() => null);
      if (draft) {
        setDescriptionGenerateUsed(draft.description_generate_used);
        setDescriptionGenerateLimit(draft.description_generate_limit);
      } else {
        setDescriptionGenerateUsed((current) => current + 1);
      }
      toast({ title: `${ROLE_LABELS[role]} description generated` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate description.";
      toast({ variant: "destructive", title: "Generate description failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setDescriptionGenerateUsed(draft?.description_generate_used ?? descriptionGenerateUsed);
        setDescriptionGenerateLimit(draft?.description_generate_limit ?? descriptionGenerateLimit);
      }
    } finally {
      setBusy((current) => ({
        ...current,
        generatingDescriptions: { ...current.generatingDescriptions, [role]: false },
      }));
    }
  }

  async function handleGenerateKeywords(role: ChannelRole) {
    const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
    const description = getRoleValue(role, state.primaryDescription, state.secondaryDescription);
    if (!selectedGenre?.name || !name) return;
    if (keywordsGenerateLimit > 0 && keywordsGenerateUsed >= keywordsGenerateLimit) {
      toast({
        variant: "destructive",
        title: "Max keyword generates reached",
        description: "You have used all keyword generation attempts for onboarding.",
      });
      return;
    }
    setBusy((current) => ({
      ...current,
      generatingKeywords: { ...current.generatingKeywords, [role]: true },
    }));
    try {
      const response = await generateKeywords({
        channel_name: name,
        genre: selectedGenre.name,
        match_key: selectedGenre.matchKey,
        description,
      });
      setRoleSeo(role, { keywords: response.keywords ?? [] });
      const draft = await getOnboardingDraft().catch(() => null);
      if (draft) {
        setKeywordsGenerateUsed(draft.keywords_generate_used);
        setKeywordsGenerateLimit(draft.keywords_generate_limit);
      } else {
        setKeywordsGenerateUsed((current) => current + 1);
      }
      toast({ title: `${ROLE_LABELS[role]} keywords generated` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate keywords.";
      toast({ variant: "destructive", title: "Generate keywords failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setKeywordsGenerateUsed(draft?.keywords_generate_used ?? keywordsGenerateUsed);
        setKeywordsGenerateLimit(draft?.keywords_generate_limit ?? keywordsGenerateLimit);
      }
    } finally {
      setBusy((current) => ({
        ...current,
        generatingKeywords: { ...current.generatingKeywords, [role]: false },
      }));
    }
  }

  async function handleGenerateTags(role: ChannelRole) {
    const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
    const description = getRoleValue(role, state.primaryDescription, state.secondaryDescription);
    if (!selectedGenre?.name || !name) return;
    if (tagsGenerateLimit > 0 && tagsGenerateUsed >= tagsGenerateLimit) {
      toast({
        variant: "destructive",
        title: "Max tag generates reached",
        description: "You have used all tag generation attempts for onboarding.",
      });
      return;
    }
    setBusy((current) => ({
      ...current,
      generatingTags: { ...current.generatingTags, [role]: true },
    }));
    try {
      const response = await generateTags({
        channel_name: name,
        genre: selectedGenre.name,
        match_key: selectedGenre.matchKey,
        description,
      });
      setRoleSeo(role, { tags: response.tags ?? [] });
      const draft = await getOnboardingDraft().catch(() => null);
      if (draft) {
        setTagsGenerateUsed(draft.tags_generate_used);
        setTagsGenerateLimit(draft.tags_generate_limit);
      } else {
        setTagsGenerateUsed((current) => current + 1);
      }
      toast({ title: `${ROLE_LABELS[role]} tags generated` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate tags.";
      toast({ variant: "destructive", title: "Generate tags failed", description: message });
      if (message.toLowerCase().includes("limit reached")) {
        const draft = await getOnboardingDraft().catch(() => null);
        setTagsGenerateUsed(draft?.tags_generate_used ?? tagsGenerateUsed);
        setTagsGenerateLimit(draft?.tags_generate_limit ?? tagsGenerateLimit);
      }
    } finally {
      setBusy((current) => ({
        ...current,
        generatingTags: { ...current.generatingTags, [role]: false },
      }));
    }
  }

  async function handleUpload(role: ChannelRole, type: "logo" | "cover", file: File | undefined) {
    if (!file) return;
    try {
      const base64 = await fileToBase64(file);
      if (type === "logo") {
        setRoleLogo(role, base64);
      } else {
        setRoleCover(role, base64);
      }
      toast({ title: `${ROLE_LABELS[role]} ${type} uploaded` });
    } catch {
      toast({
        variant: "destructive",
        title: "Upload failed",
        description: `Unable to read the selected ${type} file.`,
      });
    }
  }

  async function handleCreateProfiles() {
    if (!selectedGenre?.name) return;

    const rolesToCreate = ROLE_ORDER.filter((role) => !existingRoles[role]);
    setBusy((current) => ({ ...current, creatingProfiles: true }));
    try {
      for (const role of rolesToCreate) {
        const name = getRoleValue(role, state.primaryName, state.secondaryName).trim();
        if (!name) continue;
        const logo = getRoleValue(role, state.primaryLogoBase64, state.secondaryLogoBase64);
        const cover = getRoleValue(role, state.primaryCoverBase64, state.secondaryCoverBase64);

        await createProfile({
          name,
          genre: selectedGenre.name,
          role,
          logo_base64: logo,
          cover_images: cover ? [cover] : [],
          description: getRoleValue(role, state.primaryDescription, state.secondaryDescription),
          keywords: getRoleValue(role, state.primaryKeywords, state.secondaryKeywords),
          tags: getRoleValue(role, state.primaryTags, state.secondaryTags),
          match_key: selectedGenre.matchKey,
        });
      }

      if (addonMode) {
        await completeAddonOnboarding();
      }

      clearOnboardingDraft();
      clearPendingRedeemCode();
      toast({
        title: addonMode ? "Add-on channels activated" : "Profiles created",
        description: addonMode
          ? "Your new channel profiles are live and quotas are updated."
          : "Your onboarding is complete.",
      });
      router.push("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create profiles.";
      toast({ variant: "destructive", title: "Create profiles failed", description: message });
    } finally {
      setBusy((current) => ({ ...current, creatingProfiles: false }));
    }
  }

  function resetWizard() {
    clearOnboardingDraft();
    clearPendingRedeemCode();
    setStepIndex(0);
    setVerificationCode("");
    setVerificationError("");
    setCustomPrompt("");
    setSharedGenerateCount(0);
    setLogoGenerateUsed(0);
    setLogoGenerateLimit(0);
    setCoverGenerateUsed(0);
    setCoverGenerateLimit(0);
    setDescriptionGenerateUsed(0);
    setDescriptionGenerateLimit(0);
    setKeywordsGenerateUsed(0);
    setKeywordsGenerateLimit(0);
    setTagsGenerateUsed(0);
    setTagsGenerateLimit(0);
    setState((current) => ({
      ...createDefaultState(),
      hydrated: true,
      email: current.email,
      emailVerified: current.emailVerified,
      verificationLastSentAt: current.verificationLastSentAt,
      genres: current.genres,
    }));
  }

  function copyText(value: string, label: string) {
    navigator.clipboard.writeText(value);
    toast({ title: `${label} copied` });
  }

  if (!state.hydrated || busy.loading) {
    return (
      <div className="flex min-h-[540px] items-center justify-center rounded-[24px] border border-white/10 bg-[#0c1230]/85">
        <div className="flex items-center gap-3 text-sm text-[#8a8fa8]">
          <LoaderCircle className="h-5 w-5 animate-spin text-primary" />
          Checking your onboarding status...
        </div>
      </div>
    );
  }

  if (!state.emailVerified) {
    return (
      <PortalMarketingShell
        active="register"
        compact
        account={
          state.email
            ? {
                email: currentUser?.email ?? state.email,
                planLabel: currentUser?.plan_name ?? null,
                onSignOut: handleSignOut,
              }
            : undefined
        }
      >
        <Card className="w-full rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6 backdrop-blur supports-[backdrop-filter]:bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))]">
          <CardHeader className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-display text-2xl font-semibold tracking-tight text-white">
                  Confirm your email
                </div>
                <div className="text-sm leading-6 text-slate-200/70">
                  Enter the `6-digit` code before continuing to plan selection and onboarding.
                </div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
                <ShieldCheck className="h-4 w-4 text-fuchsia-100" />
              </div>
            </div>
          </CardHeader>

          <CardContent>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label className="text-slate-100" htmlFor="verification_email">Email</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="verification_email"
                    value={state.email ?? ""}
                    readOnly
                    className="border-white/10 bg-white/[0.04] pl-10 text-slate-300"
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label className="text-slate-100">Verification code</Label>
                <VerificationCodeBoxes
                  value={verificationCode}
                  disabled={busy.verifyingCode}
                  onChange={(next) => {
                    setVerificationCode(next);
                    setVerificationError("");
                  }}
                />
              </div>

              {verificationError ? (
                <div className="text-sm text-[#FF7262]">{verificationError}</div>
              ) : (
                <div className="text-sm text-slate-300/72">
                  We sent a confirmation code to your inbox. Enter it here to continue.
                </div>
              )}

              <Button
                type="button"
                onClick={handleVerifyEmail}
                disabled={verificationCode.length !== 6 || busy.verifyingCode}
                className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_44px_rgba(118,77,255,0.28)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
              >
                {busy.verifyingCode ? "Verifying..." : "Confirm email"}
              </Button>
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between gap-3">
            <div className="text-sm text-slate-300/72">
              Didn&apos;t receive a code?{" "}
              <button
                type="button"
                onClick={handleSendVerification}
                disabled={busy.sendingCode || resendSecondsLeft > 0}
                className="text-white underline-offset-4 hover:underline disabled:no-underline disabled:opacity-50"
              >
                {busy.sendingCode
                  ? "Sending..."
                  : resendSecondsLeft > 0
                    ? `Resend in ${resendSecondsLeft}s`
                    : "Resend"}
              </button>
            </div>
            <Link className="text-sm text-slate-300/72 underline-offset-4 hover:text-white hover:underline" href="/login">
              Sign in
            </Link>
          </CardFooter>
        </Card>
      </PortalMarketingShell>
    );
  }

  const paidPlans = publicPlans.filter((plan) => plan.effective_price_cents > 0);
  const paidCheckoutAvailable = billingConfig?.paid_checkout_available ?? true;
  const selectedPlan = publicPlans.find((plan) => plan.id === state.selectedPlanId) ?? null;
  const pricingPageUrl = `${getWebsiteBaseUrl()}/pricing`;

  if (!state.planSelectionCompleted) {
    return (
      <PortalMarketingShell
        active="register"
        wide
        account={{
          email: currentUser?.email ?? state.email ?? "Signed in",
          planLabel: currentUser?.plan_name ?? selectedPlan?.name ?? null,
          onSignOut: handleSignOut,
        }}
      >
        <div className="grid gap-5">
          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6 md:p-8">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Subscription</div>
            <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Choose your plan
            </div>
            <div className="mt-3 max-w-3xl text-sm leading-7 text-slate-200/70">
              Complete checkout to unlock channel setup. Guided onboarding is included with your
              subscription—AI assistance on each step, with no extra credit charge during setup.
            </div>
          </div>

          {!paidCheckoutAvailable ? (
            <Card className="border-amber-400/25 bg-amber-500/10">
              <CardContent className="pt-6 text-sm text-amber-50/90">
                Checkout is temporarily unavailable. Please contact support or try again later.
              </CardContent>
            </Card>
          ) : null}

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] ring-1 ring-white/6">
            <CardContent className="grid gap-4 pt-6">
              <div className="grid gap-2">
                <Label className="text-slate-100" htmlFor="onboarding_redeem_code">
                  Discount code
                </Label>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <Input
                    id="onboarding_redeem_code"
                    value={state.redeemCode}
                    onChange={(event) => {
                      const nextCode = event.target.value.toUpperCase();
                      setState((current) => ({ ...current, redeemCode: nextCode }));
                      savePendingRedeemCode(nextCode);
                    }}
                    placeholder="Enter code"
                    className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60 sm:flex-1"
                  />
                  <div className="flex flex-wrap gap-2 sm:shrink-0">
                    <Button
                      type="button"
                      onClick={() => void handleCheckRedeemCode()}
                      disabled={busy.previewingRedeem}
                      className="border border-white/15 bg-white/[0.08] text-white hover:bg-white/[0.14]"
                    >
                      {busy.previewingRedeem ? "Applying..." : "Apply code"}
                    </Button>
                    {state.redeemCode.trim() ? (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          clearPendingRedeemCode();
                          setState((current) => ({ ...current, redeemCode: "" }));
                        }}
                        className="border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                      >
                        Clear
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="text-xs leading-5 text-slate-400">
                  Codes apply at checkout and cannot be combined with a better public offer. Credit
                  codes can be redeemed later from your dashboard.
                </div>
              </div>
            </CardContent>
          </Card>

          {state.pendingBillingPaymentId ? (
            <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] ring-1 ring-white/6">
              <CardContent className="grid gap-4 pt-6 text-sm text-slate-200/78 md:grid-cols-[1fr_auto] md:items-center">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
                    Checkout in progress
                  </div>
                  <div className="mt-2 font-display text-2xl font-semibold tracking-[-0.04em] text-white">
                    Payment returns here automatically.
                  </div>
                  <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/72">
                    After checkout, CAMXORA verifies the payment on the server and continues onboarding without a manual confirmation step.
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-right">
                  <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Status</div>
                  <div className="mt-2 text-sm font-medium capitalize text-white">
                    {busy.checkingPayment ? "Checking" : currentPayment?.status ?? "pending"}
                  </div>
                </div>
                <div className="md:col-span-2 flex flex-wrap gap-3">
                  <Button
                    type="button"
                    onClick={() =>
                      state.pendingBillingCheckoutUrl
                        ? (window.location.href = state.pendingBillingCheckoutUrl)
                        : undefined
                    }
                    disabled={!state.pendingBillingCheckoutUrl}
                  >
                    Reopen checkout
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void refreshPendingPayment(true)}
                    disabled={busy.checkingPayment}
                  >
                    {busy.checkingPayment ? "Checking..." : "Check status"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <OnboardingPlanPicker
            plans={paidPlans}
            termDiscounts={termDiscounts}
            pricingPageUrl={pricingPageUrl}
            paidCheckoutAvailable={paidCheckoutAvailable}
            creatingPayment={busy.creatingPayment}
            selectedPlanId={state.selectedPlanId}
            onSelectPlan={(planId) => void handleSelectPaidPlan(planId)}
          />
        </div>
      </PortalMarketingShell>
    );
  }

  const currentStep = STEP_DEFS[stepIndex];
  const nameGeneratesRemaining = Math.max(0, nameGenerateLimit - sharedGenerateCount);
  const logoGeneratesRemaining = Math.max(0, logoGenerateLimit - logoGenerateUsed);
  const coverGeneratesRemaining = Math.max(0, coverGenerateLimit - coverGenerateUsed);
  const descriptionGeneratesRemaining = Math.max(0, descriptionGenerateLimit - descriptionGenerateUsed);
  const keywordsGeneratesRemaining = Math.max(0, keywordsGenerateLimit - keywordsGenerateUsed);
  const tagsGeneratesRemaining = Math.max(0, tagsGenerateLimit - tagsGenerateUsed);
  const completedSteps = [
    Boolean(selectedGenre),
    hasBothNames,
    logosReady,
    coversReady,
    seoReady,
  ].filter(Boolean).length;
  const setupSummary = [
    { label: "Genre", value: selectedGenre?.name ?? "Not selected" },
    { label: "Plan", value: currentUser?.plan_name ?? selectedPlan?.name ?? "Not selected" },
    { label: "Primary", value: state.primaryName || "Not set" },
    { label: "Secondary", value: state.secondaryName || "Not set" },
  ];

  function handleSignOut() {
    clearSession();
    clearOnboardingDraft();
    clearPendingRedeemCode();
    router.replace("/login");
  }

  return (
    <PortalMarketingShell
      active="register"
      wide
      account={{
        email: currentUser?.email ?? state.email ?? "Signed in",
        planLabel: currentUser?.plan_name ?? selectedPlan?.name ?? null,
        onSignOut: handleSignOut,
      }}
    >
      <div className="flex w-full flex-col gap-5">
        <div className="grid gap-4 rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-4 ring-1 ring-white/6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:p-5">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Onboarding workspace
            </div>
            <div className="mt-2 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Build your channel system.
            </div>
            <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/72">
              Create both channel profiles with one guided setup flow across naming, logos, cover art, and SEO.
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Progress</div>
              <div className="mt-2 text-lg font-semibold text-white">
                {completedSteps}/{STEP_DEFS.length}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Profiles</div>
              <div className="mt-2 text-lg font-semibold text-white">
                {profileCount === null ? "—" : `${profileCount}/2`}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Draft</div>
              <div className="mt-2 text-lg font-semibold text-white">Auto-saved</div>
            </div>
          </div>
        </div>

        <div className="grid items-stretch gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="h-full rounded-[28px] border border-white/10 bg-[#0c1230]/90 p-4 md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/8 pb-5">
              <div className="min-w-0">
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                  Step {stepIndex + 1} of {STEP_DEFS.length}
                </div>
                <div className="mt-2 text-sm text-slate-300/72">
                  {currentStep.subtitle}
                </div>
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-sm text-slate-100/82">
                <span className="text-base">{currentStep.emoji}</span>
                <span>{currentStep.title}</span>
              </div>
            </div>

            <div className="mt-5 flex items-start px-1">
              {STEP_DEFS.map((step, index) => {
                const isDone = index < stepIndex;
                const isCurrent = index === stepIndex;
                return (
                  <React.Fragment key={step.title}>
                    <div className="flex flex-1 flex-col items-center gap-2">
                      <button
                        type="button"
                        disabled={!isDone}
                        onClick={() => setStepIndex(index)}
                        className={cn(
                          "h-9 w-9 rounded-full border-2 text-sm font-bold",
                          isCurrent
                            ? "border-blue-300/50 bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white"
                            : isDone
                              ? "border-[#4ade80] bg-[linear-gradient(90deg,#4ade80,#22c55e)] text-[#052e16]"
                              : "border-[#2a2f4d] bg-[#1a1f3d] text-[#5a5f7d]",
                        )}
                      >
                        {index + 1}
                      </button>
                      <div
                        className={cn(
                          "text-center text-[10px]",
                          isCurrent
                            ? "font-bold text-white"
                            : isDone
                              ? "font-bold text-[#86efac]"
                              : "text-[#8a8fa8]",
                        )}
                      >
                        {step.title.replace("Pick Your ", "").replace("Choose ", "")}
                      </div>
                    </div>
                    {index < STEP_DEFS.length - 1 ? (
                      <div
                        className={cn(
                          "mt-4 h-0.5 flex-1",
                          index < stepIndex ? "bg-[linear-gradient(90deg,#4ade80,#22c55e)]" : "bg-[#2a2f4d]",
                        )}
                      />
                    ) : null}
                  </React.Fragment>
                );
              })}
            </div>

            <div className="mt-6">
              {stepIndex === 0 ? (
                <div className="flex min-h-[460px] flex-col gap-5 px-1 pb-1">
                  <div>
                    <div className="text-2xl font-semibold text-white">Choose a starting genre</div>
                    <div className="mt-2 max-w-2xl text-sm text-[#b0b5c8]">
                      Pick the music direction first. CAMXORA uses it to shape names, visuals, and SEO.
                    </div>
                  </div>

                  <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(210px,1fr))]">
                    {state.genres.map((genre) => {
                      const selected = genre.name === selectedGenre?.name;
                      return (
                        <button
                          key={genre.id}
                          type="button"
                          onClick={() =>
                            setSelectedGenre({ name: genre.name, matchKey: genre.match_key || genre.name })
                          }
                          className={cn(
                            "rounded-xl border px-3 py-3 text-left transition",
                            selected
                              ? "border-blue-300/40 bg-[linear-gradient(135deg,rgba(139,92,246,0.2),rgba(59,130,246,0.16))] text-white shadow-[0_0_30px_rgba(59,130,246,0.12)]"
                              : "border-white/10 bg-white/[0.03] text-slate-200/78 hover:border-white/20 hover:bg-white/[0.05]",
                          )}
                        >
                          <div className="text-sm font-medium leading-5">{genre.name}</div>
                          <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                            Genre
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-auto grid gap-4">
                    <div className="grid gap-3 md:grid-cols-3">
                      {[
                        "Names follow the selected genre",
                        "Logos and covers keep one visual direction",
                        "Descriptions and tags stay aligned",
                      ].map((item) => (
                        <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4 text-sm text-slate-200/74">
                          {item}
                        </div>
                      ))}
                    </div>

                    <Button
                      type="button"
                      onClick={() => setStepIndex(1)}
                      disabled={!selectedGenre}
                      className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
                    >
                      Continue to names
                    </Button>
                  </div>
                </div>
              ) : null}

              {stepIndex === 1 ? (
                <div className="grid gap-4 px-1 pb-1">
              <div className="w-full rounded-xl border border-white/10 bg-[#0c1230] p-4">
                <div className="flex items-center gap-3">
                  <div className="text-lg">⚡</div>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-white">
                      {nameGeneratesRemaining <= 0
                        ? "No generates remaining"
                        : `${nameGeneratesRemaining} generate${nameGeneratesRemaining === 1 ? "" : "s"} remaining`}
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#1a1f3d]">
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] transition-all"
                        style={{ width: `${nameGenerateLimit > 0 ? (nameGeneratesRemaining / nameGenerateLimit) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <Button
                type="button"
                onClick={() => handleGenerateNames("both")}
                disabled={busy.generatingNames || nameGeneratesRemaining <= 0}
                className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
              >
                {busy.generatingNames ? "Generating..." : "✨ Generate Channel Names"}
              </Button>

              <div className="grid gap-4 lg:grid-cols-2">
                <ChannelNameColumn
                  role="primary"
                  accent={ROLE_ACCENTS.primary}
                  suggestions={state.primarySuggestions}
                  value={state.primaryName}
                  status={
                    existingRoles.primary
                      ? "Primary channel already exists on this account."
                      : "Pick one below or type your own."
                  }
                  disabled={existingRoles.primary}
                  onPick={(value) => setRoleName("primary", value)}
                  onChange={(value) => setRoleName("primary", value)}
                  onGenerate={() => handleGenerateNames("primary")}
                  generateLabel={nameGeneratesRemaining > 0 ? "↻ Generate" : "Max generates reached"}
                />
                <ChannelNameColumn
                  role="secondary"
                  accent={ROLE_ACCENTS.secondary}
                  suggestions={state.secondarySuggestions}
                  value={state.secondaryName}
                  status={
                    existingRoles.secondary
                      ? "Secondary channel already exists on this account."
                      : "Pick one below or type your own."
                  }
                  disabled={existingRoles.secondary}
                  onPick={(value) => setRoleName("secondary", value)}
                  onChange={(value) => setRoleName("secondary", value)}
                  onGenerate={() => handleGenerateNames("secondary")}
                  generateLabel={nameGeneratesRemaining > 0 ? "↻ Generate" : "Max generates reached"}
                />
              </div>

              <div className="w-full rounded-xl border border-white/10 bg-[#0c1230] p-4">
                <div className="text-sm text-[#8a8fa8]">
                  Need a different direction? Add extra guidance. The selected genre is always included automatically.
                </div>
                <Input
                  value={customPrompt}
                  onChange={(event) => setCustomPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void handleGenerateNames("both", customPrompt);
                    }
                  }}
                  placeholder="e.g., Dark cyberpunk electronic, moody vibes..."
                  className="mt-3 h-12 w-full border-primary/30 bg-[#111738] px-4 text-white placeholder:text-[#7d84a0]"
                />
                <Button
                  type="button"
                  onClick={() => void handleGenerateNames("both", customPrompt)}
                  disabled={busy.generatingNames || nameGeneratesRemaining <= 0 || !customPrompt.trim()}
                  className="mt-3 h-10 rounded-lg border border-blue-400/25 bg-[linear-gradient(90deg,rgba(139,92,246,0.14),rgba(59,130,246,0.14))] px-4 text-white hover:bg-[linear-gradient(90deg,rgba(139,92,246,0.18),rgba(59,130,246,0.18))]"
                >
                  Generate With Prompt
                </Button>
              </div>

              <Button
                type="button"
                onClick={() => setStepIndex(2)}
                disabled={!hasBothNames}
                className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
              >
                Next →
              </Button>
                </div>
              ) : null}

              {stepIndex === 2 ? (
                <div className="grid gap-4 px-1 pb-1">
              <div>
                <div className="text-2xl font-semibold text-white">Design your logos</div>
                <div className="mt-2 text-sm text-[#b0b5c8]">
                  Click Generate to create logos for each channel. Logo usage is tracked on the server and does not reset on refresh.
                </div>
                <div className="mt-2 text-sm text-[#8a8fa8]">
                  Logo generation typically takes 20-60 seconds. Please be patient while our AI creates your unique design.
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <AssetColumn
                  role="primary"
                  accent={ROLE_ACCENTS.primary}
                  preview={state.primaryLogoBase64}
                  history={state.primaryLogoHistory}
                  loading={busy.generatingLogos.primary}
                  circle
                  previewLabel="Primary Logo"
                  countLabel={`Logo generates remaining: ${logoGeneratesRemaining}`}
                  generateDisabled={logoGenerateLimit > 0 && logoGeneratesRemaining === 0}
                  primaryAction={state.primaryLogoBase64 ? "↻ Regenerate" : "Generate Logo"}
                  onGenerate={() => handleGenerateLogo("primary")}
                  onSave={() => state.primaryLogoBase64 && downloadBase64(state.primaryLogoBase64, "camxora-primary-logo.png")}
                  onUpload={() => primaryLogoUploadRef.current?.click()}
                  onPickHistory={(value) => setRoleLogo("primary", value)}
                />
                <AssetColumn
                  role="secondary"
                  accent={ROLE_ACCENTS.secondary}
                  preview={state.secondaryLogoBase64}
                  history={state.secondaryLogoHistory}
                  loading={busy.generatingLogos.secondary}
                  circle
                  previewLabel="Secondary Logo"
                  countLabel={`Logo generates remaining: ${logoGeneratesRemaining}`}
                  generateDisabled={logoGenerateLimit > 0 && logoGeneratesRemaining === 0}
                  primaryAction={state.secondaryLogoBase64 ? "↻ Regenerate" : "Generate Logo"}
                  onGenerate={() => handleGenerateLogo("secondary")}
                  onSave={() => state.secondaryLogoBase64 && downloadBase64(state.secondaryLogoBase64, "camxora-secondary-logo.png")}
                  onUpload={() => secondaryLogoUploadRef.current?.click()}
                  onPickHistory={(value) => setRoleLogo("secondary", value)}
                />
              </div>

              <input
                ref={primaryLogoUploadRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void handleUpload("primary", "logo", event.target.files?.[0])}
              />
              <input
                ref={secondaryLogoUploadRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void handleUpload("secondary", "logo", event.target.files?.[0])}
              />

              <Button
                type="button"
                onClick={() => setStepIndex(3)}
                disabled={!logosReady}
                className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
              >
                Next →
              </Button>
                </div>
              ) : null}

              {stepIndex === 3 ? (
                <div className="grid gap-4 px-1 pb-1">
              <div>
                <div className="text-2xl font-semibold text-white">Channel cover images</div>
                <div className="mt-2 text-sm text-[#b0b5c8]">
                  Click Generate to create YouTube banners. Cover usage is tracked on the server and does not reset on refresh.
                </div>
                <div className="mt-2 text-sm text-[#8a8fa8]">
                  Cover generation typically takes 20-60 seconds. Previous covers are saved as thumbnails below.
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <AssetColumn
                  role="primary"
                  accent={ROLE_ACCENTS.primary}
                  preview={state.primaryCoverBase64}
                  history={state.primaryCoverHistory}
                  loading={busy.generatingCovers.primary}
                  previewLabel="Primary Channel"
                  countLabel={`Cover generates remaining: ${coverGeneratesRemaining}`}
                  generateDisabled={coverGenerateLimit > 0 && coverGeneratesRemaining === 0}
                  primaryAction="Generate Cover"
                  onGenerate={() => handleGenerateCover("primary")}
                  onSave={() => state.primaryCoverBase64 && downloadBase64(state.primaryCoverBase64, "camxora-primary-cover.png")}
                  onUpload={() => primaryCoverUploadRef.current?.click()}
                  onPickHistory={(value) => setRoleCover("primary", value)}
                />
                <AssetColumn
                  role="secondary"
                  accent={ROLE_ACCENTS.secondary}
                  preview={state.secondaryCoverBase64}
                  history={state.secondaryCoverHistory}
                  loading={busy.generatingCovers.secondary}
                  previewLabel="Secondary Channel"
                  countLabel={`Cover generates remaining: ${coverGeneratesRemaining}`}
                  generateDisabled={coverGenerateLimit > 0 && coverGeneratesRemaining === 0}
                  primaryAction="Generate Cover"
                  onGenerate={() => handleGenerateCover("secondary")}
                  onSave={() => state.secondaryCoverBase64 && downloadBase64(state.secondaryCoverBase64, "camxora-secondary-cover.png")}
                  onUpload={() => secondaryCoverUploadRef.current?.click()}
                  onPickHistory={(value) => setRoleCover("secondary", value)}
                />
              </div>

              <input
                ref={primaryCoverUploadRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void handleUpload("primary", "cover", event.target.files?.[0])}
              />
              <input
                ref={secondaryCoverUploadRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void handleUpload("secondary", "cover", event.target.files?.[0])}
              />

              <Button
                type="button"
                onClick={() => setStepIndex(4)}
                disabled={!coversReady}
                className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
              >
                Next →
              </Button>
                </div>
              ) : null}

              {stepIndex === 4 ? (
                <div className="grid gap-4 px-1 pb-1">
              <div>
                <div className="text-2xl font-semibold text-white">Channel Description & SEO</div>
                <div className="mt-2 text-sm text-[#b0b5c8]">
                  Each channel now keeps its own description, keywords, and tags directly under its logo.
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-[#8a8fa8]">
                  <span>Description left: {descriptionGeneratesRemaining}</span>
                  <span>Keywords left: {keywordsGeneratesRemaining}</span>
                  <span>Tags left: {tagsGeneratesRemaining}</span>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                {ROLE_ORDER.map((role) => {
                  const name = getRoleValue(role, state.primaryName, state.secondaryName) || "—";
                  const logo = getRoleValue(role, state.primaryLogoBase64, state.secondaryLogoBase64);
                  const description = getRoleValue(role, state.primaryDescription, state.secondaryDescription);
                  const keywords = getRoleValue(role, state.primaryKeywords, state.secondaryKeywords);
                  const tags = getRoleValue(role, state.primaryTags, state.secondaryTags);

                  return (
                    <div
                      key={role}
                      className="grid gap-4 rounded-xl border border-primary/15 bg-[linear-gradient(135deg,#0c1230,#111738)] p-6"
                    >
                      <div className="flex items-center gap-4 rounded-xl bg-white/5 px-4 py-4">
                        <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-[#1a1f3d] text-white/30">
                          {logo ? (
                            <img src={dataUrlFromBase64(logo) ?? ""} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <ImageIcon className="h-5 w-5" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs" style={{ color: ROLE_ACCENTS[role] }}>
                            {ROLE_LABELS[role]} Channel
                          </div>
                          <div className="mt-1 text-lg font-semibold text-white">{name}</div>
                          <div className="text-xs text-[#8a8fa8]">{selectedGenre?.name || "—"}</div>
                        </div>
                      </div>

                      <div className="grid gap-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-white">Channel Description</div>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => handleGenerateDescriptionText(role)}
                            disabled={
                              busy.generatingDescriptions[role] ||
                              (descriptionGenerateLimit > 0 && descriptionGeneratesRemaining === 0)
                            }
                            className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                          >
                            {busy.generatingDescriptions[role]
                              ? "Generating..."
                              : description
                                ? "↻ Regenerate Description"
                                : "Generate Description"}
                          </Button>
                        </div>
                        <Textarea
                          value={description}
                          onChange={(event) => setRoleSeo(role, { description: event.target.value })}
                          className="min-h-[220px] rounded-xl border-primary/20 bg-[#111738] p-4 text-sm text-[#eef4ff]"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => copyText(description, `${ROLE_LABELS[role]} description`)}
                          className="h-10 w-fit rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                        >
                          <Copy className="h-4 w-4" />
                          Copy Description
                        </Button>
                      </div>

                      <div className="grid gap-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-white">Channel Keywords</div>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => handleGenerateKeywords(role)}
                            disabled={
                              busy.generatingKeywords[role] ||
                              (keywordsGenerateLimit > 0 && keywordsGeneratesRemaining === 0)
                            }
                            className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                          >
                            {busy.generatingKeywords[role]
                              ? "Generating..."
                              : keywords.length
                                ? "↻ Regenerate Keywords"
                                : "Generate Keywords"}
                          </Button>
                        </div>
                        <div className="text-xs text-[#8a8fa8]">
                          Short keywords only (1-3 words). Comma-separated, ready to paste into YouTube Studio.
                        </div>
                        <Textarea
                          value={formatYoutubeKeywords(keywords)}
                          onChange={(event) =>
                            setRoleSeo(role, { keywords: parseYoutubeCommaInput(event.target.value) })
                          }
                          className="min-h-[72px] rounded-xl border-primary/20 bg-[#111738] p-4 text-sm text-[#eef4ff]"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() =>
                            copyText(formatYoutubeKeywords(keywords), `${ROLE_LABELS[role]} keywords`)
                          }
                          className="h-10 w-fit rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                        >
                          <Copy className="h-4 w-4" />
                          Copy Keywords
                        </Button>
                      </div>

                      <div className="grid gap-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-white">Channel Tags</div>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => handleGenerateTags(role)}
                            disabled={
                              busy.generatingTags[role] ||
                              (tagsGenerateLimit > 0 && tagsGeneratesRemaining === 0)
                            }
                            className="h-10 rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                          >
                            {busy.generatingTags[role]
                              ? "Generating..."
                              : tags.length
                                ? "↻ Regenerate Tags"
                                : "Generate Tags"}
                          </Button>
                        </div>
                        <div className="text-xs text-[#8a8fa8]">
                          Tags only (1-3 words). Comma-separated for YouTube tags field (max 500 characters).
                        </div>
                        <Textarea
                          value={formatYoutubeTags(tags)}
                          onChange={(event) =>
                            setRoleSeo(role, { tags: parseYoutubeCommaInput(event.target.value) })
                          }
                          className="min-h-[72px] rounded-xl border-primary/20 bg-[#111738] p-4 text-sm text-[#eef4ff]"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => copyText(formatYoutubeTags(tags), `${ROLE_LABELS[role]} tags`)}
                          className="h-10 w-fit rounded-lg border border-white/10 bg-white/5 px-4 text-sm text-white hover:bg-white/10"
                        >
                          <Copy className="h-4 w-4" />
                          Copy Tags
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <Button
                type="button"
                onClick={handleCreateProfiles}
                disabled={busy.creatingProfiles}
                className="h-12 w-full rounded-xl bg-[linear-gradient(90deg,#8B5CF6,#3B82F6)] text-white hover:opacity-95"
              >
                {busy.creatingProfiles ? "Creating your profiles..." : "Create Both Channel Profiles →"}
              </Button>
                </div>
              ) : null}
            </div>
          </div>

          <div className="xl:sticky xl:top-24 xl:h-full">
            <div className="grid h-full gap-4 rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-4 ring-1 ring-white/6 md:p-5">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Setup summary</div>
                <div className="mt-2 font-display text-2xl font-semibold tracking-[-0.04em] text-white">
                  Keep the flow visible.
                </div>
              </div>

              <div className="grid gap-3">
                {setupSummary.map((item) => (
                  <div key={item.label} className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
                    <div className="mt-2 text-sm font-medium text-white">{item.value}</div>
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Assets</div>
                <div className="mt-3 grid gap-2 text-sm text-slate-200/74">
                  <div className="flex items-center justify-between gap-3">
                    <span>Names</span>
                    <span className={hasBothNames ? "text-white" : "text-slate-400"}>
                      {hasBothNames ? "Ready" : "Pending"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>Logos</span>
                    <span className={logosReady ? "text-white" : "text-slate-400"}>
                      {logosReady ? "Ready" : "Pending"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>Covers</span>
                    <span className={coversReady ? "text-white" : "text-slate-400"}>
                      {coversReady ? "Ready" : "Pending"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>SEO</span>
                    <span className={seoReady ? "text-white" : "text-slate-400"}>
                      {seoReady ? "Ready" : "Pending"}
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={resetWizard}
                className="mt-auto rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-medium text-white transition hover:bg-white/[0.06]"
              >
                Reset onboarding draft
              </button>
            </div>
          </div>
        </div>
      </div>
    </PortalMarketingShell>
  );
}
