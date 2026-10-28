import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ConfirmResetCodeForm } from "@/components/ConfirmResetCodeForm";

export const metadata: Metadata = {
  title: "Confirm reset code",
};

export default function ConfirmResetCodePage() {
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
          <p>One quick check before you choose a new password.</p>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>Confirm your reset code.</h1>
          <p className="sub">
            Enter the 6-digit code we sent to your email. The code expires in 15
            minutes.
          </p>
          <Suspense fallback={<p className="sub">Preparing reset form…</p>}>
            <ConfirmResetCodeForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
