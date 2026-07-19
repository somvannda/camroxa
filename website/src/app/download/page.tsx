import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Download, ExternalLink } from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { getPublicDesktopRelease } from "@/lib/desktop-release";
import { getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Download",
  description: "Download the Camxora desktop studio for Windows.",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export default async function DownloadPage() {
  const userPortalBaseUrl = getUserPortalBaseUrl();
  let release = null;
  let loadError: string | null = null;

  try {
    release = await getPublicDesktopRelease();
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Unable to load the latest release.";
  }

  return (
    <ContentPageShell
      eyebrow="Desktop App"
      title="Download the CAMXORA desktop studio."
      description="The website explains the product and handles access. The desktop app is where the production workflow happens."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Desktop focus</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              The app is the production surface.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Account setup and billing stay outside the studio so the app can stay focused on work.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          {loadError ? (
            <>
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Download status</div>
              <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
                Release information is temporarily unavailable.
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-200/72">{loadError}</p>
              <p className="mt-3 text-sm leading-7 text-slate-200/72">
                Try again shortly, or contact support if the issue persists.
              </p>
            </>
          ) : release ? (
            <>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                    Latest release
                  </div>
                  <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
                    CAMXORA Desktop v{release.version}
                  </div>
                  <div className="mt-2 text-sm text-slate-400">
                    Published {formatDate(release.published_at)}
                    {release.mandatory ? " · Required update" : null}
                  </div>
                </div>
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                  <Download className="h-4 w-4 text-primary" />
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                {release.download_url ? (
                  <a
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                    href={release.download_url}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    Download for Windows
                    <ExternalLink className="h-4 w-4" />
                  </a>
                ) : (
                  <div className="text-sm leading-7 text-slate-200/72">
                    A download URL has not been configured yet. Check back after the next publish.
                  </div>
                )}
                <Link
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                  href="/changelog"
                >
                  View changelog
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>

              {release.release_notes ? (
                <div className="mt-8 rounded-2xl border border-white/8 bg-black/20 p-5">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                    Release notes
                  </div>
                  <div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200/72">
                    {release.release_notes}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Download status</div>
              <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
                No public desktop release yet.
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-200/72">
                The installer will appear here once an admin publishes a software update from the admin
                portal.
              </p>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <a
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                  href={`${userPortalBaseUrl}/register`}
                >
                  Create account
                  <ArrowRight className="h-4 w-4" />
                </a>
                <Link
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                  href="/contact"
                >
                  Contact support
                </Link>
              </div>
            </>
          )}
        </div>

        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 text-sm leading-7 text-slate-200/72 ring-1 ring-white/6">
          Recommended flow: create your account, choose a plan, then download and sign in on desktop.
        </div>
      </div>

      <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why it matters</div>
        <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
          The desktop download should feel connected to the full product.
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">
          This page stays in sync with admin-published software updates, so website downloads, user
          portal links, and in-app update prompts all point to the same release.
        </p>
      </section>
    </ContentPageShell>
  );
}
