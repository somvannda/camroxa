import type { ReactNode } from "react";

export function LegalSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28 space-y-4 border-b border-white/8 pb-10 last:border-b-0 last:pb-0">
      <h2 className="font-display text-2xl font-semibold tracking-[-0.04em] text-white md:text-3xl">
        {title}
      </h2>
      <div className="space-y-4 text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
        {children}
      </div>
    </section>
  );
}

export function LegalList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-2 pl-5 text-slate-200/78">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function LegalMeta({
  effectiveDate,
  lastUpdated,
}: {
  effectiveDate: string;
  lastUpdated: string;
}) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] px-5 py-4 text-sm text-slate-300/80 ring-1 ring-white/6">
      <div>Effective date: {effectiveDate}</div>
      <div className="mt-1">Last updated: {lastUpdated}</div>
    </div>
  );
}

export const LEGAL_EFFECTIVE_DATE = "July 19, 2026";
export const LEGAL_LAST_UPDATED = "July 19, 2026";

export const COMPANY = {
  name: "Camxora",
  product: "Camxora",
  supportEmail: "support@camxora.com",
  privacyEmail: "privacy@camxora.com",
  legalEmail: "legal@camxora.com",
  website: "https://camxora.com",
  jurisdiction: "Kingdom of Cambodia",
  governingLaw: "the laws of the Kingdom of Cambodia",
};
