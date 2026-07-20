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
import { getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Data Deletion",
  description:
    "How to delete your Camxora account and Google / YouTube connection data.",
};

export default function DataDeletionPage() {
  const userPortalBaseUrl = getUserPortalBaseUrl();

  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Data Deletion Instructions"
      description="Clear steps to delete your Camxora account data and revoke Google / YouTube access — important for user control and Google OAuth verification."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Quick links</div>
          <div className="grid gap-2 text-sm">
            <a className="text-violet-200 hover:text-fuchsia-200" href={`${userPortalBaseUrl}/login`}>
              User portal
            </a>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/privacy">
              Privacy Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Policy
            </Link>
            <a
              className="text-violet-200 hover:text-fuchsia-200"
              href="https://myaccount.google.com/permissions"
              rel="noopener noreferrer"
              target="_blank"
            >
              Google permissions
            </a>
          </div>
        </div>
      }
    >
      <LegalMeta effectiveDate={LEGAL_EFFECTIVE_DATE} lastUpdated={LEGAL_LAST_UPDATED} />

      <div className="space-y-12">
        <LegalSection id="overview" title="1. Overview">
          <p>
            You can delete Camxora account data and disconnect Google integrations at any time. This
            page explains what is deleted, what may be retained for legal reasons, and typical
            processing times.
          </p>
        </LegalSection>

        <LegalSection id="disconnect-google" title="2. Disconnect Google / YouTube">
          <LegalList
            items={[
              "In Camxora (desktop or portal, where available): open your channel / YouTube connection settings and disconnect the Google account.",
              "In Google: visit Google Account → Security → Third-party access with account access → remove Camxora.",
              "Direct link: https://myaccount.google.com/permissions",
            ]}
          />
          <p>
            Disconnecting stops new API access. Stored OAuth tokens associated with that connection
            are revoked or deleted from Camxora systems as part of disconnection / deletion
            processing.
          </p>
        </LegalSection>

        <LegalSection id="delete-account" title="3. Delete your Camxora account">
          <p>To request full account deletion:</p>
          <LegalList
            items={[
              `Email ${COMPANY.privacyEmail} from the same email address used for your Camxora account.`,
              "Subject line: Account deletion request",
              "Include your account email and any channel profile names you want confirmed deleted.",
            ]}
          />
          <p>
            Alternatively, use in-product account deletion controls when available in the user
            portal, then confirm by email if prompted.
          </p>
        </LegalSection>

        <LegalSection id="what-deleted" title="4. What is deleted">
          <LegalList
            items={[
              "Account profile and login credentials",
              "Channel profiles and app preferences",
              "Stored Google OAuth tokens and YouTube connection records",
              "Project metadata and generation history associated with your account (subject to technical backups rotating out)",
              "Optional diagnostic logs tied to your user ID where feasible",
            ]}
          />
        </LegalSection>

        <LegalSection id="what-remains" title="5. What may remain">
          <LegalList
            items={[
              "Billing and tax records required by law",
              "Fraud-prevention and security logs retained for a limited period",
              "Anonymized / aggregated analytics that no longer identify you",
              "Content you already published to YouTube or other platforms (controlled by those platforms, not Camxora)",
            ]}
          />
        </LegalSection>

        <LegalSection id="timing" title="6. Processing time">
          <p>
            We aim to process deletion requests within <strong className="text-white">30 days</strong>
            . Google access revocation through Google’s own permissions page is typically immediate
            on Google’s side.
          </p>
        </LegalSection>

        <LegalSection id="contact" title="7. Contact">
          <p>
            Deletion and privacy requests:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>
            <br />
            Support:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.supportEmail}`}>
              {COMPANY.supportEmail}
            </a>
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
