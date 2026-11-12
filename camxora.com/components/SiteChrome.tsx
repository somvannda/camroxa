import { PlayerProvider } from "@/components/PlayerProvider";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Player } from "@/components/Player";
import { Footer } from "@/components/Footer";

/**
 * The product chrome: left navigation, top bar, page content, player and footer.
 *
 * Every user-facing page uses it — including the Studio home and shared-project pages —
 * except the surfaces that genuinely need the full viewport: the Studio editor, the auth
 * screens and `/health`. Keeping it in one component means the `(site)` pages and the
 * Studio public pages cannot drift apart.
 */
export function SiteChrome({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <PlayerProvider>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Topbar />
          <div className="content">
            <main className="content-main">{children}</main>
            <Footer />
          </div>
          <Player />
        </div>
      </div>
    </PlayerProvider>
  );
}
