"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { CodeInput } from "@/components/CodeInput";
import { useAuth } from "@/components/AuthProvider";
import { sendVerificationEmail, verifyEmailCode } from "@/lib/auth-api";

export function VerifyEmailForm() {
  const params = useSearchParams();
  const { user, loading, refresh } = useAuth();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && user?.email_confirmed) {
      window.location.href = "/";
      return;
    }
    if (!email && user?.email) setEmail(user.email);
  }, [email, loading, user]);

  async function sendCode() {
    if (!email.trim()) {
      setError("Enter the email address you signed up with.");
      return;
    }
    setSending(true);
    setError("");
    setMessage("");
    try {
      await sendVerificationEmail(email.trim());
      setMessage("A new 6-digit code has been sent.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send code");
    } finally {
      setSending(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await verifyEmailCode({ email: email.trim(), code: code.trim() });
      await refresh();
      window.location.href = "/";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

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
          <p>One last step before your first song.</p>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>Verify your email.</h1>
          <p className="sub">
            Enter the 6-digit code we sent to your inbox. The code expires in 15
            minutes.
          </p>
          <form className="auth-form" onSubmit={onSubmit}>
            <div className="auth-field">
              <label htmlFor="verify-email">Email</label>
              <input
                id="verify-email"
                className="auth-input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="auth-field">
              <label>Verification code</label>
              <CodeInput value={code} onChange={setCode} ariaLabel="Verification code" />
            </div>
            {message ? (
              <p className="fine" style={{ color: "var(--play)", textAlign: "left" }} role="status">
                {message}
              </p>
            ) : null}
            {error ? (
              <p className="fine" style={{ color: "#f87171", textAlign: "left" }} role="alert">
                {error}
              </p>
            ) : null}
            <button className="auth-btn primary" type="submit" disabled={busy || code.length !== 6}>
              <Icon name="fa-check" /> {busy ? "Verifying…" : "Verify email"}
            </button>
            <button
              className="auth-btn google"
              type="button"
              onClick={sendCode}
              disabled={sending}
            >
              {sending ? "Sending…" : "Resend code"}
            </button>
            <p className="auth-alt">
              <Link href="/login">Back to sign in</Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
