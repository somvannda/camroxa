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
  title: "Privacy Policy",
  description:
    "How Camxora collects, uses, and protects account, content, billing, and Google/YouTube data.",
};

export default function PrivacyPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Privacy Policy"
      description="This Privacy Policy explains what information Camxora collects, how we use it, and the choices you have — including Google user data used for YouTube features."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <div className="grid gap-2 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/cookies">
              Cookie Policy
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
        <LegalSection id="who" title="1. Who we are">
          <p>
            {COMPANY.name} (“Camxora,” “we,” “us”) operates the Camxora website, account portal,
            desktop application, and related APIs. Contact privacy questions at{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>
            .
          </p>
        </LegalSection>

        <LegalSection id="collect" title="2. Information we collect">
          <p>
            <strong className="text-white">Account information:</strong> email address, name or
            display name, password hashes or auth tokens, account preferences, and channel profiles.
          </p>
          <p>
            <strong className="text-white">Usage & diagnostics:</strong> app and API logs, feature
            usage, error reports, device/OS information for the desktop app, IP address, and
            approximate location derived from network data.
          </p>
          <p>
            <strong className="text-white">Billing:</strong> plan selection, invoices, payment status,
            and records from payment processors (such as CutLuy). We do not store full card numbers
            on Camxora servers when payments are handled by a processor.
          </p>
          <p>
            <strong className="text-white">Content you create or upload:</strong> lyrics, prompts,
            music and image assets, video templates, export paths, progress metadata, and project
            history needed to provide the Services.
          </p>
          <p>
            <strong className="text-white">Google / YouTube data:</strong> only when you voluntarily
            connect a Google Account. Depending on the permissions you grant, this may include OAuth
            tokens, YouTube channel identifiers and titles, basic channel metadata, and information
            required to upload or manage videos you request. See Section 3 and our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Usage
            </Link>{" "}
            page.
          </p>
        </LegalSection>

        <LegalSection id="google-data" title="3. Google user data">
          <p>
            When you connect your Google Account, Camxora may access only the permissions you
            explicitly authorize through Google’s consent screen. Current Camxora YouTube features
            use scopes such as:
          </p>
          <LegalList
            items={[
              "https://www.googleapis.com/auth/youtube.upload — upload videos you request",
              "https://www.googleapis.com/auth/youtube.readonly — read channel information needed for connection and status",
              "https://www.googleapis.com/auth/youtube.force-ssl — YouTube API access over HTTPS for authorized operations",
            ]}
          />
          <p>
            We use this access solely to provide requested features (for example connecting a
            channel profile, retrieving basic channel information, and uploading videos you initiate
            when that feature is enabled for your account).
          </p>
        </LegalSection>

        <LegalSection id="do-not" title="4. What we do not do with Google user data">
          <LegalList
            items={[
              "We do not sell Google user data.",
              "We do not use Google user data for advertising.",
              "We do not use Google user data for personalized ads or creditworthiness decisions.",
              "We do not transfer Google user data to third parties except as necessary to operate requested features, with subprocessors under contract, or to comply with law.",
              "We do not access Google data beyond the scopes you authorize.",
              "We do not use Google Workspace APIs to train generalized AI/ML models in a way that violates Google’s Limited Use requirements.",
            ]}
          />
          <p>
            Camxora’s use and transfer of information received from Google APIs adheres to the{" "}
            <a
              className="text-violet-200 hover:text-fuchsia-200"
              href="https://developers.google.com/terms/api-services-user-data-policy"
              rel="noopener noreferrer"
              target="_blank"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
        </LegalSection>

        <LegalSection id="use" title="5. How we use data">
          <LegalList
            items={[
              "Authenticate users and secure accounts",
              "Provide generation, storage, preview, export, merge, and progress features",
              "Connect YouTube channels and perform uploads you request",
              "Process subscriptions, credits, and support requests",
              "Monitor reliability, prevent abuse, and improve the product",
              "Comply with legal obligations",
            ]}
          />
        </LegalSection>

        <LegalSection id="sharing" title="6. Data sharing">
          <p>We share data only as needed with:</p>
          <LegalList
            items={[
              "Cloud hosting, storage, and email infrastructure providers",
              "AI / media generation providers required to fulfill your requests",
              "Payment processors (e.g., CutLuy) for checkout and billing",
              "Google, when you authorize YouTube/Google API access",
              "Professional advisors or authorities when required by law or to protect rights and safety",
            ]}
          />
          <p>We do not sell personal data to advertisers.</p>
        </LegalSection>

        <LegalSection id="retention" title="7. Data retention">
          <p>
            We retain account, billing, and content data for as long as your account is active and as
            needed to provide the Services. We may retain limited records after account closure for
            legal, tax, fraud-prevention, or dispute-resolution purposes. Google OAuth tokens are
            retained while a connection remains active and are revoked or deleted when you disconnect
            or delete related data as described on the{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
            </Link>{" "}
            page.
          </p>
        </LegalSection>

        <LegalSection id="cookies" title="8. Cookies">
          <p>
            We use cookies and similar technologies for authentication, preferences, and analytics.
            Details are in our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/cookies">
              Cookie Policy
            </Link>
            .
          </p>
        </LegalSection>

        <LegalSection id="security" title="9. Security">
          <LegalList
            items={[
              "HTTPS / TLS encryption in transit",
              "Access controls for production systems",
              "Hashed passwords and token-based authentication where applicable",
              "Operational logging and monitoring for abuse detection",
            ]}
          />
          <p>
            No method of transmission or storage is 100% secure. We do not claim certifications we
            have not obtained.
          </p>
        </LegalSection>

        <LegalSection id="rights" title="10. Your rights">
          <p>Depending on your location, you may have rights to:</p>
          <LegalList
            items={[
              "Access the personal data we hold about you",
              "Correct inaccurate information",
              "Request deletion of your account and associated data",
              "Export a copy of certain account data",
              "Withdraw consent for optional processing (including Google connection)",
              "Object to or restrict certain processing where applicable law allows",
            ]}
          />
          <p>
            To exercise these rights, email{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>{" "}
            or follow the steps on{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
            </Link>
            . You can also revoke Google access in your Google Account settings.
          </p>
        </LegalSection>

        <LegalSection id="children" title="11. Children’s privacy">
          <p>
            Camxora is not directed to children under 13. We do not knowingly collect personal
            information from children under 13. If you believe a child has provided data, contact{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>{" "}
            and we will take appropriate steps to delete it.
          </p>
        </LegalSection>

        <LegalSection id="international" title="12. International transfers">
          <p>
            We may process data on servers outside your country. Where required, we use appropriate
            safeguards for cross-border transfers. Camxora is operated with primary business focus in{" "}
            {COMPANY.jurisdiction}.
          </p>
        </LegalSection>

        <LegalSection id="changes" title="13. Changes">
          <p>
            We may update this Privacy Policy from time to time. Material changes will be posted on
            this page with a revised “Last updated” date.
          </p>
        </LegalSection>

        <LegalSection id="contact" title="14. Contact">
          <p>
            Privacy requests:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>
            <br />
            General support:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.supportEmail}`}>
              {COMPANY.supportEmail}
            </a>
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
