import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Privacy",
  description: "Privacy policy placeholder for the CAMXORA website and user platform.",
};

export default function PrivacyPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Privacy policy"
      description="This page is reserved for the formal privacy policy covering website usage, account data, and platform interactions."
    >
      <section className="grid gap-6 md:grid-cols-3">
        {[
          "Website analytics and account data disclosures will be published here.",
          "Updates will reflect account access, billing, and platform interactions.",
          "This route keeps the website and footer linked to a stable legal destination.",
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
