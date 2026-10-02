import Link from "next/link";

/**
 * Public chrome for the standalone legal pages (privacy / terms) that Google's
 * OAuth branding review fetches directly. These must be viewable without a
 * login, so they never depend on session or dashboard state.
 */
export default function PublicLegalShell({
  title,
  lastUpdated,
  children,
}: {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-black/40 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <div className="grad-bg flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white">♪</div>
            <span className="text-lg font-bold">Camxora Music API</span>
          </Link>
          <Link href="/" className="text-sm text-[var(--muted)] hover:text-white">
            ← Back to home
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-extrabold sm:text-4xl">{title}</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">Last updated: {lastUpdated}</p>
        <div className="mt-8 space-y-8 text-sm leading-relaxed text-[var(--muted)]">{children}</div>
      </main>

      <footer className="border-t border-[var(--border)] bg-black/30">
        <div className="mx-auto flex max-w-3xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-[var(--muted)] md:flex-row">
          <span>© {new Date().getFullYear()} Camxora Music API. All rights reserved.</span>
          <div className="flex gap-6">
            <Link href="/privacy" className="hover:text-white">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-white">Terms of Service</Link>
            <a href="mailto:support@camxora.com" className="hover:text-white">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
