import { Outlet } from "react-router-dom";
import { ToastViewport } from "../components/toast";
import { Footer } from "./footer";
import { NavigationGuardProvider } from "./navigation-guard";
import { Sidebar } from "./sidebar";
import { TitleBar } from "./titlebar";

function ShellFrame() {
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
