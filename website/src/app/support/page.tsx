import type { Metadata } from "next";
import Link from "next/link";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { COMPANY } from "@/components/marketing/legal-doc";
import { getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Support / Help Center",
  description:
    "Camxora help center — getting started, billing, AI generation, YouTube connection, and desktop app support.",
};

const sections = [
  {
    title: "Getting started",
    items: [
      { q: "Create an account", a: "Register from the website Create account button, verify your email if prompted, then sign in to the user portal." },
      { q: "Download the app", a: "Visit the Download page for the latest Windows installer published by Camxora." },
      { q: "Install & sign in", a: "Run the installer, open Camxora, and sign in with the same account used in the portal." },
      { q: "Choose a plan", a: "Pick a channel plan in the portal before heavy generation so credits and quotas are available." },
    ],
  },
  {
    title: "Billing & credits",
    items: [
      { q: "Upgrade or change plan", a: "Manage plans in the user portal billing area. Sandbox environments may show low test prices." },
      { q: "Cancel renewal", a: "Cancel from the portal before the next billing date. Access typically continues until the period ends." },
      { q: "Plan refunds", a: "Monetization guarantee: if you use Camxora to build and publish your faceless music channel and you do not reach YouTube monetization, we refund your plan payment in full. Contact support@camxora.com with your account, invoice, and channel details. You must follow Camxora’s workflow and YouTube policies. The refund covers the plan fee, not lost AdSense earnings. Other plan fees are generally non-refundable once a billing period starts, except where required by law (see Terms)." },
      { q: "Export cancel & usage refunds", a: "Track exports (studio and manual) share one allowance pool. If export fails for a technical reason and no usable file is produced, that unit is restored. If you stop an export yourself: finished tracks and the track that was encoding keep their charge; tracks that never started are restored. Stopping a merge after it started keeps the merge charge. Details: Terms § Credits System." },
      { q: "How credits work", a: "Plans include allowances for drafts, music packages, images, track exports (studio + manual), and merges. Overage may use wallet credits at published rates." },
    ],
  },
  {
    title: "AI generation",
    items: [
      { q: "Lyrics & music", a: "Use the Music workspace to draft lyrics, polish, and generate songs in batches." },
      { q: "Images", a: "Generate backgrounds and thumbnails aligned to each track and channel profile." },
      { q: "Video & merge", a: "Build templates, export MP4s, and merge outputs in the desktop studio. Studio and manual track exports share one quota pool; cancel/refund rules for exports are under Billing & credits." },
      { q: "Who owns outputs?", a: "See Terms § AI Generated Content. You are responsible for what you publish; review AI outputs before upload." },
    ],
  },
  {
    title: "YouTube",
    items: [
      { q: "Connect Google / YouTube", a: "When the feature is enabled, connect from channel settings using Google OAuth and approve only the shown permissions." },
      { q: "Disconnect", a: "Disconnect in Camxora settings and revoke access at myaccount.google.com/permissions." },
      { q: "OAuth permissions", a: "Camxora uses YouTube upload/readonly/force-ssl scopes to connect channels and upload videos you request. Details: Google API Data Policy." },
      { q: "Upload troubleshooting", a: "Confirm the account is connected, scopes are granted, the video file exists, and your Google account owns the target channel. Auto-upload may be rolling out gradually." },
    ],
  },
  {
    title: "Desktop app",
    items: [
      { q: "Windows install", a: "Use CamxoraSetup installer from the Download page. Allow VC++ redistributable if prompted." },
      { q: "Updates", a: "In-app update prompts and the Download page point to the same published release when configured." },
      { q: "macOS", a: "Not available in the current release. Windows is supported first." },
    ],
  },
];

const faqs = [
  {
    q: "Can I monetize AI-generated videos?",
    a: "Yes — that is our promise. Use Camxora to build and publish your faceless music channel. If you do not reach YouTube monetization, we refund your plan payment in full (see Pricing and Terms). You must follow YouTube policies and own/clear rights to publish.",
  },
  {
    q: "Who owns generated content?",
    a: "You retain rights in your prompts and uploads subject to our Terms and third-party AI provider terms. Camxora does not guarantee copyright registration or uniqueness.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes — cancel renewal in the portal. You generally keep access until the paid period ends unless suspended for policy violations.",
  },
  {
    q: "What if I stop a video export?",
    a: "Stopping yourself does not restore finished tracks or the track that was encoding. Tracks that never started are restored. Technical failures that produce no usable file are restored. See Support → Billing & credits and Terms § Credits System.",
  },
  {
    q: "How do I reconnect YouTube?",
    a: "Disconnect and reconnect from Camxora channel settings, or revoke and re-authorize in Google Account permissions, then complete OAuth again.",
  },
];

export default function SupportPage() {
  const userPortalBaseUrl = getUserPortalBaseUrl();

  return (
    <ContentPageShell
      eyebrow="Support"
      title="Help Center"
      description="Guides for getting started, billing, generation, YouTube connection, and the Windows desktop app."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Need a human?</div>
          <p className="text-sm leading-6 text-slate-200/72">
            Average reply time: 24–48 business hours.
          </p>
          <a
            className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-white transition hover:bg-white/[0.06]"
            href={`mailto:${COMPANY.supportEmail}`}
          >
            Email support
          </a>
          <Link className="block text-sm text-violet-200 hover:text-fuchsia-200" href="/contact">
            Contact page
          </Link>
          <a className="block text-sm text-violet-200 hover:text-fuchsia-200" href={`${userPortalBaseUrl}/login`}>
            User portal
          </a>
        </div>
      }
    >
      <div className="space-y-12">
        {sections.map((section) => (
          <section key={section.title} className="space-y-4">
            <h2 className="font-display text-2xl font-semibold tracking-[-0.04em] text-white md:text-3xl">
              {section.title}
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {section.items.map((item) => (
                <div
                  key={item.q}
                  className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6"
                >
                  <div className="font-medium text-white">{item.q}</div>
                  <p className="mt-2 text-sm leading-7 text-slate-200/72">{item.a}</p>
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className="space-y-4 border-t border-white/8 pt-10">
          <h2 className="font-display text-2xl font-semibold tracking-[-0.04em] text-white md:text-3xl">
            FAQ
          </h2>
          <div className="space-y-4">
            {faqs.map((item) => (
              <div
                key={item.q}
                className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6"
              >
                <div className="font-medium text-white">{item.q}</div>
                <p className="mt-2 text-sm leading-7 text-slate-200/72">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Legal & privacy</div>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/terms">
              Terms
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/privacy">
              Privacy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data deletion
            </Link>
          </div>
        </section>
      </div>
    </ContentPageShell>
  );
}
