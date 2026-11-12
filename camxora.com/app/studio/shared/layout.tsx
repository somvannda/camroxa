import { SiteChrome } from "@/components/SiteChrome";

/**
 * Shared-project pages are read-only views of a Studio project, not the editor, so they
 * keep the product chrome. The editor routes (`/studio/editor*`) deliberately do not.
 */
export default function SharedStudioLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <SiteChrome>{children}</SiteChrome>;
}
