"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { CodeInput } from "@/components/CodeInput";
import { forgotPassword, verifyResetCode } from "@/lib/auth-api";
import { saveResetSession } from "@/lib/reset-session";

export function ConfirmResetCodeForm() {
  const router = useRouter();
  const params = useSearchParams();
  const sent = params.get("sent") === "1";
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState(
    sent ? "If an account exists, a reset code was sent. Check your inbox." : "",
  );
  const [error, setError] = useState("");

  async function resendCode() {
    if (!email.trim()) {
      setError("Enter the email address you requested the reset for.");
      return;
    }
    setSending(true);
    setError("");
    setMessage("");
    try {
      await forgotPassword(email.trim());
      setMessage("A new 6-digit reset code has been sent.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send reset code");
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
      await verifyResetCode({ email: email.trim(), code: code.trim() });
      saveResetSession({ email: email.trim(), code: code.trim() });
      router.push("/reset-password/new");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not confirm reset code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <div className="auth-field">
        <label htmlFor="reset-email">Email</label>
        <input
          id="reset-email"
          className="auth-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </div>
      <div className="auth-field">
        <label>Reset code</label>
        <CodeInput value={code} onChange={setCode} ariaLabel="Reset code" />
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
      <button
        className="auth-btn primary"
        type="submit"
        disabled={busy || code.length !== 6}
      >
        <Icon name="fa-check" /> {busy ? "Confirming…" : "Confirm code"}
      </button>
      <button
        className="auth-btn google"
        type="button"
        onClick={resendCode}
        disabled={sending}
      >
        {sending ? "Sending…" : "Resend code"}
      </button>
      <p className="auth-alt">
        <Link href="/forgot-password">Use a different email</Link>
        {" · "}
        <Link href="/login">Back to sign in</Link>
      </p>
    </form>
  );
}
