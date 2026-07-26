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
  title: "Terms & Conditions",
  description:
    "Terms of service for Camxora — accounts, subscriptions, credits, AI content, and YouTube integrations.",
};

export default function TermsPage() {
  return (
    <ContentPageShell
      eyebrow="Legal"
      title="Terms & Conditions"
      description="These Terms govern your use of Camxora’s website, account portal, desktop application, and related services."
      aside={
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Related</div>
          <div className="grid gap-2 text-sm">
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/privacy">
              Privacy Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/acceptable-use">
              Acceptable Use Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Policy
            </Link>
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/contact">
              Contact
            </Link>
          </div>
        </div>
      }
    >
      <LegalMeta effectiveDate={LEGAL_EFFECTIVE_DATE} lastUpdated={LEGAL_LAST_UPDATED} />

      <div className="space-y-12">
        <LegalSection id="introduction" title="1. Introduction">
          <p>
            Welcome to {COMPANY.name}. {COMPANY.product} is an AI-assisted content creation platform
            that helps users produce faceless music and video content for platforms such as YouTube.
            Our services include the marketing website, user account portal, Windows desktop
            application, billing, credits, and related APIs (collectively, the “Services”).
          </p>
          <p>
            By creating an account, downloading the desktop app, connecting third-party services, or
            otherwise using Camxora, you agree to these Terms & Conditions (“Terms”). If you do not
            agree, do not use the Services.
          </p>
        </LegalSection>

        <LegalSection id="eligibility" title="2. Eligibility">
          <LegalList
            items={[
              "You must be at least 18 years old, or the age of majority in your jurisdiction, to create a paid account.",
              "If you are between 13 and 17, you may use Camxora only with verified parental or guardian consent where required by law.",
              "You must have authority to bind yourself (or the organization you represent) to these Terms.",
              "You must comply with applicable local laws and the terms of any third-party platforms you use (including YouTube).",
            ]}
          />
        </LegalSection>

        <LegalSection id="accounts" title="3. User Accounts">
          <p>
            You must provide accurate registration information and keep your credentials secure. You
            are responsible for activity under your account. Notify us promptly at{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.supportEmail}`}>
              {COMPANY.supportEmail}
            </a>{" "}
            if you suspect unauthorized access.
          </p>
          <LegalList
            items={[
              "Do not share passwords or authentication tokens.",
              "Do not create accounts to evade suspensions or billing limits.",
              "We may suspend or terminate accounts for fraud, abuse, non-payment, or Acceptable Use violations.",
              "Channel profiles and connected YouTube accounts remain under your control and responsibility.",
            ]}
          />
        </LegalSection>

        <LegalSection id="subscriptions" title="4. Subscriptions & Billing">
          <p>
            Camxora offers subscription plans with channel capacity, generation allowances, and
            access to the desktop studio. Prices, quotas, and features are shown on the Pricing page
            and in your account portal at purchase time. Sandbox or promotional pricing may differ
            from production pricing.
          </p>
          <LegalList
            items={[
              "Paid plans renew according to the billing term you select (monthly, multi-month, or annual), unless cancelled.",
              "Payments may be processed by third-party providers (including CutLuy / Bakong KHQR where available).",
              "Taxes, bank fees, or payment-provider fees may apply.",
              "Monetization guarantee: if you use Camxora to build and publish dual faceless music channels following our workflow and YouTube policies, and you do not reach YouTube monetization, contact support@camxora.com for a full refund of that plan payment (account, invoice, and channel details required). The refund covers the plan fee only — not AdSense earnings or third-party costs.",
              "Except for that monetization guarantee, or where required by law, fees are otherwise non-refundable once a billing period starts.",
              "You may cancel renewal from your account portal; access continues until the end of the paid period unless earlier terminated for cause.",
            ]}
          />
        </LegalSection>

        <LegalSection id="credits" title="5. Credits System">
          <p>
            Some operations consume plan allowances or wallet credits (for example drafts, music
            packages, images, video export, or merge). Credit rates may change when model costs or
            routing change.
          </p>
          <LegalList
            items={[
              "Credits and allowances are non-transferable between accounts.",
              "Purchased wallet credits are generally non-refundable except where required by law.",
              "Unused plan allowances typically reset at the start of each billing cycle and do not roll over unless we state otherwise.",
              "Video track exports (studio / pipeline and manual) and merges may consume plan video/merge allowance or wallet credits when a job starts. Studio and manual track exports share one track-export pool.",
              "If a track export or merge fails because of a Camxora or technical error and no usable output is produced for that unit, we restore the corresponding allowance or credits for that failed unit.",
              "If you stop or cancel an export yourself: finished tracks keep their charge; the track that was encoding when you stopped keeps its charge; tracks that had not started yet are restored. Stopping a merge after it has started keeps the merge charge.",
              "Abuse of credit systems (automation fraud, shared accounts to evade limits) may result in suspension.",
            ]}
          />
        </LegalSection>

        <LegalSection id="ai-content" title="6. AI-Generated Content">
          <p>
            Camxora uses third-party AI and media providers to help generate lyrics, music, images,
            and related assets. You are responsible for reviewing outputs before publishing.
          </p>
          <LegalList
            items={[
              "You retain rights in your original prompts, uploads, and branding assets, subject to these Terms and third-party licenses.",
              "AI outputs may be similar to content generated for other users; Camxora does not guarantee uniqueness or copyright registration success.",
              "You are solely responsible for content you publish to YouTube or elsewhere, including copyright, trademarks, publicity rights, and platform policies.",
              "Camxora offers a monetization guarantee on paid plans as described on the Pricing page and in Billing & Fees: if you follow the Camxora workflow and YouTube policies and still do not reach YouTube monetization, you may request a full refund of that plan payment. Camxora does not guarantee specific AdSense amounts, view counts, or algorithmic ranking.",
              "Underlying AI/provider terms may further restrict commercial use; you must comply with those terms.",
            ]}
          />
        </LegalSection>

        <LegalSection id="youtube" title="7. YouTube & Google Integration">
          <p>
            Camxora may offer optional Google / YouTube account connection so you can manage channel
            metadata and, when enabled for your account, upload videos you create. Connection is
            voluntary and uses Google OAuth.
          </p>
          <LegalList
            items={[
              "Camxora only requests Google API permissions (scopes) you authorize — currently including YouTube upload, readonly channel information, and related YouTube API access needed to provide requested features.",
              "You can revoke Camxora’s access at any time in your Google Account permissions and/or disconnect inside Camxora.",
              "Camxora is not affiliated with, endorsed by, or sponsored by Google or YouTube.",
              "Your use of YouTube remains subject to the YouTube Terms of Service and YouTube API Services Terms.",
              "You must not use Camxora to violate YouTube policies, spam, or upload infringing content.",
            ]}
          />
          <p>
            See our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/google-api">
              Google API Data Usage & Limited Use
            </Link>{" "}
            page for how Google user data is handled.
          </p>
        </LegalSection>

        <LegalSection id="acceptable-use" title="8. Acceptable Use">
          <p>
            You must follow our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/acceptable-use">
              Acceptable Use Policy
            </Link>
            . Prohibited activities include spam, illegal content, hate speech, malware, credential
            theft, copyright infringement, and API abuse.
          </p>
        </LegalSection>

        <LegalSection id="ip" title="9. Intellectual Property">
          <p>
            Camxora and its licensors own the software, UI, logos, documentation, and website
            design. Except for rights expressly granted, no license is transferred to you.
          </p>
          <p>
            Subject to these Terms and third-party AI/provider terms, you own your prompts, uploaded
            assets, and project outputs you lawfully create with the Services. You grant Camxora a
            limited license to process that content solely to operate and improve the Services (for
            example storage, rendering, support, and security).
          </p>
        </LegalSection>

        <LegalSection id="termination" title="10. Termination">
          <p>
            You may stop using Camxora at any time. We may suspend or terminate access for Terms
            violations, fraud, non-payment, security risk, or legal requirements. Upon termination,
            your right to use the Services ends. Provisions that should survive (including IP,
            disclaimers, and liability limits) will survive.
          </p>
          <p>
            For account and Google-data deletion instructions, see{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/data-deletion">
              Data Deletion
            </Link>
            .
          </p>
        </LegalSection>

        <LegalSection id="disclaimer" title="11. Disclaimer">
          <p>
            THE SERVICES ARE PROVIDED “AS IS” AND “AS AVAILABLE.” TO THE MAXIMUM EXTENT PERMITTED BY
            LAW, CAMXORA DISCLAIMS WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE,
            AND NON-INFRINGEMENT. WE DO NOT WARRANT UNINTERRUPTED UPTIME, ERROR-FREE AI OUTPUTS,
            YOUTUBE APPROVAL, OR MONETIZATION RESULTS.
          </p>
        </LegalSection>

        <LegalSection id="liability" title="12. Limitation of Liability">
          <p>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, CAMXORA AND ITS SUPPLIERS WILL NOT BE LIABLE FOR
            INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR LOST PROFITS,
            REVENUE, OR DATA. OUR AGGREGATE LIABILITY FOR CLAIMS RELATING TO THE SERVICES WILL NOT
            EXCEED THE AMOUNTS YOU PAID TO CAMXORA IN THE THREE (3) MONTHS BEFORE THE CLAIM.
          </p>
        </LegalSection>

        <LegalSection id="changes" title="13. Changes to These Terms">
          <p>
            We may update these Terms from time to time. Material changes will be posted on this
            page with an updated “Last updated” date. Continued use after changes become effective
            constitutes acceptance of the revised Terms.
          </p>
        </LegalSection>

        <LegalSection id="governing-law" title="14. Governing Law">
          <p>
            These Terms are governed by {COMPANY.governingLaw}, without regard to conflict-of-law
            principles. Courts located in {COMPANY.jurisdiction} will have exclusive jurisdiction,
            except where mandatory consumer protections require otherwise.
          </p>
        </LegalSection>

        <LegalSection id="contact" title="15. Contact">
          <p>
            Questions about these Terms:{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.legalEmail}`}>
              {COMPANY.legalEmail}
            </a>{" "}
            or{" "}
            <a className="text-violet-200 hover:text-fuchsia-200" href={`mailto:${COMPANY.supportEmail}`}>
              {COMPANY.supportEmail}
            </a>
            . See also our{" "}
            <Link className="text-violet-200 hover:text-fuchsia-200" href="/contact">
              Contact
            </Link>{" "}
            page.
          </p>
        </LegalSection>
      </div>
    </ContentPageShell>
  );
}
