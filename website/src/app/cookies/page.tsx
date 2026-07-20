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
  title: "Cookie Policy",
  description: "How Camxora uses cookies and similar technologies on the website and portals.",
};

export default function CookiesPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Cookie Policy"
      description="This Cookie Policy explains how Camxora uses cookies and similar technologies on our websites and account portals."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <Link className="text-sm text-violet-200 hover:text-fuchsia-200" href="/privacy">
            Privacy Policy
          </Link>
        </div>
      }
    >
      <LegalMeta effectiveDate={LEGAL_EFFECTIVE_DATE} lastUpdated={LEGAL_LAST_UPDATED} />

      <div className="space-y-12">
        <LegalSection id="what" title="1. What are cookies?">
          <p>
            Cookies are small text files stored on your device. We also use similar technologies
            such as local storage and session tokens for authentication and preferences.
          </p>
        </LegalSection>

        <LegalSection id="types" title="2. Types we use">
          <p>
            <strong className="text-white">Essential:</strong> required for sign-in, session
            security, CSRF protection, and core site functionality.
          </p>
          <p>
            <strong className="text-white">Preferences:</strong> remember UI choices such as locale
            or dismissed notices.
          </p>
          <p>
            <strong className="text-white">Analytics:</strong> help us understand aggregate traffic
            and improve the website (used only where enabled).
          </p>
        </LegalSection>

        <LegalSection id="manage" title="3. Managing cookies">
          <LegalList
            items={[
              "You can block or delete cookies in your browser settings.",
              "Blocking essential cookies may prevent login or checkout from working.",
              "The Camxora desktop app primarily uses local app storage rather than website cookies.",
            ]}
          />
        </LegalSection>

        <LegalSection id="contact" title="4. Contact">
          <p>
            Questions:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
