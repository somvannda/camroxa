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
  title: "Google API Data Usage & Limited Use",
  description:
    "How Camxora uses Google / YouTube API data in compliance with Google’s Limited Use requirements.",
};

export default function GoogleApiPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Google API Data Usage & Limited Use"
      description="This page explains how Camxora uses information received from Google APIs when you connect YouTube — written for transparency during Google OAuth verification."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <div className="grid gap-2 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/privacy">
              Privacy Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
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
        <LegalSection id="overview" title="1. Overview">
          <p>
            Camxora integrates with Google OAuth and the YouTube Data API so users can optionally
            connect YouTube channels and upload videos they create in Camxora. Connection is
            voluntary. Camxora is not affiliated with Google or YouTube.
          </p>
        </LegalSection>

        <LegalSection id="scopes" title="2. Scopes we request">
          <p>Depending on enabled features, Camxora may request:</p>
          <LegalList
            items={[
              "youtube.upload — to upload videos you explicitly request",
              "youtube.readonly — to read channel information needed to identify and manage connected channels",
              "youtube.force-ssl — to call YouTube APIs securely for authorized operations",
            ]}
          />
          <p>
            We do not request Google scopes unrelated to providing these YouTube features. If scopes
            change, we will update this page and the Google consent screen accordingly.
          </p>
        </LegalSection>

        <LegalSection id="use" title="3. How Google API data is used">
          <p>Camxora uses Google API data only to:</p>
          <LegalList
            items={[
              "Authenticate your Google / YouTube connection",
              "Retrieve basic channel information required for linked channel profiles",
              "Upload videos you create and choose to publish through Camxora (when the upload feature is available for your account)",
              "Show upload status and related progress inside Camxora",
              "Maintain and refresh OAuth tokens needed for the above",
            ]}
          />
        </LegalSection>

        <LegalSection id="limited-use" title="4. Limited Use compliance">
          <p>
            Camxora’s use and transfer to any other app of information received from Google APIs
            will adhere to the{" "}
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
          <LegalList
            items={[
              "Google user data is used only to provide or improve user-facing features that are prominent in Camxora’s interface.",
              "We do not sell Google user data.",
              "We do not use Google user data for serving advertisements.",
              "We do not allow humans to read Google user data unless you give us permission for support, it is necessary for security/compliance, or we are required by law — and then only with appropriate access controls.",
            ]}
          />
        </LegalSection>

        <LegalSection id="no-ads" title="5. No advertising use">
          <p>
            No Google user data obtained through Google APIs is used for advertising, including
            personalized, retargeted, or interest-based advertising.
          </p>
        </LegalSection>

        <LegalSection id="sharing" title="6. Sharing and storage">
          <p>
            OAuth tokens and related YouTube connection metadata are stored securely to operate the
            integration. We do not share Google user data with third parties except:
          </p>
          <LegalList
            items={[
              "With Google, as required to call the APIs you authorized",
              "With infrastructure providers under contract that process data solely to host Camxora",
              "When required by law or to protect against abuse and security threats",
            ]}
          />
        </LegalSection>

        <LegalSection id="control" title="7. User control">
          <LegalList
            items={[
              "Disconnect YouTube inside Camxora channel / profile settings when available",
              "Revoke Camxora access in your Google Account → Security → Third-party access",
              "Request deletion of Google-related connection data via our Data Deletion page",
            ]}
          />
          <p>
            Google Account permissions:{" "}
            <a
              className="text-violet-200 hover:text-fuchsia-200"
              href="https://myaccount.google.com/permissions"
              rel="noopener noreferrer"
              target="_blank"
            >
              https://myaccount.google.com/permissions
            </a>
          </p>
        </LegalSection>

        <LegalSection id="contact" title="8. Contact">
          <p>
            Questions about Google data use:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.privacyEmail}`}>
              {COMPANY.privacyEmail}
            </a>
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
