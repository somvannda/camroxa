import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact CAMXORA for product, support, and business inquiries.",
};

export default function ContactPage() {
  return (
    <ContentPageShell
      eyebrow="Contact"
      title="Reach the CAMXORA team for product, support, and business questions."
      description="This page gives the website a clear public contact layer while richer support flows continue to mature."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Public contact</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Clear routing makes the platform feel operational.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Visitors should know where account, support, and business conversations belong.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Account help",
            detail: "For sign-in, setup, plan selection, and getting started questions.",
          },
          {
            title: "Support",
            detail: "For workflow, production, and desktop usage questions as support routing expands.",
          },
          {
            title: "Business and partnerships",
            detail: "For partnerships, creator programs, and platform-level conversations.",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
          >
            <h2 className="font-display text-2xl font-semibold text-white">{item.title}</h2>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">{item.detail}</p>
          </div>
        ))}
      </div>

      <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Next layer</div>
        <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
          Form routing and support resources come next.
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">
          This page is designed to support a future contact form, clearer email routing, and links to
          account, billing, and desktop help resources.
        </p>
      </section>
    </ContentPageShell>
  );
}
