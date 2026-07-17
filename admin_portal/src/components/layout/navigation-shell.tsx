import { Outlet } from 'react-router-dom';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Sidebar } from './sidebar';
import { TopBar } from './top-bar';

/**
 * NavigationShell wraps authenticated pages with sidebar + top bar.
 * Uses Outlet to render child routes.
 */
export function NavigationShell() {
  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_24%),radial-gradient(circle_at_top_right,rgba(14,165,233,0.14),transparent_20%),linear-gradient(180deg,rgba(15,23,42,1),rgba(2,6,23,1))] text-slate-100">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto flex h-full w-full max-w-[1680px] flex-col px-4 pb-6 pt-4 lg:px-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
