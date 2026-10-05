import type { Metadata } from "next";
import Link from "next/link";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { COMPANY } from "@/components/marketing/legal-doc";
import { getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact Camxora for support, privacy, billing, and Google OAuth / YouTube questions.",
};

// Optional: set NEXT_PUBLIC_COMPANY_ADDRESS to publish a registered address.
// Left unset, the public page simply omits the address block (no placeholder).
const BUSINESS_ADDRESS = (process.env.NEXT_PUBLIC_COMPANY_ADDRESS ?? "").trim();

export default function ContactPage() {
  const userPortalBaseUrl = getUserPortalBaseUrl();

  return (
    <ContentPageShell
      eyebrow="Contact"
      title="Contact Camxora"
      description="Reach us for product support, privacy requests, billing questions, and Google / YouTube OAuth help."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Response time</div>
          <div className="font-display text-2xl font-semibold tracking-[-0.05em] text-white">
            24–48 business hours
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Business hours: Mon–Fri, 09:00–18:00 (Asia/Phnom_Penh).
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {[
          {
            title: "Company",
            detail: COMPANY.name,
            extra: `Jurisdiction: ${COMPANY.jurisdiction}`,
          },
          {
            title: "Support",
            detail: COMPANY.supportEmail,
            href: `mailto:${COMPANY.supportEmail}`,
            extra: "Account, desktop app, billing, generation",
          },
          {
            title: "Privacy",
            detail: COMPANY.privacyEmail,
            href: `mailto:${COMPANY.privacyEmail}`,
            extra: "Access, correction, deletion, Google data",
          },
          {
            title: "Legal",
            detail: COMPANY.legalEmail,
            href: `mailto:${COMPANY.legalEmail}`,
            extra: "Terms, copyright notices, legal questions",
          },
          {
            title: "Website",
            detail: COMPANY.website,
            href: COMPANY.website,
            extra: "Marketing site & product information",
          },
          {
            title: "User portal",
            detail: "Sign in / billing",
            href: `${userPortalBaseUrl}/login`,
            extra: "Plans, credits, and account settings",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
          >
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">{item.title}</div>
            {item.href ? (
              <a
                className="mt-3 block font-display text-xl font-semibold text-white hover:text-fuchsia-100"
                href={item.href}
                rel={item.href.startsWith("http") ? "noopener noreferrer" : undefined}
                target={item.href.startsWith("http") ? "_blank" : undefined}
              >
                {item.detail}
              </a>
            ) : (
              <div className="mt-3 font-display text-xl font-semibold text-white">{item.detail}</div>
            )}
            <p className="mt-3 text-sm leading-7 text-slate-200/72">{item.extra}</p>
          </div>
        ))}
      </div>

      <section className="grid gap-6 border-t border-white/8 pt-10 md:grid-cols-2">
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <h2 className="font-display text-2xl font-semibold text-white">Google OAuth / YouTube</h2>
          <p className="mt-3 text-sm leading-7 text-slate-200/72">
            For consent-screen questions, disconnect help, or Limited Use policy details, see our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Policy
            </Link>{" "}
            and{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
            </Link>{" "}
            pages, or email {COMPANY.privacyEmail}.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <h2 className="font-display text-2xl font-semibold text-white">Help Center</h2>
          <p className="mt-3 text-sm leading-7 text-slate-200/72">
            Browse getting-started, billing, AI generation, and YouTube guides in the{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/support">
              Support / Help Center
            </Link>
            .
          </p>
        </div>
      </section>

      {BUSINESS_ADDRESS ? (
        <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 text-sm leading-7 text-slate-200/85 ring-1 ring-white/6">
          <strong className="text-white">Business address:</strong> {BUSINESS_ADDRESS}
        </section>
      ) : null}
    </ContentPageShell>
  );
}
