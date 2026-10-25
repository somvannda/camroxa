import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Google API Policy",
};

export default function GoogleApiPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Legal</div>
          <h1>Google API data usage.</h1>
          <p>
            How Camxora uses information received from Google APIs when you connect
            YouTube, written for transparency during Google OAuth verification.
          </p>
        </div>
      </div>

      <div className="legal-layout">
        <nav className="legal-nav" aria-label="Related legal pages">
          <Link href="/privacy">Privacy Policy</Link>
          <Link href="/data-deletion">Data Deletion</Link>
          <Link href="/terms">Terms &amp; Conditions</Link>
          <Link href="/contact">Contact</Link>
        </nav>

        <article className="legal-content panel">
          <p className="legal-updated">Effective July 19, 2026 · Last updated July 19, 2026</p>

          <section>
            <h2>1. Overview</h2>
            <p>
              Camxora integrates with Google OAuth and the YouTube Data API so users
              can optionally connect YouTube channels and upload videos they create in
              Camxora. Connection is voluntary. Camxora is not affiliated with Google
              or YouTube.
            </p>
          </section>

          <section>
            <h2>2. Scopes we request</h2>
            <p>Depending on enabled features, Camxora may request:</p>
            <ul>
              <li><code>youtube.upload</code> — to upload videos you explicitly request.</li>
              <li><code>youtube.readonly</code> — to read channel information needed to identify and manage connected channels.</li>
              <li><code>youtube.force-ssl</code> — to call YouTube APIs securely for authorized operations.</li>
            </ul>
            <p>
              We do not request Google scopes unrelated to providing these YouTube
              features. If scopes change, we will update this page and the Google
              consent screen accordingly.
            </p>
          </section>

          <section>
            <h2>3. How Google API data is used</h2>
            <p>Camxora uses Google API data only to:</p>
            <ul>
              <li>Authenticate your Google / YouTube connection.</li>
              <li>Retrieve basic channel information required for linked channel profiles.</li>
              <li>Upload videos you create and choose to publish through Camxora, when the upload feature is available for your account.</li>
              <li>Show upload status and related progress inside Camxora.</li>
              <li>Maintain and refresh OAuth tokens needed for the above.</li>
            </ul>
          </section>

          <section>
            <h2>4. Limited Use compliance</h2>
            <p>
              Camxora’s use and transfer to any other app of information received from
              Google APIs will adhere to the{" "}
              <a
                href="https://developers.google.com/terms/api-services-user-data-policy"
                target="_blank"
                rel="noreferrer"
              >
                Google API Services User Data Policy
              </a>
              , including the Limited Use requirements.
            </p>
            <ul>
              <li>Google user data is used only to provide or improve user-facing features that are prominent in Camxora’s interface.</li>
              <li>We do not sell Google user data.</li>
              <li>We do not use Google user data for serving advertisements.</li>
              <li>We do not allow humans to read Google user data unless you give us permission for support, it is necessary for security/compliance, or we are required by law — and then only with appropriate access controls.</li>
            </ul>
          </section>

          <section>
            <h2>5. No advertising use</h2>
            <p>
              No Google user data obtained through Google APIs is used for advertising,
              including personalized, retargeted, or interest-based advertising.
            </p>
          </section>

          <section>
            <h2>6. Sharing and storage</h2>
            <p>
              OAuth tokens and related YouTube connection metadata are stored securely
              to operate the integration. We do not share Google user data with third
              parties except:
            </p>
            <ul>
              <li>With Google, as required to call the APIs you authorized.</li>
              <li>With infrastructure providers under contract that process data solely to host Camxora.</li>
              <li>When required by law or to protect against abuse and security threats.</li>
            </ul>
          </section>

          <section>
            <h2>7. User control</h2>
            <ul>
              <li>Disconnect YouTube inside Camxora channel / profile settings when available.</li>
              <li>Revoke Camxora access in your Google Account → Security → Third-party access.</li>
              <li>Request deletion of Google-related connection data via our Data Deletion page.</li>
            </ul>
            <p>
              Google Account permissions:{" "}
              <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer">
                myaccount.google.com/permissions
              </a>
            </p>
          </section>

          <section>
            <h2>8. Contact</h2>
            <p>
              Questions about Google data use:{" "}
              <a href="mailto:privacy@camxora.com">privacy@camxora.com</a>.
            </p>
          </section>
        </article>
      </div>
    </div>
  );
}
