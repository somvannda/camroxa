import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailForm } from "@/components/VerifyEmailForm";

export const metadata: Metadata = {
  title: "Verify email",
};

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-page">
          <div className="auth-panel">
            <div className="auth-card">
              <h1>Verify your email.</h1>
              <p className="sub">Preparing your verification form…</p>
            </div>
          </div>
        </div>
      }
    >
      <VerifyEmailForm />
    </Suspense>
  );
}
