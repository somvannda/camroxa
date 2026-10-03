import type { Metadata } from "next";
import PublicLegalShell from "@/components/public-legal-shell";

export const metadata: Metadata = {
  title: "Data Deletion",
  description:
    "How to request deletion of your Camxora Music API account, generated media, and Google Sign-In data.",
};

const EFFECTIVE_DATE = "October 3, 2026";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="text-lg font-bold text-white">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

export default function DataDeletionPage() {
  return (
    <PublicLegalShell title="Data Deletion" lastUpdated={EFFECTIVE_DATE}>
      <p>
        This page explains how to request deletion of data associated with your{" "}
        <strong className="text-white">Camxora Music API</strong> account, including information we receive when you
        sign in with Google. It is provided so users and Google can always find a clear deletion path.
      </p>

      <Section id="request" title="1. How to request deletion">
        <p>
          Email <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a> from the
          address associated with your account, with the subject <em>&ldquo;Data Deletion Request&rdquo;</em>. Include
          the email you signed in with so we can locate and verify your account. We may ask you to confirm control of
          that email before acting.
        </p>
        <p>
          You can also reach us at{" "}
          <a href="mailto:support@camxora.com" className="grad-text font-medium">support@camxora.com</a> if you have
          questions about what will be deleted.
        </p>
      </Section>

      <Section id="what-is-deleted" title="2. What we delete">
        <p>Once your request is verified, we delete or irreversibly anonymize:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>your account record and profile information (including the Google account identifier and profile data we received at sign-in);</li>
          <li>your API keys and their credit balances;</li>
          <li>generated media and related metadata stored for your account (audio, images, and their cover art);</li>
          <li>prompts, lyrics, and other inputs associated with your generations; and</li>
          <li>associated usage logs, except where we must retain limited records for legal, tax, fraud-prevention, or dispute-resolution purposes.</li>
        </ul>
      </Section>

      <Section id="google-data" title="3. Google Sign-In data">
        <p>
          If you signed in with Google, we store only the basic profile identifiers Google provides (your account
          identifier, email, and name/profile picture). To revoke Camxora Music API&rsquo;s access to your Google
          account independently, visit your{" "}
          <a
            href="https://myaccount.google.com/permissions"
            className="grad-text font-medium"
            target="_blank"
            rel="noreferrer"
          >
            Google account permissions
          </a>{" "}
          and remove access. Submitting a deletion request to us also deletes the Google identifier we stored.
        </p>
      </Section>

      <Section id="timeline" title="4. Timing">
        <p>
          We aim to complete verified deletion requests within <strong className="text-white">30 days</strong>. Where a
          longer period is required (for example, to unwind billing or satisfy a legal obligation), we will tell you
          and delete the remaining data once that period ends.
        </p>
      </Section>

      <Section id="contact" title="5. Contact">
        <p>
          Privacy requests: <a href="mailto:privacy@camxora.com" className="grad-text font-medium">privacy@camxora.com</a>
          <br />
          General support:{" "}
          <a href="mailto:support@camxora.com" className="grad-text font-medium">support@camxora.com</a>
        </p>
        <p>
          See also our{" "}
          <a href="/privacy" className="grad-text font-medium">Privacy Policy</a> and{" "}
          <a href="/terms" className="grad-text font-medium">Terms of Service</a>.
        </p>
      </Section>
    </PublicLegalShell>
  );
}
