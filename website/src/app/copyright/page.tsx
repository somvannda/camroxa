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
  title: "Copyright Policy",
  description: "How to report copyright infringement related to Camxora content and accounts.",
};

export default function CopyrightPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Copyright Policy"
      description="Camxora respects intellectual property rights. This page explains how to report alleged infringement and how we handle notices."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <div className="grid gap-2 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/acceptable-use">
              Acceptable Use
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/terms">
              Terms & Conditions
            </Link>
          </div>
        </div>
      }
    >
      <LegalMeta effectiveDate={LEGAL_EFFECTIVE_DATE} lastUpdated={LEGAL_LAST_UPDATED} />

      <div className="space-y-12">
        <LegalSection id="policy" title="1. Our policy">
          <p>
            Users may not upload, generate for distribution, or publish content through Camxora that
            infringes copyrights, trademarks, or other rights. Users are responsible for content they
            create and publish to YouTube or other platforms.
          </p>
        </LegalSection>

        <LegalSection id="report" title="2. How to report infringement">
          <p>Send a notice to:</p>
          <p>
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.legalEmail}`}>
              {COMPANY.legalEmail}
            </a>
          </p>
          <p>Include:</p>
          <LegalList
            items={[
              "Your contact name, address, email, and phone number",
              "Description of the copyrighted work claimed to be infringed",
              "URL, account email, or other information reasonably sufficient to locate the material in Camxora",
              "A statement that you have a good-faith belief the use is not authorized",
              "A statement under penalty of perjury that the information is accurate and you are authorized to act",
              "Your physical or electronic signature",
            ]}
          />
        </LegalSection>

        <LegalSection id="response" title="3. What we do">
          <LegalList
            items={[
              "Review complete notices in good faith",
              "Remove or disable access to allegedly infringing material where appropriate",
              "Notify the affected user when feasible",
              "Terminate repeat infringers in appropriate circumstances",
            ]}
          />
        </LegalSection>

        <LegalSection id="counter" title="4. Counter-notices">
          <p>
            If you believe material was removed in error, email {COMPANY.legalEmail} with a
            counter-notice including your contact information, identification of the removed
            material, a good-faith statement, consent to jurisdiction in {COMPANY.jurisdiction}, and
            your signature.
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
