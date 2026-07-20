import type { Metadata } from "next";
import Link from "next/link";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import {
  COMPANY,
  LEGAL_EFFECTIVE_DATE,
  LEGAL_LAST_UPDATED,
  LegalList,
  LegalMeta,
  LegalSection,
} from "@/components/marketing/legal-doc";

export const metadata: Metadata = {
  title: "Acceptable Use Policy",
  description: "Prohibited uses of Camxora, including spam, infringement, and API abuse.",
};

export default function AcceptableUsePage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Acceptable Use Policy"
      description="Rules for using Camxora safely and lawfully. Violations may result in suspension or termination."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <div className="grid gap-2 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/terms">
              Terms & Conditions
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/copyright">
              Copyright Policy
            </Link>
          </div>
        </div>
      }
    >
      <LegalMeta effectiveDate={LEGAL_EFFECTIVE_DATE} lastUpdated={LEGAL_LAST_UPDATED} />

      <div className="space-y-12">
        <LegalSection id="allowed" title="1. Allowed use">
          <p>
            Use Camxora to create, organize, export, and (when enabled) upload music and video
            content you have rights to use, in compliance with these rules and third-party platform
            terms (including YouTube).
          </p>
        </LegalSection>

        <LegalSection id="prohibited" title="2. Prohibited activities">
          <LegalList
            items={[
              "Illegal content or activity under applicable law",
              "Copyright, trademark, or publicity-right infringement",
              "Hate speech, harassment, exploitation, or content that exploits minors",
              "Spam, scams, phishing, or deceptive practices",
              "Malware, credential theft, or attempts to compromise Camxora or other users",
              "Circumventing plan limits, billing, credits, or security controls",
              "Automated abuse of APIs, generation endpoints, or Google/YouTube integrations",
              "Impersonation of Camxora, Google, YouTube, or other people/entities",
              "Using connected Google accounts you do not own or are not authorized to manage",
              "Uploading content that violates YouTube Community Guidelines or YouTube Terms of Service",
            ]}
          />
        </LegalSection>

        <LegalSection id="ai" title="3. AI transparency & review">
          <LegalList
            items={[
              "AI outputs can be inaccurate, biased, or similar to other outputs — review before publishing",
              "You are responsible for ensuring published content complies with platform rules and laws",
              "Do not use Camxora to generate prohibited content at scale",
            ]}
          />
        </LegalSection>

        <LegalSection id="enforcement" title="4. Enforcement">
          <p>
            We may investigate suspected violations, remove content, suspend features (including
            YouTube upload), or terminate accounts. Report concerns to{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.supportEmail}`}>
              {COMPANY.supportEmail}
            </a>
            .
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
