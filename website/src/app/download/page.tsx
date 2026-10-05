import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Download, ExternalLink } from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { ReleaseNotesContent } from "@/components/marketing/release-notes-content";
import { getPublicDesktopRelease } from "@/lib/desktop-release";
import { getUserPortalBaseUrl } from "@/lib/site-urls";
import { summarizeReleaseNotes } from "@/lib/release-notes";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Download",
  description: "Download Camxora for Windows and start dual faceless YouTube music channels.",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function summarizeReleaseNotesPreview(notes: string): string {
  return summarizeReleaseNotes(notes, 220);
}

function formatDownloadCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.max(0, value));
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
      eyebrow="Download"
      title="Install Camxora and start your first song-to-video run."
      description="Create an account, choose a plan, then download the Windows app — where lyrics, music, artwork, and video export live."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Desktop focus</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              The app is where creation happens.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Billing stays in the portal. Preview, export, and merge stay in Camxora. Auto YouTube
            upload is coming soon.
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
                    Camxora Desktop v{release.version}
                  </div>
                  <div className="mt-2 text-sm text-slate-400">
                    Published {formatDate(release.published_at)}
                    {release.mandatory ? " · Required update" : null}
                    {typeof release.download_count === "number"
                      ? ` · ${formatDownloadCount(release.download_count)} download${release.download_count === 1 ? "" : "s"} for v${release.version}`
                      : null}
                    {typeof release.total_downloads === "number" && release.total_downloads > release.download_count
                      ? ` · ${formatDownloadCount(release.total_downloads)} total`
                      : null}
                  </div>
                </div>
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                  <Download className="h-4 w-4 text-primary" />
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                {release.download_url && /^https?:\/\//i.test(release.download_url) ? (
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
                    A download URL has not been published yet. Check back after the next release.
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
                    What&apos;s new
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-200/80">
                    {summarizeReleaseNotesPreview(release.release_notes)}
                  </p>
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-white/90">
                      Full release notes
                    </summary>
                    <div className="mt-4">
                      <ReleaseNotesContent content={release.release_notes} className="text-sm md:text-base" />
                    </div>
                  </details>
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
                The installer will appear here once a software update is published.
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
          Recommended path: create your account → choose a plan → download Camxora → sign in on
          desktop and start a batch.
        </div>
      </div>

      <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">What you can do today</div>
        <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
          Export YouTube-ready music videos.
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">
          Lyrics, music, images, templates, export, and merge are in the app now. Auto YouTube upload
          will follow in a later release — this page always points to the same published installer as
          the portal and in-app updates.
        </p>
      </section>
    </ContentPageShell>
  );
}
