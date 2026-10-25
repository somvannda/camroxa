import type { Metadata } from "next";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Contact",
};

const contacts = [
  {
    icon: "fa-life-ring",
    title: "Support",
    body: "Account, credits, generation, or playback issues.",
    email: "support@camxora.com",
  },
  {
    icon: "fa-scale-balanced",
    title: "Legal",
    body: "Copyright notices, terms questions, and data requests.",
    email: "legal@camxora.com",
  },
  {
    icon: "fa-shield-halved",
    title: "Privacy",
    body: "Access, correction, export, or deletion of your data.",
    email: "privacy@camxora.com",
  },
];

export default function ContactPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Contact</div>
          <h1>Talk to a human.</h1>
          <p>
            Pick the right inbox and we’ll get back to you. Include your account
            email and any relevant track or payment reference.
          </p>
        </div>
      </div>

      <div className="info-grid">
        {contacts.map((item) => (
          <a className="info-card panel" href={`mailto:${item.email}`} key={item.title}>
            <span className="info-icon"><Icon name={item.icon} /></span>
            <h2>{item.title}</h2>
            <p>{item.body}</p>
            <b>{item.email}</b>
          </a>
        ))}
      </div>

      <section className="panel contact-note">
        <h2>Before you write</h2>
        <p>
          For account access issues, email us from the address on the account. For
          payment questions, include the payment reference from your receipt. We
          usually reply within two business days.
        </p>
        <p>
          For copyright reports, see the{" "}
          <a href="/legal#copyright">copyright section</a> and include the required
          details.
        </p>
      </section>
    </div>
  );
}
