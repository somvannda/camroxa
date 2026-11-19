import { Outlet } from "react-router-dom";
import { ToastViewport } from "../components/toast";
import { Footer } from "./footer";
import { Sidebar } from "./sidebar";
import { TitleBar } from "./titlebar";

export function Shell() {
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
