import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { ToastViewport } from "../components/toast";
import { Footer } from "./footer";
import { NavigationGuardProvider } from "./navigation-guard";
import { Sidebar } from "./sidebar";
import { TitleBar } from "./titlebar";

function ShellFrame() {
  const { pathname } = useLocation();

  // The Vizzy editor is a native view above the DOM. Hide it the moment the
  // shell leaves /vizzy; the page's own attach re-shows it on return.
  useEffect(() => {
    if (!pathname.startsWith("/vizzy")) {
      void window.camxora?.vizzy?.setVisible(false);
    }
  }, [pathname]);

  return (
    <div className="flex h-full flex-col bg-bg">
      <TitleBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <Footer />
      <ToastViewport />
    </div>
  );
}

export function Shell() {
  return (
    <NavigationGuardProvider>
      <ShellFrame />
    </NavigationGuardProvider>
  );
}
