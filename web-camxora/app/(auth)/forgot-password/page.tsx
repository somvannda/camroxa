import type { Metadata } from "next";
import Link from "next/link";
import { ForgotPasswordForm } from "@/components/ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Forgot password",
};

export default function ForgotPasswordPage() {
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
          <p>We’ll send a six-digit reset code to your email.</p>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>Forgot your password?</h1>
          <p className="sub">
            Enter your email and we’ll send a reset code. The code expires in 15
            minutes.
          </p>
          <ForgotPasswordForm />
        </div>
      </div>
    </div>
  );
}
