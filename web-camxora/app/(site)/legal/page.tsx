import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Legal",
};

const sections = [
  { id: "terms", label: "Terms of service" },
  { id: "privacy", label: "Privacy" },
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
          <p className="legal-updated">Last updated: October 2026</p>

          <section id="terms">
            <h2>Terms of service</h2>
            <p>
              Camxora is a music creation and listening platform. By creating an
              account or using the service, you agree to use it lawfully, keep your
              credentials secure, and respect the rights of other creators.
            </p>
            <p>
              Credits are prepaid and are consumed when a generation starts. Credit
              packs are valid for 30 days from purchase unless a promotion says
              otherwise. Credits have no cash value and are not transferable.
            </p>
            <p>
              You are responsible for the prompts, lyrics, and other material you
              submit. Do not upload content you do not have the right to use.
            </p>
          </section>

          <section id="privacy">
            <h2>Privacy</h2>
            <p>
              We collect the information needed to run your account: your email,
              display name, authentication data, credit balance, and the content you
              create. We use it to provide the service, secure accounts, and improve
              the product.
            </p>
            <p>
              We do not sell personal information. Payment details are handled by our
              payment provider; Camxora does not store full card numbers.
            </p>
            <p>
              You can request a copy of your account data or ask us to delete it using
              the contact details below.
            </p>
          </section>

          <section id="cookies">
            <h2>Cookies</h2>
            <p>
              Camxora uses essential cookies to keep you signed in and to protect
              forms from abuse. If you choose “remember me”, a preference cookie keeps
              your session available for longer.
            </p>
            <p>
              We do not use advertising cookies. You can clear cookies in your browser
              at any time; doing so will sign you out.
            </p>
          </section>

          <section id="copyright">
            <h2>Copyright</h2>
            <p>
              You keep ownership of the material you create and upload. By publishing
              a track, you give Camxora permission to host, stream, and display it on
              the platform.
            </p>
            <p>
              If you believe content on Camxora infringes your rights, contact
              support@camxora.com with the track link, a description of the work, and
              your contact details. We review complete notices and may remove content
              while a claim is investigated.
            </p>
          </section>

          <section id="acceptable">
            <h2>Acceptable use</h2>
            <p>Do not use Camxora to:</p>
            <ul>
              <li>upload or generate illegal, harassing, or deceptive content;</li>
              <li>impersonate another person or creator;</li>
              <li>scrape, overload, or bypass rate limits on the service;</li>
              <li>resell access without a written agreement;</li>
              <li>infringe copyright, trademark, or other rights.</li>
            </ul>
            <p>
              Accounts that violate these rules may be limited or suspended. Serious
              abuse may be reported to the relevant authorities.
            </p>
          </section>

          <section id="deletion">
            <h2>Data deletion</h2>
            <p>
              You can delete your account from the account page, or email
              support@camxora.com from the address on the account. We remove account
              data and generated content within 30 days, except where we must retain
              records for legal, tax, or fraud-prevention reasons.
            </p>
            <p>
              Deleting your account does not automatically remove tracks you published
              to public playlists. Contact support if you want those removed too.
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
