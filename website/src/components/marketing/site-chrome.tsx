import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { getUserPortalBaseUrl, isSandboxEnvironment } from "@/lib/site-urls";

type MarketingHeaderProps = {
  userPortalBaseUrl: string;
};

type MarketingFooterProps = {
  userPortalBaseUrl: string;
};

const primaryNavLinks = [
  { href: "/#why-switch", label: "Why Camxora" },
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/download", label: "Download" },
  { href: "/about", label: "About" },
];

const productLinks = [
  { href: "/#why-switch", label: "Why Camxora" },
  { href: "/features", label: "Features" },
  { href: "/services", label: "Who it's for" },
  { href: "/pricing", label: "Pricing" },
  { href: "/download", label: "Download" },
];

const companyLinks = [
  { href: "/about", label: "About" },
  { href: "/blog", label: "Blog" },
  { href: "/changelog", label: "Changelog" },
  { href: "/contact", label: "Contact" },
];

const supportLinks = [
  { href: "/support", label: "Help Center" },
  { href: "/contact", label: "Contact" },
  { href: "/data-deletion", label: "Data deletion" },
];

const legalLinks = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/google-api", label: "Google API policy" },
  { href: "/cookies", label: "Cookies" },
  { href: "/copyright", label: "Copyright" },
  { href: "/acceptable-use", label: "Acceptable use" },
];

export { getUserPortalBaseUrl, isSandboxEnvironment };

export function SandboxBanner() {
  if (!isSandboxEnvironment()) {
    return null;
  }

  return (
    <div className="border-b border-amber-400/25 bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-100">
      Sandbox environment — test payments may apply. Not the production Camxora site.
    </div>
  );
}

export function MarketingHeader({ userPortalBaseUrl }: MarketingHeaderProps) {
  return (
    <>
      <SandboxBanner />
      <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
        <div className="mx-auto w-full max-w-7xl px-6 py-4 md:px-10">
          <div className="flex items-center justify-between gap-4">
            <Link className="flex items-center gap-3" href="/">
              <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
              <div>
                <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                  Camxora
                </div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/58">
                  Faceless desktop studio
                </div>
              </div>
            </Link>

            <nav className="hidden items-center gap-6 text-sm font-medium text-slate-200/74 xl:flex">
              {primaryNavLinks.map((item) => (
                <Link key={item.href} className="transition hover:text-white" href={item.href}>
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="flex items-center gap-2">
              <a
                className="hidden h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-100 transition hover:bg-white/[0.06] sm:inline-flex"
                href={`${userPortalBaseUrl}/login`}
              >
                Sign in
              </a>
              <a
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                href={`${userPortalBaseUrl}/register`}
              >
                Create account
                <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>

          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 text-sm xl:hidden">
            {primaryNavLinks.map((item) => (
              <Link
                key={item.href}
                className="whitespace-nowrap rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-200/72 transition hover:bg-white/[0.06] hover:text-white"
                href={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
    </>
  );
}

export function MarketingFooter({ userPortalBaseUrl }: MarketingFooterProps) {
  return (
    <footer className="relative mt-auto border-t border-white/8 bg-[linear-gradient(180deg,rgba(8,10,20,0.24),rgba(4,6,14,0.92))]">
      <div className="mx-auto grid w-full max-w-7xl gap-10 px-6 py-12 text-sm text-slate-200/68 md:px-10 lg:grid-cols-[1.4fr_1fr_1fr_1fr_1fr]">
        <div className="max-w-md">
          <div className="flex items-center gap-3">
            <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
            <div>
              <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                Camxora
              </div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/54">
                Faceless desktop studio
              </div>
            </div>
          </div>
          <p className="mt-4 leading-7 text-slate-200/60">
            Build dual faceless YouTube music channels — lyrics to video in one Windows app.
          </p>
          <div className="mt-6 text-xs uppercase tracking-[0.2em] text-slate-400">
            Export ready today. Auto-upload coming soon.
          </div>
        </div>

        <FooterColumn title="Product" items={productLinks} />
        <FooterColumn
          title="Company"
          items={[
            ...companyLinks,
            { href: `${userPortalBaseUrl}/login`, label: "User Portal", external: true },
          ]}
        />
        <FooterColumn title="Support" items={supportLinks} />
        <FooterColumn title="Legal" items={legalLinks} />
      </div>

      <div className="border-t border-white/6">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-6 py-4 text-xs text-slate-400 md:flex-row md:items-center md:justify-between md:px-10">
          <div>© {new Date().getFullYear()} Camxora</div>
          <div>No camera. No face. YouTube-ready music videos.</div>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  items,
}: {
  title: string;
  items: Array<{ href: string; label: string; external?: boolean }>;
}) {
  return (
    <div>
      <div className="font-medium text-white">{title}</div>
      <div className="mt-4 grid gap-2.5">
        {items.map((item) =>
          item.external ? (
            <a key={item.href} className="transition hover:text-white" href={item.href}>
              {item.label}
            </a>
          ) : (
            <Link key={item.href} className="transition hover:text-white" href={item.href}>
              {item.label}
            </Link>
          ),
        )}
      </div>
    </div>
  );
}
