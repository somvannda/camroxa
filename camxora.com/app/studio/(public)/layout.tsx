import { SiteChrome } from "@/components/SiteChrome";

/**
 * Studio pages that are not the editor use the product chrome (left nav, top bar, footer,
 * player). The editor routes live outside this group and keep the full viewport; see the
 * route map in docs/studio/SESSION_HANDOFF.md.
 */
export default function StudioPublicLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <SiteChrome>{children}</SiteChrome>;
}
