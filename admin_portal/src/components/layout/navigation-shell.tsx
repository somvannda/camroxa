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
      <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
