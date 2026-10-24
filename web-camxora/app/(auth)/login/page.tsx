import type { Metadata } from "next";
import Link from "next/link";
import { LoginForm } from "@/components/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
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
          <p>Listen to what creators are making, then make the next track everyone plays.</p>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>Welcome back.</h1>
          <p className="sub">Sign in to listen, create and publish.</p>
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
