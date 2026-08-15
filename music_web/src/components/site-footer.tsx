import Link from 'next/link';

import { getUserPortalBaseUrl, getWebsiteBaseUrl } from '@/lib/site-urls';

export default function SiteFooter() {
  const website = getWebsiteBaseUrl();
  const portal = getUserPortalBaseUrl();
  const year = new Date().getFullYear();

  return (
    <footer className="mt-10 border-t border-white/8 bg-[linear-gradient(180deg,rgba(8,10,20,0.24),rgba(4,6,14,0.92))]">
      <div className="mx-auto grid w-full max-w-[1600px] gap-10 px-4 py-12 text-sm text-slate-200/68 md:grid-cols-[1.4fr_1fr_1fr_1fr] md:px-6">
        <div className="max-w-md">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
            <div>
              <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                Camxora Music
              </div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/54">
                Music
              </div>
            </div>
          </div>
          <p className="mt-4 leading-7 text-slate-200/60">
            Listen and create AI music on Camxora. One account can later unlock the studio app.
          </p>
        </div>

        <FooterColumn
          title="Discover"
          items={[
            { href: '/', label: 'Home' },
            { href: '/explore', label: 'Explore' },
            { href: '/create', label: 'Create' },
            { href: '/library', label: 'Library' },
          ]}
        />
        <FooterColumn
          title="Camxora"
          items={[
            { href: website, label: 'Website', external: true },
            { href: `${website}/download`, label: 'Download app', external: true },
            { href: `${portal}/login`, label: 'User portal', external: true },
            { href: `${website}/pricing`, label: 'Pricing', external: true },
          ]}
        />
        <FooterColumn
          title="Legal"
          items={[
            { href: `${website}/terms`, label: 'Terms', external: true },
            { href: `${website}/privacy`, label: 'Privacy', external: true },
            { href: `${website}/copyright`, label: 'Copyright', external: true },
            { href: `${website}/support`, label: 'Support', external: true },
          ]}
        />
      </div>
      <div className="border-t border-white/6">
        <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-2 px-4 py-4 text-xs text-slate-400 md:flex-row md:items-center md:justify-between md:px-6">
          <div>© {year} Camxora</div>
          <div>Browse free. Sign in to listen, save, and build playlists.</div>
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
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
        {title}
      </h3>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.href + item.label}>
            {item.external ? (
              <a className="transition hover:text-white" href={item.href}>
                {item.label}
              </a>
            ) : (
              <Link className="transition hover:text-white" href={item.href}>
                {item.label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
