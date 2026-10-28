"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import TurnstileWidget from "@/components/TurnstileWidget";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { Checkbox } from "@/components/ui/checkbox";
import { useAuth } from "@/components/AuthProvider";

const TURNSTILE_DISABLED = process.env.NEXT_PUBLIC_TURNSTILE_DISABLED === "1";

export function SignupForm() {
  const { register } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [turnstileKey, setTurnstileKey] = useState(0);
  const [referralCode, setReferralCode] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setReferralCode(new URLSearchParams(window.location.search).get("ref")?.trim() ?? "");
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agreed) {
      setError("Please agree to the Terms & Conditions and Privacy Policy to continue.");
      return;
    }
    if (!TURNSTILE_DISABLED && !token) {
      setError("Please complete the security check.");
      return;
    }
    setBusy(true);
    setError("");

    try {
      await register({
        display_name: displayName.trim(),
        email: email.trim(),
        password,
        referral_code: referralCode || undefined,
        cf_turnstile_response: token,
      });
      window.location.href = `/verify-email?email=${encodeURIComponent(email.trim())}`;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign up failed");
      setToken("");
      setTurnstileKey((value) => value + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <div className="auth-field">
        <label htmlFor="display-name">Display name</label>
        <input
          id="display-name"
          className="auth-input"
          type="text"
          autoComplete="name"
          placeholder="Somvannda"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          required
        />
      </div>
      <div className="auth-field">
        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
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
        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          className="auth-input"
          type="password"
          autoComplete="new-password"
          placeholder="Create a password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
        />
      </div>
      {TURNSTILE_DISABLED ? null : (
        <TurnstileWidget
          key={turnstileKey}
          action="register"
          onToken={setToken}
          onExpire={() => setToken("")}
          onError={() => setToken("")}
        />
      )}
      <div className="auth-check">
        <Checkbox
          id="signup-terms"
          checked={agreed}
          onCheckedChange={(checked) => {
            setAgreed(checked === true);
            if (checked === true) setError("");
          }}
          aria-invalid={error && !agreed ? true : undefined}
          aria-describedby={error && !agreed ? "signup-terms-error" : undefined}
        />
        <label htmlFor="signup-terms">
          I agree to the <Link href="/terms">Terms &amp; Conditions</Link> and{" "}
          <Link href="/privacy">Privacy Policy</Link>.
        </label>
      </div>
      {error ? (
        <p
          className="auth-error"
          id={!agreed ? "signup-terms-error" : undefined}
          role="alert"
        >
          {error}
        </p>
      ) : null}
      <button
        className="auth-btn primary"
        type="submit"
        disabled={busy || (!TURNSTILE_DISABLED && !token)}
      >
        <Icon name="fa-user-plus" /> {busy ? "Creating account…" : "Create account"}
      </button>
      {process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ? (
        <>
          <div className="auth-divider">or</div>
          <GoogleSignInButton />
        </>
      ) : null}
      <p className="auth-alt">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
}
