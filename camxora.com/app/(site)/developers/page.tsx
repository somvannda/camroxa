import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Music API",
};

const features = [
  {
    title: "Generate songs",
    body: "Send a prompt, style, and model. Get a finished track back with vocals and cover art.",
  },
  {
    title: "Credit-based billing",
    body: "Every request is metered against a single credit wallet. No separate plans per endpoint.",
  },
  {
    title: "Webhooks",
    body: "Subscribe to generation events instead of polling long-running jobs.",
  },
  {
    title: "OpenAPI",
    body: "Typed request and response schemas, ready for generated clients and SDKs.",
  },
];

export default function DevelopersPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Developers</div>
          <h1>Music API.</h1>
          <p>
            Build Camxora generation into your own product. One API key, one credit
            balance, and the same models behind the studio.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn btn-primary" href="https://musicapi.camxora.com/docs" target="_blank" rel="noreferrer">
            <Icon name="fa-book-open" /> Read the docs
          </a>
          <Link className="btn btn-ghost" href="/account">
            Get an API key
          </Link>
        </div>
      </div>

      <div className="dev-grid">
        <section className="dev-copy">
          <div className="eyebrow">Quick start</div>
          <h2>One request. A finished track.</h2>
          <p>
            Authenticate with a bearer key, send a prompt, and poll or subscribe for
            the result. Credits are charged only when a generation starts.
          </p>
          <ul>
            <li><span>Base URL</span><span>https://musicapi.camxora.com</span></li>
            <li><span>Auth</span><span>Bearer API key</span></li>
            <li><span>Billing</span><span>Credits per generation</span></li>
            <li><span>Events</span><span>Webhook or poll</span></li>
          </ul>
        </section>

        <pre className="code-block"><code>{`curl -X POST https://musicapi.camxora.com/api/v1/generate \\
  -H "Authorization: Bearer $CAMXORA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "A late-night Khmer pop song about the Bassac river",
    "style": "khmer pop, dreamy, 90 bpm",
    "model": "v6"
  }'`}</code></pre>
      </div>

      <div className="dev-features">
        {features.map((feature) => (
          <article className="dev-feature" key={feature.title}>
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </article>
        ))}
      </div>

      <div className="status-row">
        <div className="status"><b>REST</b><span>JSON over HTTPS</span></div>
        <div className="status"><b>OpenAPI</b><span>Typed schemas</span></div>
        <div className="status"><b>Credits</b><span>One shared wallet</span></div>
      </div>

      <section className="download-panel">
        <div>
          <h2>Ship your first generation.</h2>
          <p>
            Create a key from your account, then follow the quick-start guide. The
            API uses the same credit balance as Camxora Studio.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn btn-primary" href="https://musicapi.camxora.com/docs" target="_blank" rel="noreferrer">
            Open API docs
          </a>
          <Link className="btn btn-ghost" href="/account">
            Account &amp; keys
          </Link>
        </div>
      </section>
    </div>
  );
}
