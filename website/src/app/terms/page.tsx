import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms of service placeholder for the CAMXORA website and platform.",
};

export default function TermsPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Terms of service"
      description="This page is reserved for the formal service terms covering usage, subscriptions, and platform policies."
    >
      <section className="grid gap-6 md:grid-cols-3">
        {[
          "Use of CAMXORA services remains subject to platform and account policies.",
          "Subscription, billing, and renewal terms will be published here as they are finalized.",
          "This route provides a stable legal destination for the website, account, and billing flow.",
        ].map((item) => (
          <div
            key={item}
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 text-sm leading-7 text-slate-200/72 ring-1 ring-white/6"
          >
            {item}
          </div>
        ))}
      </section>
    </ContentPageShell>
  );
}
