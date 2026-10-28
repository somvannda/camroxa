"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { resetPassword } from "@/lib/auth-api";
import {
  clearResetSession,
  readResetSession,
  type ResetSession,
} from "@/lib/reset-session";

export function ResetPasswordForm() {
  const router = useRouter();
  const [session, setSession] = useState<ResetSession | null>(null);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const saved = readResetSession();
    if (!saved) {
      router.replace("/reset-password");
      return;
    }
    setSession(saved);
    setReady(true);
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setError("");
    setMessage("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const result = await resetPassword({
        email: session.email,
        code: session.code,
        new_password: password,
      });
      clearResetSession();
      setMessage(result.message);
      window.setTimeout(() => {
        window.location.href = "/login";
      }, 1200);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Password reset failed");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || !session) {
    return (
      <p className="fine" style={{ textAlign: "left" }} role="status">
        Preparing password setup…
      </p>
    );
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <div className="auth-field">
        <label htmlFor="reset-email">Email</label>
        <input
          id="reset-email"
          className="auth-input"
          type="email"
          value={session.email}
          readOnly
        />
      </div>
      <div className="auth-field">
        <label htmlFor="new-password">New password</label>
        <input
          id="new-password"
          className="auth-input"
          type="password"
          autoComplete="new-password"
          placeholder="New password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
        />
      </div>
      <div className="auth-field">
        <label htmlFor="confirm-password">Confirm password</label>
        <input
          id="confirm-password"
          className="auth-input"
          type="password"
          autoComplete="new-password"
          placeholder="Confirm password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          minLength={8}
          required
        />
      </div>
      <p className="fine" style={{ textAlign: "left" }}>
        Use at least 8 characters, including an uppercase letter, a lowercase
        letter, and a number.
      </p>
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
        disabled={busy}
      >
        <Icon name="fa-check" /> {busy ? "Saving…" : "Set new password"}
      </button>
      <p className="auth-alt">
        <Link href="/reset-password">Use a different email</Link>
        {" · "}
        <Link href="/login">Back to sign in</Link>
      </p>
    </form>
  );
}
