"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

const FEATURES = [
  {
    title: "Latest AI Music Models",
    desc: "Access the newest models for vocal and instrumental tracks, plus extension, covers and multi-format downloads.",
    icon: "◆",
  },
  {
    title: "Watermark-Free & Commercial Ready",
    desc: "Every track is watermark-free and cleared for commercial projects — no extra fees, no licensing headaches.",
    icon: "◈",
  },
  {
    title: "Fast Streaming Output",
    desc: "A streaming response system delivers results in as little as 20 seconds, so your app never waits.",
    icon: "⚡",
  },
  {
    title: "High-Concurrency Architecture",
    desc: "Built to handle many simultaneous requests reliably, so it scales with your traffic without breaking.",
    icon: "▦",
  },
  {
    title: "Transparent, Usage-Based Pricing",
    desc: "Simple credit packages with predictable costs. Top up anytime and scale without overspending.",
    icon: "◫",
  },
  {
    title: "Developer-First Support",
    desc: "Clear documentation, real-time logs and a technical team ready to help you ship faster.",
    icon: "⌘",
  },
];

const STEPS = [
  { n: "1", title: "Create an account", desc: "Sign up to get instant access to your workspace and API tooling." },
  { n: "2", title: "Generate an API key", desc: "Create a key, add credits, and configure safe-spend limits." },
  { n: "3", title: "Generate & monitor", desc: "Send requests to the REST API and watch usage, logs and credits in real time." },
];

const USE_CASES = [
  { title: "Developers", desc: "Rapid, clean integration that saves time and reduces complexity." },
  { title: "Content Creators", desc: "Royalty-free music for videos, podcasts and media — fast." },
  { title: "Businesses", desc: "Automate audio generation and connect systems at scale." },
  { title: "Startups", desc: "Ship an MVP with music generation without backend heavy-lifting." },
];

// Shown only until the live packs load (or if the API is unreachable) so the
// section never renders empty. The real prices come from the `credit_packs`
// table via GET /pricing, so this list can't drift from what billing charges.
const FALLBACK_PLANS = [
  { name: "Credit pack", amount: "1,000", price: "USD 10", bonus: "" },
  { name: "Credit pack", amount: "5,000", price: "USD 30", bonus: "" },
  { name: "Credit pack", amount: "20,000", price: "USD 60", bonus: "" },
  { name: "Credit pack", amount: "50,000", price: "USD 100", bonus: "Best value" },
];

interface Plan {
  name: string;
  amount: string;
  price: string;
  bonus: string;
}

const FAQS = [
  { q: "What is Camxora Music API?", a: "A REST API that generates watermark-free AI music on top of the latest models — vocals, instrumentals, extensions and covers." },
  { q: "How do credits work?", a: "Every request consumes credits at the rates published on your billing page. Buy a credit package and top up anytime from your dashboard." },
  { q: "Is the music safe for commercial use?", a: "Yes. Generated tracks are watermark-free and ready for commercial projects with no additional fees." },
  { q: "How fast are results?", a: "Streaming output typically delivers in around 20 seconds, with real-time task status polling." },
  { q: "How do I get started?", a: "Create an account, generate an API key, add credits, then call the REST endpoints with your bearer token." },
  { q: "Is there monitoring?", a: "Yes — the dashboard shows usage, success rate, logs and remaining credits in real time." },
];

export default function LandingPage() {
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS);

  useEffect(() => {
    apiFetch<{ packs: Array<{ id: string; amount: number; price: number; currency: string }> }>("/pricing")
      .then((data) => {
        if (!data.packs?.length) return;
        const top = Math.max(...data.packs.map((p) => p.amount));
        setPlans(
          data.packs.map((p) => ({
            name: "Credit pack",
            amount: p.amount.toLocaleString(),
            price: `${p.currency} ${p.price.toLocaleString()}`,
            bonus: data.packs.length > 1 && p.amount === top ? "Best value" : "",
          })),
        );
      })
      .catch(() => { /* keep the fallback list */ });
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-black/40 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <img src="/camxora-logo.svg" alt="Camxora" className="h-8 w-8 rounded-lg" />
            <span className="text-lg font-bold">Camxora Music API</span>
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-[var(--muted)] md:flex">
            <a href="#about" className="hover:text-white">About</a>
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#how" className="hover:text-white">How it works</a>
            <a href="#pricing" className="hover:text-white">Pricing</a>
            <a href="#faq" className="hover:text-white">FAQ</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="rounded-lg px-4 py-2 text-sm font-medium text-[var(--muted)] hover:text-white">
              Sign in
            </Link>
            <Link href="/login" className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-2 lg:items-center">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-white/5 px-3 py-1 text-xs text-[var(--muted)]">
                <span className="h-2 w-2 rounded-full bg-[var(--emerald)]" />
                All systems operational
              </div>
              <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl">
                Generate watermark-free music with a <span className="grad-text">simple API</span>
              </h1>
              <p className="mt-5 max-w-lg text-[var(--muted)]">
                Production-quality AI music — vocals, instrumentals, extensions and covers — delivered through a stable
                REST API with fast streaming output and transparent credit pricing.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/docs" className="grad-bg rounded-lg px-5 py-3 text-sm font-semibold text-white">
                  Explore the API
                </Link>
                <Link href="/login" className="rounded-lg border border-[var(--border)] px-5 py-3 text-sm font-medium text-[var(--muted)] hover:text-white">
                  Get started
                </Link>
              </div>
              <div className="mt-8 flex flex-wrap gap-8 text-sm">
                <div>
                  <div className="text-xl font-bold text-[var(--emerald)]">~20s</div>
                  <div className="text-xs text-[var(--muted)]">avg. generation</div>
                </div>
                <div>
                  <div className="text-xl font-bold">0%</div>
                  <div className="text-xs text-[var(--muted)]">watermark</div>
                </div>
                <div>
                  <div className="text-xl font-bold">REST</div>
                  <div className="text-xs text-[var(--muted)]">JSON API</div>
                </div>
              </div>
            </div>


          </div>

          {/* Waveform accent */}
          <div className="mx-auto max-w-6xl px-6">
            <div className="flex h-16 items-end gap-1 opacity-60">
              {Array.from({ length: 48 }).map((_, i) => (
                <div
                  key={i}
                  className="grad-bg w-full rounded-t"
                  style={{ height: `${(20 + Math.abs(Math.sin(i * 0.6)) * 80).toFixed(2)}%` }}
                />
              ))}
            </div>
          </div>
        </section>

        {/* About / purpose */}
        <section id="about" className="border-y border-[var(--border)] bg-black/20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-3xl text-center">
              <h2 className="text-3xl font-bold">What is Camxora Music API?</h2>
              <p className="mt-4 text-[var(--muted)]">
                Camxora Music API is a developer platform for AI music generation. Our purpose is to let developers and
                businesses add studio-quality, watermark-free music — vocals, instrumentals, extensions and covers — to
                their own products and workflows through a simple, reliable REST API. You create an account, generate
                an API key, and call our endpoints to generate audio, monitor usage, and manage credits.
              </p>
              <p className="mt-4 text-[var(--muted)]">
                The Service is operated by Camxora and is intended for lawful, authorized use only. It is not intended
                for creating deceptive, harmful, or non-consensual content.
              </p>
            </div>
            <div className="mx-auto mt-12 grid max-w-4xl gap-5 sm:grid-cols-3">
              <div className="glass rounded-2xl p-6 text-center">
                <div className="grad-text text-xl font-bold">REST API</div>
                <p className="mt-2 text-sm text-[var(--muted)]">A documented JSON API for music generation.</p>
              </div>
              <div className="glass rounded-2xl p-6 text-center">
                <div className="grad-text text-xl font-bold">Workspace</div>
                <p className="mt-2 text-sm text-[var(--muted)]">A web dashboard for API keys, usage and billing.</p>
              </div>
              <div className="glass rounded-2xl p-6 text-center">
                <div className="grad-text text-xl font-bold">Sign in with Google</div>
                <p className="mt-2 text-sm text-[var(--muted)]">We use only basic sign-in, so you can access the workspace securely.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="mx-auto max-w-6xl px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold">Why choose our API for seamless integration?</h2>
            <p className="mt-3 text-[var(--muted)]">Everything you need to add AI music to your product — fast, reliable and ready for production.</p>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="glass rounded-2xl p-6">
                <div className="grad-text text-xl">{f.icon}</div>
                <h3 className="mt-3 font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="border-y border-[var(--border)] bg-black/20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold">Get started in three steps</h2>
              <p className="mt-3 text-[var(--muted)]">From sign-up to your first generated track in minutes.</p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n} className="glass rounded-2xl p-6">
                  <div className="grad-text text-3xl font-extrabold">{s.n}</div>
                  <h3 className="mt-3 font-semibold">{s.title}</h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Use cases */}
        <section className="mx-auto max-w-6xl px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold">Built for every team</h2>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {USE_CASES.map((u) => (
              <div key={u.title} className="glass rounded-2xl p-6">
                <h3 className="font-semibold">{u.title}</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">{u.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="border-y border-[var(--border)] bg-black/20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold">Transparent credit packages</h2>
              <p className="mt-3 text-[var(--muted)]">Buy credits before you integrate. Top up anytime from your billing dashboard.</p>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {plans.map((p, i) => (
                <div key={i} className={`glass relative rounded-2xl p-6 ${p.bonus ? "border-[var(--violet)]/50" : ""}`}>
                  {p.bonus && (
                    <span className="grad-bg absolute -top-3 left-4 rounded-full px-3 py-0.5 text-xs font-semibold text-white">
                      {p.bonus}
                    </span>
                  )}
                  <div className="text-sm font-medium capitalize text-[var(--muted)]">{p.name}</div>
                  <div className="mt-2 text-3xl font-extrabold">{p.price}</div>
                  <div className="mt-1 text-sm text-[var(--muted)]">{p.amount} credits</div>
                  <Link href="/login" className="grad-bg mt-5 block w-full rounded-lg py-2.5 text-center text-sm font-semibold text-white">
                    Buy credits
                  </Link>
                </div>
              ))}
            </div>
            <p className="mt-6 text-center text-sm text-[var(--muted)]">
              Need help choosing? <a href="mailto:support@camxora.com" className="grad-text font-medium">Contact us</a>
            </p>
          </div>
        </section>

        {/* Responsible use */}
        <section id="responsible-use" className="mx-auto max-w-4xl px-6 py-20">
          <div className="glass rounded-3xl p-8 sm:p-10">
            <h2 className="text-2xl font-bold">Responsible use and prohibited content</h2>
            <p className="mt-4 text-sm text-[var(--muted)]">
              Camxora Music API is built for lawful, creative, and authorized use. We do not permit the Service to be
              used to create or distribute unlawful content. In particular, we prohibit the generation or distribution
              of <strong className="text-white">AI-generated non-consensual intimate imagery (AI NCII)</strong> — that
              is, realistic sexual or intimate depictions of a real, identifiable person created or shared without that
              person&rsquo;s consent. We do not use Google APIs for AI NCII.
            </p>
            <p className="mt-4 text-sm text-[var(--muted)]">
              We also prohibit child sexual abuse material and any sexual content involving minors, deepfakes used to
              harass, sexualize, defame, or impersonate a real person, and content that infringes the intellectual
              property, voice, likeness, or privacy rights of others. You must have all necessary rights and consents
              before using someone else&rsquo;s voice, likeness, or material. Violations may result in content removal
              and account suspension or termination. See our{" "}
              <Link href="/terms" className="grad-text font-medium">Terms of Service</Link> and{" "}
              <Link href="/privacy" className="grad-text font-medium">Privacy Policy</Link>.
            </p>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="mx-auto max-w-3xl px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold">Frequently asked questions</h2>
          </div>
          <div className="mt-10 space-y-3">
            {FAQS.map((f) => (
              <details key={f.q} className="glass group rounded-xl p-5">
                <summary className="cursor-pointer list-none font-medium">
                  <span className="flex items-center justify-between">
                    {f.q}
                    <span className="grad-text text-lg transition-transform group-open:rotate-45">+</span>
                  </span>
                </summary>
                <p className="mt-3 text-sm text-[var(--muted)]">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-6 pb-20">
          <div className="glass rounded-3xl p-12 text-center">
            <h2 className="text-3xl font-bold">Ready to generate music at scale?</h2>
            <p className="mt-3 text-[var(--muted)]">Create your account and get your first API key in seconds.</p>
            <Link href="/login" className="grad-bg mt-6 inline-block rounded-lg px-6 py-3 text-sm font-semibold text-white">
              Get started free
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border)]">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <Link href="/" className="flex items-center gap-2">
                <img src="/camxora-logo.svg" alt="Camxora Music API" className="h-9 w-9 rounded-lg" />
                <span className="text-lg font-bold text-white">Camxora Music API</span>
              </Link>
              <p className="mt-4 max-w-xs text-sm leading-relaxed text-[var(--muted)]">
                A REST API for watermark-free AI music generation — vocals, instrumentals, extensions and covers, with
                durable MP3/WAV delivery.
              </p>
            </div>

            <FooterCol
              title="Product"
              links={[
                { label: "Features", href: "#features" },
                { label: "Pricing", href: "#pricing" },
                { label: "Use cases", href: "#about" },
                { label: "Playground", href: "/dashboard/playground" },
              ]}
            />
            <FooterCol
              title="Developers"
              links={[
                { label: "API reference", href: "/docs" },
                { label: "Endpoint status", href: "/docs" },
                { label: "Service health", href: "/health" },
                { label: "Status & updates", href: "/dashboard/updates" },
              ]}
            />
            <FooterCol
              title="Company & legal"
              links={[
                { label: "Contact", href: "mailto:support@camxora.com" },
                { label: "Privacy Policy", href: "/privacy" },
                { label: "Terms of Service", href: "/terms" },
                { label: "Data Deletion", href: "/data-deletion" },
              ]}
            />
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-[var(--border)] pt-6 text-xs text-[var(--muted)] md:flex-row">
            <div>© {new Date().getFullYear()} Camxora Music API. All rights reserved.</div>
            <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
              <Link href="/privacy" className="hover:text-white">Privacy</Link>
              <Link href="/terms" className="hover:text-white">Terms</Link>
              <Link href="/data-deletion" className="hover:text-white">Data Deletion</Link>
              <a href="mailto:support@camxora.com" className="hover:text-white">Support</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FooterCol({ title, links }: { title: string; links: { label: string; href: string }[] }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wider text-white">{title}</h4>
      <ul className="mt-4 space-y-2.5 text-sm text-[var(--muted)]">
        {links.map((l) => (
          <li key={l.label}>
            {l.href.startsWith("http") || l.href.startsWith("mailto:") ? (
              <a href={l.href} className="transition hover:text-white">{l.label}</a>
            ) : (
              <Link href={l.href} className="transition hover:text-white">{l.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
