import type { Metadata } from "next";
import { Download } from "lucide-react";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Download",
  description: "Download the Camxora desktop studio for Windows.",
};

export default function DownloadPage() {
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
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="text-sm font-medium text-white">CAMXORA Desktop for Windows</div>
              <div className="mt-2 text-sm leading-7 text-slate-200/72">
                This page is ready for the public installer, version information, and release notes.
              </div>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
              <Download className="h-4 w-4 text-primary" />
            </div>
          </div>
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
          This page makes it clear that the app is part of a larger system, not an isolated
          download.
        </p>
      </section>
    </ContentPageShell>
  );
}
