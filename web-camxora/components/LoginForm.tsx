"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import TurnstileWidget from "@/components/TurnstileWidget";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { useAuth } from "@/components/AuthProvider";

const TURNSTILE_DISABLED = process.env.NEXT_PUBLIC_TURNSTILE_DISABLED === "1";

export function LoginForm() {
  const { login, user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [remember, setRemember] = useState(false);
  const [turnstileKey, setTurnstileKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const nextPath = () => {
    const raw = new URLSearchParams(window.location.search).get("next");
    return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
  };

  useEffect(() => {
    if (!loading && user) {
      window.location.href =
        user.email_confirmed === false
          ? `/verify-email?email=${encodeURIComponent(user.email)}`
          : nextPath();
    }
  }, [loading, user]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!TURNSTILE_DISABLED && !token) {
      setError("Please complete the security check.");
      return;
    }
    setBusy(true);
    setError("");

    try {
      const me = await login(email.trim(), password, token, remember);
      window.location.href =
        me?.email_confirmed === false
          ? `/verify-email?email=${encodeURIComponent(me.email)}`
          : nextPath();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed");
      setToken("");
      setTurnstileKey((value) => value + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <div className="auth-field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          className="auth-input"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </div>
      <div className="auth-field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          className="auth-input"
          type="password"
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </div>
      <div className="auth-row">
        <label>
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />{" "}
          Remember me
        </label>
        <Link href="/forgot-password">Forgot password?</Link>
      </div>
      {TURNSTILE_DISABLED ? null : (
        <TurnstileWidget
          key={turnstileKey}
          action="login"
          onToken={setToken}
          onExpire={() => setToken("")}
          onError={() => setToken("")}
        />
      )}
      {error ? (
        <p className="fine" style={{ color: "#f87171", textAlign: "left", marginTop: 0 }} role="alert">
          {error}
        </p>
      ) : null}
      <button
        className="auth-btn primary"
        type="submit"
        disabled={busy || (!TURNSTILE_DISABLED && !token)}
      >
        <Icon name="fa-arrow-right-to-bracket" /> {busy ? "Signing in…" : "Sign in"}
      </button>
      {process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ? (
        <>
          <div className="auth-divider">or</div>
          <GoogleSignInButton />
        </>
      ) : null}
      <p className="auth-alt">
        New here? <Link href="/signup">Create an account</Link>
      </p>
    </form>
  );
}
