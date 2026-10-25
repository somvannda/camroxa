import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Help Center",
};

const topics = [
  {
    icon: "fa-credit-card",
    title: "Credits & billing",
    body: "Pack validity, balances, receipts, and checkout questions.",
    href: "/pricing",
  },
  {
    icon: "fa-microphone",
    title: "Creating music",
    body: "Prompts, models, generation status, and failed jobs.",
    href: "/create",
  },
  {
    icon: "fa-key",
    title: "Account & access",
    body: "Sign-in, email verification, password reset, and API keys.",
    href: "/account",
  },
  {
    icon: "fa-file-shield",
    title: "Privacy & legal",
    body: "Data deletion, copyright reports, terms, and cookies.",
    href: "/legal",
  },
];

export default function SupportPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Support</div>
          <h1>Help Center.</h1>
          <p>Find the right starting point, then contact us if you need a human.</p>
        </div>
        <Link className="btn btn-primary" href="/contact">
          <Icon name="fa-envelope" /> Contact support
        </Link>
      </div>

      <div className="info-grid">
        {topics.map((topic) => (
          <Link className="info-card panel" href={topic.href} key={topic.title}>
            <span className="info-icon"><Icon name={topic.icon} /></span>
            <h2>{topic.title}</h2>
            <p>{topic.body}</p>
            <b>Open guide <Icon name="fa-arrow-right" /></b>
          </Link>
        ))}
      </div>

      <section className="panel contact-note">
        <h2>Still stuck?</h2>
        <p>
          Email <a href="mailto:support@camxora.com">support@camxora.com</a> with your
          account email, a description of the issue, and any track or payment
          reference. We usually reply within two business days.
        </p>
      </section>
    </div>
  );
}
