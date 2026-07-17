import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Services",
  description: "CAMXORA services across account access, desktop production, and branded music channel workflow control.",
};

export default function ServicesPage() {
  return (
    <ContentPageShell
      eyebrow="Services"
      title="Services across discovery, access, and desktop production."
      description="CAMXORA uses separate surfaces for public trust, account setup, and studio workflow so each part of the journey stays clearer."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Service model</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              One ecosystem with coordinated entry points.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Each surface should support one continuous creator journey, not feel like a disconnected tool.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Website and trust",
            detail: "Public pages explain the product and move qualified users into account creation.",
          },
          {
            title: "Account access and billing",
            detail: "Account setup and live pricing prepare users before they reach the studio.",
          },
          {
            title: "Desktop production",
            detail: "Music, image, video, and workflow tools stay focused on repeatable production.",
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

      <section className="grid gap-6 border-t border-white/8 pt-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Operational focus</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            Separation improves both UX and trust.
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/72 md:text-base">
            The website explains, the account flow prepares, and the desktop app produces. That
            makes the whole system feel more intentional.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Result</div>
          <div className="mt-3 text-sm leading-7 text-slate-200/72">
            Clearer expectations, stronger conversion, and a more premium handoff into the product.
          </div>
        </div>
      </section>
    </ContentPageShell>
  );
}
