import type { Metadata } from "next";
import Link from "next/link";
import { ResetPasswordForm } from "@/components/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Set a new password",
};

export default function SetNewPasswordPage() {
  return (
    <div className="auth-page">
      <div className="auth-visual">
        <img src="/hero.png" alt="Singer with headphones in neon light" />
        <div className="quote">
          <div className="eyebrow">Camxora</div>
          <h2>
            Create. Discover.
            <br />
            Enjoy AI Music.
          </h2>
          <p>Almost back to the music.</p>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>Set a new password.</h1>
          <p className="sub">
            Choose a strong password for your Camxora account.
          </p>
          <ResetPasswordForm />
        </div>
      </div>
    </div>
  );
}
