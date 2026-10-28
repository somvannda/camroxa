import { PlayerProvider } from "@/components/PlayerProvider";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Player } from "@/components/Player";
import { Footer } from "@/components/Footer";

export default function SiteLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <PlayerProvider>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Topbar />
          <div className="content">
            {children}
            <Footer />
          </div>
          <Player />
        </div>
      </div>
    </PlayerProvider>
  );
}
