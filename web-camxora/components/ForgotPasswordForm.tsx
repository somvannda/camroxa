"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { forgotPassword } from "@/lib/auth-api";

export function ForgotPasswordForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await forgotPassword(email.trim());
      setMessage(result.message);
      const target = `/reset-password?email=${encodeURIComponent(email.trim())}&sent=1`;
      router.push(target);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send reset code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <div className="auth-field">
        <label htmlFor="forgot-email">Email</label>
        <input
          id="forgot-email"
          className="auth-input"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
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
      <button className="auth-btn primary" type="submit" disabled={busy}>
        <Icon name="fa-envelope" /> {busy ? "Sending…" : "Send reset code"}
      </button>
      <p className="auth-alt">
        <Link href={`/reset-password?email=${encodeURIComponent(email)}`}>
          I already have a code
        </Link>
        {" · "}
        <Link href="/login">Back to sign in</Link>
      </p>
    </form>
  );
}
