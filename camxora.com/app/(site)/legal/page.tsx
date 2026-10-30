import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Legal",
};

const sections = [
  { id: "terms", label: "Terms of service" },
  { id: "privacy", label: "Privacy" },
  { id: "google-api", label: "Google API policy" },
  { id: "cookies", label: "Cookies" },
  { id: "copyright", label: "Copyright" },
  { id: "acceptable", label: "Acceptable use" },
  { id: "deletion", label: "Data deletion" },
];

export default function LegalPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Legal</div>
          <h1>Clear terms. No surprises.</h1>
          <p>
            The rules for using Camxora, how we handle your data, and how to reach us
            about content or account issues.
          </p>
        </div>
      </div>

      <div className="legal-layout">
        <nav className="legal-nav" aria-label="Legal sections">
          {sections.map((section) => (
            <a key={section.id} href={`#${section.id}`}>{section.label}</a>
          ))}
        </nav>

        <article className="legal-content panel">
          <p className="legal-updated">Effective July 19, 2026 · Last updated July 19, 2026</p>

          <section id="terms">
            <h2>Terms &amp; Conditions</h2>
            <p>
              These Terms govern your use of Camxora’s website, account portal,
              desktop application, and related services. By creating an account,
              downloading the desktop app, connecting third-party services, or
              otherwise using Camxora, you agree to these Terms.
            </p>
            <h3>1. Introduction</h3>
            <p>
              Camxora is an AI-assisted content creation platform that helps users
              produce faceless music and video content for platforms such as YouTube.
              Our services include the marketing website, user account portal,
              desktop application, billing, credits, and related APIs.
            </p>
            <h3>2. Eligibility</h3>
            <ul>
              <li>You must be at least 18, or the age of majority in your jurisdiction, to create a paid account.</li>
              <li>If you are between 13 and 17, you may use Camxora only with verified parental or guardian consent where required by law.</li>
              <li>You must have authority to bind yourself or the organization you represent to these Terms.</li>
              <li>You must comply with applicable local laws and third-party platform terms, including YouTube.</li>
            </ul>
            <h3>3. User accounts</h3>
            <p>
              Provide accurate registration information and keep your credentials
              secure. You are responsible for activity under your account. Notify us
              promptly at support@camxora.com if you suspect unauthorized access.
              Do not share passwords or tokens, create accounts to evade suspensions
              or billing limits, or use accounts for fraud or abuse. We may suspend
              accounts for violations of these Terms or our Acceptable Use Policy.
            </p>
            <h3>4. Credit packs &amp; billing</h3>
            <p>
              Camxora is credits-only. There are no plans, subscriptions, quotas,
              or renewals. You buy credit packs when you need them; each pack is
              valid for 30 days from purchase. Free accounts receive a monthly
              credit allowance that resets each month and does not accumulate.
            </p>
            <p>
              Prices and pack sizes are shown on the Pricing page at purchase time.
              Payments may be processed by third-party providers, including CutLuy /
              Bakong KHQR or ChmabaPay where available. Except where required by law,
              purchased credits are non-refundable once used.
            </p>
            <h3>5. Credits system</h3>
            <ul>
              <li>Credits are non-transferable between accounts.</li>
              <li>Purchased wallet credits are generally non-refundable except where required by law.</li>
              <li>Credit packs are valid for 30 days from purchase unless a promotion states otherwise. Buying another pack resets the live balance’s 30-day clock.</li>
              <li>Free monthly credits reset each month and do not accumulate; unused free credits expire.</li>
              <li>All credits expire within 30 days.</li>
              <li>If a generation fails because of a Camxora or technical error and no usable output is produced, we restore the corresponding credits for that failed unit.</li>
              <li>Abuse of credit systems, automation fraud, or shared accounts to evade limits may result in suspension.</li>
            </ul>
            <h3>6. AI-generated content</h3>
            <p>
              Camxora uses third-party AI and media providers to generate lyrics,
              music, images, and related assets. You are responsible for reviewing
              outputs before publishing. You retain rights in your original prompts,
              uploads, and branding assets, subject to these Terms and third-party
              licenses. AI outputs may be similar to content generated for other users;
              Camxora does not guarantee uniqueness or copyright registration success.
            </p>
            <h3>7. YouTube &amp; Google integration</h3>
            <p>
              Camxora may offer optional Google / YouTube connection so you can manage
              channel metadata and, when enabled, upload videos you create. Connection
              is voluntary and uses Google OAuth. Camxora only requests permissions
              you authorize and is not affiliated with, endorsed by, or sponsored by
              Google or YouTube. Your use of YouTube remains subject to YouTube’s
              terms and policies.
            </p>
            <h3>8. Acceptable use</h3>
            <p>
              You must follow our Acceptable Use Policy. Prohibited activities include
              spam, illegal content, hate speech, malware, credential theft, copyright
              infringement, and API abuse.
            </p>
            <h3>9. Intellectual property</h3>
            <p>
              Camxora and its licensors own the software, UI, logos, documentation, and
              website design. Subject to these Terms and third-party provider terms,
              you own your prompts, uploaded assets, and project outputs you lawfully
              create with the Services. You grant Camxora a limited license to process
              that content solely to operate and improve the Services.
            </p>
            <h3>10. Termination</h3>
            <p>
              You may stop using Camxora at any time. We may suspend or terminate
              access for Terms violations, fraud, non-payment, security risk, or legal
              requirements. Provisions that should survive termination, including IP,
              disclaimers, and liability limits, will survive.
            </p>
            <h3>11. Disclaimer</h3>
            <p>
              THE SERVICES ARE PROVIDED “AS IS” AND “AS AVAILABLE.” TO THE MAXIMUM
              EXTENT PERMITTED BY LAW, CAMXORA DISCLAIMS WARRANTIES OF
              MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
              NON-INFRINGEMENT. WE DO NOT WARRANT UNINTERRUPTED UPTIME, ERROR-FREE AI
              OUTPUTS, YOUTUBE APPROVAL, OR MONETIZATION RESULTS.
            </p>
            <h3>12. Limitation of liability</h3>
            <p>
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, CAMXORA AND ITS SUPPLIERS WILL
              NOT BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR
              PUNITIVE DAMAGES, OR LOST PROFITS, REVENUE, OR DATA. OUR AGGREGATE
              LIABILITY FOR CLAIMS RELATING TO THE SERVICES WILL NOT EXCEED THE
              AMOUNTS YOU PAID TO CAMXORA IN THE THREE MONTHS BEFORE THE CLAIM.
            </p>
            <h3>13. Changes &amp; governing law</h3>
            <p>
              We may update these Terms from time to time. Material changes will be
              posted on this page with an updated date. Continued use after changes
              become effective constitutes acceptance. These Terms are governed by the
              laws of the Kingdom of Cambodia, without regard to conflict-of-law
              principles.
            </p>
            <h3>14. Contact</h3>
            <p>
              Questions about these Terms: legal@camxora.com or support@camxora.com.
            </p>
          </section>

          <section id="privacy">
            <h2>Privacy Policy</h2>
            <p>
              This Privacy Policy explains what information Camxora collects, how we
              use it, and the choices you have, including Google user data used for
              YouTube features.
            </p>
            <h3>Information we collect</h3>
            <ul>
              <li><b>Account:</b> email, display name, password hashes or auth tokens, preferences, and channel profiles.</li>
              <li><b>Usage &amp; diagnostics:</b> app and API logs, feature usage, error reports, device/OS information, IP address, and approximate location.</li>
              <li><b>Billing:</b> plan selection, invoices, payment status, and records from payment processors. We do not store full card numbers.</li>
              <li><b>Content:</b> lyrics, prompts, music and image assets, video templates, export paths, progress metadata, and project history.</li>
              <li><b>Google / YouTube:</b> only when you voluntarily connect an account. This may include OAuth tokens, channel identifiers, basic metadata, and information required to upload or manage videos you request.</li>
            </ul>
            <h3>How we use data</h3>
            <p>
              We use data to authenticate users, provide generation and storage,
              connect channels and perform requested uploads, process credits and
              support requests, monitor reliability, prevent abuse, improve the
              product, and comply with legal obligations.
            </p>
            <h3>Google user data</h3>
            <p>
              We do not sell Google user data, use it for advertising or personalized
              ads, use it for creditworthiness decisions, or access data beyond the
              scopes you authorize. We do not use Google Workspace APIs to train
              generalized AI/ML models in a way that violates Google’s Limited Use
              requirements. Camxora’s use and transfer of information received from
              Google APIs adheres to the Google API Services User Data Policy,
              including the Limited Use requirements.
            </p>
            <h3>Data sharing</h3>
            <p>
              We share data only as needed with cloud hosting, storage, and email
              providers; AI / media generation providers; payment processors; Google
              when you authorize access; and professional advisors or authorities
              when required by law or to protect rights and safety. We do not sell
              personal data to advertisers.
            </p>
            <h3>Retention, security, and your rights</h3>
            <p>
              We retain account, billing, and content data while your account is
              active and as needed to provide the Services. We may retain limited
              records after closure for legal, tax, fraud-prevention, or
              dispute-resolution purposes. We use HTTPS/TLS, access controls, hashed
              passwords, token-based authentication, and operational monitoring. No
              method is 100% secure.
            </p>
            <p>
              Depending on your location, you may have rights to access, correct,
              delete, export, or restrict processing of your data, and to withdraw
              consent for optional processing. Email privacy@camxora.com or follow the
              Data Deletion steps. You can also revoke Google access in your Google
              Account settings.
            </p>
            <h3>Children and international transfers</h3>
            <p>
              Camxora is not directed to children under 13. We do not knowingly collect
              personal information from children under 13. We may process data on
              servers outside your country and use appropriate safeguards where
              required. Camxora is operated with a primary business focus in the
              Kingdom of Cambodia.
            </p>
            <h3>Contact</h3>
            <p>Privacy requests: privacy@camxora.com · General support: support@camxora.com</p>
          </section>

          <section id="google-api">
            <h2>Google API Data Policy</h2>
            <p>
              Camxora uses Google OAuth only when you choose to connect a Google
              account for YouTube features. We request the minimum scopes needed for
              the features you enable:
            </p>
            <ul>
              <li><code>youtube.upload</code> — upload videos you request.</li>
              <li><code>youtube.readonly</code> — read channel information needed for connection and status.</li>
              <li><code>youtube.force-ssl</code> — authorized YouTube API operations over HTTPS.</li>
            </ul>
            <p>
              We do not sell Google user data, use it for advertising, or transfer it
              except as necessary to operate requested features, with contracted
              subprocessors, or as required by law. You can revoke access at any time
              at myaccount.google.com/permissions or by disconnecting the channel in
              Camxora.
            </p>
            <p>
              Camxora’s use and transfer of information received from Google APIs
              adheres to the Google API Services User Data Policy, including the
              Limited Use requirements.
            </p>
          </section>

          <section id="cookies">
            <h2>Cookie Policy</h2>
            <p>
              Cookies are small text files stored on your device. We also use local
              storage and session tokens for authentication and preferences.
            </p>
            <ul>
              <li><b>Essential:</b> required for sign-in, session security, CSRF protection, and core site functionality.</li>
              <li><b>Preferences:</b> remember UI choices such as locale, theme, or dismissed notices.</li>
              <li><b>Analytics:</b> help us understand aggregate traffic and improve the website where enabled.</li>
            </ul>
            <p>
              You can block or delete cookies in your browser settings. Blocking
              essential cookies may prevent login or checkout from working. The
              desktop app primarily uses local app storage rather than website
              cookies. Questions: privacy@camxora.com.
            </p>
          </section>

          <section id="copyright">
            <h2>Copyright Policy</h2>
            <p>
              Users may not upload, generate for distribution, or publish content
              through Camxora that infringes copyrights, trademarks, or other rights.
              Users are responsible for content they create and publish to YouTube or
              other platforms.
            </p>
            <h3>How to report infringement</h3>
            <p>Send a notice to legal@camxora.com including:</p>
            <ul>
              <li>Your contact name, address, email, and phone number.</li>
              <li>Description of the copyrighted work claimed to be infringed.</li>
              <li>URL, account email, or other information sufficient to locate the material.</li>
              <li>A statement that you have a good-faith belief the use is not authorized.</li>
              <li>A statement under penalty of perjury that the information is accurate and you are authorized to act.</li>
              <li>Your physical or electronic signature.</li>
            </ul>
            <p>
              We review complete notices in good faith, remove or disable access where
              appropriate, notify the affected user when feasible, and terminate
              repeat infringers in appropriate circumstances. If you believe material
              was removed in error, email legal@camxora.com with a counter-notice
              including your contact information, identification of the removed
              material, a good-faith statement, consent to jurisdiction in the Kingdom
              of Cambodia, and your signature.
            </p>
          </section>

          <section id="acceptable">
            <h2>Acceptable Use Policy</h2>
            <p>
              Use Camxora to create, organize, export, and (when enabled) upload music
              and video content you have rights to use, in compliance with these rules
              and third-party platform terms, including YouTube.
            </p>
            <h3>Prohibited activities</h3>
            <ul>
              <li>Illegal content or activity under applicable law.</li>
              <li>Copyright, trademark, or publicity-right infringement.</li>
              <li>Hate speech, harassment, exploitation, or content that exploits minors.</li>
              <li>Spam, scams, phishing, or deceptive practices.</li>
              <li>Malware, credential theft, or attempts to compromise Camxora or other users.</li>
              <li>Circumventing plan limits, billing, credits, or security controls.</li>
              <li>Automated abuse of APIs, generation endpoints, or Google/YouTube integrations.</li>
              <li>Impersonation of Camxora, Google, YouTube, or other people or entities.</li>
              <li>Using connected Google accounts you do not own or are not authorized to manage.</li>
              <li>Uploading content that violates YouTube Community Guidelines or YouTube Terms of Service.</li>
            </ul>
            <h3>AI transparency &amp; review</h3>
            <p>
              AI outputs can be inaccurate, biased, or similar to other outputs.
              Review before publishing. You are responsible for ensuring published
              content complies with platform rules and laws. Do not use Camxora to
              generate prohibited content at scale.
            </p>
            <h3>Enforcement</h3>
            <p>
              We may investigate suspected violations, remove content, suspend
              features (including YouTube upload), or terminate accounts. Report
              concerns to support@camxora.com.
            </p>
          </section>

          <section id="deletion">
            <h2>Data Deletion Instructions</h2>
            <p>
              You can delete Camxora account data and disconnect Google integrations
              at any time.
            </p>
            <h3>Disconnect Google / YouTube</h3>
            <ul>
              <li>In Camxora, open your channel / YouTube connection settings and disconnect the Google account.</li>
              <li>In Google, visit Google Account → Security → Third-party access with account access → remove Camxora.</li>
              <li>Direct link: myaccount.google.com/permissions.</li>
            </ul>
            <p>
              Disconnecting stops new API access. Stored OAuth tokens associated with
              that connection are revoked or deleted as part of disconnection /
              deletion processing.
            </p>
            <h3>Delete your Camxora account</h3>
            <p>
              Email privacy@camxora.com from the same email address used for your
              account. Subject line: Account deletion request. Include your account
              email and any channel profile names you want confirmed deleted. Use
              in-product account deletion controls when available, then confirm by
              email if prompted.
            </p>
            <h3>What is deleted</h3>
            <ul>
              <li>Account profile and login credentials.</li>
              <li>Channel profiles and app preferences.</li>
              <li>Stored Google OAuth tokens and YouTube connection records.</li>
              <li>Project metadata and generation history associated with your account, subject to technical backups rotating out.</li>
              <li>Optional diagnostic logs tied to your user ID where feasible.</li>
            </ul>
            <h3>What may remain</h3>
            <ul>
              <li>Billing and tax records required by law.</li>
              <li>Fraud-prevention and security logs retained for a limited period.</li>
              <li>Anonymized or aggregated analytics that no longer identify you.</li>
              <li>Content you already published to YouTube or other platforms, controlled by those platforms.</li>
            </ul>
            <p>
              We aim to process deletion requests within 30 days. Google access
              revocation through Google’s permissions page is typically immediate.
              Deletion and privacy requests: privacy@camxora.com · Support:
              support@camxora.com.
            </p>
          </section>

          <div className="legal-contact">
            <h2>Questions?</h2>
            <p>
              Email <a href="mailto:support@camxora.com">support@camxora.com</a> or
              visit the <Link href="/contact">contact page</Link>.
            </p>
          </div>
        </article>
      </div>
    </div>
  );
}
