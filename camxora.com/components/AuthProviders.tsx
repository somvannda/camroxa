"use client";

import type { ReactElement } from "react";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

/**
 * S02 sign-in providers, in the captured order:
 *   Continue with Google / Apple / Phone — or — Discord / Facebook / Microsoft
 *
 * Only Google is wired in this build. The other five are rendered with the
 * captured label and glyph but stay disabled, dashed and titled with the
 * reason, so none of them looks like a live control.
 */

type InertProvider = {
  id: string;
  label: string;
  title: string;
  glyph: () => ReactElement;
};

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: "false" as const,
  className: "auth-provider-glyph",
};

function AppleGlyph() {
  return (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M16.4 12.7c0-2.2 1.8-3.2 1.9-3.3-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.6.8-3.3.8-.7 0-1.7-.8-2.8-.8-1.5 0-2.9.9-3.6 2.2-1.5 2.7-.4 6.7 1.1 8.9.7 1.1 1.6 2.3 2.7 2.2 1.1 0 1.5-.7 2.8-.7 1.3 0 1.6.7 2.8.7 1.2 0 1.9-1.1 2.6-2.1.8-1.2 1.2-2.4 1.2-2.5-.1 0-2.2-.9-2.2-3.7Z" />
      <path d="M14.4 6.6c.6-.7 1-1.7.9-2.6-.9 0-1.9.6-2.5 1.3-.6.6-1.1 1.6-.9 2.5 1 .1 1.9-.5 2.5-1.2Z" />
    </svg>
  );
}

function PhoneGlyph() {
  return (
    <svg viewBox="0 0 24 24" {...stroke}>
      <rect x="7" y="2.5" width="10" height="19" rx="2.6" />
      <path d="M10.6 5.4h2.8" />
      <path d="M11 18.6h2" />
    </svg>
  );
}

function DiscordGlyph() {
  return (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M8.4 5.6C9.5 5.2 10.7 5 12 5s2.5.2 3.6.6" />
      <path d="M15.6 18.4c-1.1.5-2.3.7-3.6.7s-2.5-.2-3.6-.7" />
      <path d="M6.6 7.1C5 9.3 4.3 12 4.5 15c0 .9.7 1.7 1.6 1.8l1.4.2 1-1.6" />
      <path d="M17.4 7.1c1.6 2.2 2.3 4.9 2.1 7.9 0 .9-.7 1.7-1.6 1.8l-1.4.2-1-1.6" />
      <circle cx="9.5" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="14.5" cy="12" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function FacebookGlyph() {
  return (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3Z" />
    </svg>
  );
}

function MicrosoftGlyph() {
  return (
    <svg viewBox="0 0 24 24" {...stroke} stroke="none">
      <rect x="3" y="3" width="8" height="8" fill="#F25022" />
      <rect x="13" y="3" width="8" height="8" fill="#7FBA00" />
      <rect x="3" y="13" width="8" height="8" fill="#00A4EF" />
      <rect x="13" y="13" width="8" height="8" fill="#FFB900" />
    </svg>
  );
}

const LARGE_INERT: InertProvider[] = [
  {
    id: "apple",
    label: "Continue with Apple",
    title: "Apple sign-in is not configured in this build",
    glyph: AppleGlyph,
  },
  {
    id: "phone",
    label: "Continue with Phone",
    title: "Phone sign-in is not configured in this build",
    glyph: PhoneGlyph,
  },
];

const COMPACT_INERT: InertProvider[] = [
  {
    id: "discord",
    label: "Discord",
    title: "Discord sign-in is not configured in this build",
    glyph: DiscordGlyph,
  },
  {
    id: "facebook",
    label: "Facebook",
    title: "Facebook sign-in is not configured in this build",
    glyph: FacebookGlyph,
  },
  {
    id: "microsoft",
    label: "Microsoft",
    title: "Microsoft sign-in is not configured in this build",
    glyph: MicrosoftGlyph,
  },
];

function InertButton({
  provider,
  compact = false,
}: {
  provider: InertProvider;
  compact?: boolean;
}) {
  const Glyph = provider.glyph;
  return (
    <button
      type="button"
      className={`auth-btn provider-inert${compact ? " provider-compact" : ""}`}
      data-provider={provider.id}
      data-configured="false"
      disabled
      aria-disabled="true"
      title={provider.title}
    >
      <Glyph />
      {provider.label}
    </button>
  );
}

export function AuthProviders() {
  return (
    <div
      className="auth-providers"
      role="group"
      aria-label="Continue with a provider"
      data-testid="auth-providers"
    >
      <GoogleSignInButton />
      {LARGE_INERT.map((provider) => (
        <InertButton key={provider.id} provider={provider} />
      ))}
      <div className="auth-divider">or</div>
      <div className="auth-provider-row">
        {COMPACT_INERT.map((provider) => (
          <InertButton key={provider.id} provider={provider} compact />
        ))}
      </div>
    </div>
  );
}
