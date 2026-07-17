import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "About",
  description: "About CAMXORA and the product direction behind its desktop studio for branded music channel production.",
};

export default function AboutPage() {
  return (
    <ContentPageShell
      eyebrow="About"
      title="CAMXORA is the desktop studio for branded music channel production."
      description="The product is designed around clearer workflow, stronger control, and a more professional path from website to desktop."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Positioning</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Workflow-first and desktop-first.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            CAMXORA is not a lightweight web tool. It is a production system with a real studio workflow.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Clear product entry",
            detail: "The website and account flow explain the product before users enter the desktop studio.",
          },
          {
            title: "Desktop-first production",
            detail: "Music, image, video, preview, rendering, and export stay centered in the app.",
          },
          {
            title: "One product system",
            detail: "Website, pricing, account, and desktop are being shaped to feel consistent end to end.",
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
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why it matters</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            Better trust before the studio opens.
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/72 md:text-base">
            A stronger website reduces confusion, improves trust, and sets the right expectation for
            the desktop workflow users are about to enter.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Focus</div>
          <div className="mt-3 text-sm leading-7 text-slate-200/72">
            Fewer disconnected surfaces. Stronger brand continuity. Clearer product story.
          </div>
        </div>
      </section>
    </ContentPageShell>
  );
}
