import type { Metadata } from "next";
import Link from "next/link";
import PublicLegalShell from "@/components/public-legal-shell";

export const metadata: Metadata = {
  title: "Privacy Policy — Camxora Music API",
  description:
    "How Camxora Music API collects, uses, shares, and protects information, including data received through Google Sign-In.",
};

const EFFECTIVE_DATE = "October 4, 2026";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="text-lg font-bold text-white">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <PublicLegalShell title="Privacy Policy" lastUpdated={EFFECTIVE_DATE}>
      <p>
        This Privacy Policy explains how <strong className="text-white">Camxora Music API</strong> (&ldquo;Camxora Music
        API&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;) collects, uses, and protects information when you use our
        website at <a href="https://musicapi.camxora.com" className="grad-text font-medium">musicapi.camxora.com</a>,
        our REST API, and our developer workspace (together, the &ldquo;Service&rdquo;). It also describes how we handle
        information we receive from Google when you sign in with Google.
      </p>

      <div className="rounded-xl border border-[var(--border)] bg-white/[0.02] p-5">
        <h2 className="text-base font-bold text-white">At a glance</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5">
          <li>
            <strong className="text-white">What we collect:</strong> the basic Google profile you share at
            sign-in (account identifier, email, name, and avatar), plus the prompts, lyrics, audio, and API
            activity you submit, your credit and billing records, and basic diagnostics such as IP address and
            error logs.
          </li>
          <li>
            <strong className="text-white">Why we collect it:</strong> to sign you in, create and secure your
            account, generate and deliver music, meter credits and prevent abuse, support you, and keep the
            Service reliable and secure.
          </li>
          <li>
            <strong className="text-white">Who we share it with:</strong> infrastructure, payment, and
            AI/audio model providers that process it on our behalf so the Service can run. We never sell your
            personal information, and we do not use Google user data for advertising or to train AI models.
          </li>
          <li>
            <strong className="text-white">Your controls:</strong> you can revoke our access to your Google
            account, and you can request access to, correction of, export of, or deletion of your data at any
            time — see{" "}
            <Link href="/data-deletion" className="grad-text font-medium">
              Data Deletion
            </Link>
            .
          </li>
        </ul>
      </div>

      <Section id="who-we-are" title="1. Who we are">
        <p>
          Camxora Music API is an AI music generation service operated from the Kingdom of Cambodia. We are the data
          controller responsible for the personal information described in this policy. You can reach us at{" "}
          <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a> for any privacy
          question or request.
        </p>
      </Section>

      <Section id="what-we-collect" title="2. Information we collect">
        <p>
          <strong className="text-white">Account information you provide or that Google provides.</strong> When you
          create an account and sign in with Google, we receive the following basic profile information, which is
          limited to the <code className="rounded bg-white/10 px-1.5 py-0.5">openid</code>,{" "}
          <code className="rounded bg-white/10 px-1.5 py-0.5">email</code>, and{" "}
          <code className="rounded bg-white/10 px-1.5 py-0.5">profile</code> scopes:
        </p>
        <ul className="list-disc space-y-1.5 pl-6">
          <li>your Google account identifier (OpenID <code className="rounded bg-white/10 px-1.5 py-0.5">sub</code> value);</li>
          <li>your email address and whether it is verified;</li>
          <li>your name and profile picture URL, if your Google account exposes them.</li>
        </ul>
        <p>
          <strong className="text-white">Service and usage data.</strong> When you use the Service we collect the
          content you submit (for example prompts, lyrics, and audio you upload), the API requests you make, generated
          results and their metadata, credit balances and transaction records, API key metadata (name, prefix, usage
          counters, optional IP allowlists), and diagnostic data such as IP address, timestamps, and error logs.
        </p>
        <p>
          <strong className="text-white">Payment data.</strong> Credit purchases are processed by third-party payment
          providers. We receive confirmation of payment and a transaction reference; we do not store full card numbers.
        </p>
      </Section>

      <Section id="google-limited-use" title="3. Google user data and Limited Use">
        <p>
          Our use of information received from Google APIs adheres to the{" "}
          <a
            href="https://developers.google.com/terms/api-services-user-data-policy"
            className="grad-text font-medium"
            target="_blank"
            rel="noreferrer"
          >
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements.
        </p>
        <p>
          We do not use Google user data to train, fine-tune, or otherwise develop AI or machine-learning
          models, and we do not use it for advertising.
        </p>
        <p>In particular, with respect to Google user data we:</p>
        <ul className="list-disc space-y-1.5 pl-6">
          <li>use it only to authenticate you, create and secure your account, display your name/avatar, and contact you about the Service;</li>
          <li>do not use it for advertising, and do not sell it or transfer it to third parties for advertising or data-broker purposes;</li>
          <li>do not use it to determine creditworthiness or for lending purposes;</li>
          <li>do not allow humans to read it except where you have given consent, where it is necessary for security or to comply with law, or where the data has been aggregated and anonymized;</li>
          <li>do not request or access Google services beyond the basic sign-in scopes listed in Section 2 — we do not request Gmail, Google Drive, Calendar, YouTube, or any other sensitive or restricted Google scope.</li>
        </ul>
      </Section>

      <Section id="how-we-use" title="4. How we use information">
        <ul className="list-disc space-y-1.5 pl-6">
          <li>to create, authenticate, and administer your account;</li>
          <li>to provide the API and workspace, including generating and delivering music, lyrics, and related assets;</li>
          <li>to meter usage, apply credit balances, and prevent abuse, fraud, and circumvention of spend limits;</li>
          <li>to provide customer support and respond to your requests;</li>
          <li>to maintain the security, integrity, and reliability of the Service and to debug problems;</li>
          <li>to comply with legal obligations and enforce our <Link href="/terms" className="grad-text font-medium">Terms of Service</Link> and Acceptable Use rules.</li>
        </ul>
      </Section>

      <Section id="sharing" title="5. How we share information">
        <p>We do not sell your personal information. We share it only as needed to run the Service, with:</p>
        <ul className="list-disc space-y-1.5 pl-6">
          <li><strong className="text-white">Infrastructure providers</strong> that host our servers, databases, object storage, and CDN;</li>
          <li><strong className="text-white">Sign-in and identity providers</strong>, including Google, to authenticate you;</li>
          <li><strong className="text-white">Payment processors</strong> that handle credit purchases;</li>
          <li><strong className="text-white">AI/audio model providers</strong> that process the prompts and audio needed to generate your requested output;</li>
          <li><strong className="text-white">Authorities</strong> where we are legally required to disclose information, or where disclosure is necessary to protect rights, safety, or the integrity of the Service.</li>
        </ul>
        <p>These providers are bound to use the information only to deliver their services to us.</p>
      </Section>

      <Section id="retention" title="6. Retention and deletion">
        <p>
          We keep personal information for as long as your account is active and for a reasonable period afterwards to
          meet legal, accounting, security, and backup requirements. Generated media (audio, images, and their
          metadata) is stored for as long as your account is active, so you can download it at any time. You may
          request deletion of your account and
          associated personal data at any time by emailing{" "}
          <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a>; we will
          delete or anonymize the data unless we are required to keep it by law.
        </p>
        <p>In practice, we retain data for the following periods:</p>
        <ul className="list-disc space-y-1.5 pl-6">
          <li>
            <strong className="text-white">Account, profile, and Google identifiers</strong> — while your
            account is active; deleted or anonymized within 30 days of a verified account-deletion request.
          </li>
          <li>
            <strong className="text-white">Generated media and inputs</strong> (prompts, lyrics, audio) —
            until you delete them or your account; removed within 30 days of account deletion.
          </li>
          <li>
            <strong className="text-white">Usage logs and diagnostics</strong> — up to 12 months, then
            deleted or aggregated.
          </li>
          <li>
            <strong className="text-white">Billing and tax records</strong> — for as long as the law requires
            after a purchase, even if you close your account.
          </li>
          <li>
            <strong className="text-white">Backups</strong> — encrypted backups are cycled out within 90 days.
          </li>
        </ul>
      </Section>

      <Section id="cookies" title="7. Cookies and sessions">
        <p>
          We use a first-party session cookie (and, in the workspace, local storage) to keep you signed in and to
          protect requests against cross-site request forgery. These are strictly necessary for the Service to
          function. We do not use third-party advertising cookies or cross-site tracking.
        </p>
      </Section>

      <Section id="security" title="8. Security">
        <p>
          We protect information with HTTPS/TLS in transit, encryption of sensitive credentials at rest, scoped API
          keys, access controls, and operational monitoring. No system is perfectly secure; if we become aware of a
          breach affecting your personal data, we will notify you and the relevant authorities as required by law.
        </p>
      </Section>

      <Section id="rights" title="9. Your rights and choices">
        <p>
          Depending on where you live, you may have the right to access, correct, export, or delete your personal
          information, and to object to or restrict certain processing. You can also revoke Camxora Music API&rsquo;s
          access to your Google account at any time from your{" "}
          <a href="https://myaccount.google.com/permissions" className="grad-text font-medium" target="_blank" rel="noreferrer">
            Google account permissions
          </a>
          , and you can manage your profile and API keys from the workspace. To exercise any right, contact{" "}
          <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a>.
        </p>
      </Section>

      <Section id="children" title="10. Children">
        <p>
          The Service is not directed to children under 16, and we do not knowingly collect personal information from
          them. If you believe a child has provided us with personal information, contact us and we will delete it.
        </p>
      </Section>

      <Section id="international" title="11. International transfers">
        <p>
          We may process and store information in countries other than your own, including where our providers operate.
          Where required, we use appropriate safeguards for these transfers, such as standard contractual clauses.
        </p>
      </Section>

      <Section id="content-policy" title="12. Responsible AI and prohibited content">
        <p>
          We prohibit the use of the Service to create or distribute unlawful content, and in particular we do not
          permit the generation of AI &ldquo;non-consensual intimate imagery&rdquo; (AI NCII) — that is, realistic
          sexual or intimate depictions of a real, identifiable person created or shared without that person&rsquo;s
          consent — nor any child sexual abuse material, sexual content involving minors, or deepfakes used to harass,
          sexualize, defame, or impersonate a real person. Users must not upload or generate content that infringes
          others&rsquo; rights, including voice or likeness rights, without authorization. We may remove content and
          suspend or terminate accounts that violate this section. See our{" "}
          <Link href="/terms" className="grad-text font-medium">Terms of Service</Link> for the full acceptable-use
          rules.
        </p>
      </Section>

      <Section id="changes" title="13. Changes to this policy">
        <p>
          We may update this policy from time to time. When we make material changes we will update the
          &ldquo;Last updated&rdquo; date above and, where appropriate, provide additional notice. Your continued use
          of the Service after an update means you accept the revised policy.
        </p>
      </Section>

      <Section id="contact" title="14. Contact us">
        <p>
          Questions or requests about this policy or your data can be sent to{" "}
          <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a> or{" "}
          <a href="mailto:support@camxora.com" className="grad-text font-medium">support@camxora.com</a>.
        </p>
      </Section>
    </PublicLegalShell>
  );
}
